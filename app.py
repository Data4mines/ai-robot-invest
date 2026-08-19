import os
import re
import sqlite3
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# DATA4MINES - COMPLETE SINGLE-FILE FLASK APPLICATION
# ============================================================
#
# Required packages:
#   Flask
#   Werkzeug
#   gunicorn
#
# Render start command:
#   gunicorn app:app
#
# Project structure:
#
#   app.py
#   static/
#       machines/
#           bg.jpg
#           m1.jpg
#           m2.jpg
#           m3.jpg
#           m4.jpg
#           m5.jpg
#           m6.jpg
#           m7.jpg
#           m8.jpg
#           m9.jpg
#           m10.jpg
#           m11.jpg
#
# This version fixes the previous Python syntax problem caused by
# JavaScript being outside a Python string.
#
# Features:
# - Login / registration
# - Primary admin
# - Additional admins
# - Admin-only button/panel
# - Shop
# - Machines
# - Machine images
# - Background machine image
# - Machine countdown
# - Receive Money after completion
# - Machine purchase reward
# - Referral system
# - 5,000 UGX referral reward
# - Manual deposits
# - Admin deposit approval
# - Manual withdrawals
# - Admin withdrawal approval
# - 7% withdrawal tax
# - Tax shown on withdrawal page
# - Notifications
# - User-to-admin chat
# - Admin-to-user replies
# - Deposit-number management
# - Machine management
# - Admin statistics
# - Deposit/withdraw/growth chart
# - Mobile 16px layout
# - Custom 404/500 pages
# - /health endpoint
# - Old SQLite database migration
#
# IMPORTANT:
# This code does NOT connect to a mobile-money/bank API.
# Deposits and withdrawals remain manual and require admin approval.
# For production handling of real customer funds, use the appropriate
# licensing, KYC/AML, accounting, security, audit, payment-provider,
# HTTPS and persistent database requirements for your jurisdiction.
# ============================================================


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
MACHINE_DIR = STATIC_DIR / "machines"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
MACHINE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY_BEFORE_PRODUCTION",
)


# ============================================================
# SETTINGS
# ============================================================

ADMIN_PHONE = os.getenv(
    "ADMIN_PHONE",
    "0792759363",
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "twix1831",
)

COMPANY_NAME = "DATA4MINES"

DEPOSIT_OWNER = "Nuwahereza Christine"

REFERRAL_REWARD = 5000

WITHDRAW_TAX_RATE = 0.07

DB_PATH = BASE_DIR / "data4mines.db"


# ============================================================
# DEFAULT MACHINES
# ============================================================

DEFAULT_MACHINES = [
    (
        "M1",
        "DATA4MINES Starter",
        50000,
        60000,
        10,
        1000,
        "m1.jpg",
    ),
    (
        "M2",
        "DATA4MINES Bronze",
        100000,
        125000,
        15,
        2500,
        "m2.jpg",
    ),
    (
        "M3",
        "DATA4MINES Silver",
        250000,
        325000,
        20,
        6000,
        "m3.jpg",
    ),
    (
        "M4",
        "DATA4MINES Gold",
        500000,
        700000,
        25,
        12000,
        "m4.jpg",
    ),
    (
        "M5",
        "DATA4MINES Platinum",
        1000000,
        1500000,
        30,
        25000,
        "m5.jpg",
    ),
    (
        "M6",
        "DATA4MINES Diamond",
        2000000,
        3200000,
        35,
        55000,
        "m6.jpg",
    ),
    (
        "M7",
        "DATA4MINES Elite",
        5000000,
        8500000,
        40,
        120000,
        "m7.jpg",
    ),
    (
        "M8",
        "DATA4MINES Pro",
        10000000,
        18000000,
        45,
        250000,
        "m8.jpg",
    ),
    (
        "M9",
        "DATA4MINES Ultra",
        20000000,
        38000000,
        50,
        500000,
        "m9.jpg",
    ),
    (
        "M10",
        "DATA4MINES Max",
        50000000,
        100000000,
        60,
        1000000,
        "m10.jpg",
    ),
    (
        "M11",
        "DATA4MINES Titan",
        100000000,
        220000000,
        75,
        2500000,
        "m11.jpg",
    ),
]


# ============================================================
# DATABASE
# ============================================================

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def now():
    return datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat()


def parse_dt(value):
    return datetime.fromisoformat(value)


def money(value):
    return f"{int(value):,} UGX"


def normalize_phone(value):
    return re.sub(
        r"[^0-9+]",
        "",
        value or "",
    )


def make_referral_code():
    return (
        "D4M-"
        + secrets.token_hex(4).upper()
    )


def buyer_reward(machine):
    """
    Buyer reward scales with machine amount.
    The machine's configured reward is the minimum.
    """
    configured = int(
        machine["buyer_reward"]
    )

    scaled = int(
        int(machine["purchase_amount"]) * 0.02
    )

    return max(
        configured,
        scaled,
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    connection = db()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by TEXT,
            referral_reward_paid INTEGER NOT NULL DEFAULT 0,
            balance INTEGER NOT NULL DEFAULT 0,
            total_deposited INTEGER NOT NULL DEFAULT 0,
            total_withdrawn INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            purchase_amount INTEGER NOT NULL,
            payout_amount INTEGER NOT NULL,
            days INTEGER NOT NULL,
            buyer_reward INTEGER NOT NULL DEFAULT 0,
            image TEXT NOT NULL DEFAULT 'm1.jpg',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            machine_id INTEGER NOT NULL,
            purchased_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            reward_paid INTEGER NOT NULL DEFAULT 0,
            received INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY(machine_id)
                REFERENCES machines(id)
                ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            account_number TEXT NOT NULL,
            reference TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            approved_at TEXT,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            tax INTEGER NOT NULL,
            net_amount INTEGER NOT NULL,
            phone TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            approved_at TEXT,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS deposit_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            owner_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            from_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # ========================================================
    # CREATE PRIMARY ADMIN
    # ========================================================

    admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE phone = ?
        """,
        (ADMIN_PHONE,),
    ).fetchone()

    if admin is None:

        connection.execute(
            """
            INSERT INTO users (
                phone,
                name,
                password_hash,
                referral_code,
                referred_by,
                referral_reward_paid,
                balance,
                created_at,
                is_admin
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, 1
            )
            """,
            (
                ADMIN_PHONE,
                "Primary Admin",
                generate_password_hash(
                    ADMIN_PASSWORD
                ),
                "ADMIN",
                None,
                0,
                0,
                now(),
            ),
        )

    else:

        connection.execute(
            """
            UPDATE users
            SET is_admin = 1
            WHERE phone = ?
            """,
            (ADMIN_PHONE,),
        )

    # ========================================================
    # CREATE DEFAULT MACHINES
    # ========================================================

    for machine in DEFAULT_MACHINES:

        connection.execute(
            """
            INSERT OR IGNORE INTO machines (
                code,
                name,
                purchase_amount,
                payout_amount,
                days,
                buyer_reward,
                image,
                active,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                machine[0],
                machine[1],
                machine[2],
                machine[3],
                machine[4],
                machine[5],
                machine[6],
                1,
                now(),
            ),
        )

    # ========================================================
    # CREATE DEFAULT DEPOSIT NUMBER
    # ========================================================

    deposit_count = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM deposit_numbers
        """
    ).fetchone()["total"]

    if deposit_count == 0:

        connection.execute(
            """
            INSERT INTO deposit_numbers (
                number,
                owner_name,
                active,
                created_at
            )
            VALUES (?, ?, 1, ?)
            """,
            (
                ADMIN_PHONE,
                DEPOSIT_OWNER,
                now(),
            ),
        )

    # ========================================================
    # MIGRATE OLD DATABASES
    # ========================================================

    required_columns = {

        "users": {
            "referral_reward_paid":
                "INTEGER NOT NULL DEFAULT 0",

            "balance":
                "INTEGER NOT NULL DEFAULT 0",

            "total_deposited":
                "INTEGER NOT NULL DEFAULT 0",

            "total_withdrawn":
                "INTEGER NOT NULL DEFAULT 0",

            "is_admin":
                "INTEGER NOT NULL DEFAULT 0",
        },

        "machines": {
            "buyer_reward":
                "INTEGER NOT NULL DEFAULT 0",

            "image":
                "TEXT NOT NULL DEFAULT 'm1.jpg'",

            "active":
                "INTEGER NOT NULL DEFAULT 1",
        },

        "user_machines": {
            "reward_paid":
                "INTEGER NOT NULL DEFAULT 0",

            "received":
                "INTEGER NOT NULL DEFAULT 0",
        },
    }

    for table, columns in required_columns.items():

        existing_columns = {
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        for column, definition in columns.items():

            if column not in existing_columns:

                connection.execute(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN {column} {definition}
                    """
                )

    connection.commit()
    connection.close()


# ============================================================
# AUTHENTICATION
# ============================================================

def current_user():

    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    connection = db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    connection.close()

    return user


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not current_user():

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        user = current_user()

        if (
            not user
            or not user["is_admin"]
        ):

            flash(
                "Admin access required.",
                "error",
            )

            return redirect(
                url_for("dashboard")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# MAIN HTML TEMPLATE
# ============================================================

PAGE = """
<!doctype html>

<html lang="en">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1"
>

<title>
    {{ title }} - DATA4MINES
</title>

<style>

:root {

    font-size: 16px;

    --bg: #06130e;
    --panel: #0d241a;
    --panel2: #102b20;
    --text: #f4fff9;
    --muted: #a8c0b5;
    --line: #24513e;
    --accent: #20d37b;
    --danger: #ff6b6b;
    --warn: #f6c453;

}

* {
    box-sizing: border-box;
}

html {
    font-size: 16px;
}

body {

    margin: 0;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    font-size: 16px;

    line-height: 1.5;

    color: var(--text);

    background:

        linear-gradient(
            rgba(3,15,10,.88),
            rgba(3,15,10,.94)
        ),

        url(
            "{{ url_for(
                'static',
                filename='machines/bg.jpg'
            ) }}"
        )

        center / cover fixed;

    background-color: var(--bg);

}

a {
    color: inherit;
    text-decoration: none;
}

.wrap {

    max-width: 1200px;

    margin: auto;

    padding: 20px;

}

.nav {

    position: sticky;

    top: 0;

    z-index: 20;

    background:
        rgba(5,18,13,.96);

    border-bottom:
        1px solid var(--line);

}

.navin {

    max-width: 1200px;

    margin: auto;

    display: flex;

    align-items: center;

    justify-content:
        space-between;

    gap: 14px;

    padding: 12px 20px;

}

.brand {

    font-size: 22px;

    font-weight: 800;

}

.brand span {
    color: var(--accent);
}

.links {

    display: flex;

    gap: 10px;

    align-items: center;

    flex-wrap: wrap;

}

.links a {

    padding:
        8px 10px;

    border-radius:
        9px;

}

.links a:hover {

    background:
        var(--panel2);

}

.adminlink {

    border:
        1px solid var(--accent);

}

.grid {

    display: grid;

    grid-template-columns:
        repeat(3, 1fr);

    gap: 16px;

}

.grid2 {

    display: grid;

    grid-template-columns:
        repeat(2, 1fr);

    gap: 16px;

}

.card {

    background:
        rgba(13,36,26,.94);

    border:
        1px solid var(--line);

    border-radius:
        16px;

    padding:
        18px;

    box-shadow:
        0 8px 30px
        rgba(0,0,0,.18);

}

.stat {
    min-height: 120px;
}

.muted {
    color: var(--muted);
}

h1 {

    font-size:
        30px;

    margin:
        8px 0 18px;

}

h2 {
    font-size: 22px;
}

h3 {
    font-size: 18px;
}

.big {

    font-size:
        26px;

    font-weight:
        800;

}

.btn {

    display:
        inline-block;

    border:
        0;

    border-radius:
        10px;

    padding:
        11px 15px;

    background:
        var(--accent);

    color:
        #03130b;

    font-weight:
        700;

    cursor:
        pointer;

    font-size:
        16px;

}

.btn.secondary {

    background:
        #183c2b;

    color:
        var(--text);

    border:
        1px solid var(--line);

}

.btn.danger {

    background:
        var(--danger);

    color:
        #260000;

}

.btn.warn {

    background:
        var(--warn);

    color:
        #241900;

}

.btn:disabled {

    opacity:
        .45;

    cursor:
        not-allowed;

}

form {
    margin: 0;
}

input,
select,
textarea {

    width: 100%;

    padding: 12px;

    border-radius: 10px;

    border:
        1px solid var(--line);

    background:
        #071a12;

    color:
        var(--text);

    font-size:
        16px;

    margin:
        6px 0 12px;

}

textarea {

    min-height:
        100px;

}

.row {

    display:
        flex;

    gap:
        10px;

    align-items:
        center;

    flex-wrap:
        wrap;

}

.table {

    width:
        100%;

    border-collapse:
        collapse;

    font-size:
        15px;

}

.table th,
.table td {

    padding:
        10px;

    border-bottom:
        1px solid var(--line);

    text-align:
        left;

    vertical-align:
        top;

}

.machine-grid {

    display:
        grid;

    grid-template-columns:
        repeat(3, 1fr);

    gap:
        16px;

}

.machine img {

    width:
        100%;

    height:
        230px;

    object-fit:
        cover;

    border-radius:
        12px;

    background:
        #06130e;

}

.badge {

    display:
        inline-block;

    padding:
        4px 9px;

    border-radius:
        999px;

    background:
        #164b31;

    color:
        #b8ffd7;

    font-size:
        13px;

}

.notice {

    padding:
        12px;

    border-radius:
        10px;

    background:
        #102d21;

    border:
        1px solid var(--line);

    margin-bottom:
        10px;

}

.error {

    background:
        #3a1111;

    border-color:
        #7b2a2a;

}

.success {

    background:
        #103d27;

    border-color:
        #287e52;

}

.warning {

    background:
        #3b2b0c;

    border-color:
        #80631d;

}

.flash {
    margin: 10px 0;
}

.bar {

    height:
        18px;

    background:
        #092016;

    border:
        1px solid var(--line);

    border-radius:
        999px;

    overflow:
        hidden;

}

.fill {

    height:
        100%;

    background:
        var(--accent);

}

.footer {

    text-align:
        center;

    padding:
        30px;

    color:
        var(--muted);

}

.bottom {
    display: none;
}

.login {

    max-width:
        520px;

    margin:
        50px auto;

}

.small {
    font-size: 14px;
}

.center {
    text-align: center;
}

.icon {
    font-size: 21px;
    display: block;
}

.admin-grid {

    display:
        grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap:
        12px;

}

.kpi {

    font-size:
        24px;

    font-weight:
        800;

}


/* ============================================================
   MOBILE
   ============================================================ */

@media (max-width: 800px) {

    html {
        font-size: 16px;
    }

    body {
        font-size: 16px;
    }

    .wrap {
        padding: 14px;
    }

    .navin {
        padding:
            10px 14px;
    }

    .links {
        display: none;
    }

    .grid,
    .grid2,
    .machine-grid {

        grid-template-columns:
            1fr;

    }

    .admin-grid {

        grid-template-columns:
            repeat(2, 1fr);

    }

    h1 {
        font-size: 26px;
    }

    .machine img {
        height: 240px;
    }

    .bottom {

        display:
            grid;

        position:
            fixed;

        bottom:
            0;

        left:
            0;

        right:
            0;

        z-index:
            30;

        grid-template-columns:
            repeat(6, 1fr);

        background:
            #06150f;

        border-top:
            1px solid var(--line);

        padding:
            7px 4px;

    }

    .bottom a {

        text-align:
            center;

        font-size:
            12px;

        color:
            var(--muted);

    }

    .bottom .icon {
        font-size: 20px;
    }

    .page-space {
        height: 72px;
    }

}

</style>

</head>

<body>


<header class="nav">

<div class="navin">

<a
    class="brand"
    href="{{ url_for('dashboard') }}"
>
    DATA4<span>MINES</span>
</a>


<nav class="links">

{% if user %}

<a href="{{ url_for('dashboard') }}">
    Dashboard
</a>

<a href="{{ url_for('shop') }}">
    🛒 Shop
</a>

<a href="{{ url_for('my_machines') }}">
    ⚙ My Machines
</a>

<a href="{{ url_for('rewards') }}">
    🎁 Rewards
</a>

<a href="{{ url_for('deposit') }}">
    Deposit
</a>

<a href="{{ url_for('withdraw') }}">
    Withdraw
</a>

<a href="{{ url_for('notifications') }}">
    🔔
</a>

<a href="{{ url_for('chat') }}">
    💬
</a>

{% if user['is_admin'] %}

<a
    class="adminlink"
    href="{{ url_for('admin') }}"
>
    Admin
</a>

{% endif %}

<a href="{{ url_for('logout') }}">
    Logout
</a>

{% endif %}

</nav>

</div>

</header>


<main class="wrap">

{% with messages =
    get_flashed_messages(
        with_categories=true
    )
%}

{% for category, msg in messages %}

<div
    class="notice flash {{ category }}"
>
    {{ msg }}
</div>

{% endfor %}

{% endwith %}


{{ body|safe }}

</main>


{% if user %}

<div class="bottom">

<a href="{{ url_for('dashboard') }}">
    <span class="icon">⌂</span>
    Home
</a>

<a href="{{ url_for('shop') }}">
    <span class="icon">🛒</span>
    Shop
</a>

<a href="{{ url_for('my_machines') }}">
    <span class="icon">⚙</span>
    Machines
</a>

<a href="{{ url_for('rewards') }}">
    <span class="icon">🎁</span>
    Rewards
</a>

<a href="{{ url_for('chat') }}">
    <span class="icon">💬</span>
    Chat
</a>

<a href="{{ url_for('withdraw') }}">
    <span class="icon">💸</span>
    Withdraw
</a>

</div>

<div class="page-space"></div>

{% endif %}


<footer class="footer">

{{ COMPANY_NAME }}

•

Manual deposit and withdrawal approval

</footer>


</body>
</html>
"""


def render_page(
    title,
    content,
    **context
):

    user = current_user()

    return render_template_string(
        PAGE,
        title=title,
        body=content,
        user=user,
        COMPANY_NAME=COMPANY_NAME,
        **context,
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    if current_user():

        return redirect(
            url_for("dashboard")
        )

    return render_page(
        "Welcome",
        """
        <section class="card login center">

            <h1>
                DATA4<span
                    style="color:#20d37b"
                >MINES</span>
            </h1>

            <p class="muted">
                Investment management portal
            </p>

            <div
                class="row"
                style="justify-content:center"
            >

                <a
                    class="btn"
                    href="{{ url_for('login') }}"
                >
                    Login
                </a>

                <a
                    class="btn secondary"
                    href="{{ url_for('register') }}"
                >
                    Register
                </a>

            </div>

        </section>
        """
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        phone = normalize_phone(
            request.form.get("phone")
        )

        password = request.form.get(
            "password",
            ""
        )

        referral = request.form.get(
            "referral",
            ""
        ).strip().upper()

        if (
            not name
            or len(phone) < 9
            or len(password) < 6
        ):

            flash(
                "Enter a valid name, phone number and password of at least 6 characters.",
                "error",
            )

            return redirect(
                url_for("register")
            )

        connection = db()

        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE phone = ?
            """,
            (phone,),
        ).fetchone()

        if existing:

            connection.close()

            flash(
                "Phone number is already registered.",
                "error",
            )

            return redirect(
                url_for("register")
            )

        referred_by = None

        if referral:

            referral_user = connection.execute(
                """
                SELECT referral_code
                FROM users
                WHERE referral_code = ?
                """,
                (referral,),
            ).fetchone()

            if referral_user:
                referred_by = referral

        referral_code = make_referral_code()

        while connection.execute(
            """
            SELECT id
            FROM users
            WHERE referral_code = ?
            """,
            (referral_code,),
        ).fetchone():

            referral_code = make_referral_code()

        connection.execute(
            """
            INSERT INTO users (
                phone,
                name,
                password_hash,
                referral_code,
                referred_by,
                referral_reward_paid,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                phone,
                name,
                generate_password_hash(
                    password
                ),
                referral_code,
                referred_by,
                now(),
            ),
        )

        connection.commit()
        connection.close()

        flash(
            "Registration successful. Please log in.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_page(
        "Register",
        """
        <section class="card login">

            <h1>Create account</h1>

            <form method="post">

                <label>
                    Full name
                </label>

                <input
                    name="name"
                    required
                >

                <label>
                    Phone number
                </label>

                <input
                    name="phone"
                    inputmode="tel"
                    required
                >

                <label>
                    Password
                </label>

                <input
                    name="password"
                    type="password"
                    minlength="6"
                    required
                >

                <label>
                    Referral code
                </label>

                <input
                    name="referral"
                    value="{{ request.args.get('ref','') }}"
                >

                <button class="btn">
                    Register
                </button>

            </form>

            <p class="muted">
                Already registered?
                <a href="{{ url_for('login') }}">
                    Login
                </a>
            </p>

        </section>
        """
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        phone = normalize_phone(
            request.form.get("phone")
        )

        password = request.form.get(
            "password",
            ""
        )

        connection = db()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (phone,),
        ).fetchone()

        connection.close()

        if (
            user
            and check_password_hash(
                user["password_hash"],
                password,
            )
        ):

            session.clear()

            session["user_id"] = user["id"]

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid phone number or password.",
            "error",
        )

    return render_page(
        "Login",
        """
        <section class="card login">

            <h1>Login</h1>

            <form method="post">

                <label>
                    Phone number
                </label>

                <input
                    name="phone"
                    inputmode="tel"
                    required
                >

                <label>
                    Password
                </label>

                <input
                    name="password"
                    type="password"
                    required
                >

                <button class="btn">
                    Login
                </button>

            </form>

            <p class="muted">

                New user?

                <a href="{{ url_for('register') }}">
                    Register
                </a>

            </p>

        </section>
        """
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()

    connection = db()

    machine_count = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM user_machines
        WHERE user_id = ?
        """,
        (user["id"],),
    ).fetchone()["total"]

    deposit_accounts = connection.execute(
        """
        SELECT *
        FROM deposit_numbers
        WHERE active = 1
        ORDER BY id
        """
    ).fetchall()

    notifications = connection.execute(
        """
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 3
        """
    ).fetchall()

    connection.close()

    body = """
    <h1>
        Welcome,
        {{ user['name'] }}
    </h1>


    <div class="grid">

        <div class="card stat">

            <div class="muted">
                Available Balance
            </div>

            <div class="big">
                {{ money(user['balance']) }}
            </div>

        </div>


        <div class="card stat">

            <div class="muted">
                Approved Deposits
            </div>

            <div class="big">
                {{ money(user['total_deposited']) }}
            </div>

        </div>


        <div class="card stat">

            <div class="muted">
                Approved Withdrawals
            </div>

            <div class="big">
                {{ money(user['total_withdrawn']) }}
            </div>

        </div>

    </div>


    <div
        class="grid"
        style="margin-top:16px"
    >

        <a
            class="card center"
            href="{{ url_for('shop') }}"
        >

            <span class="icon">
                🛒
            </span>

            <h2>
                Shop
            </h2>

            <p class="muted">
                Purchase a DATA4MINES machine
            </p>

        </a>


        <a
            class="card center"
            href="{{ url_for('my_machines') }}"
        >

            <span class="icon">
                ⚙
            </span>

            <h2>
                My Machines
            </h2>

            <p class="muted">
                {{ machine_count }}
                purchased machine(s)
            </p>

        </a>


        <a
            class="card center"
            href="{{ url_for('rewards') }}"
        >

            <span class="icon">
                🎁
            </span>

            <h2>
                Rewards
            </h2>

            <p class="muted">
                Invite friends and earn rewards
            </p>

        </a>

    </div>


    <div
        class="grid2"
        style="margin-top:16px"
    >

        <div class="card">

            <h2>
                Deposit Accounts
            </h2>

            {% for d in deposit_accounts %}

            <div class="notice">

                <b>
                    {{ d['number'] }}
                </b>

                <br>

                {{ d['owner_name'] }}

            </div>

            {% else %}

            <p class="muted">
                No active deposit number.
            </p>

            {% endfor %}


            <a
                class="btn"
                href="{{ url_for('deposit') }}"
            >
                Make Deposit Request
            </a>

        </div>


        <div class="card">

            <h2>
                Latest Updates 🔔
            </h2>

            {% for n in notifications %}

            <div class="notice">

                <b>
                    {{ n['title'] }}
                </b>

                <br>

                {{ n['message'] }}

                <div class="small muted">
                    {{ n['created_at'] }}
                </div>

            </div>

            {% else %}

            <p class="muted">
                No new notifications.
            </p>

            {% endfor %}

        </div>

    </div>
    """

    return render_page(
        "Dashboard",
        render_template_string(
            body,
            user=user,
            money=money,
            machine_count=machine_count,
            deposit_accounts=deposit_accounts,
            notifications=notifications,
        ),
    )


# ============================================================
# SHOP
# ============================================================

@app.route("/shop")
@login_required
def shop():

    connection = db()

    machines = connection.execute(
        """
        SELECT *
        FROM machines
        WHERE active = 1
        ORDER BY id
        """
    ).fetchall()

    connection.close()

    body = """
    <h1>
        Machine Shop
    </h1>

    <p class="muted">
        Machines are purchased immediately when the user's
        approved balance is sufficient.
        Machine purchase itself does not require a second
        admin approval.
    </p>

    <div class="machine-grid">

    {% for m in machines %}

    <article class="card machine">

        <img
            src="{{ url_for(
                'machine_image',
                filename=m['image']
            ) }}"
            alt="{{ m['name'] }}"
        >

        <span class="badge">
            {{ m['code'] }}
        </span>

        <h2>
            {{ m['name'] }}
        </h2>

        <p>
            Purchase:
            <b>
                {{ money(m['purchase_amount']) }}
            </b>
        </p>

        <p>
            Total payout:
            <b>
                {{ money(m['payout_amount']) }}
            </b>
        </p>

        <p>
            Duration:
            <b>
                {{ m['days'] }} days
            </b>
        </p>

        <p>
            Buyer reward:
            <b>
                {{ money(buyer_reward(m)) }}
            </b>
        </p>

        <form
            method="post"
            action="{{ url_for(
                'buy_machine',
                machine_id=m['id']
            ) }}"
        >

            <button class="btn">
                Buy Machine
            </button>

        </form>

    </article>

    {% endfor %}

    </div>
    """

    return render_page(
        "Shop",
        render_template_string(
            body,
            machines=machines,
            money=money,
            buyer_reward=buyer_reward,
        ),
    )


# ============================================================
# BUY MACHINE
# ============================================================

@app.route(
    "/buy/<int:machine_id>",
    methods=["POST"]
)
@login_required
def buy_machine(machine_id):

    user = current_user()

    connection = db()

    machine = connection.execute(
        """
        SELECT *
        FROM machines
        WHERE id = ?
        AND active = 1
        """,
        (machine_id,),
    ).fetchone()

    if not machine:

        connection.close()

        flash(
            "Machine is unavailable.",
            "error",
        )

        return redirect(
            url_for("shop")
        )

    user_record = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user["id"],),
    ).fetchone()

    if (
        user_record["balance"]
        < machine["purchase_amount"]
    ):

        connection.close()

        flash(
            "Insufficient approved balance. Make a deposit and wait for admin approval.",
            "error",
        )

        return redirect(
            url_for("shop")
        )

    start = datetime.now(
        timezone.utc
    )

    expiry = (
        start
        + timedelta(
            days=machine["days"]
        )
    )

    reward = buyer_reward(
        machine
    )

    connection.execute(
        """
        UPDATE users
        SET balance =
            balance - ?
        WHERE id = ?
        """,
        (
            machine["purchase_amount"],
            user["id"],
        ),
    )

    connection.execute(
        """
        INSERT INTO user_machines (
            user_id,
            machine_id,
            purchased_at,
            expires_at,
            reward_paid,
            received
        )
        VALUES (?, ?, ?, ?, 1, 0)
        """,
        (
            user["id"],
            machine["id"],
            start.replace(
                microsecond=0
            ).isoformat(),
            expiry.replace(
                microsecond=0
            ).isoformat(),
        ),
    )

    # Buyer reward
    connection.execute(
        """
        UPDATE users
        SET balance =
            balance + ?
        WHERE id = ?
        """,
        (
            reward,
            user["id"],
        ),
    )

    # ========================================================
    # REFERRAL REWARD
    # ========================================================

    if (
        user_record["referred_by"]
        and not user_record["referral_reward_paid"]
    ):

        referrer = connection.execute(
            """
            SELECT *
            FROM users
            WHERE referral_code = ?
            """,
            (
                user_record[
                    "referred_by"
                ],
            ),
        ).fetchone()

        if (
            referrer
            and referrer["id"]
            != user["id"]
        ):

            connection.execute(
                """
                UPDATE users
                SET balance =
                    balance + ?
                WHERE id = ?
                """,
                (
                    REFERRAL_REWARD,
                    referrer["id"],
                ),
            )

            connection.execute(
                """
                UPDATE users
                SET referral_reward_paid = 1
                WHERE id = ?
                """,
                (
                    user["id"],
                ),
            )

            connection.execute(
                """
                INSERT INTO notifications (
                    title,
                    message,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    "Referral Reward",
                    (
                        "A referral reward of "
                        f"{REFERRAL_REWARD:,} UGX "
                        "was credited."
                    ),
                    now(),
                ),
            )

    connection.commit()
    connection.close()

    flash(
        (
            "Machine purchased. "
            f"Your machine reward of "
            f"{money(reward)} was credited."
        ),
        "success",
    )

    return redirect(
        url_for("my_machines")
    )


# ============================================================
# MACHINE IMAGE
# ============================================================

@app.route(
    "/machine-image/<path:filename>"
)
def machine_image(filename):

    # Prevent paths such as ../something
    safe_name = Path(
        filename
    ).name

    return send_from_directory(
        MACHINE_DIR,
        safe_name,
    )


# ============================================================
# MY MACHINES
# ============================================================

@app.route("/my-machines")
@login_required
def my_machines():

    user = current_user()

    connection = db()

    machines = connection.execute(
        """
        SELECT
            um.*,
            m.code,
            m.name,
            m.purchase_amount,
            m.payout_amount,
            m.days,
            m.image,
            m.buyer_reward

        FROM user_machines um

        JOIN machines m
        ON m.id = um.machine_id

        WHERE um.user_id = ?

        ORDER BY um.id DESC
        """,
        (
            user["id"],
        ),
    ).fetchall()

    connection.close()

    body = """
    <h1>
        My Machines
    </h1>

    <div class="machine-grid">

    {% for machine in machines %}

        {% set expiry =
            parse_dt(machine['expires_at'])
        %}

        {% set purchased =
            parse_dt(machine['purchased_at'])
        %}

        {% set current =
            now_dt()
        %}

        {% set total_days =
            machine['days']
        %}

        {% if current >= expiry %}

            {% set current_day =
                total_days
            %}

            {% set completed = true %}

        {% else %}

            {% set seconds =
                (current - purchased).total_seconds()
            %}

            {% set current_day =
                [1, (seconds // 86400)|int + 1]|max
            %}

            {% if current_day > total_days %}
                {% set current_day =
                    total_days
                %}
            {% endif %}

            {% set completed = false %}

        {% endif %}


        <article class="card machine">

            <img
                src="{{ url_for(
                    'machine_image',
                    filename=machine['image']
                ) }}"
                alt="{{ machine['name'] }}"
            >

            <span class="badge">
                {{ machine['code'] }}
            </span>

            <h2>
                {{ machine['name'] }}
            </h2>

            <p>
                Purchased:
                <b>
                    {{ money(
                        machine['purchase_amount']
                    ) }}
                </b>
            </p>

            <p>
                Total payout:
                <b>
                    {{ money(
                        machine['payout_amount']
                    ) }}
                </b>
            </p>

            <p>
                Countdown:
                <b>
                    {{ current_day }}/{{ total_days }}
                    days
                </b>
            </p>

            <p>
                Expires:
                {{ expiry.strftime(
                    '%Y-%m-%d %H:%M'
                ) }}
            </p>


            {% if completed
                and not machine['received'] %}

                <form
                    method="post"
                    action="{{ url_for(
                        'receive_machine',
                        machine_id=machine['id']
                    ) }}"
                >

                    <button class="btn">
                        Receive Money
                    </button>

                </form>

            {% elif machine['received'] %}

                <span class="badge">
                    Money Received
                </span>

            {% else %}

                <button
                    class="btn secondary"
                    disabled
                >
                    Not Mature Yet
                </button>

            {% endif %}

        </article>

    {% else %}

        <div class="card">

            <h2>
                No machines yet
            </h2>

            <p>
                You have not purchased a machine.
            </p>

            <a
                class="btn"
                href="{{ url_for('shop') }}"
            >
                Open Shop
            </a>

        </div>

    {% endfor %}

    </div>
    """

    return render_page(
        "My Machines",
        render_template_string(
            body,
            machines=machines,
            money=money,
            parse_dt=parse_dt,
            now_dt=lambda:
                datetime.now(
                    timezone.utc
                ),
        ),
    )


# ============================================================
# RECEIVE MACHINE PAYOUT
# ============================================================

@app.route(
    "/receive/<int:machine_id>",
    methods=["POST"]
)
@login_required
def receive_machine(machine_id):

    user = current_user()

    connection = db()

    machine = connection.execute(
        """
        SELECT
            um.*,
            m.payout_amount

        FROM user_machines um

        JOIN machines m
        ON m.id = um.machine_id

        WHERE um.id = ?
        AND um.user_id = ?
        """,
        (
            machine_id,
            user["id"],
        ),
    ).fetchone()

    if not machine:

        connection.close()

        flash(
            "Machine not found.",
            "error",
        )

        return redirect(
            url_for("my_machines")
        )

    if machine["received"]:

        connection.close()

        flash(
            "Machine payout was already received.",
            "warning",
        )

        return redirect(
            url_for("my_machines")
        )

    if (
        datetime.now(timezone.utc)
        < parse_dt(
            machine["expires_at"]
        )
    ):

        connection.close()

        flash(
            "Machine has not completed its duration yet.",
            "error",
        )

        return redirect(
            url_for("my_machines")
        )

    connection.execute(
        """
        UPDATE users
        SET balance =
            balance + ?
        WHERE id = ?
        """,
        (
            machine["payout_amount"],
            user["id"],
        ),
    )

    connection.execute(
        """
        UPDATE user_machines
        SET received = 1
        WHERE id = ?
        """,
        (
            machine_id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        (
            f"{money(machine['payout_amount'])} "
            "was added to your balance."
        ),
        "success",
    )

    return redirect(
        url_for("my_machines")
    )


# ============================================================
# REWARDS
# ============================================================

@app.route("/rewards")
@login_required
def rewards():

    user = current_user()

    connection = db()

    invited = connection.execute(
        """
        SELECT
            name,
            phone,
            created_at
        FROM users
        WHERE referred_by = ?
        ORDER BY id DESC
        """,
        (
            user["referral_code"],
        ),
    ).fetchall()

    connection.close()

    referral_link = url_for(
        "register",
        ref=user["referral_code"],
        _external=True,
    )

    body = """
    <h1>
        Rewards
    </h1>

    <div class="grid2">

        <div class="card">

            <h2>
                Your Referral Link
            </h2>

            <input
                readonly
                value="{{ referral_link }}"
            >

            <p>
                When someone registers through
                your link and later buys a machine,
                you receive
                <b>
                    {{ money(referral_reward) }}
                </b>.
            </p>

            <p>
                Your referral code:
                <b>
                    {{ user['referral_code'] }}
                </b>
            </p>

        </div>


        <div class="card">

            <h2>
                Invited Users
            </h2>

            {% for invited_user in invited %}

            <div class="notice">

                <b>
                    {{ invited_user['name'] }}
                </b>

                <br>

                {{ invited_user['phone'] }}

                <br>

                <span class="muted">
                    {{ invited_user['created_at'] }}
                </span>

            </div>

            {% else %}

            <p class="muted">
                No invited users yet.
            </p>

            {% endfor %}

        </div>

    </div>
    """

    return render_page(
        "Rewards",
        render_template_string(
            body,
            user=user,
            referral_link=referral_link,
            referral_reward=REFERRAL_REWARD,
            money=money,
            invited=invited,
        ),
    )


# ============================================================
# DEPOSIT
# ============================================================

@app.route(
    "/deposit",
    methods=["GET", "POST"]
)
@login_required
def deposit():

    user = current_user()

    connection = db()

    deposit_numbers = connection.execute(
        """
        SELECT *
        FROM deposit_numbers
        WHERE active = 1
        ORDER BY id
        """
    ).fetchall()

    if request.method == "POST":

        try:
            amount = int(
                request.form.get(
                    "amount",
                    0,
                )
            )
        except ValueError:
            amount = 0

        number = request.form.get(
            "number",
            "",
        ).strip()

        reference = request.form.get(
            "reference",
            "",
        ).strip()

        valid_number = connection.execute(
            """
            SELECT number
            FROM deposit_numbers
            WHERE number = ?
            AND active = 1
            """,
            (
                number,
            ),
        ).fetchone()

        if (
            amount <= 0
            or not valid_number
            or not reference
        ):

            connection.close()

            flash(
                "Enter a valid amount, deposit number and transaction reference.",
                "error",
            )

            return redirect(
                url_for("deposit")
            )

        connection.execute(
            """
            INSERT INTO deposits (
                user_id,
                amount,
                account_number,
                reference,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                user["id"],
                amount,
                number,
                reference,
                now(),
            ),
        )

        connection.commit()
        connection.close()

        flash(
            "Deposit request submitted. Balance changes only after admin approval.",
            "success",
        )

        return redirect(
            url_for("dashboard")
        )

    connection.close()

    body = """
    <h1>
        Deposit
    </h1>

    <div class="card">

        <h2>
            Send Money Manually
        </h2>

        {% for number in deposit_numbers %}

        <div class="notice">

            <b>
                {{ number['number'] }}
            </b>

            <br>

            {{ number['owner_name'] }}

        </div>

        {% else %}

        <p class="muted">
            No active deposit number.
        </p>

        {% endfor %}


        <form method="post">

            <label>
                Deposit Account
            </label>

            <select
                name="number"
                required
            >

                {% for number in deposit_numbers %}

                <option
                    value="{{ number['number'] }}"
                >
                    {{ number['number'] }}
                    —
                    {{ number['owner_name'] }}
                </option>

                {% endfor %}

            </select>


            <label>
                Amount (UGX)
            </label>

            <input
                name="amount"
                type="number"
                min="1"
                required
            >


            <label>
                Transaction ID / Reference
            </label>

            <input
                name="reference"
                required
            >


            <button class="btn">
                Submit Deposit
            </button>

        </form>


        <p class="muted">
            Your balance will not change until
            an administrator approves the deposit.
        </p>

    </div>
    """

    return render_page(
        "Deposit",
        render_template_string(
            body,
            deposit_numbers=deposit_numbers,
        ),
    )


# ============================================================
# WITHDRAW
# ============================================================

@app.route(
    "/withdraw",
    methods=["GET", "POST"]
)
@login_required
def withdraw():

    user = current_user()

    connection = db()

    if request.method == "POST":

        try:
            amount = int(
                request.form.get(
                    "amount",
                    0,
                )
            )
        except ValueError:
            amount = 0

        phone = normalize_phone(
            request.form.get(
                "phone"
            )
        )

        if (
            amount <= 0
            or amount > user["balance"]
            or len(phone) < 9
        ):

            connection.close()

            flash(
                "Invalid amount, phone number, or insufficient balance.",
                "error",
            )

            return redirect(
                url_for("withdraw")
            )

        tax = round(
            amount
            * WITHDRAW_TAX_RATE
        )

        net_amount = (
            amount - tax
        )

        connection.execute(
            """
            INSERT INTO withdrawals (
                user_id,
                amount,
                tax,
                net_amount,
                phone,
                status,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, 'pending', ?
            )
            """,
            (
                user["id"],
                amount,
                tax,
                net_amount,
                phone,
                now(),
            ),
        )

        connection.commit()
        connection.close()

        flash(
            "Withdrawal request submitted. Balance remains unchanged until admin approval.",
            "success",
        )

        return redirect(
            url_for("withdraw")
        )

    connection.close()

    body = """
    <h1>
        Withdraw
    </h1>

    <div class="card">

        <p>
            Available balance:
            <b>
                {{ money(user['balance']) }}
            </b>
        </p>


        <form method="post">

            <label>
                Amount to Withdraw
            </label>

            <input
                id="withdraw_amount"
                name="amount"
                type="number"
                min="1"
                max="{{ user['balance'] }}"
                required
            >


            <div
                id="tax_box"
                class="notice"
                style="display:none"
            >

                <div>
                    Tax (7%):
                    <b id="tax_value">
                        0 UGX
                    </b>
                </div>

                <div>
                    Amount remaining
                    for withdrawal:
                    <b id="net_value">
                        0 UGX
                    </b>
                </div>

            </div>


            <label>
                Mobile Money /
                Receiving Phone Number
            </label>

            <input
                name="phone"
                inputmode="tel"
                required
            >


            <button class="btn">
                Request Withdrawal
            </button>

        </form>


        <p class="muted">

            The 7% tax is displayed only
            on the withdrawal page after
            you enter an amount.

            Admin approval is required.

        </p>

    </div>


    <script>

    const amountInput =
        document.getElementById(
            "withdraw_amount"
        );

    const taxBox =
        document.getElementById(
            "tax_box"
        );

    const taxValue =
        document.getElementById(
            "tax_value"
        );

    const netValue =
        document.getElementById(
            "net_value"
        );


    function calculateWithdraw()
    {

        const value =
            Number(
                amountInput.value || 0
            );

        if (value <= 0)
        {

            taxBox.style.display =
                "none";

            return;

        }

        const tax =
            Math.round(
                value * 0.07
            );

        const net =
            value - tax;

        taxBox.style.display =
            "block";

        taxValue.textContent =
            tax.toLocaleString()
            + " UGX";

        netValue.textContent =
            net.toLocaleString()
            + " UGX";

    }


    amountInput.addEventListener(
        "input",
        calculateWithdraw
    );

    </script>
    """

    return render_page(
        "Withdraw",
        render_template_string(
            body,
            user=user,
            money=money,
        ),
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    connection = db()

    rows = connection.execute(
        """
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    connection.close()

    if not rows:

        body = """
        <h1>
            Notifications 🔔
        </h1>

        <div class="card">
            No notifications yet.
        </div>
        """

    else:

        body = """
        <h1>
            Notifications 🔔
        </h1>
        """

        for row in rows:

            body += f"""
            <div class="notice">

                <b>
                    {row['title']}
                </b>

                <br>

                {row['message']}

                <div class="small muted">
                    {row['created_at']}
                </div>

            </div>
            """

    return render_page(
        "Notifications",
        body,
    )


# ============================================================
# USER CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["GET", "POST"]
)
@login_required
def chat():

    user = current_user()

    connection = db()

    if request.method == "POST":

        message = request.form.get(
            "message",
            "",
        ).strip()

        if message:

            connection.execute(
                """
                INSERT INTO chats (
                    user_id,
                    message,
                    from_admin,
                    created_at
                )
                VALUES (?, ?, 0, ?)
                """,
                (
                    user["id"],
                    message,
                    now(),
                ),
            )

            connection.commit()

    messages = connection.execute(
        """
        SELECT *
        FROM chats
        WHERE user_id = ?
        ORDER BY id
        """,
        (
            user["id"],
        ),
    ).fetchall()

    connection.close()

    body = """
    <h1>
        Chat with Admin 💬
    </h1>

    <div class="card">

        {% for message in messages %}

        <div class="notice">

            <b>
                {% if message['from_admin'] %}
                    Admin
                {% else %}
                    You
                {% endif %}
            </b>

            <br>

            {{ message['message'] }}

            <div class="small muted">
                {{ message['created_at'] }}
            </div>

        </div>

        {% else %}

        <p class="muted">
            No messages yet.
        </p>

        {% endfor %}


        <form method="post">

            <textarea
                name="message"
                placeholder="Write a message..."
                required
            ></textarea>

            <button class="btn">
                Send
            </button>

        </form>

    </div>
    """

    return render_page(
        "Chat",
        render_template_string(
            body,
            messages=messages,
        ),
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@admin_required
def admin():

    connection = db()

    joined = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE is_admin = 0
        """
    ).fetchone()["total"]

    approved_deposits = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total

        FROM deposits

        WHERE status = 'approved'
        """
    ).fetchone()["total"]

    approved_withdrawals = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(net_amount),
                0
            ) AS total

        FROM withdrawals

        WHERE status = 'approved'
        """
    ).fetchone()["total"]

    pending_deposits = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM deposits
        WHERE status = 'pending'
        """
    ).fetchone()["total"]

    pending_withdrawals = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM withdrawals
        WHERE status = 'pending'
        """
    ).fetchone()["total"]

    pending_deposit_rows = connection.execute(
        """
        SELECT
            d.*,
            u.name,
            u.phone

        FROM deposits d

        JOIN users u
        ON u.id = d.user_id

        WHERE d.status = 'pending'

        ORDER BY d.id DESC
        """
    ).fetchall()

    pending_withdrawal_rows = connection.execute(
        """
        SELECT
            w.*,
            u.name

        FROM withdrawals w

        JOIN users u
        ON u.id = w.user_id

        WHERE w.status = 'pending'

        ORDER BY w.id DESC
        """
    ).fetchall()

    deposit_numbers = connection.execute(
        """
        SELECT *
        FROM deposit_numbers
        ORDER BY id
        """
    ).fetchall()

    machines = connection.execute(
        """
        SELECT *
        FROM machines
        ORDER BY id
        """
    ).fetchall()

    admins = connection.execute(
        """
        SELECT
            id,
            name,
            phone,
            created_at

        FROM users

        WHERE is_admin = 1

        ORDER BY id
        """
    ).fetchall()

    chats = connection.execute(
        """
        SELECT
            c.*,
            u.name,
            u.phone

        FROM chats c

        JOIN users u
        ON u.id = c.user_id

        WHERE c.from_admin = 0

        ORDER BY c.id DESC

        LIMIT 50
        """
    ).fetchall()

    connection.close()

    # Simple admin-only flow indicators.

    denominator = max(
        1,
        joined,
    )

    deposit_rate = min(
        100,
        round(
            approved_deposits
            / (
                denominator
                * 100000
            )
            * 100,
            1,
        ),
    )

    withdrawal_rate = min(
        100,
        round(
            approved_withdrawals
            / (
                denominator
                * 100000
            )
            * 100,
            1,
        ),
    )

    growth_rate = min(
        100,
        round(
            joined
            / 100
            * 100,
            1,
        ),
    )

    body = """
    <h1>
        Admin Panel
    </h1>


    <div class="admin-grid">

        <div class="card">

            <div class="muted">
                People Joined
            </div>

            <div class="kpi">
                {{ joined }}
            </div>

        </div>


        <div class="card">

            <div class="muted">
                Approved Deposits
            </div>

            <div class="kpi">
                {{ money(approved_deposits) }}
            </div>

        </div>


        <div class="card">

            <div class="muted">
                Approved Withdrawals
            </div>

            <div class="kpi">
                {{ money(approved_withdrawals) }}
            </div>

        </div>


        <div class="card">

            <div class="muted">
                Pending Actions
            </div>

            <div class="kpi">
                {{
                    pending_deposits
                    + pending_withdrawals
                }}
            </div>

        </div>

    </div>


    <!-- ADMIN-ONLY CHART -->

    <div
        class="grid2"
        style="margin-top:16px"
    >

        <div class="card">

            <h2>
                Company Flow Chart
            </h2>

            <p>
                People Joined:
                <b>
                    {{ joined }}
                </b>
            </p>

            <div class="bar">
                <div
                    class="fill"
                    style="
                        width:{{ growth_rate }}%;
                    "
                ></div>
            </div>


            <p>
                Deposit Flow:
                <b>
                    {{ money(approved_deposits) }}
                </b>
            </p>

            <div class="bar">
                <div
                    class="fill"
                    style="
                        width:{{ deposit_rate }}%;
                    "
                ></div>
            </div>


            <p>
                Withdraw Flow:
                <b>
                    {{ money(approved_withdrawals) }}
                </b>
            </p>

            <div class="bar">
                <div
                    class="fill"
                    style="
                        width:{{ withdrawal_rate }}%;
                    "
                ></div>
            </div>

        </div>


        <!-- NOTIFICATION -->

        <div class="card">

            <h2>
                Add Notification
            </h2>

            <form
                method="post"
                action="{{ url_for(
                    'admin_notification'
                ) }}"
            >

                <input
                    name="title"
                    placeholder="Notification title"
                    required
                >

                <textarea
                    name="message"
                    placeholder="Update for users"
                    required
                ></textarea>

                <button class="btn">
                    Publish Notification
                </button>

            </form>

        </div>

    </div>


    <!-- DEPOSITS -->

    <div
        class="card"
        style="margin-top:16px"
    >

        <h2>
            Pending Deposits
        </h2>

        <div style="overflow-x:auto">

        <table class="table">

            <tr>

                <th>
                    User
                </th>

                <th>
                    Amount
                </th>

                <th>
                    Reference
                </th>

                <th>
                    Action
                </th>

            </tr>


            {% for deposit in pending_deposit_rows %}

            <tr>

                <td>

                    {{ deposit['name'] }}

                    <br>

                    {{ deposit['phone'] }}

                </td>


                <td>
                    {{ money(
                        deposit['amount']
                    ) }}
                </td>


                <td>
                    {{ deposit['reference'] }}
                </td>


                <td>

                    <form
                        method="post"
                        action="{{ url_for(
                            'approve_deposit',
                            deposit_id=deposit['id']
                        ) }}"
                    >

                        <button class="btn">
                            Approve
                        </button>

                    </form>


                    <form
                        method="post"
                        action="{{ url_for(
                            'reject_deposit',
                            deposit_id=deposit['id']
                        ) }}"
                        style="margin-top:5px"
                    >

                        <button
                            class="btn danger"
                        >
                            Reject
                        </button>

                    </form>

                </td>

            </tr>

            {% else %}

            <tr>

                <td colspan="4">
                    No pending deposits.
                </td>

            </tr>

            {% endfor %}

        </table>

        </div>

    </div>


    <!-- WITHDRAWALS -->

    <div
        class="card"
        style="margin-top:16px"
    >

        <h2>
            Pending Withdrawals
        </h2>

        <div style="overflow-x:auto">

        <table class="table">

            <tr>

                <th>
                    User
                </th>

                <th>
                    Requested
                </th>

                <th>
                    Tax
                </th>

                <th>
                    Net Amount
                </th>

                <th>
                    Phone
                </th>

                <th>
                    Action
                </th>

            </tr>


            {% for withdrawal
                in pending_withdrawal_rows %}

            <tr>

                <td>
                    {{ withdrawal['name'] }}
                </td>

                <td>
                    {{ money(
                        withdrawal['amount']
                    ) }}
                </td>

                <td>
                    {{ money(
                        withdrawal['tax']
                    ) }}
                </td>

                <td>
                    {{ money(
                        withdrawal['net_amount']
                    ) }}
                </td>

                <td>
                    {{ withdrawal['phone'] }}
                </td>

                <td>

                    <form
                        method="post"
                        action="{{ url_for(
                            'approve_withdrawal',
                            withdrawal_id=withdrawal['id']
                        ) }}"
                    >

                        <button class="btn">
                            Approve
                        </button>

                    </form>


                    <form
                        method="post"
                        action="{{ url_for(
                            'reject_withdrawal',
                            withdrawal_id=withdrawal['id']
                        ) }}"
                        style="margin-top:5px"
                    >

                        <button
                            class="btn danger"
                        >
                            Reject
                        </button>

                    </form>

                </td>

            </tr>

            {% else %}

            <tr>

                <td colspan="6">
                    No pending withdrawals.
                </td>

            </tr>

            {% endfor %}

        </table>

        </div>

    </div>


    <!-- DEPOSIT NUMBERS -->

    <div
        class="grid2"
        style="margin-top:16px"
    >

        <div class="card">

            <h2>
                Deposit Numbers
            </h2>

            <form
                method="post"
                action="{{ url_for(
                    'admin_add_deposit_number'
                ) }}"
            >

                <input
                    name="number"
                    placeholder="Deposit number"
                    required
                >

                <input
                    name="owner_name"
                    placeholder="Account owner"
                    required
                >

                <button class="btn">
                    Add Deposit Number
                </button>

            </form>


            {% for number in deposit_numbers %}

            <div class="notice">

                <b>
                    {{ number['number'] }}
                </b>

                —
                {{ number['owner_name'] }}

                <form
                    method="post"
                    action="{{ url_for(
                        'admin_remove_deposit_number',
                        number_id=number['id']
                    ) }}"
                    style="margin-top:6px"
                >

                    <button
                        class="btn danger"
                    >
                        Remove
                    </button>

                </form>

            </div>

            {% endfor %}

        </div>


        <!-- MACHINES -->

        <div class="card">

            <h2>
                Machine Management
            </h2>

            <form
                method="post"
                action="{{ url_for(
                    'admin_add_machine'
                ) }}"
            >

                <input
                    name="code"
                    placeholder="Code e.g. M12"
                    required
                >

                <input
                    name="name"
                    placeholder="Machine name"
                    required
                >

                <input
                    name="purchase_amount"
                    type="number"
                    placeholder="Purchase amount"
                    required
                >

                <input
                    name="payout_amount"
                    type="number"
                    placeholder="Total payout"
                    required
                >

                <input
                    name="days"
                    type="number"
                    min="1"
                    placeholder="Days"
                    required
                >

                <input
                    name="buyer_reward"
                    type="number"
                    min="0"
                    placeholder="Buyer reward"
                    required
                >

                <input
                    name="image"
                    placeholder="Image e.g. m11.jpg"
                    value="m1.jpg"
                >

                <button class="btn">
                    Add Machine
                </button>

            </form>


            {% for machine in machines %}

            <div class="notice">

                <b>
                    {{ machine['code'] }}
                </b>

                —
                {{ machine['name'] }}

                <br>

                {{ money(
                    machine['purchase_amount']
                ) }}

                /

                {{ machine['days'] }}
                days


                <form
                    method="post"
                    action="{{ url_for(
                        'admin_toggle_machine',
                        machine_id=machine['id']
                    ) }}"
                    style="margin-top:6px"
                >

                    <button
                        class="btn secondary"
                    >

                        {% if machine['active'] %}
                            Remove from Shop
                        {% else %}
                            Put in Shop
                        {% endif %}

                    </button>

                </form>

            </div>

            {% endfor %}

        </div>

    </div>


    <!-- ADMIN MANAGEMENT -->

    <div
        class="grid2"
        style="margin-top:16px"
    >

        <div class="card">

            <h2>
                Manage Administrators
            </h2>

            <form
                method="post"
                action="{{ url_for(
                    'admin_add_admin'
                ) }}"
            >

                <input
                    name="name"
                    placeholder="Admin name"
                >

                <input
                    name="phone"
                    placeholder="Admin phone"
                    required
                >

                <input
                    name="password"
                    type="password"
                    placeholder="Admin password"
                    required
                >

                <button class="btn">
                    Add / Update Admin
                </button>

            </form>


            {% for administrator in admins %}

            <div class="notice">

                <b>
                    {{ administrator['name'] }}
                </b>

                <br>

                {{ administrator['phone'] }}


                {% if administrator['phone']
                    != primary_admin_phone %}

                <form
                    method="post"
                    action="{{ url_for(
                        'admin_remove_admin',
                        user_id=administrator['id']
                    ) }}"
                    style="margin-top:6px"
                >

                    <button
                        class="btn danger"
                    >
                        Remove Admin
                    </button>

                </form>

                {% else %}

                <div class="small muted">
                    Primary administrator
                </div>

                {% endif %}

            </div>

            {% endfor %}

        </div>


        <div class="card">

            <h2>
                Transaction Summary
            </h2>

            <p>
                Approved deposits:
                <b>
                    {{ money(
                        approved_deposits
                    ) }}
                </b>
            </p>

            <p>
                Approved withdrawals:
                <b>
                    {{ money(
                        approved_withdrawals
                    ) }}
                </b>
            </p>

            <p>
                Pending deposits:
                <b>
                    {{ pending_deposits }}
                </b>
            </p>

            <p>
                Pending withdrawals:
                <b>
                    {{ pending_withdrawals }}
                </b>
            </p>

            <p>
                Registered users:
                <b>
                    {{ joined }}
                </b>
            </p>

        </div>

    </div>


    <!-- CHAT -->

    <div
        class="card"
        style="margin-top:16px"
    >

        <h2>
            User Chat
        </h2>

        {% for chat_message in chats %}

        <div class="notice">

            <b>
                {{ chat_message['name'] }}
                ({{ chat_message['phone'] }})
            </b>

            <br>

            {{ chat_message['message'] }}


            <form
                method="post"
                action="{{ url_for(
                    'admin_reply',
                    user_id=chat_message['user_id']
                ) }}"
            >

                <input
                    name="message"
                    placeholder="Reply"
                    required
                >

                <button class="btn">
                    Reply
                </button>

            </form>

        </div>

        {% else %}

        <p class="muted">
            No user messages.
        </p>

        {% endfor %}

    </div>
    """

    return render_page(
        "Admin",
        render_template_string(
            body,
            joined=joined,
            approved_deposits=approved_deposits,
            approved_withdrawals=approved_withdrawals,
            pending_deposits=pending_deposits,
            pending_withdrawals=pending_withdrawals,
            deposit_numbers=deposit_numbers,
            machines=machines,
            admins=admins,
            chats=chats,
            deposit_rate=deposit_rate,
            withdrawal_rate=withdrawal_rate,
            growth_rate=growth_rate,
            pending_deposit_rows=pending_deposit_rows,
            pending_withdrawal_rows=pending_withdrawal_rows,
            primary_admin_phone=ADMIN_PHONE,
            money=money,
        ),
    )


# ============================================================
# APPROVE DEPOSIT
# ============================================================

@app.route(
    "/admin/deposit/<int:deposit_id>/approve",
    methods=["POST"]
)
@admin_required
def approve_deposit(deposit_id):

    connection = db()

    deposit = connection.execute(
        """
        SELECT *
        FROM deposits
        WHERE id = ?
        AND status = 'pending'
        """,
        (
            deposit_id,
        ),
    ).fetchone()

    if deposit:

        connection.execute(
            """
            UPDATE deposits

            SET
                status = 'approved',
                approved_at = ?

            WHERE id = ?
            """,
            (
                now(),
                deposit_id,
            ),
        )

        connection.execute(
            """
            UPDATE users

            SET
                balance =
                    balance + ?,

                total_deposited =
                    total_deposited + ?

            WHERE id = ?
            """,
            (
                deposit["amount"],
                deposit["amount"],
                deposit["user_id"],
            ),
        )

        connection.commit()

        flash(
            "Deposit approved and balance updated.",
            "success",
        )

    connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# REJECT DEPOSIT
# ============================================================

@app.route(
    "/admin/deposit/<int:deposit_id>/reject",
    methods=["POST"]
)
@admin_required
def reject_deposit(deposit_id):

    connection = db()

    connection.execute(
        """
        UPDATE deposits

        SET
            status = 'rejected',
            approved_at = ?

        WHERE id = ?
        AND status = 'pending'
        """,
        (
            now(),
            deposit_id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        "Deposit rejected.",
        "warning",
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# APPROVE WITHDRAWAL
# ============================================================

@app.route(
    "/admin/withdraw/<int:withdrawal_id>/approve",
    methods=["POST"]
)
@admin_required
def approve_withdrawal(
    withdrawal_id
):

    connection = db()

    withdrawal = connection.execute(
        """
        SELECT *
        FROM withdrawals
        WHERE id = ?
        AND status = 'pending'
        """,
        (
            withdrawal_id,
        ),
    ).fetchone()

    if not withdrawal:

        connection.close()

        flash(
            "Withdrawal not found or already processed.",
            "error",
        )

        return redirect(
            url_for("admin")
        )

    user = connection.execute(
        """
        SELECT balance
        FROM users
        WHERE id = ?
        """,
        (
            withdrawal["user_id"],
        ),
    ).fetchone()

    if (
        not user
        or user["balance"]
        < withdrawal["amount"]
    ):

        connection.close()

        flash(
            "Cannot approve: user's current balance is insufficient.",
            "error",
        )

        return redirect(
            url_for("admin")
        )

    connection.execute(
        """
        UPDATE users

        SET
            balance =
                balance - ?,

            total_withdrawn =
                total_withdrawn + ?

        WHERE id = ?
        """,
        (
            withdrawal["amount"],
            withdrawal["net_amount"],
            withdrawal["user_id"],
        ),
    )

    connection.execute(
        """
        UPDATE withdrawals

        SET
            status = 'approved',
            approved_at = ?

        WHERE id = ?
        """,
        (
            now(),
            withdrawal_id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        "Withdrawal approved.",
        "success",
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# REJECT WITHDRAWAL
# ============================================================

@app.route(
    "/admin/withdraw/<int:withdrawal_id>/reject",
    methods=["POST"]
)
@admin_required
def reject_withdrawal(
    withdrawal_id
):

    connection = db()

    connection.execute(
        """
        UPDATE withdrawals

        SET
            status = 'rejected',
            approved_at = ?

        WHERE id = ?
        AND status = 'pending'
        """,
        (
            now(),
            withdrawal_id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        "Withdrawal rejected. No balance was deducted.",
        "warning",
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# ADD DEPOSIT NUMBER
# ============================================================

@app.route(
    "/admin/deposit-number/add",
    methods=["POST"]
)
@admin_required
def admin_add_deposit_number():

    number = normalize_phone(
        request.form.get(
            "number"
        )
    )

    owner = request.form.get(
        "owner_name",
        "",
    ).strip()

    connection = db()

    try:

        connection.execute(
            """
            INSERT INTO deposit_numbers (
                number,
                owner_name,
                active,
                created_at
            )
            VALUES (?, ?, 1, ?)
            """,
            (
                number,
                owner,
                now(),
            ),
        )

        connection.commit()

        flash(
            "Deposit number added.",
            "success",
        )

    except sqlite3.IntegrityError:

        flash(
            "That deposit number already exists.",
            "error",
        )

    finally:

        connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# REMOVE DEPOSIT NUMBER
# ============================================================

@app.route(
    "/admin/deposit-number/<int:number_id>/remove",
    methods=["POST"]
)
@admin_required
def admin_remove_deposit_number(
    number_id
):

    connection = db()

    connection.execute(
        """
        UPDATE deposit_numbers

        SET active = 0

        WHERE id = ?
        """,
        (
            number_id,
        ),
    )

    connection.commit()
    connection.close()

    flash(
        "Deposit number removed from the active list.",
        "success",
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# ADD MACHINE
# ============================================================

@app.route(
    "/admin/machine/add",
    methods=["POST"]
)
@admin_required
def admin_add_machine():

    connection = None

    try:

        code = (
            request.form.get(
                "code",
                "",
            )
            .strip()
            .upper()
        )

        name = request.form.get(
            "name",
            "",
        ).strip()

        purchase_amount = int(
            request.form.get(
                "purchase_amount",
                0,
            )
        )

        payout_amount = int(
            request.form.get(
                "payout_amount",
                0,
            )
        )

        days = int(
            request.form.get(
                "days",
                0,
            )
        )

        reward = int(
            request.form.get(
                "buyer_reward",
                0,
            )
        )

        image = Path(
            request.form.get(
                "image",
                "m1.jpg",
            )
        ).name

        if (
            not code
            or not name
            or purchase_amount <= 0
            or payout_amount <= 0
            or days <= 0
            or reward < 0
        ):

            raise ValueError

        connection = db()

        connection.execute(
            """
            INSERT INTO machines (
                code,
                name,
                purchase_amount,
                payout_amount,
                days,
                buyer_reward,
                image,
                active,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, 1, ?
            )
            """,
            (
                code,
                name,
                purchase_amount,
                payout_amount,
                days,
                reward,
                image,
                now(),
            ),
        )

        connection.commit()

        flash(
            "Machine added to shop.",
            "success",
        )

    except (
        ValueError,
        sqlite3.IntegrityError,
    ):

        flash(
            "Machine could not be added. Check the values and make sure the machine code is unique.",
            "error",
        )

    finally:

        if connection is not None:
            connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# ENABLE / DISABLE MACHINE
# ============================================================

@app.route(
    "/admin/machine/<int:machine_id>/toggle",
    methods=["POST"]
)
@admin_required
def admin_toggle_machine(
    machine_id
):

    connection = db()

    connection.execute(
        """
        UPDATE machines

        SET active =
            CASE active
                WHEN 1 THEN 0
                ELSE 1
            END

        WHERE id = ?
        """,
        (
            machine_id,
        ),
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# ADD NOTIFICATION
# ============================================================

@app.route(
    "/admin/notification",
    methods=["POST"]
)
@admin_required
def admin_notification():

    title = request.form.get(
        "title",
        "",
    ).strip()

    message = request.form.get(
        "message",
        "",
    ).strip()

    connection = db()

    if title and message:

        connection.execute(
            """
            INSERT INTO notifications (
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                title,
                message,
                now(),
            ),
        )

        connection.commit()

        flash(
            "Notification published.",
            "success",
        )

    connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# ADMIN REPLY
# ============================================================

@app.route(
    "/admin/reply/<int:user_id>",
    methods=["POST"]
)
@admin_required
def admin_reply(user_id):

    message = request.form.get(
        "message",
        "",
    ).strip()

    connection = db()

    if message:

        connection.execute(
            """
            INSERT INTO chats (
                user_id,
                message,
                from_admin,
                created_at
            )
            VALUES (?, ?, 1, ?)
            """,
            (
                user_id,
                message,
                now(),
            ),
        )

        connection.commit()

        flash(
            "Reply sent.",
            "success",
        )

    connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# ADD / UPDATE ADMIN
# ============================================================

@app.route(
    "/admin/add-admin",
    methods=["POST"]
)
@admin_required
def admin_add_admin():

    phone = normalize_phone(
        request.form.get(
            "phone"
        )
    )

    password = request.form.get(
        "password",
        "",
    )

    name = (
        request.form.get(
            "name",
            "",
        ).strip()
        or "Administrator"
    )

    if (
        len(phone) < 9
        or len(password) < 6
    ):

        flash(
            "Enter a valid admin phone number and password of at least 6 characters.",
            "error",
        )

        return redirect(
            url_for("admin")
        )

    connection = db()

    try:

        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE phone = ?
            """,
            (
                phone,
            ),
        ).fetchone()

        if existing:

            connection.execute(
                """
                UPDATE users

                SET
                    is_admin = 1,
                    name = ?,
                    password_hash = ?

                WHERE phone = ?
                """,
                (
                    name,
                    generate_password_hash(
                        password
                    ),
                    phone,
                ),
            )

        else:

            referral_code = make_referral_code()

            while connection.execute(
                """
                SELECT id
                FROM users
                WHERE referral_code = ?
                """,
                (
                    referral_code,
                ),
            ).fetchone():

                referral_code = make_referral_code()

            connection.execute(
                """
                INSERT INTO users (
                    phone,
                    name,
                    password_hash,
                    referral_code,
                    referred_by,
                    referral_reward_paid,
                    created_at,
                    is_admin
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 1
                )
                """,
                (
                    phone,
                    name,
                    generate_password_hash(
                        password
                    ),
                    referral_code,
                    None,
                    0,
                    now(),
                ),
            )

        connection.commit()

        flash(
            "Administrator added or updated.",
            "success",
        )

    except sqlite3.IntegrityError:

        flash(
            "Could not add administrator.",
            "error",
        )

    finally:

        connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# REMOVE ADMIN
# ============================================================

@app.route(
    "/admin/remove-admin/<int:user_id>",
    methods=["POST"]
)
@admin_required
def admin_remove_admin(
    user_id
):

    connection = db()

    target = connection.execute(
        """
        SELECT phone
        FROM users
        WHERE id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    if (
        target
        and target["phone"]
        != ADMIN_PHONE
    ):

        connection.execute(
            """
            UPDATE users

            SET is_admin = 0

            WHERE id = ?
            """,
            (
                user_id,
            ),
        )

        connection.commit()

        flash(
            "Administrator access removed.",
            "success",
        )

    else:

        flash(
            "The primary administrator cannot be removed here.",
            "warning",
        )

    connection.close()

    return redirect(
        url_for("admin")
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "service": COMPANY_NAME,
    }


# ============================================================
# 404
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return (
        render_page(
            "Not Found",
            """
            <div class="card">

                <h1>
                    Page Not Found
                </h1>

                <p>
                    The page you requested
                    does not exist.
                </p>

                <a
                    class="btn"
                    href="/dashboard"
                >
                    Dashboard
                </a>

            </div>
            """,
        ),
        404,
    )


# ============================================================
# 500
# ============================================================

@app.errorhandler(500)
def server_error(error):

    return (
        render_page(
            "Server Error",
            """
            <div class="card">

                <h1>
                    Server Error
                </h1>

                <p>
                    An application error occurred.
                    Check the server logs for details.
                </p>

                <a
                    class="btn"
                    href="/dashboard"
                >
                    Dashboard
                </a>

            </div>
            """,
        ),
        500,
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000",
        )
    )

    print("=" * 60)

    print(
        f"{COMPANY_NAME} running on "
        f"http://127.0.0.1:{port}"
    )

    print(
        f"Admin phone: {ADMIN_PHONE}"
    )

    print(
        "Admin password is configured "
        "through ADMIN_PASSWORD."
    )

    print(
        "Render start command:"
        " gunicorn app:app"
    )

    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )