import os
from datetime import datetime
#export API_KEY=pk_6637a11bf9034c908f98837a11a2486c
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

if __name__ == '__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("postgres://sepmqwsnyizqto:7c37113d0bc33aa1ceb10ba364742190f28503024e2df3dcdc85f4eeaacd131d@ec2-34-197-212-240.compute-1.amazonaws.com:5432/d5vlb069732o5i
")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = user=session["user_id"]
    buy_data = db.execute("SELECT symbol, shares FROM purchases JOIN users ON buyer_id = users.id WHERE buyer_id = :user", user=user)
    sell_data = db.execute("SELECT symbol, shares FROM sells JOIN users ON seller_id = users.id WHERE seller_id = :user", user=user)
    user_data = db.execute("SELECT * FROM users WHERE users.id = :user", user=user)
    data = {}
    for rows in buy_data:
        symbol = rows["symbol"]
        data[symbol] = [symbol, 0, lookup(symbol)["Price"], 0]
    for rows in buy_data:
        symbol = rows["symbol"]
        data[symbol][1] += rows["shares"]
        data[symbol][3] = data[symbol][2] * data[symbol][1]
    for rows in sell_data:
        symbol = rows["symbol"]
        data[symbol][1] -= rows["shares"]
        data[symbol][3] = data[symbol][2] * data[symbol][1]
        if data[symbol][1] == 0:
            del data[symbol]
    total_value = 0
    cash = user_data[0]["cash"]
    for rows in data:
        total_value += data[rows][3]
        data[rows][2] = "{:.2f}".format(data[rows][2])
        data[rows][3] = "{:.2f}".format(data[rows][3])
    total_value = "{:.2f}".format(total_value + cash)
    return render_template("index.html", user=user_data[0]["username"], data=data, cash="{:.2f}".format(cash), total_value=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        user = session["user_id"]
        if not symbol:
            return apology("must provide stock symbol")
        elif not shares:
            return apology("must provide number of shares")
        elif not shares.isdigit():
            return apology("shares must be a number")
        elif int(shares) < 0:
            return apology("share number must be positive")
        shares = int(shares)
        data = lookup(symbol)
        if not data:
            return apology("symbol does not exist")
        else:
            rows = db.execute("SELECT * FROM users WHERE id = :user", user=user)
            total = data["Price"] * shares
            new_cash = int(rows[0]["cash"]) - total
            if new_cash < 0:
                return apology("you don't have enough money", 403)
            db.execute("UPDATE users SET cash = :amount WHERE id = :user",
                        amount=new_cash, user=user)
            db.execute("INSERT INTO purchases (symbol, shares, buyer_id, total_spent, time) VALUES (:symbol, :shares, :buyer, :total, :time)",
                        symbol=symbol, shares=shares, buyer=user, total=total, time=datetime.now())
        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    user_data = db.execute("SELECT * FROM users WHERE users.id = :user", user=user)
    buy_data = db.execute("SELECT * FROM purchases JOIN users ON buyer_id = id WHERE id = :user", user=user)
    sell_data = db.execute("SELECT * FROM sells JOIN users ON seller_id = id WHERE id = :user", user=user)
    data = []
    for row in buy_data:
        data.append([row["symbol"], "Bought", row["shares"], "{:.2f}".format(row["total_spent"]), row["time"]])
    for row in sell_data:
        data.append([row["symbol"], "Sold", row["shares"], "{:.2f}".format(row["total_gained"]), row["time"]])
    return render_template("history.html", data=data, user=user_data[0]["username"])


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    symbol = request.form.get("symbol")
    if request.method == "POST":
        if not symbol:
            return apology("must provide stock symbol")
        data = lookup(symbol)
        if not data:
            return apology("symbol does not exist")
        else:
            return render_template("quoted.html", symbol=symbol, data=data)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must enter a username", 403)
        elif not request.form.get("password"):
            return apology("must enter a password", 403)
        elif len(request.form.get("password")) < 8:
            return apology("password must be at least 8 characters")
        elif not request.form.get("confirm"):
            return apology("must confirm your password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(rows) != 0:
            return apology("username taken", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
                username=request.form.get("username"), password=generate_password_hash(request.form.get("password")))

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        user = user=session["user_id"]
        rows = db.execute("SELECT symbol, shares FROM purchases JOIN users ON buyer_id = users.id WHERE buyer_id = :user", user=user)
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide stock symbol")
        elif not shares:
            return apology("must provide number of shares")
        elif not shares.isdigit():
            return apology("shares must be a number")
        elif int(shares) < 0:
            return apology("share number must be positive")
        shares = int(shares)
        for row in rows:
            if row["symbol"] != symbol:
                continue;
            else:
                if row["shares"] < shares:
                    return apology("you don't have enough shares")
                else:
                    data = lookup(symbol)
                    gained = data["Price"] * shares
                    user_data = db.execute("SELECT cash FROM users WHERE users.id = :user", user=user)
                    new_cash = user_data[0]["cash"] + gained
                    db.execute("UPDATE users SET cash = :amount WHERE id = :user",
                        amount=new_cash, user=user)
                    db.execute("INSERT INTO sells (symbol, shares, seller_id, total_gained, time) VALUES (:symbol, :shares, :seller_id, :gained, :time)",
                            symbol=symbol, shares=shares, seller_id=user, gained=gained, time=datetime.now())
                    return redirect("/")
        return apology("you don't have that stock")
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
