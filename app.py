# ============================================================
# DATA4MINES - SINGLE FILE FLASK APPLICATION
# ============================================================
# Features:
# - User registration / login
# - Referral links
# - 5,000 UGX referral reward after referred user purchases
# - Dashboard
# - Shop with machines
# - Machine images from static/machines/
# - My Machines
# - Manual deposits
# - Admin approval of deposits
# - Manual withdrawals
# - Admin approval of withdrawals
# - Balance only changes after approval
# - Deposit account numbers managed by admin
# - Admin notifications
# - User -> Admin chat
# - Admin -> Users chat
# - Admin dashboard
# - Deposit / withdrawal / user-growth statistics
# - Admin can add/remove machines
# - Admin can add/remove administrators
# - Mobile-friendly 16px base font
# - Safe money formatting (fixes Undefined.__format__)
# - SQLite database
# ============================================================

import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    render_template_string,
    flash,
    abort,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY_BEFORE_PUBLIC_DEPLOYMENT"
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data4mines.db")

MACHINE_DIR = os.path.join(BASE_DIR, "static", "machines")
os.makedirs(MACHINE_DIR, exist_ok=True)

ADMIN_PHONE = os.environ.get(
    "ADMIN_PHONE",
    "0792759363"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "twix1831"
)

REFERRAL_REWARD = 5000


# ============================================================
# DATABASE
# ============================================================

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by INTEGER,
        referral_reward_paid INTEGER NOT NULL DEFAULT 0,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        total_return REAL NOT NULL,
        days INTEGER NOT NULL,
        image TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        machine_id INTEGER NOT NULL,
        purchase_price REAL NOT NULL,
        expected_total REAL NOT NULL,
        days INTEGER NOT NULL,
        purchased_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(machine_id) REFERENCES machines(id)
    );

    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        transaction_id TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        admin_note TEXT,
        created_at TEXT NOT NULL,
        approved_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        phone TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        admin_note TEXT,
        created_at TEXT NOT NULL,
        approved_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS deposit_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        name TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sender_type TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # --------------------------------------------------------
    # Primary admin
    # --------------------------------------------------------

    existing = con.execute(
        "SELECT id FROM users WHERE phone = ?",
        (ADMIN_PHONE,)
    ).fetchone()

    if existing is None:
        referral = "ADMIN-" + secrets.token_hex(4).upper()

        con.execute("""
            INSERT INTO users
            (name, phone, password_hash, balance, referral_code,
             is_admin, created_at)
            VALUES (?, ?, ?, 0, ?, 1, ?)
        """, (
            "DATA4MINES Administrator",
            ADMIN_PHONE,
            generate_password_hash(ADMIN_PASSWORD),
            referral,
            now()
        ))

    else:
        con.execute("""
            UPDATE users
            SET is_admin = 1
            WHERE phone = ?
        """, (ADMIN_PHONE,))

    admin_exists = con.execute(
        "SELECT id FROM admin_users WHERE phone = ?",
        (ADMIN_PHONE,)
    ).fetchone()

    if admin_exists is None:
        con.execute("""
            INSERT INTO admin_users
            (phone, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (
            ADMIN_PHONE,
            generate_password_hash(ADMIN_PASSWORD),
            now()
        ))

    # --------------------------------------------------------
    # Deposit number
    # --------------------------------------------------------

    number_exists = con.execute("""
        SELECT id
        FROM deposit_numbers
        WHERE phone = ?
    """, (ADMIN_PHONE,)).fetchone()

    if number_exists is None:
        con.execute("""
            INSERT INTO deposit_numbers
            (phone, name, active, created_at)
            VALUES (?, ?, 1, ?)
        """, (
            ADMIN_PHONE,
            "Nuwahereza Christine",
            now()
        ))

    # --------------------------------------------------------
    # Machines
    # --------------------------------------------------------

    machine_count = con.execute(
        "SELECT COUNT(*) AS count FROM machines"
    ).fetchone()["count"]

    if machine_count == 0:

        machines = [
            (
                "M1",
                "DATA4MINES Starter",
                10000,
                12000,
                30,
                "m1.jpg"
            ),
            (
                "M2",
                "DATA4MINES Bronze",
                25000,
                30000,
                30,
                "m2.jpg"
            ),
            (
                "M3",
                "DATA4MINES Silver",
                50000,
                65000,
                45,
                "m3.jpg"
            ),
            (
                "M4",
                "DATA4MINES Gold",
                100000,
                140000,
                60,
                "m4.jpg"
            ),
            (
                "M5",
                "DATA4MINES Platinum",
                250000,
                375000,
                75,
                "m5.jpg"
            ),
            (
                "M6",
                "DATA4MINES Diamond",
                500000,
                800000,
                90,
                "m6.jpg"
            ),
            (
                "M7",
                "DATA4MINES Pro",
                1000000,
                1700000,
                120,
                "m7.jpg"
            ),
            (
                "M8",
                "DATA4MINES Elite",
                2500000,
                4500000,
                150,
                "m8.jpg"
            ),
            (
                "M9",
                "DATA4MINES Master",
                5000000,
                9500000,
                180,
                "m9.jpg"
            ),
            (
                "M10",
                "DATA4MINES Enterprise",
                10000000,
                20000000,
                240,
                "m10.jpg"
            ),
            (
                "M11",
                "DATA4MINES Ultra",
                25000000,
                55000000,
                300,
                "m11.jpg"
            )
        ]

        for machine in machines:
            con.execute("""
                INSERT INTO machines
                (code, name, price, total_return, days, image,
                 active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (*machine, now()))

    con.commit()
    con.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# MONEY HELPERS
# ============================================================

def money(value):
    try:
        return f"{float(value or 0):,.0f}"
    except (ValueError, TypeError):
        return "0"


app.jinja_env.filters["money"] = money


# ============================================================
# AUTHENTICATION
# ============================================================

def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    con = db()

    user = con.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    con.close()

    return user


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if not current_user():
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        user = current_user()

        if not user or not user["is_admin"]:
            abort(403)

        return function(*args, **kwargs)

    return wrapper


# ============================================================
# COMMON HTML
# ============================================================

CSS = """
<style>

* {
    box-sizing: border-box;
}

html {
    font-size: 16px;
}

body {
    margin: 0;
    padding: 0;
    background: #06130e;
    color: #f3f7f5;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 16px;
    line-height: 1.5;
}

a {
    color: inherit;
    text-decoration: none;
}

nav {
    background: #071d14;
    border-bottom: 1px solid #1c4d38;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    position: sticky;
    top: 0;
    z-index: 50;
}

.logo {
    font-size: 24px;
    font-weight: 800;
    white-space: nowrap;
}

.logo span {
    color: #18e47a;
}

.navlinks {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}

.navlinks a {
    padding: 8px;
}

.container {
    width: min(1200px, 94%);
    margin: 30px auto;
}

.card {
    background: #0b2117;
    border: 1px solid #1b4c37;
    border-radius: 14px;
    padding: 22px;
    margin-bottom: 20px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.machine-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

.machine {
    overflow: hidden;
    padding: 0;
}

.machine-image {
    width: 100%;
    height: 230px;
    object-fit: contain;
    background: #10281d;
    display: block;
}

.machine-body {
    padding: 20px;
}

.stat {
    min-height: 130px;
}

.stat-title {
    color: #9bb4a8;
}

.stat-value {
    font-size: 26px;
    font-weight: 700;
    margin-top: 10px;
}

button,
.btn {
    border: 0;
    border-radius: 8px;
    background: #10b864;
    color: white;
    padding: 12px 18px;
    font-size: 16px;
    cursor: pointer;
    display: inline-block;
}

button:hover,
.btn:hover {
    background: #0e9f57;
}

.btn-danger {
    background: #b92c3b;
}

.btn-secondary {
    background: #243c32;
}

input,
select,
textarea {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #315847;
    background: #081a12;
    color: white;
    font-size: 16px;
    margin-top: 6px;
    margin-bottom: 14px;
}

textarea {
    min-height: 120px;
    resize: vertical;
}

label {
    display: block;
    margin-bottom: 5px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #244638;
}

th {
    color: #8ff0bd;
}

.flash {
    padding: 14px;
    border-radius: 8px;
    background: #163a28;
    margin-bottom: 15px;
}

.error {
    background: #48202a;
}

.success {
    background: #123e29;
}

.warning {
    background: #443a1c;
}

.badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    background: #164c35;
    font-size: 14px;
}

.pending {
    background: #59451a;
}

.approved {
    background: #155b38;
}

.rejected {
    background: #622431;
}

.chat {
    max-height: 500px;
    overflow-y: auto;
    padding: 10px;
}

.message {
    padding: 12px;
    margin: 8px 0;
    border-radius: 10px;
    background: #102a1e;
}

.message.admin {
    background: #124a31;
}

.center {
    text-align: center;
}

.small {
    color: #9eb5aa;
    font-size: 14px;
}

.refbox {
    word-break: break-all;
    background: #06140e;
    border: 1px dashed #3b7659;
    padding: 12px;
    border-radius: 8px;
}

footer {
    text-align: center;
    color: #8ba69a;
    padding: 30px;
}

canvas {
    width: 100%;
    max-height: 400px;
}

@media (max-width: 900px) {

    .grid,
    .machine-grid {
        grid-template-columns: repeat(2, 1fr);
    }

}

@media (max-width: 650px) {

    html {
        font-size: 16px;
    }

    body {
        font-size: 16px;
    }

    nav {
        align-items: flex-start;
        flex-direction: column;
    }

    .navlinks {
        width: 100%;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 5px;
    }

    .navlinks a {
        text-align: center;
        padding: 9px 3px;
    }

    .grid,
    .machine-grid {
        grid-template-columns: 1fr;
    }

    .container {
        width: 94%;
        margin: 20px auto;
    }

    .card {
        padding: 17px;
    }

    table {
        display: block;
        overflow-x: auto;
        white-space: nowrap;
    }

    .machine-image {
        height: 240px;
    }

    .logo {
        font-size: 22px;
    }
}

</style>
"""


def layout(title, body, admin=False):
    user = current_user()

    navigation = ""

    if user:
        navigation = f"""
        <a href="{url_for('dashboard')}">Dashboard</a>
        <a href="{url_for('shop')}">🛒 Shop</a>
        <a href="{url_for('my_machines')}">⚙ My Machines</a>
        <a href="{url_for('rewards')}">🎁 Rewards</a>
        <a href="{url_for('deposit')}">Deposit</a>
        <a href="{url_for('withdraw')}">Withdraw</a>
        <a href="{url_for('notifications')}">🔔</a>
        <a href="{url_for('chat')}">💬</a>
        """

        if user["is_admin"]:
            navigation += f"""
            <a href="{url_for('admin_dashboard')}">Admin</a>
            """

        navigation += f"""
        <a href="{url_for('logout')}">Logout</a>
        """

    else:
        navigation = """
        <a href="/login">Login</a>
        <a href="/register">Register</a>
        """

    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>{title} - DATA4MINES</title>
        {CSS}
    </head>

    <body>

        <nav>

            <div class="logo">
                DATA4<span>MINES</span>
            </div>

            <div class="navlinks">
                {navigation}
            </div>

        </nav>

        <main class="container">

            {{% with messages = get_flashed_messages(with_categories=true) %}}
                {{% for category, message in messages %}}
                    <div class="flash {{category}}">
                        {{message}}
                    </div>
                {{% endfor %}}
            {{% endwith %}}

            {body}

        </main>

        <footer>
            DATA4MINES
        </footer>

    </body>
    </html>
    """


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if current_user():
        return redirect(url_for("dashboard"))

    body = """
    <div class="card center">

        <h1>DATA4MINES</h1>

        <p>
            Welcome to the DATA4MINES platform.
        </p>

        <p>
            <a class="btn" href="/register">Create Account</a>
            <a class="btn btn-secondary" href="/login">Login</a>
        </p>

    </div>
    """

    return render_template_string(
        layout("Home", body)
    )


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        referral_code = request.form.get(
            "referral_code",
            ""
        ).strip()

        if not name or not phone or not password:
            flash(
                "All fields are required.",
                "error"
            )
            return redirect(url_for("register"))

        con = db()

        existing = con.execute(
            "SELECT id FROM users WHERE phone = ?",
            (phone,)
        ).fetchone()

        if existing:
            con.close()

            flash(
                "That phone number is already registered.",
                "error"
            )

            return redirect(url_for("register"))

        referred_by = None

        if referral_code:

            referrer = con.execute(
                """
                SELECT id
                FROM users
                WHERE referral_code = ?
                """,
                (referral_code,)
            ).fetchone()

            if referrer:
                referred_by = referrer["id"]

        new_code = "D4M-" + secrets.token_hex(5).upper()

        con.execute("""
            INSERT INTO users
            (name, phone, password_hash, balance,
             referral_code, referred_by,
             referral_reward_paid, is_admin, created_at)
            VALUES (?, ?, ?, 0, ?, ?, 0, 0, ?)
        """, (
            name,
            phone,
            generate_password_hash(password),
            new_code,
            referred_by,
            now()
        ))

        con.commit()
        con.close()

        flash(
            "Registration successful. You can now log in.",
            "success"
        )

        return redirect(url_for("login"))

    body = """
    <div class="card">

        <h1>Create Account</h1>

        <form method="post">

            <label>Name</label>
            <input name="name" required>

            <label>Phone Number</label>
            <input name="phone" required>

            <label>Password</label>
            <input type="password" name="password" required>

            <label>Referral Code</label>
            <input
                name="referral_code"
                value="{{ request.args.get('ref', '') }}"
                placeholder="Optional"
            >

            <button type="submit">
                Register
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("Register", body),
        request=request
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        con = db()

        user = con.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (phone,)
        ).fetchone()

        con.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()
            session["user_id"] = user["id"]

            return redirect(url_for("dashboard"))

        flash(
            "Invalid phone number or password.",
            "error"
        )

    body = """
    <div class="card">

        <h1>Login</h1>

        <form method="post">

            <label>Phone Number</label>
            <input name="phone" required>

            <label>Password</label>
            <input type="password" name="password" required>

            <button type="submit">
                Login
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("Login", body)
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()

    con = db()

    deposit_total = con.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM deposits
        WHERE user_id = ?
        AND status = 'approved'
    """, (user["id"],)).fetchone()["total"]

    withdrawal_total = con.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM withdrawals
        WHERE user_id = ?
        AND status = 'approved'
    """, (user["id"],)).fetchone()["total"]

    machine_count = con.execute("""
        SELECT COUNT(*) AS total
        FROM user_machines
        WHERE user_id = ?
    """, (user["id"],)).fetchone()["total"]

    con.close()

    balance = float(user["balance"] or 0)
    deposit_total = float(deposit_total or 0)
    withdrawal_total = float(withdrawal_total or 0)

    body = f"""
    <h1>Welcome, {user["name"]}</h1>

    <div class="grid">

        <div class="card stat">
            <div class="stat-title">
                Available Balance
            </div>

            <div class="stat-value">
                {money(balance)} UGX
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Approved Deposits
            </div>

            <div class="stat-value">
                {money(deposit_total)} UGX
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Approved Withdrawals
            </div>

            <div class="stat-value">
                {money(withdrawal_total)} UGX
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                My Machines
            </div>

            <div class="stat-value">
                {machine_count}
            </div>
        </div>

    </div>

    <div class="card">

        <h2>Deposit Account</h2>

        <p>
            Use the currently active deposit number shown below.
        </p>

        <a class="btn" href="{url_for('deposit')}">
            Make Deposit
        </a>

    </div>

    <div class="card">

        <h2>Quick Actions</h2>

        <a class="btn" href="{url_for('shop')}">
            🛒 Shop
        </a>

        <a class="btn" href="{url_for('my_machines')}">
            ⚙ My Machines
        </a>

        <a class="btn" href="{url_for('rewards')}">
            🎁 Rewards
        </a>

        <a class="btn" href="{url_for('chat')}">
            💬 Chat
        </a>

    </div>
    """

    return render_template_string(
        layout("Dashboard", body)
    )


# ============================================================
# SHOP
# ============================================================

@app.route("/shop")
@login_required
def shop():

    con = db()

    machines = con.execute("""
        SELECT *
        FROM machines
        WHERE active = 1
        ORDER BY id ASC
    """).fetchall()

    con.close()

    cards = ""

    for machine in machines:

        image = machine["image"] or "m1.jpg"

        cards += f"""
        <div class="card machine">

            <img
                class="machine-image"
                src="/machine-image/{machine["id"]}"
                alt="{machine["name"]}"
            >

            <div class="machine-body">

                <span class="badge">
                    {machine["code"]}
                </span>

                <h2>{machine["name"]}</h2>

                <p>
                    Purchase:
                    <strong>
                        {money(machine["price"])} UGX
                    </strong>
                </p>

                <p>
                    Total amount:
                    <strong>
                        {money(machine["total_return"])} UGX
                    </strong>
                </p>

                <p>
                    Period:
                    <strong>
                        {machine["days"]} days
                    </strong>
                </p>

                <a
                    class="btn"
                    href="/buy-machine/{machine["id"]}"
                >
                    Purchase Machine
                </a>

            </div>

        </div>
        """

    body = f"""
    <h1>Machine Shop</h1>

    <div class="machine-grid">
        {cards}
    </div>
    """

    return render_template_string(
        layout("Shop", body)
    )


# ============================================================
# MACHINE IMAGE
# ============================================================

@app.route("/machine-image/<int:machine_id>")
@login_required
def machine_image(machine_id):

    con = db()

    machine = con.execute(
        "SELECT image FROM machines WHERE id = ?",
        (machine_id,)
    ).fetchone()

    con.close()

    if not machine:
        abort(404)

    filename = machine["image"]

    if not filename:
        filename = "m1.jpg"

    filepath = os.path.join(
        MACHINE_DIR,
        filename
    )

    if not os.path.isfile(filepath):

        # Try common case variations.
        files = os.listdir(MACHINE_DIR)

        matched = None

        for item in files:
            if item.lower() == filename.lower():
                matched = item
                break

        if matched:
            filename = matched
        else:
            # Return the first available machine image.
            image_files = [
                x for x in files
                if x.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                )
            ]

            if image_files:
                filename = image_files[0]
            else:
                abort(404)

    return send_from_directory(
        MACHINE_DIR,
        filename
    )


# ============================================================
# BUY MACHINE
# ============================================================

@app.route("/buy-machine/<int:machine_id>")
@login_required
def buy_machine(machine_id):

    user = current_user()

    con = db()

    machine = con.execute("""
        SELECT *
        FROM machines
        WHERE id = ?
        AND active = 1
    """, (machine_id,)).fetchone()

    if not machine:
        con.close()

        flash(
            "Machine is unavailable.",
            "error"
        )

        return redirect(url_for("shop"))

    balance = float(user["balance"] or 0)
    price = float(machine["price"] or 0)

    if balance < price:

        con.close()

        flash(
            "Insufficient approved balance.",
            "error"
        )

        return redirect(url_for("shop"))

    # Purchase is recorded immediately.
    # No separate admin machine-purchase approval.
    con.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE id = ?
    """, (
        price,
        user["id"]
    ))

    con.execute("""
        INSERT INTO user_machines
        (user_id, machine_id, purchase_price,
         expected_total, days, purchased_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    """, (
        user["id"],
        machine["id"],
        machine["price"],
        machine["total_return"],
        machine["days"],
        now()
    ))

    # --------------------------------------------------------
    # Referral reward
    # --------------------------------------------------------

    updated_user = con.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (user["id"],)).fetchone()

    if (
        updated_user["referred_by"]
        and not updated_user["referral_reward_paid"]
    ):

        referrer = con.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (
            updated_user["referred_by"],
        )).fetchone()

        if referrer:

            con.execute("""
                UPDATE users
                SET balance = balance + ?
                WHERE id = ?
            """, (
                REFERRAL_REWARD,
                referrer["id"]
            ))

            con.execute("""
                UPDATE users
                SET referral_reward_paid = 1
                WHERE id = ?
            """, (
                updated_user["id"],
            ))

            con.execute("""
                INSERT INTO notifications
                (title, message, created_at)
                VALUES (?, ?, ?)
            """, (
                "Referral Reward",
                f"{REFERRAL_REWARD:,} UGX referral reward credited.",
                now()
            ))

    con.commit()
    con.close()

    flash(
        "Machine purchased successfully.",
        "success"
    )

    return redirect(url_for("my_machines"))


# ============================================================
# MY MACHINES
# ============================================================

@app.route("/my-machines")
@login_required
def my_machines():

    user = current_user()

    con = db()

    machines = con.execute("""
        SELECT
            user_machines.*,
            machines.code,
            machines.name,
            machines.image
        FROM user_machines
        JOIN machines
        ON machines.id = user_machines.machine_id
        WHERE user_machines.user_id = ?
        ORDER BY user_machines.id DESC
    """, (
        user["id"],
    )).fetchall()

    con.close()

    rows = ""

    for item in machines:

        rows += f"""
        <div class="card">

            <h2>
                {item["code"]} - {item["name"]}
            </h2>

            <p>
                Purchased:
                {money(item["purchase_price"])} UGX
            </p>

            <p>
                Total:
                {money(item["expected_total"])} UGX
            </p>

            <p>
                Period:
                {item["days"]} days
            </p>

            <p>
                Date:
                {item["purchased_at"]}
            </p>

            <span class="badge">
                {item["status"]}
            </span>

        </div>
        """

    if not rows:
        rows = """
        <div class="card">
            <p>
                You have not purchased a machine yet.
            </p>

            <a class="btn" href="/shop">
                Visit Shop
            </a>
        </div>
        """

    body = f"""
    <h1>My Machines</h1>
    {rows}
    """

    return render_template_string(
        layout("My Machines", body)
    )


# ============================================================
# REWARDS
# ============================================================

@app.route("/rewards")
@login_required
def rewards():

    user = current_user()

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    con = db()

    referrals = con.execute("""
        SELECT
            name,
            phone,
            created_at,
            referral_reward_paid
        FROM users
        WHERE referred_by = ?
        ORDER BY id DESC
    """, (
        user["id"],
    )).fetchall()

    con.close()

    rows = ""

    for person in referrals:

        status = (
            "Reward paid"
            if person["referral_reward_paid"]
            else "Waiting for machine purchase"
        )

        rows += f"""
        <tr>
            <td>{person["name"]}</td>
            <td>{person["phone"]}</td>
            <td>{person["created_at"]}</td>
            <td>{status}</td>
        </tr>
        """

    body = f"""
    <h1>Rewards</h1>

    <div class="card">

        <h2>Referral Reward</h2>

        <p>
            Referral reward:
            <strong>{money(REFERRAL_REWARD)} UGX</strong>
        </p>

        <p>
            The reward is credited after the referred user
            purchases a machine.
        </p>

        <h3>Your Referral Link</h3>

        <div class="refbox">
            {referral_link}
        </div>

    </div>

    <div class="card">

        <h2>People You Referred</h2>

        <table>

            <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Joined</th>
                <th>Reward</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Rewards", body)
    )


# ============================================================
# DEPOSIT
# ============================================================

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    user = current_user()

    con = db()

    numbers = con.execute("""
        SELECT *
        FROM deposit_numbers
        WHERE active = 1
        ORDER BY id ASC
    """).fetchall()

    con.close()

    if request.method == "POST":

        try:
            amount = float(
                request.form.get("amount", "0")
            )
        except ValueError:
            amount = 0

        transaction_id = request.form.get(
            "transaction_id",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        if amount <= 0:

            flash(
                "Enter a valid deposit amount.",
                "error"
            )

            return redirect(url_for("deposit"))

        if not transaction_id:

            flash(
                "Enter the transaction ID.",
                "error"
            )

            return redirect(url_for("deposit"))

        con = db()

        con.execute("""
            INSERT INTO deposits
            (user_id, amount, transaction_id,
             message, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (
            user["id"],
            amount,
            transaction_id,
            message,
            now()
        ))

        con.commit()
        con.close()

        flash(
            "Deposit submitted. Waiting for admin approval.",
            "success"
        )

        return redirect(url_for("dashboard"))

    number_html = ""

    for number in numbers:
        number_html += f"""
        <div class="card">
            <strong>{number["name"]}</strong><br>
            <span>{number["phone"]}</span>
        </div>
        """

    body = f"""
    <h1>Deposit</h1>

    <div class="card">

        <h2>Send Money To</h2>

        {number_html}

        <p>
            Submit your transaction information below.
            Your balance is increased only after administrator
            approval.
        </p>

    </div>

    <div class="card">

        <form method="post">

            <label>Amount (UGX)</label>
            <input
                type="number"
                name="amount"
                min="1"
                step="1"
                required
            >

            <label>Transaction ID</label>
            <input
                name="transaction_id"
                required
            >

            <label>Payment Message</label>
            <textarea
                name="message"
                placeholder="Paste the payment message here"
            ></textarea>

            <button type="submit">
                Submit Deposit
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("Deposit", body)
    )


# ============================================================
# WITHDRAW
# ============================================================

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    user = current_user()

    if request.method == "POST":

        try:
            amount = float(
                request.form.get("amount", "0")
            )
        except ValueError:
            amount = 0

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        name = request.form.get(
            "name",
            ""
        ).strip()

        if amount <= 0:

            flash(
                "Enter a valid withdrawal amount.",
                "error"
            )

            return redirect(url_for("withdraw"))

        if amount > float(user["balance"] or 0):

            flash(
                "Withdrawal amount is greater than your approved balance.",
                "error"
            )

            return redirect(url_for("withdraw"))

        if not phone or not name:

            flash(
                "Name and phone number are required.",
                "error"
            )

            return redirect(url_for("withdraw"))

        con = db()

        con.execute("""
            INSERT INTO withdrawals
            (user_id, amount, phone, name,
             status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (
            user["id"],
            amount,
            phone,
            name,
            now()
        ))

        con.commit()
        con.close()

        flash(
            "Withdrawal submitted for admin approval.",
            "success"
        )

        return redirect(url_for("dashboard"))

    body = f"""
    <h1>Withdraw</h1>

    <div class="card">

        <p>
            Current approved balance:
            <strong>
                {money(user["balance"])} UGX
            </strong>
        </p>

        <form method="post">

            <label>Amount (UGX)</label>
            <input
                type="number"
                name="amount"
                min="1"
                step="1"
                required
            >

            <label>Your Name</label>
            <input name="name" required>

            <label>Mobile Money Number</label>
            <input name="phone" required>

            <button type="submit">
                Submit Withdrawal
            </button>

        </form>

        <p class="small">
            Withdrawals remain pending until an administrator
            reviews and approves them.
        </p>

    </div>
    """

    return render_template_string(
        layout("Withdraw", body)
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    con = db()

    items = con.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    con.close()

    rows = ""

    for item in items:

        rows += f"""
        <div class="card">

            <h3>{item["title"]}</h3>

            <p>{item["message"]}</p>

            <div class="small">
                {item["created_at"]}
            </div>

        </div>
        """

    body = f"""
    <h1>Notifications</h1>

    {rows or '<div class="card">No notifications yet.</div>'}
    """

    return render_template_string(
        layout("Notifications", body)
    )


# ============================================================
# CHAT
# ============================================================

@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():

    user = current_user()

    if request.method == "POST":

        message = request.form.get(
            "message",
            ""
        ).strip()

        if message:

            con = db()

            con.execute("""
                INSERT INTO messages
                (user_id, sender_type, message, created_at)
                VALUES (?, 'user', ?, ?)
            """, (
                user["id"],
                message,
                now()
            ))

            con.commit()
            con.close()

        return redirect(url_for("chat"))

    con = db()

    messages = con.execute("""
        SELECT *
        FROM messages
        WHERE user_id = ?
        ORDER BY id ASC
    """, (
        user["id"],
    )).fetchall()

    con.close()

    chat_html = ""

    for item in messages:

        admin_class = (
            "admin"
            if item["sender_type"] == "admin"
            else ""
        )

        chat_html += f"""
        <div class="message {admin_class}">

            <strong>
                {item["sender_type"].title()}
            </strong>

            <p>
                {item["message"]}
            </p>

            <span class="small">
                {item["created_at"]}
            </span>

        </div>
        """

    body = f"""
    <h1>Chat With Admin</h1>

    <div class="card">

        <div class="chat">
            {chat_html or "No messages yet."}
        </div>

    </div>

    <div class="card">

        <form method="post">

            <label>Message</label>

            <textarea
                name="message"
                required
                placeholder="Write your message..."
            ></textarea>

            <button type="submit">
                Send Message
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("Chat", body)
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    con = db()

    users = con.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]

    deposits = con.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM deposits
        WHERE status='approved'
    """).fetchone()["total"]

    withdrawals = con.execute("""
        SELECT COALESCE(SUM(amount),0) AS total
        FROM withdrawals
        WHERE status='approved'
    """).fetchone()["total"]

    pending_deposits = con.execute("""
        SELECT COUNT(*) AS c
        FROM deposits
        WHERE status='pending'
    """).fetchone()["c"]

    pending_withdrawals = con.execute("""
        SELECT COUNT(*) AS c
        FROM withdrawals
        WHERE status='pending'
    """).fetchone()["c"]

    con.close()

    body = f"""
    <h1>Admin Dashboard</h1>

    <div class="grid">

        <div class="card stat">
            <div class="stat-title">
                Registered Users
            </div>

            <div class="stat-value">
                {users}
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Approved Deposits
            </div>

            <div class="stat-value">
                {money(deposits)} UGX
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Approved Withdrawals
            </div>

            <div class="stat-value">
                {money(withdrawals)} UGX
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Pending Deposits
            </div>

            <div class="stat-value">
                {pending_deposits}
            </div>
        </div>

        <div class="card stat">
            <div class="stat-title">
                Pending Withdrawals
            </div>

            <div class="stat-value">
                {pending_withdrawals}
            </div>
        </div>

    </div>

    <div class="card">

        <h2>Admin Controls</h2>

        <a class="btn" href="/admin/deposits">
            Deposits
        </a>

        <a class="btn" href="/admin/withdrawals">
            Withdrawals
        </a>

        <a class="btn" href="/admin/machines">
            Machines
        </a>

        <a class="btn" href="/admin/numbers">
            Deposit Numbers
        </a>

        <a class="btn" href="/admin/notifications">
            Notifications
        </a>

        <a class="btn" href="/admin/chat">
            User Chat
        </a>

        <a class="btn" href="/admin/admins">
            Administrators
        </a>

        <a class="btn" href="/admin/analytics">
            Analytics
        </a>

    </div>
    """

    return render_template_string(
        layout("Admin", body)
    )


# ============================================================
# ADMIN DEPOSITS
# ============================================================

@app.route("/admin/deposits")
@admin_required
def admin_deposits():

    con = db()

    deposits = con.execute("""
        SELECT
            deposits.*,
            users.name,
            users.phone
        FROM deposits
        JOIN users
        ON users.id = deposits.user_id
        ORDER BY deposits.id DESC
    """).fetchall()

    con.close()

    rows = ""

    for d in deposits:

        actions = ""

        if d["status"] == "pending":

            actions = f"""
            <a
                class="btn"
                href="/admin/deposit/{d["id"]}/approve"
            >
                Approve
            </a>

            <a
                class="btn btn-danger"
                href="/admin/deposit/{d["id"]}/reject"
            >
                Reject
            </a>
            """

        rows += f"""
        <tr>

            <td>{d["id"]}</td>

            <td>
                {d["name"]}<br>
                {d["phone"]}
            </td>

            <td>
                {money(d["amount"])} UGX
            </td>

            <td>
                {d["transaction_id"]}
            </td>

            <td>
                {d["message"] or ""}
            </td>

            <td>
                <span class="badge {d["status"]}">
                    {d["status"]}
                </span>
            </td>

            <td>
                {actions}
            </td>

        </tr>
        """

    body = f"""
    <h1>Deposit Management</h1>

    <div class="card">

        <table>

            <tr>
                <th>ID</th>
                <th>User</th>
                <th>Amount</th>
                <th>TX ID</th>
                <th>Message</th>
                <th>Status</th>
                <th>Action</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Admin Deposits", body)
    )


@app.route("/admin/deposit/<int:deposit_id>/approve")
@admin_required
def approve_deposit(deposit_id):

    con = db()

    deposit = con.execute("""
        SELECT *
        FROM deposits
        WHERE id = ?
        AND status = 'pending'
    """, (
        deposit_id,
    )).fetchone()

    if not deposit:
        con.close()

        flash(
            "Deposit was not found or has already been processed.",
            "error"
        )

        return redirect(url_for("admin_deposits"))

    con.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE id = ?
    """, (
        deposit["amount"],
        deposit["user_id"]
    ))

    con.execute("""
        UPDATE deposits
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (
        now(),
        deposit_id
    ))

    con.commit()
    con.close()

    flash(
        "Deposit approved and balance updated.",
        "success"
    )

    return redirect(url_for("admin_deposits"))


@app.route("/admin/deposit/<int:deposit_id>/reject")
@admin_required
def reject_deposit(deposit_id):

    con = db()

    con.execute("""
        UPDATE deposits
        SET status = 'rejected',
            approved_at = ?
        WHERE id = ?
        AND status = 'pending'
    """, (
        now(),
        deposit_id
    ))

    con.commit()
    con.close()

    flash(
        "Deposit rejected.",
        "success"
    )

    return redirect(url_for("admin_deposits"))


# ============================================================
# ADMIN WITHDRAWALS
# ============================================================

@app.route("/admin/withdrawals")
@admin_required
def admin_withdrawals():

    con = db()

    withdrawals = con.execute("""
        SELECT
            withdrawals.*,
            users.balance AS current_balance
        FROM withdrawals
        JOIN users
        ON users.id = withdrawals.user_id
        ORDER BY withdrawals.id DESC
    """).fetchall()

    con.close()

    rows = ""

    for w in withdrawals:

        actions = ""

        if w["status"] == "pending":

            actions = f"""
            <a
                class="btn"
                href="/admin/withdrawal/{w["id"]}/approve"
            >
                Approve
            </a>

            <a
                class="btn btn-danger"
                href="/admin/withdrawal/{w["id"]}/reject"
            >
                Reject
            </a>
            """

        rows += f"""
        <tr>

            <td>{w["id"]}</td>

            <td>{w["name"]}</td>

            <td>{w["phone"]}</td>

            <td>
                {money(w["amount"])} UGX
            </td>

            <td>
                {money(w["current_balance"])} UGX
            </td>

            <td>
                <span class="badge {w["status"]}">
                    {w["status"]}
                </span>
            </td>

            <td>{actions}</td>

        </tr>
        """

    body = f"""
    <h1>Withdrawal Management</h1>

    <div class="card">

        <table>

            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Phone</th>
                <th>Amount</th>
                <th>Balance</th>
                <th>Status</th>
                <th>Action</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Admin Withdrawals", body)
    )


@app.route("/admin/withdrawal/<int:withdrawal_id>/approve")
@admin_required
def approve_withdrawal(withdrawal_id):

    con = db()

    withdrawal = con.execute("""
        SELECT *
        FROM withdrawals
        WHERE id = ?
        AND status = 'pending'
    """, (
        withdrawal_id,
    )).fetchone()

    if not withdrawal:

        con.close()

        flash(
            "Withdrawal not found or already processed.",
            "error"
        )

        return redirect(url_for("admin_withdrawals"))

    user = con.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        withdrawal["user_id"],
    )).fetchone()

    if float(user["balance"] or 0) < float(
        withdrawal["amount"] or 0
    ):

        con.close()

        flash(
            "User does not have enough balance.",
            "error"
        )

        return redirect(url_for("admin_withdrawals"))

    con.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE id = ?
    """, (
        withdrawal["amount"],
        withdrawal["user_id"]
    ))

    con.execute("""
        UPDATE withdrawals
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (
        now(),
        withdrawal_id
    ))

    con.commit()
    con.close()

    flash(
        "Withdrawal approved and balance updated.",
        "success"
    )

    return redirect(url_for("admin_withdrawals"))


@app.route("/admin/withdrawal/<int:withdrawal_id>/reject")
@admin_required
def reject_withdrawal(withdrawal_id):

    con = db()

    con.execute("""
        UPDATE withdrawals
        SET status = 'rejected',
            approved_at = ?
        WHERE id = ?
        AND status = 'pending'
    """, (
        now(),
        withdrawal_id
    ))

    con.commit()
    con.close()

    flash(
        "Withdrawal rejected.",
        "success"
    )

    return redirect(url_for("admin_withdrawals"))


# ============================================================
# ADMIN MACHINES
# ============================================================

@app.route("/admin/machines")
@admin_required
def admin_machines():

    con = db()

    machines = con.execute("""
        SELECT *
        FROM machines
        ORDER BY id ASC
    """).fetchall()

    con.close()

    rows = ""

    for m in machines:

        status = (
            "Available"
            if m["active"]
            else "Out of stock"
        )

        rows += f"""
        <tr>

            <td>{m["code"]}</td>
            <td>{m["name"]}</td>
            <td>{money(m["price"])} UGX</td>
            <td>{money(m["total_return"])} UGX</td>
            <td>{m["days"]}</td>
            <td>{m["image"]}</td>
            <td>{status}</td>

            <td>

                <a
                    class="btn"
                    href="/admin/machine/{m["id"]}/toggle"
                >
                    Toggle
                </a>

            </td>

        </tr>
        """

    body = f"""
    <h1>Machine Management</h1>

    <div class="card">

        <h2>Add Machine</h2>

        <form method="post"
              action="/admin/machine/add">

            <label>Machine Code</label>
            <input name="code" required>

            <label>Machine Name</label>
            <input name="name" required>

            <label>Purchase Amount</label>
            <input
                type="number"
                name="price"
                required
            >

            <label>Total Amount</label>
            <input
                type="number"
                name="total_return"
                required
            >

            <label>Days</label>
            <input
                type="number"
                name="days"
                required
            >

            <label>Image Filename</label>
            <input
                name="image"
                placeholder="m12.jpg"
            >

            <button type="submit">
                Add Machine
            </button>

        </form>

    </div>

    <div class="card">

        <table>

            <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Purchase</th>
                <th>Total</th>
                <th>Days</th>
                <th>Image</th>
                <th>Status</th>
                <th>Action</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Machines", body)
    )


@app.route("/admin/machine/add", methods=["POST"])
@admin_required
def add_machine():

    code = request.form.get(
        "code",
        ""
    ).strip()

    name = request.form.get(
        "name",
        ""
    ).strip()

    image = request.form.get(
        "image",
        "m1.jpg"
    ).strip()

    try:
        price = float(
            request.form.get("price", "0")
        )

        total_return = float(
            request.form.get("total_return", "0")
        )

        days = int(
            request.form.get("days", "0")
        )

    except ValueError:

        flash(
            "Invalid machine values.",
            "error"
        )

        return redirect(url_for("admin_machines"))

    if not code or not name or price <= 0 or days <= 0:

        flash(
            "Complete all machine fields.",
            "error"
        )

        return redirect(url_for("admin_machines"))

    con = db()

    try:

        con.execute("""
            INSERT INTO machines
            (code, name, price, total_return,
             days, image, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            code,
            name,
            price,
            total_return,
            days,
            image,
            now()
        ))

        con.commit()

        flash(
            "Machine added.",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "Machine code already exists.",
            "error"
        )

    con.close()

    return redirect(url_for("admin_machines"))


@app.route("/admin/machine/<int:machine_id>/toggle")
@admin_required
def toggle_machine(machine_id):

    con = db()

    con.execute("""
        UPDATE machines
        SET active =
            CASE
                WHEN active = 1 THEN 0
                ELSE 1
            END
        WHERE id = ?
    """, (
        machine_id,
    ))

    con.commit()
    con.close()

    return redirect(url_for("admin_machines"))


# ============================================================
# ADMIN DEPOSIT NUMBERS
# ============================================================

@app.route("/admin/numbers")
@admin_required
def admin_numbers():

    con = db()

    numbers = con.execute("""
        SELECT *
        FROM deposit_numbers
        ORDER BY id ASC
    """).fetchall()

    con.close()

    rows = ""

    for number in numbers:

        status = (
            "Active"
            if number["active"]
            else "Removed"
        )

        rows += f"""
        <tr>

            <td>{number["name"]}</td>
            <td>{number["phone"]}</td>
            <td>{status}</td>

            <td>
                <a
                    class="btn"
                    href="/admin/number/{number["id"]}/toggle"
                >
                    Toggle
                </a>
            </td>

        </tr>
        """

    body = f"""
    <h1>Deposit Numbers</h1>

    <div class="card">

        <form method="post"
              action="/admin/number/add">

            <label>Name</label>
            <input name="name" required>

            <label>Phone Number</label>
            <input name="phone" required>

            <button type="submit">
                Add Deposit Number
            </button>

        </form>

    </div>

    <div class="card">

        <table>

            <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Status</th>
                <th>Action</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Deposit Numbers", body)
    )


@app.route("/admin/number/add", methods=["POST"])
@admin_required
def add_number():

    name = request.form.get(
        "name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    if not name or not phone:

        flash(
            "Name and phone are required.",
            "error"
        )

        return redirect(url_for("admin_numbers"))

    con = db()

    con.execute("""
        INSERT INTO deposit_numbers
        (phone, name, active, created_at)
        VALUES (?, ?, 1, ?)
    """, (
        phone,
        name,
        now()
    ))

    con.commit()
    con.close()

    flash(
        "Deposit number added.",
        "success"
    )

    return redirect(url_for("admin_numbers"))


@app.route("/admin/number/<int:number_id>/toggle")
@admin_required
def toggle_number(number_id):

    con = db()

    con.execute("""
        UPDATE deposit_numbers
        SET active =
            CASE
                WHEN active = 1 THEN 0
                ELSE 1
            END
        WHERE id = ?
    """, (
        number_id,
    ))

    con.commit()
    con.close()

    return redirect(url_for("admin_numbers"))


# ============================================================
# ADMIN NOTIFICATIONS
# ============================================================

@app.route("/admin/notifications", methods=["GET", "POST"])
@admin_required
def admin_notifications():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        if title and message:

            con = db()

            con.execute("""
                INSERT INTO notifications
                (title, message, created_at)
                VALUES (?, ?, ?)
            """, (
                title,
                message,
                now()
            ))

            con.commit()
            con.close()

            flash(
                "Notification published.",
                "success"
            )

        return redirect(url_for("admin_notifications"))

    body = """
    <h1>Admin Notifications</h1>

    <div class="card">

        <form method="post">

            <label>Title</label>
            <input name="title" required>

            <label>Message</label>

            <textarea
                name="message"
                required
            ></textarea>

            <button type="submit">
                Publish Notification
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("Admin Notifications", body)
    )


# ============================================================
# ADMIN CHAT
# ============================================================

@app.route("/admin/chat")
@admin_required
def admin_chat():

    con = db()

    users = con.execute("""
        SELECT *
        FROM users
        WHERE is_admin = 0
        ORDER BY name ASC
    """).fetchall()

    con.close()

    rows = ""

    for user in users:

        rows += f"""
        <div class="card">

            <h3>
                {user["name"]}
            </h3>

            <p>
                {user["phone"]}
            </p>

            <a
                class="btn"
                href="/admin/chat/{user["id"]}"
            >
                Open Chat
            </a>

        </div>
        """

    body = f"""
    <h1>User Messages</h1>
    {rows or '<div class="card">No users yet.</div>'}
    """

    return render_template_string(
        layout("Admin Chat", body)
    )


@app.route(
    "/admin/chat/<int:user_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_user_chat(user_id):

    con = db()

    user = con.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if not user:
        con.close()
        abort(404)

    if request.method == "POST":

        message = request.form.get(
            "message",
            ""
        ).strip()

        if message:

            con.execute("""
                INSERT INTO messages
                (user_id, sender_type, message, created_at)
                VALUES (?, 'admin', ?, ?)
            """, (
                user_id,
                message,
                now()
            ))

            con.commit()

        con.close()

        return redirect(
            url_for(
                "admin_user_chat",
                user_id=user_id
            )
        )

    messages = con.execute("""
        SELECT *
        FROM messages
        WHERE user_id = ?
        ORDER BY id ASC
    """, (
        user_id,
    )).fetchall()

    con.close()

    chat_html = ""

    for item in messages:

        admin_class = (
            "admin"
            if item["sender_type"] == "admin"
            else ""
        )

        chat_html += f"""
        <div class="message {admin_class}">

            <strong>
                {item["sender_type"].title()}
            </strong>

            <p>
                {item["message"]}
            </p>

            <span class="small">
                {item["created_at"]}
            </span>

        </div>
        """

    body = f"""
    <h1>
        Chat: {user["name"]}
    </h1>

    <div class="card">

        <div class="chat">
            {chat_html}
        </div>

    </div>

    <div class="card">

        <form method="post">

            <textarea
                name="message"
                required
                placeholder="Write reply..."
            ></textarea>

            <button type="submit">
                Send Reply
            </button>

        </form>

    </div>
    """

    return render_template_string(
        layout("User Chat", body)
    )


# ============================================================
# ADMIN MANAGEMENT
# ============================================================

@app.route("/admin/admins")
@admin_required
def admin_admins():

    con = db()

    admins = con.execute("""
        SELECT *
        FROM admin_users
        ORDER BY id ASC
    """).fetchall()

    con.close()

    rows = ""

    for admin in admins:

        rows += f"""
        <tr>

            <td>{admin["phone"]}</td>

            <td>
                {admin["created_at"]}
            </td>

        </tr>
        """

    body = f"""
    <h1>Administrators</h1>

    <div class="card">

        <h2>Add Administrator</h2>

        <form method="post"
              action="/admin/admin/add">

            <label>Phone Number</label>
            <input name="phone" required>

            <label>Password</label>
            <input
                type="password"
                name="password"
                required
            >

            <button type="submit">
                Add Administrator
            </button>

        </form>

    </div>

    <div class="card">

        <table>

            <tr>
                <th>Phone</th>
                <th>Created</th>
            </tr>

            {rows}

        </table>

    </div>
    """

    return render_template_string(
        layout("Administrators", body)
    )


@app.route("/admin/admin/add", methods=["POST"])
@admin_required
def add_admin():

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not phone or not password:

        flash(
            "Phone and password are required.",
            "error"
        )

        return redirect(url_for("admin_admins"))

    con = db()

    try:

        con.execute("""
            INSERT INTO admin_users
            (phone, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (
            phone,
            generate_password_hash(password),
            now()
        ))

        # Make/create corresponding user account as admin.
        user = con.execute("""
            SELECT id
            FROM users
            WHERE phone = ?
        """, (
            phone,
        )).fetchone()

        if user:

            con.execute("""
                UPDATE users
                SET is_admin = 1
                WHERE id = ?
            """, (
                user["id"],
            ))

        else:

            con.execute("""
                INSERT INTO users
                (name, phone, password_hash,
                 balance, referral_code,
                 is_admin, created_at)
                VALUES (?, ?, ?, 0, ?, 1, ?)
            """, (
                "Administrator",
                phone,
                generate_password_hash(password),
                "ADMIN-" + secrets.token_hex(5).upper(),
                now()
            ))

        con.commit()

        flash(
            "Administrator added.",
            "success"
        )

    except sqlite3.IntegrityError:

        flash(
            "That administrator already exists.",
            "error"
        )

    con.close()

    return redirect(url_for("admin_admins"))


# ============================================================
# ADMIN ANALYTICS
# ============================================================

@app.route("/admin/analytics")
@admin_required
def admin_analytics():

    con = db()

    days = []

    for i in range(13, -1, -1):

        date_value = (
            datetime.now() -
            timedelta(days=i)
        ).strftime("%Y-%m-%d")

        users_count = con.execute("""
            SELECT COUNT(*) AS c
            FROM users
            WHERE date(created_at) <= date(?)
        """, (
            date_value,
        )).fetchone()["c"]

        deposits_total = con.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM deposits
            WHERE status='approved'
            AND date(approved_at) = date(?)
        """, (
            date_value,
        )).fetchone()["total"]

        withdrawals_total = con.execute("""
            SELECT COALESCE(SUM(amount),0) AS total
            FROM withdrawals
            WHERE status='approved'
            AND date(approved_at) = date(?)
        """, (
            date_value,
        )).fetchone()["total"]

        days.append({
            "date": date_value,
            "users": int(users_count or 0),
            "deposits": float(deposits_total or 0),
            "withdrawals": float(withdrawals_total or 0)
        })

    con.close()

    labels = [
        x["date"]
        for x in days
    ]

    users_data = [
        x["users"]
        for x in days
    ]

    deposits_data = [
        x["deposits"]
        for x in days
    ]

    withdrawals_data = [
        x["withdrawals"]
        for x in days
    ]

    body = f"""
    <h1>Company Analytics</h1>

    <div class="card">

        <h2>Growth / Deposits / Withdrawals</h2>

        <canvas id="growthChart"></canvas>

    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script>

    const labels = {labels};

    const usersData = {users_data};

    const depositsData = {deposits_data};

    const withdrawalsData = {withdrawals_data};

    new Chart(
        document.getElementById("growthChart"),
        {{
            type: "line",

            data: {{
                labels: labels,

                datasets: [
                    {{
                        label: "Users",
                        data: usersData,
                        tension: 0.3
                    }},

                    {{
                        label: "Deposits UGX",
                        data: depositsData,
                        tension: 0.3
                    }},

                    {{
                        label: "Withdrawals UGX",
                        data: withdrawalsData,
                        tension: 0.3
                    }}
                ]
            }},

            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }}
    );

    </script>

    <style>
        #growthChart {{
            min-height: 350px;
        }}
    </style>
    """

    return render_template_string(
        layout("Analytics", body)
    )


# ============================================================
# ERROR PAGES
# ============================================================

@app.errorhandler(403)
def forbidden(error):

    body = """
    <div class="card center">

        <h1>403</h1>

        <p>
            You do not have permission to access this page.
        </p>

        <a class="btn" href="/dashboard">
            Dashboard
        </a>

    </div>
    """

    return render_template_string(
        layout("Access Denied", body)
    ), 403


@app.errorhandler(404)
def not_found(error):

    body = """
    <div class="card center">

        <h1>404</h1>

        <p>
            The page you requested was not found.
        </p>

        <a class="btn" href="/dashboard">
            Dashboard
        </a>

    </div>
    """

    return render_template_string(
        layout("Not Found", body)
    ), 404


@app.errorhandler(500)
def server_error(error):

    body = """
    <div class="card center">

        <h1>500</h1>

        <p>
            An application error occurred.
        </p>

        <p class="small">
            Check the terminal for the Python error.
        </p>

        <a class="btn" href="/dashboard">
            Dashboard
        </a>

    </div>
    """

    return render_template_string(
        layout("Server Error", body)
    ), 500


# ============================================================
# STARTUP
# ============================================================

init_db()


if __name__ == "__main__":

    print("=" * 60)
    print("DATA4MINES")
    print("=" * 60)
    print("Server: http://127.0.0.1:5000")
    print()
    print("Primary Admin")
    print("Phone:", ADMIN_PHONE)
    print("Password:", ADMIN_PASSWORD)
    print()
    print("Machine images directory:")
    print(MACHINE_DIR)
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )