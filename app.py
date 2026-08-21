import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

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
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# ============================================================
# DATA4MINE - SINGLE FILE FLASK APPLICATION
# ============================================================

app = Flask(__name__)

# ------------------------------------------------------------
# Basic configuration
# ------------------------------------------------------------

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "DATA4MINE_CHANGE_THIS_SECRET_KEY_2026"
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

STATIC_DIR = os.path.join(BASE_DIR, "static")
MACHINE_DIR = os.path.join(STATIC_DIR, "machines")
BACKGROUND_DIR = os.path.join(STATIC_DIR, "background")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(MACHINE_DIR, exist_ok=True)
os.makedirs(BACKGROUND_DIR, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Render sometimes provides postgres://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(BASE_DIR, "data4mine.db")
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

db = SQLAlchemy(app)


# ============================================================
# CONSTANTS
# ============================================================

ADMIN_PHONE = "0792759363"
ADMIN_PASSWORD = "1831"

WITHDRAW_TAX_RATE = 0.07
WITHDRAW_WAIT_HOURS = 24
REFERRAL_REWARD = 5000

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif"
}


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_aware(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt


def format_money(value):
    try:
        return f"UGX {float(value):,.0f}"
    except Exception:
        return "UGX 0"


def allowed_image(filename):
    if not filename:
        return False

    if "." not in filename:
        return False

    ext = filename.rsplit(".", 1)[1].lower()

    return ext in ALLOWED_IMAGE_EXTENSIONS


# ============================================================
# DATABASE MODELS
# ============================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    phone = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    balance = db.Column(db.Float, default=0.0, nullable=False)

    referral_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    referred_by = db.Column(db.Integer, nullable=True)

    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)

    description = db.Column(
        db.Text,
        default=""
    )

    price = db.Column(db.Float, nullable=False)

    daily_profit = db.Column(
        db.Float,
        nullable=False,
        default=0
    )

    duration_days = db.Column(
        db.Integer,
        nullable=False,
        default=20
    )

    stock = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    image_filename = db.Column(
        db.String(255),
        nullable=True
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    @property
    def total_profit(self):
        return self.daily_profit * self.duration_days

    @property
    def total_return(self):
        return self.price + self.total_profit


class UserMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machine.id"),
        nullable=False
    )

    purchase_price = db.Column(
        db.Float,
        nullable=False
    )

    daily_profit = db.Column(
        db.Float,
        nullable=False
    )

    duration_days = db.Column(
        db.Integer,
        nullable=False
    )

    purchased_at = db.Column(
        db.DateTime,
        default=utc_now,
        nullable=False
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    received_at = db.Column(
        db.DateTime,
        nullable=True
    )

    reward_received = db.Column(
        db.Boolean,
        default=False
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "machines",
            lazy=True
        )
    )

    machine = db.relationship(
        "Machine",
        backref=db.backref(
            "purchases",
            lazy=True
        )
    )

    @property
    def finish_time(self):
        return self.purchased_at + timedelta(
            days=self.duration_days
        )

    @property
    def is_complete(self):
        return utc_now() >= self.finish_time

    @property
    def days_completed(self):
        elapsed = utc_now() - self.purchased_at

        seconds = max(
            0,
            elapsed.total_seconds()
        )

        completed = int(
            seconds // 86400
        )

        return min(
            completed,
            self.duration_days
        )

    @property
    def progress_text(self):
        return (
            str(self.days_completed)
            + "/"
            + str(self.duration_days)
            + " days"
        )

    @property
    def seconds_remaining(self):
        remaining = (
            self.finish_time - utc_now()
        ).total_seconds()

        return max(
            0,
            int(remaining)
        )

    @property
    def total_profit(self):
        return (
            self.daily_profit
            * self.duration_days
        )


class Deposit(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    deposit_number = db.Column(
        db.String(100),
        nullable=False
    )

    transaction_message = db.Column(
        db.Text,
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="pending"
    )

    admin_note = db.Column(
        db.Text,
        default=""
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    processed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "deposits",
            lazy=True
        )
    )


class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    tax = db.Column(
        db.Float,
        nullable=False
    )

    net_amount = db.Column(
        db.Float,
        nullable=False
    )

    account_name = db.Column(
        db.String(150),
        nullable=False
    )

    account_number = db.Column(
        db.String(100),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="pending"
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    processed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    admin_note = db.Column(
        db.Text,
        default=""
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "withdrawals",
            lazy=True
        )
    )

    @property
    def available_at(self):
        return self.created_at + timedelta(
            hours=WITHDRAW_WAIT_HOURS
        )

    @property
    def seconds_remaining(self):
        seconds = (
            self.available_at - utc_now()
        ).total_seconds()

        return max(
            0,
            int(seconds)
        )


class DepositNumber(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    number = db.Column(
        db.String(100),
        nullable=False
    )

    owner_name = db.Column(
        db.String(150),
        default=""
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(200),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )


class NotificationRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notification.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    read_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    __table_args__ = (
        db.UniqueConstraint(
            "notification_id",
            "user_id",
            name="unique_notification_user"
        ),
    )


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    sender = db.Column(
        db.String(20),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "chat_messages",
            lazy=True
        )
    )


class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    key = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    value = db.Column(
        db.Text,
        default=""
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():
    db.create_all()

    # --------------------------------------------------------
    # Create main administrator automatically
    # --------------------------------------------------------
    admin = User.query.filter_by(
        phone=ADMIN_PHONE
    ).first()

    if admin is None:
        admin = User(
            phone=ADMIN_PHONE,
            referral_code="ADMIN",
            is_admin=True,
            is_active=True,
            balance=0
        )

        admin.set_password(
            ADMIN_PASSWORD
        )

        db.session.add(admin)
        db.session.commit()
    else:
        # Keep requested administrator credentials usable.
        if not admin.is_admin:
            admin.is_admin = True

        admin.set_password(
            ADMIN_PASSWORD
        )

        db.session.commit()

    # --------------------------------------------------------
    # Default deposit number
    # --------------------------------------------------------
    if DepositNumber.query.count() == 0:
        default_number = DepositNumber(
            number="0792759363",
            owner_name="DATA4MINE",
            active=True
        )

        db.session.add(
            default_number
        )

    # --------------------------------------------------------
    # Default machines
    # --------------------------------------------------------
    if Machine.query.count() == 0:

        machines = [
            Machine(
                name="Diamond Miner",
                description=(
                    "Diamond mining machine with "
                    "20-day earning cycle."
                ),
                price=50000,
                daily_profit=3500,
                duration_days=20,
                stock=50,
                image_filename="diamond.jpg",
                active=True
            ),

            Machine(
                name="Gold Miner",
                description=(
                    "Gold mining machine with "
                    "20-day earning cycle."
                ),
                price=100000,
                daily_profit=7500,
                duration_days=20,
                stock=30,
                image_filename="gold.jpg",
                active=True
            ),

            Machine(
                name="Platinum Miner",
                description=(
                    "Platinum machine with "
                    "20-day earning cycle."
                ),
                price=200000,
                daily_profit=16000,
                duration_days=20,
                stock=20,
                image_filename="platinum.jpg",
                active=True
            ),

            Machine(
                name="Titanium Miner",
                description=(
                    "Titanium machine with "
                    "20-day earning cycle."
                ),
                price=500000,
                daily_profit=42000,
                duration_days=20,
                stock=10,
                image_filename="titanium.jpg",
                active=True
            )
        ]

        db.session.add_all(
            machines
        )

    # --------------------------------------------------------
    # Default notification
    # --------------------------------------------------------
    if Notification.query.count() == 0:
        notification = Notification(
            title="DATA4MINE WELCOME",
            message=(
                "Welcome to DATA4MINE. "
                "Please read the deposit, withdrawal "
                "and machine instructions carefully."
            ),
            active=True
        )

        db.session.add(
            notification
        )

    db.session.commit()


with app.app_context():
    initialize_database()


# ============================================================
# AUTHENTICATION HELPERS
# ============================================================

def current_user():
    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id
    )


def login_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):

        user = current_user()

        if user is None:
            flash(
                "Please login first.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        if not user.is_active:
            session.clear()

            flash(
                "Your account is disabled.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapped


def admin_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):

        user = current_user()

        if user is None:
            flash(
                "Admin login required.",
                "error"
            )

            return redirect(
                url_for("admin_login")
            )

        if not user.is_admin:
            flash(
                "Administrator access required.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# HTML / CSS
# ============================================================

BASE_CSS = """
:root {
    --green-dark: #032d20;
    --green: #075b3d;
    --green-mid: #08784f;
    --green-light: #10a66a;
    --green-soft: #0d3f2e;
    --black-green: #011d15;
    --white: #ffffff;
    --muted: #c6ddd5;
    --danger: #ff5c67;
    --warning: #f3bd3e;
    --success: #33d18b;
    --border: rgba(255,255,255,.13);
    --shadow: 0 12px 35px rgba(0,0,0,.30);
}

* {
    box-sizing: border-box;
}

html {
    font-size: 16px;
}

body {
    margin: 0;
    min-height: 100vh;
    color: var(--white);
    background:
        linear-gradient(
            rgba(1,29,21,.88),
            rgba(1,29,21,.94)
        ),
        url('/static/background/background.jpg')
        center / cover fixed no-repeat;
    font-family:
        Arial,
        Helvetica,
        sans-serif;
    font-size: 16px;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background:
        radial-gradient(
            circle at top right,
            rgba(16,166,106,.15),
            transparent 35%
        );
    z-index: -1;
}

a {
    color: #8ff0c5;
    text-decoration: none;
}

button,
input,
select,
textarea {
    font: inherit;
}

button {
    cursor: pointer;
}

.container {
    width: min(1180px, 94%);
    margin: auto;
}

.nav {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(1,29,21,.96);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(15px);
}

.nav-inner {
    min-height: 66px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
}

.brand {
    font-weight: 900;
    letter-spacing: 1px;
    color: #fff;
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.nav-links a {
    padding: 10px 12px;
    border-radius: 10px;
    color: #fff;
}

.nav-links a:hover {
    background: rgba(16,166,106,.18);
}

.hero {
    padding: 45px 0 25px;
}

.hero h1 {
    margin: 0 0 10px;
    font-size: clamp(28px, 6vw, 52px);
    color: #fff;
}

.hero p {
    color: var(--muted);
    max-width: 700px;
    line-height: 1.7;
}

.card {
    background: rgba(3,45,32,.88);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 20px;
    box-shadow: var(--shadow);
}

.grid {
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(240px, 1fr)
        );
    gap: 18px;
}

.stats {
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(180px, 1fr)
        );
    gap: 14px;
    margin: 20px 0;
}

.stat {
    background: rgba(7,91,61,.75);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px;
}

.stat strong {
    display: block;
    font-size: 25px;
    margin-top: 8px;
}

.muted {
    color: var(--muted);
}

.title {
    margin-top: 0;
}

.btn {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    min-height: 44px;
    padding: 10px 16px;
    border: 0;
    border-radius: 11px;
    background: var(--green-light);
    color: #fff;
    font-weight: 700;
}

.btn:hover {
    filter: brightness(1.12);
}

.btn.secondary {
    background: #0a4935;
    border: 1px solid var(--border);
}

.btn.danger {
    background: #b52e39;
}

.btn.warning {
    background: #9c7518;
}

.form {
    display: grid;
    gap: 13px;
}

label {
    font-weight: 700;
    margin-bottom: -6px;
}

input,
select,
textarea {
    width: 100%;
    padding: 13px;
    color: #fff;
    background: #062f23;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 10px;
    outline: none;
}

input:focus,
select:focus,
textarea:focus {
    border-color: var(--green-light);
    box-shadow: 0 0 0 3px rgba(16,166,106,.14);
}

textarea {
    min-height: 110px;
    resize: vertical;
}

.machine {
    overflow: hidden;
    padding: 0;
}

.machine-image {
    width: 100%;
    height: 190px;
    object-fit: cover;
    display: block;
    background: #052a20;
}

.machine-body {
    padding: 18px;
}

.machine h3 {
    margin-top: 0;
}

.price {
    font-size: 23px;
    font-weight: 900;
}

.badge {
    display: inline-block;
    padding: 5px 9px;
    border-radius: 999px;
    background: rgba(16,166,106,.18);
    border: 1px solid rgba(16,166,106,.3);
    font-size: 13px;
}

.alert {
    margin: 15px 0;
    padding: 13px 15px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: #073426;
}

.alert.error {
    background: #541f25;
}

.alert.success {
    background: #074b31;
}

.alert.warning {
    background: #5a4513;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    padding: 11px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    vertical-align: top;
}

.table-wrap {
    overflow-x: auto;
}

.popup {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(0,0,0,.72);
}

.popup-box {
    width: min(500px, 100%);
    background: #043324;
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 24px;
    box-shadow: var(--shadow);
}

.popup-close {
    float: right;
    border: 0;
    background: transparent;
    color: #fff;
    font-size: 27px;
}

.chat-box {
    max-height: 420px;
    overflow-y: auto;
    display: grid;
    gap: 10px;
}

.chat-message {
    padding: 11px;
    border-radius: 12px;
    background: #073b2b;
}

.chat-message.admin {
    background: #086444;
}

.notification-icon {
    position: relative;
}

.notification-dot {
    position: absolute;
    top: 4px;
    right: 3px;
    min-width: 17px;
    height: 17px;
    padding: 0 4px;
    border-radius: 99px;
    background: #ff4e59;
    font-size: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.progress {
    height: 12px;
    background: #011c14;
    border-radius: 999px;
    overflow: hidden;
    margin: 10px 0;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(
        90deg,
        #08784f,
        #33d18b
    );
}

.referral {
    word-break: break-all;
    padding: 12px;
    border-radius: 10px;
    background: #011d15;
    border: 1px solid var(--border);
}

.footer {
    padding: 40px 0;
    color: var(--muted);
    text-align: center;
}

.small {
    font-size: 14px;
}

@media (max-width: 700px) {
    .nav-inner {
        align-items: flex-start;
        padding: 12px 0;
        flex-direction: column;
    }

    .nav-links {
        width: 100%;
        overflow-x: auto;
        flex-wrap: nowrap;
    }

    .nav-links a {
        white-space: nowrap;
    }

    .card {
        padding: 16px;
    }

    th,
    td {
        font-size: 14px;
    }
}
"""


# ============================================================
# BASE TEMPLATE
# ============================================================

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1">
<title>{{ title or "DATA4MINE" }}</title>
<style>
""" + BASE_CSS + """
</style>
</head>

<body>

<nav class="nav">
<div class="container nav-inner">

<a class="brand"
   href="{{ url_for('dashboard') if user else url_for('login') }}">
DATA4MINE
</a>

<div class="nav-links">

{% if user %}

<a href="{{ url_for('dashboard') }}">
Dashboard
</a>

<a href="{{ url_for('shop') }}">
Shop
</a>

<a href="{{ url_for('my_machines') }}">
My Machines
</a>

<a href="{{ url_for('deposit') }}">
Deposit
</a>

<a href="{{ url_for('withdraw') }}">
Withdraw
</a>

<a href="{{ url_for('rewards') }}">
Rewards
</a>

<a href="{{ url_for('chat') }}">
Chat
</a>

<a class="notification-icon"
   href="{{ url_for('notifications') }}">
🔔

{% if unread_notifications > 0 %}
<span class="notification-dot">
{{ unread_notifications }}
</span>
{% endif %}

</a>

{% if user.is_admin %}
<a href="{{ url_for('admin_panel') }}">
Admin
</a>
{% endif %}

<a href="{{ url_for('logout') }}">
Logout
</a>

{% else %}

<a href="{{ url_for('login') }}">
Login
</a>

<a href="{{ url_for('register') }}">
Register
</a>

{% endif %}

</div>
</div>
</nav>


<main class="container">

{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}

{% for category, message in messages %}

<div class="alert {{ category }}">
{{ message }}
</div>

{% endfor %}

{% endif %}
{% endwith %}


{{ content|safe }}

</main>


<div class="footer">
DATA4MINE © 2026
</div>

</body>
</html>
"""


def page(title, content, **context):
    user = current_user()

    unread = 0

    if user:
        active_notifications = Notification.query.filter_by(
            active=True
        ).all()

        read_ids = {
            row.notification_id
            for row in NotificationRead.query.filter_by(
                user_id=user.id
            ).all()
        }

        unread = sum(
            1
            for notification in active_notifications
            if notification.id not in read_ids
        )

    return render_template_string(
        BASE_TEMPLATE,
        title=title,
        content=content,
        user=user,
        unread_notifications=unread,
        **context
    )


# ============================================================
# PUBLIC ROUTES
# ============================================================

@app.route("/")
def index():
    user = current_user()

    if user:
        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user():
        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm = request.form.get(
            "confirm",
            ""
        )

        referral = request.form.get(
            "referral",
            ""
        ).strip().upper()

        if not phone or not password:
            flash(
                "Phone number and password are required.",
                "error"
            )

        elif password != confirm:
            flash(
                "Passwords do not match.",
                "error"
            )

        elif len(password) < 4:
            flash(
                "Password must contain at least 4 characters.",
                "error"
            )

        elif User.query.filter_by(
            phone=phone
        ).first():
            flash(
                "This phone number is already registered.",
                "error"
            )

        else:

            referral_user = None

            if referral:
                referral_user = User.query.filter_by(
                    referral_code=referral
                ).first()

            code = uuid.uuid4().hex[:10].upper()

            user = User(
                phone=phone,
                referral_code=code,
                referred_by=(
                    referral_user.id
                    if referral_user
                    else None
                ),
                balance=0
            )

            user.set_password(
                password
            )

            db.session.add(
                user
            )

            db.session.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

    referral = request.args.get(
        "ref",
        ""
    )

    content = """
    <section class="hero">
        <h1>DATA4MINE WELCOME</h1>
        <p>
            Create your account and start using your DATA4MINE dashboard.
        </p>
    </section>

    <div class="card" style="max-width:520px;margin:auto;">
        <h2 class="title">Create Account</h2>

        <form class="form" method="POST">

            <label>Phone Number</label>
            <input
                name="phone"
                required
                placeholder="Enter phone number">

            <label>Password</label>
            <input
                type="password"
                name="password"
                required
                placeholder="Create password">

            <label>Confirm Password</label>
            <input
                type="password"
                name="confirm"
                required
                placeholder="Repeat password">

            <label>Referral Code</label>
            <input
                name="referral"
                value="{{ referral }}"
                placeholder="Optional referral code">

            <button class="btn" type="submit">
                Register
            </button>

        </form>
    </div>
    """

    return page(
        "Register",
        render_template_string(
            content,
            referral=referral
        )
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user():
        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            phone=phone
        ).first()

        if user and user.check_password(password):

            if not user.is_active:
                flash(
                    "Your account is disabled.",
                    "error"
                )

            else:

                session.clear()

                session["user_id"] = user.id

                # Admin goes directly to admin panel.
                if user.is_admin:
                    return redirect(
                        url_for("admin_panel")
                    )

                return redirect(
                    url_for("dashboard")
                )

        else:
            flash(
                "Invalid phone number or password.",
                "error"
            )

    content = """
    <section class="hero">
        <h1>DATA4MINE WELCOME</h1>
        <p>
            Login to your account.
        </p>
    </section>

    <div class="card" style="max-width:520px;margin:auto;">

        <h2 class="title">Login</h2>

        <form class="form" method="POST">

            <label>Phone Number</label>

            <input
                name="phone"
                required
                autocomplete="username"
                placeholder="Phone number">

            <label>Password</label>

            <input
                type="password"
                name="password"
                required
                autocomplete="current-password"
                placeholder="Password">

            <button class="btn" type="submit">
                Login
            </button>

        </form>

        <p class="muted">
            Don't have an account?
            <a href="{{ url_for('register') }}">
                Register
            </a>
        </p>

    </div>
    """

    return page(
        "Login",
        content
    )


# ============================================================
# HIDDEN ADMIN LOGIN
# ============================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if current_user():

        if current_user().is_admin:
            return redirect(
                url_for("admin_panel")
            )

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            phone=phone,
            is_admin=True
        ).first()

        if user and user.check_password(password):

            session.clear()

            session["user_id"] = user.id

            return redirect(
                url_for("admin_panel")
            )

        flash(
            "Invalid administrator login.",
            "error"
        )

    content = """
    <section class="hero">
        <h1>Administrator</h1>
    </section>

    <div class="card"
         style="max-width:500px;margin:auto;">

        <h2>Admin Login</h2>

        <form class="form" method="POST">

            <label>Admin Phone</label>

            <input
                name="phone"
                required>

            <label>Admin Password</label>

            <input
                type="password"
                name="password"
                required>

            <button class="btn" type="submit">
                Admin Login
            </button>

        </form>

    </div>
    """

    return page(
        "Admin Login",
        content
    )


@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()

    machines = UserMachine.query.filter_by(
        user_id=user.id
    ).order_by(
        UserMachine.id.desc()
    ).all()

    pending_deposits = Deposit.query.filter_by(
        user_id=user.id,
        status="pending"
    ).count()

    pending_withdrawals = Withdrawal.query.filter_by(
        user_id=user.id,
        status="pending"
    ).count()

    content = """
    <section class="hero">
        <h1>DATA4MINE WELCOME</h1>

        <p>
            Welcome, {{ user.phone }}.
        </p>
    </section>

    <div class="stats">

        <div class="stat">
            Balance
            <strong>
                {{ money(user.balance) }}
            </strong>
        </div>

        <div class="stat">
            My Machines
            <strong>
                {{ machines|length }}
            </strong>
        </div>

        <div class="stat">
            Pending Deposits
            <strong>
                {{ pending_deposits }}
            </strong>
        </div>

        <div class="stat">
            Pending Withdrawals
            <strong>
                {{ pending_withdrawals }}
            </strong>
        </div>

    </div>

    <div class="grid">

        <a class="card"
           href="{{ url_for('shop') }}">
            <h2>🏭 Shop</h2>
            <p class="muted">
                View available machines.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('my_machines') }}">
            <h2>⚙️ My Machines</h2>
            <p class="muted">
                Track your machine days.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('deposit') }}">
            <h2>💰 Deposit</h2>
            <p class="muted">
                Submit a manual deposit.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('withdraw') }}">
            <h2>💸 Withdraw</h2>
            <p class="muted">
                Submit a withdrawal request.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('rewards') }}">
            <h2>🎁 Rewards</h2>
            <p class="muted">
                Your referral link and rewards.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('chat') }}">
            <h2>💬 Chat</h2>
            <p class="muted">
                Contact the administrator.
            </p>
        </a>

    </div>

    {% if user.is_admin %}

    <div class="card" style="margin-top:20px;">
        <h2>Administrator</h2>
        <a class="btn"
           href="{{ url_for('admin_panel') }}">
            Open Admin Panel
        </a>
    </div>

    {% endif %}
    """

    return page(
        "Dashboard",
        render_template_string(
            content,
            user=user,
            machines=machines,
            pending_deposits=pending_deposits,
            pending_withdrawals=pending_withdrawals,
            money=format_money
        )
    )


# ============================================================
# SHOP
# ============================================================

@app.route("/shop")
@login_required
def shop():

    machines = Machine.query.filter_by(
        active=True
    ).order_by(
        Machine.price.asc()
    ).all()

    content = """
    <section class="hero">
        <h1>Machine Shop</h1>
        <p>
            Choose an available machine.
        </p>
    </section>

    <div class="grid">

    {% for machine in machines %}

        <div class="card machine">

            {% if machine.image_filename %}

                <img
                    class="machine-image"
                    src="{{ url_for('machine_image',
                                    filename=machine.image_filename) }}"
                    alt="{{ machine.name }}">

            {% else %}

                <div class="machine-image"
                     style="display:flex;
                            align-items:center;
                            justify-content:center;">
                    🏭
                </div>

            {% endif %}

            <div class="machine-body">

                <h3>
                    {{ machine.name }}
                </h3>

                <p class="muted">
                    {{ machine.description }}
                </p>

                <p class="price">
                    {{ money(machine.price) }}
                </p>

                <p>
                    Daily earning:
                    <strong>
                        {{ money(machine.daily_profit) }}
                    </strong>
                </p>

                <p>
                    Duration:
                    <strong>
                        {{ machine.duration_days }} days
                    </strong>
                </p>

                <p>
                    Total profit:
                    <strong>
                        {{ money(machine.total_profit) }}
                    </strong>
                </p>

                <p>
                    Total expected amount:
                    <strong>
                        {{ money(machine.total_return) }}
                    </strong>
                </p>

                {% if machine.stock > 0 %}

                    <span class="badge">
                        Stock: {{ machine.stock }}
                    </span>

                    <form method="POST"
                          action="{{ url_for(
                              'buy_machine',
                              machine_id=machine.id
                          ) }}"
                          style="margin-top:14px;">

                        <button class="btn"
                                type="submit">
                            Buy Machine
                        </button>

                    </form>

                {% else %}

                    <span class="badge">
                        Out of Stock
                    </span>

                {% endif %}

            </div>
        </div>

    {% else %}

        <div class="card">
            <h2>No machines available</h2>
            <p class="muted">
                The administrator has not made any machines available.
            </p>
        </div>

    {% endfor %}

    </div>
    """

    return page(
        "Machine Shop",
        render_template_string(
            content,
            machines=machines,
            money=format_money
        )
    )


@app.route("/machine/<int:machine_id>/buy", methods=["POST"])
@login_required
def buy_machine(machine_id):

    user = current_user()

    machine = db.session.get(
        Machine,
        machine_id
    )

    if machine is None or not machine.active:
        flash(
            "Machine is not available.",
            "error"
        )

        return redirect(
            url_for("shop")
        )

    if machine.stock <= 0:
        flash(
            "This machine is out of stock.",
            "error"
        )

        return redirect(
            url_for("shop")
        )

    if user.balance < machine.price:
        flash(
            "Insufficient balance. Please make a deposit and wait for admin approval.",
            "error"
        )

        return redirect(
            url_for("shop")
        )

    # Deduct purchase price.
    user.balance -= machine.price

    # Reduce stock.
    machine.stock -= 1

    purchase = UserMachine(
        user_id=user.id,
        machine_id=machine.id,
        purchase_price=machine.price,
        daily_profit=machine.daily_profit,
        duration_days=machine.duration_days,
        purchased_at=utc_now()
    )

    db.session.add(
        purchase
    )

    # Referral reward is paid when a referred user
    # makes a verified machine purchase.
    if user.referred_by:

        inviter = db.session.get(
            User,
            user.referred_by
        )

        if inviter:

            inviter.balance += REFERRAL_REWARD

            chat = ChatMessage(
                user_id=inviter.id,
                sender="admin",
                message=(
                    "Referral reward of "
                    + format_money(REFERRAL_REWARD)
                    + " has been added because your referred user purchased a machine."
                )
            )

            db.session.add(
                chat
            )

            # Clear referred_by so the registration reward
            # cannot be paid repeatedly.
            user.referred_by = None

    db.session.commit()

    flash(
        "Machine purchased successfully.",
        "success"
    )

    return redirect(
        url_for("my_machines")
    )


# ============================================================
# MY MACHINES
# ============================================================

@app.route("/my-machines")
@login_required
def my_machines():

    user = current_user()

    machines = UserMachine.query.filter_by(
        user_id=user.id
    ).order_by(
        UserMachine.purchased_at.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>My Machines</h1>
        <p>
            Machine days are based on actual elapsed time.
            Every 24 hours equals one machine day.
        </p>
    </section>

    <div class="grid">

    {% for item in machines %}

        <div class="card">

            <h2>
                {{ item.machine.name }}
            </h2>

            <p>
                Progress:
                <strong>
                    {{ item.progress_text }}
                </strong>
            </p>

            <div class="progress">

                <div class="progress-bar"
                     style="width:
                     {{ (item.days_completed /
                         item.duration_days * 100)
                         if item.duration_days else 0 }}%;">
                </div>

            </div>

            {% if not item.is_complete %}

                <p class="muted">
                    Remaining:
                    <span
                      data-countdown="{{ item.seconds_remaining }}">
                    </span>
                </p>

                <p class="small muted">
                    Completion:
                    {{ item.finish_time }}
                    UTC
                </p>

            {% else %}

                <div class="alert success">
                    Machine completed.
                    Your receive-money button is now available.
                </div>

                {% if item.received_at %}

                    <div class="alert">
                        Money already received.
                        <br>
                        Received:
                        {{ item.received_at }}
                    </div>

                {% else %}

                    <form method="POST"
                          action="{{ url_for(
                              'receive_machine',
                              purchase_id=item.id
                          ) }}">

                        <button class="btn"
                                type="submit">
                            Receive Money
                        </button>

                    </form>

                {% endif %}

            {% endif %}

            <hr>

            <p>
                Daily:
                <strong>
                    {{ money(item.daily_profit) }}
                </strong>
            </p>

            <p>
                Total profit:
                <strong>
                    {{ money(item.total_profit) }}
                </strong>
            </p>

            <p>
                Purchased:
                {{ item.purchased_at }}
                UTC
            </p>

        </div>

    {% else %}

        <div class="card">
            <h2>You have no machines yet.</h2>

            <a class="btn"
               href="{{ url_for('shop') }}">
                Visit Shop
            </a>
        </div>

    {% endfor %}

    </div>

    <script>
    function formatRemaining(seconds) {

        if (seconds <= 0) {
            return "Completed";
        }

        const days =
            Math.floor(seconds / 86400);

        seconds %= 86400;

        const hours =
            Math.floor(seconds / 3600);

        seconds %= 3600;

        const minutes =
            Math.floor(seconds / 60);

        const secs =
            seconds % 60;

        return (
            days + "d " +
            hours + "h " +
            minutes + "m " +
            secs + "s"
        );
    }

    function updateCountdowns() {

        document.querySelectorAll(
            "[data-countdown]"
        ).forEach(function(element) {

            let seconds =
                parseInt(
                    element.getAttribute(
                        "data-countdown"
                    )
                );

            element.textContent =
                formatRemaining(seconds);

            if (seconds > 0) {

                seconds--;

                element.setAttribute(
                    "data-countdown",
                    seconds
                );

            } else {

                element.textContent =
                    "Completed — refresh page";

            }

        });

    }

    updateCountdowns();

    setInterval(
        updateCountdowns,
        1000
    );
    </script>
    """

    return page(
        "My Machines",
        render_template_string(
            content,
            machines=machines,
            money=format_money
        )
    )


@app.route(
    "/machine/<int:purchase_id>/receive",
    methods=["POST"]
)
@login_required
def receive_machine(purchase_id):

    user = current_user()

    item = UserMachine.query.filter_by(
        id=purchase_id,
        user_id=user.id
    ).first()

    if item is None:
        flash(
            "Machine not found.",
            "error"
        )

        return redirect(
            url_for("my_machines")
        )

    if item.received_at:
        flash(
            "Money from this machine has already been received.",
            "error"
        )

        return redirect(
            url_for("my_machines")
        )

    if not item.is_complete:
        flash(
            "The machine has not completed its full 24-hour days yet.",
            "error"
        )

        return redirect(
            url_for("my_machines")
        )

    # Complete it once.
    item.completed_at = (
        item.finish_time
    )

    item.received_at = utc_now()

    # Add profit to balance.
    user.balance += item.total_profit

    item.reward_received = True

    db.session.commit()

    flash(
        "Machine profit of "
        + format_money(item.total_profit)
        + " has been added to your balance.",
        "success"
    )

    return redirect(
        url_for("my_machines")
    )


# ============================================================
# DEPOSIT
# ============================================================

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    user = current_user()

    numbers = DepositNumber.query.filter_by(
        active=True
    ).all()

    if request.method == "POST":

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        number_id = request.form.get(
            "number_id",
            ""
        )

        transaction_message = request.form.get(
            "transaction_message",
            ""
        ).strip()

        try:
            amount = float(
                amount_text
            )
        except Exception:
            amount = 0

        selected = None

        try:
            selected = db.session.get(
                DepositNumber,
                int(number_id)
            )
        except Exception:
            selected = None

        if amount <= 0:
            flash(
                "Enter a valid deposit amount.",
                "error"
            )

        elif selected is None or not selected.active:
            flash(
                "Select a valid deposit number.",
                "error"
            )

        elif not transaction_message:
            flash(
                "Paste the money-sent/transaction message.",
                "error"
            )

        else:

            deposit_record = Deposit(
                user_id=user.id,
                amount=amount,
                deposit_number=selected.number,
                transaction_message=transaction_message,
                status="pending"
            )

            db.session.add(
                deposit_record
            )

            db.session.commit()

            flash(
                "Deposit submitted. It will remain pending until the administrator verifies it.",
                "success"
            )

            return redirect(
                url_for("deposit")
            )

    deposits = Deposit.query.filter_by(
        user_id=user.id
    ).order_by(
        Deposit.created_at.desc()
    ).limit(20).all()

    content = """
    <section class="hero">
        <h1>Deposit</h1>
        <p>
            Deposits are manually verified and approved by the administrator.
        </p>
    </section>

    <div class="grid">

        <div class="card">

            <h2>Send Money</h2>

            {% if numbers %}

                <div class="alert">

                    <strong>Deposit Numbers</strong>

                    {% for number in numbers %}

                        <p>
                            {{ number.owner_name }}
                            <br>
                            <strong>
                                {{ number.number }}
                            </strong>
                        </p>

                    {% endfor %}

                </div>

                <form class="form"
                      method="POST">

                    <label>
                        Amount (UGX)
                    </label>

                    <input
                        name="amount"
                        type="number"
                        min="1"
                        step="1"
                        required>

                    <label>
                        Deposit Number
                    </label>

                    <select
                        name="number_id"
                        required>

                        <option value="">
                            Select number
                        </option>

                        {% for number in numbers %}

                        <option value="{{ number.id }}">
                            {{ number.owner_name }}
                            -
                            {{ number.number }}
                        </option>

                        {% endfor %}

                    </select>

                    <label>
                        Paste Money-Sent / Transaction Message
                    </label>

                    <textarea
                        name="transaction_message"
                        required
                        placeholder="Paste the complete transaction message here"></textarea>

                    <button class="btn"
                            type="submit">
                        Submit Deposit for Approval
                    </button>

                </form>

            {% else %}

                <div class="alert error">
                    No deposit number is currently available.
                </div>

            {% endif %}

        </div>

        <div class="card">

            <h2>My Deposits</h2>

            <div class="table-wrap">

            <table>

                <tr>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Date</th>
                </tr>

                {% for item in deposits %}

                <tr>

                    <td>
                        {{ money(item.amount) }}
                    </td>

                    <td>
                        {{ item.status }}
                    </td>

                    <td>
                        {{ item.created_at }}
                    </td>

                </tr>

                {% else %}

                <tr>
                    <td colspan="3">
                        No deposits yet.
                    </td>
                </tr>

                {% endfor %}

            </table>

            </div>

        </div>

    </div>
    """

    return page(
        "Deposit",
        render_template_string(
            content,
            numbers=numbers,
            deposits=deposits,
            money=format_money
        )
    )


# ============================================================
# WITHDRAW
# ============================================================

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    user = current_user()

    if request.method == "POST":

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        account_name = request.form.get(
            "account_name",
            ""
        ).strip()

        account_number = request.form.get(
            "account_number",
            ""
        ).strip()

        try:
            amount = float(
                amount_text
            )
        except Exception:
            amount = 0

        tax = amount * WITHDRAW_TAX_RATE
        net_amount = amount - tax

        if amount <= 0:
            flash(
                "Enter a valid withdrawal amount.",
                "error"
            )

        elif not account_name:
            flash(
                "Enter the account name.",
                "error"
            )

        elif not account_number:
            flash(
                "Enter the account number.",
                "error"
            )

        elif amount > user.balance:
            flash(
                "Insufficient balance.",
                "error"
            )

        else:

            # Reserve the requested amount immediately.
            user.balance -= amount

            withdrawal = Withdrawal(
                user_id=user.id,
                amount=amount,
                tax=tax,
                net_amount=net_amount,
                account_name=account_name,
                account_number=account_number,
                status="pending"
            )

            db.session.add(
                withdrawal
            )

            db.session.commit()

            flash(
                "Withdrawal submitted. The administrator will manually process it after the 24-hour processing period.",
                "success"
            )

            return redirect(
                url_for("withdraw")
            )

    withdrawals = Withdrawal.query.filter_by(
        user_id=user.id
    ).order_by(
        Withdrawal.created_at.desc()
    ).limit(20).all()

    content = """
    <section class="hero">
        <h1>Withdraw</h1>
        <p>
            Withdrawals are manually approved by the administrator.
            A 7% tax is deducted from each withdrawal.
        </p>
    </section>

    <div class="grid">

        <div class="card">

            <h2>New Withdrawal</h2>

            <div class="alert">

                Balance:
                <strong>
                    {{ money(user.balance) }}
                </strong>

                <br><br>

                Tax:
                <strong>7%</strong>

                <br>

                Example:
                UGX 100,000 withdrawal =
                UGX 7,000 tax =
                UGX 93,000 received.

            </div>

            <form class="form"
                  method="POST">

                <label>
                    Withdrawal Amount (UGX)
                </label>

                <input
                    id="withdrawAmount"
                    name="amount"
                    type="number"
                    min="1"
                    step="1"
                    required>

                <div class="alert">

                    Tax:
                    <strong id="taxAmount">
                        UGX 0
                    </strong>

                    <br>

                    You receive:
                    <strong id="netAmount">
                        UGX 0
                    </strong>

                </div>

                <label>
                    Account Name
                </label>

                <input
                    name="account_name"
                    required
                    placeholder="Name registered on payment account">

                <label>
                    Account / Mobile Money Number
                </label>

                <input
                    name="account_number"
                    required
                    placeholder="Payment number">

                <button class="btn"
                        type="submit">
                    Submit Withdrawal
                </button>

            </form>

        </div>

        <div class="card">

            <h2>My Withdrawals</h2>

            <div class="table-wrap">

            <table>

                <tr>
                    <th>Amount</th>
                    <th>Tax</th>
                    <th>Receive</th>
                    <th>Status</th>
                </tr>

                {% for item in withdrawals %}

                <tr>

                    <td>
                        {{ money(item.amount) }}
                    </td>

                    <td>
                        {{ money(item.tax) }}
                    </td>

                    <td>
                        {{ money(item.net_amount) }}
                    </td>

                    <td>
                        {{ item.status }}

                        {% if item.status == "pending" %}

                        <br>

                        <span
                          data-countdown="{{ item.seconds_remaining }}">
                        </span>

                        {% endif %}

                    </td>

                </tr>

                {% else %}

                <tr>
                    <td colspan="4">
                        No withdrawals yet.
                    </td>
                </tr>

                {% endfor %}

            </table>

            </div>

        </div>

    </div>

    <script>

    const amountInput =
        document.getElementById(
            "withdrawAmount"
        );

    function updateWithdraw() {

        const amount =
            parseFloat(
                amountInput.value
            ) || 0;

        const tax =
            amount * 0.07;

        const net =
            amount - tax;

        document.getElementById(
            "taxAmount"
        ).textContent =
            "UGX " +
            Math.round(tax).toLocaleString();

        document.getElementById(
            "netAmount"
        ).textContent =
            "UGX " +
            Math.round(net).toLocaleString();
    }

    amountInput.addEventListener(
        "input",
        updateWithdraw
    );

    function countdown() {

        document.querySelectorAll(
            "[data-countdown]"
        ).forEach(function(el) {

            let seconds =
                parseInt(
                    el.getAttribute(
                        "data-countdown"
                    )
                );

            if (seconds <= 0) {
                el.textContent =
                    "24-hour period completed";
                return;
            }

            const hours =
                Math.floor(
                    seconds / 3600
                );

            const minutes =
                Math.floor(
                    (seconds % 3600) / 60
                );

            const secs =
                seconds % 60;

            el.textContent =
                hours + "h " +
                minutes + "m " +
                secs + "s remaining";

            seconds--;

            el.setAttribute(
                "data-countdown",
                seconds
            );

        });

    }

    setInterval(
        countdown,
        1000
    );

    countdown();

    </script>
    """

    return page(
        "Withdraw",
        render_template_string(
            content,
            user=user,
            withdrawals=withdrawals,
            money=format_money
        )
    )


# ============================================================
# REWARDS
# ============================================================

@app.route("/rewards")
@login_required
def rewards():

    user = current_user()

    host = request.host_url.rstrip("/")

    referral_link = (
        host
        + url_for(
            "register"
        )
        + "?ref="
        + user.referral_code
    )

    referred_users = User.query.filter_by(
        referred_by=user.id
    ).all()

    content = """
    <section class="hero">
        <h1>Rewards</h1>
        <p>
            Invite people using your personal referral link.
        </p>
    </section>

    <div class="grid">

        <div class="card">

            <h2>Your Referral Link</h2>

            <div class="referral"
                 id="referralLink">
                {{ referral_link }}
            </div>

            <br>

            <button
                class="btn"
                onclick="copyReferral()">
                Copy Referral Link
            </button>

            <button
                class="btn secondary"
                onclick="shareReferral()">
                Share Link
            </button>

            <p class="muted small">
                Referral reward:
                UGX {{ reward }}.
                The reward is credited when a referred
                user successfully purchases a machine.
            </p>

        </div>

        <div class="card">

            <h2>Referral Statistics</h2>

            <p>
                People registered through you:
                <strong>
                    {{ referred_users|length }}
                </strong>
            </p>

            <p>
                Reward per qualifying machine purchase:
                <strong>
                    {{ money(reward) }}
                </strong>
            </p>

        </div>

    </div>

    <script>

    function copyReferral() {

        const link =
            document.getElementById(
                "referralLink"
            ).textContent.trim();

        navigator.clipboard.writeText(
            link
        ).then(function() {

            alert(
                "Referral link copied."
            );

        });

    }

    function shareReferral() {

        const link =
            document.getElementById(
                "referralLink"
            ).textContent.trim();

        if (
            navigator.share
        ) {

            navigator.share({
                title: "DATA4MINE",
                text: "Join DATA4MINE",
                url: link
            });

        } else {

            copyReferral();

        }

    }

    </script>
    """

    return page(
        "Rewards",
        render_template_string(
            content,
            referral_link=referral_link,
            referred_users=referred_users,
            reward=REFERRAL_REWARD,
            money=format_money
        )
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    user = current_user()

    active = Notification.query.filter_by(
        active=True
    ).order_by(
        Notification.created_at.desc()
    ).all()

    # Mark as read when notification page is opened.
    for notification in active:

        existing = NotificationRead.query.filter_by(
            notification_id=notification.id,
            user_id=user.id
        ).first()

        if existing is None:

            db.session.add(
                NotificationRead(
                    notification_id=notification.id,
                    user_id=user.id
                )
            )

    db.session.commit()

    content = """
    <section class="hero">
        <h1>Notifications</h1>
        <p>
            Updates from DATA4MINE.
        </p>
    </section>

    <div class="grid">

    {% for item in notifications %}

        <div class="card">

            <h2>
                {{ item.title }}
            </h2>

            <p>
                {{ item.message }}
            </p>

            <p class="small muted">
                {{ item.created_at }}
            </p>

        </div>

    {% else %}

        <div class="card">
            No notifications.
        </div>

    {% endfor %}

    </div>
    """

    return page(
        "Notifications",
        render_template_string(
            content,
            notifications=active
        )
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

            db.session.add(
                ChatMessage(
                    user_id=user.id,
                    sender="user",
                    message=message
                )
            )

            db.session.commit()

            flash(
                "Message sent.",
                "success"
            )

            return redirect(
                url_for("chat")
            )

    messages = ChatMessage.query.filter_by(
        user_id=user.id
    ).order_by(
        ChatMessage.created_at.asc()
    ).all()

    content = """
    <section class="hero">
        <h1>Chat with Admin</h1>
    </section>

    <div class="card">

        <div class="chat-box">

        {% for item in messages %}

            <div class="chat-message
                {% if item.sender == 'admin' %}
                    admin
                {% endif %}">

                <strong>
                    {{ item.sender|capitalize }}
                </strong>

                <p>
                    {{ item.message }}
                </p>

                <small class="muted">
                    {{ item.created_at }}
                </small>

            </div>

        {% else %}

            <p class="muted">
                No messages yet.
            </p>

        {% endfor %}

        </div>

        <form class="form"
              method="POST"
              style="margin-top:20px;">

            <textarea
                name="message"
                required
                placeholder="Write your message..."></textarea>

            <button class="btn"
                    type="submit">
                Send Message
            </button>

        </form>

    </div>
    """

    return page(
        "Chat",
        render_template_string(
            content,
            messages=messages
        )
    )


# ============================================================
# MACHINE IMAGE ROUTE
# ============================================================

@app.route("/static/machines/<path:filename>")
def machine_image(filename):

    return send_from_directory(
        MACHINE_DIR,
        filename
    )


# ============================================================
# ADMIN PANEL
# ============================================================

@app.route("/admin")
@admin_required
def admin_panel():

    users_count = User.query.count()

    joined_today = User.query.filter(
        User.created_at >= (
            utc_now() - timedelta(days=1)
        )
    ).count()

    deposits_pending = Deposit.query.filter_by(
        status="pending"
    ).count()

    withdrawals_pending = Withdrawal.query.filter_by(
        status="pending"
    ).count()

    total_deposits = db.session.query(
        db.func.coalesce(
            db.func.sum(Deposit.amount),
            0
        )
    ).filter(
        Deposit.status == "approved"
    ).scalar()

    total_withdrawals = db.session.query(
        db.func.coalesce(
            db.func.sum(Withdrawal.net_amount),
            0
        )
    ).filter(
        Withdrawal.status == "approved"
    ).scalar()

    content = """
    <section class="hero">
        <h1>Admin Panel</h1>
        <p>
            DATA4MINE administration dashboard.
        </p>
    </section>

    <div class="stats">

        <div class="stat">
            Joined
            <strong>
                {{ users_count }}
            </strong>
        </div>

        <div class="stat">
            Joined Last 24h
            <strong>
                {{ joined_today }}
            </strong>
        </div>

        <div class="stat">
            Pending Deposits
            <strong>
                {{ deposits_pending }}
            </strong>
        </div>

        <div class="stat">
            Pending Withdrawals
            <strong>
                {{ withdrawals_pending }}
            </strong>
        </div>

        <div class="stat">
            Approved Deposits
            <strong>
                {{ money(total_deposits) }}
            </strong>
        </div>

        <div class="stat">
            Approved Withdrawals
            <strong>
                {{ money(total_withdrawals) }}
            </strong>
        </div>

    </div>

    <div class="grid">

        <a class="card"
           href="{{ url_for('admin_deposits') }}">
            <h2>💰 Deposits</h2>
            <p>
                Verify and approve deposits.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_withdrawals') }}">
            <h2>💸 Withdrawals</h2>
            <p>
                Process withdrawals.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_machines') }}">
            <h2>🏭 Machines</h2>
            <p>
                Add, edit and remove machines.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_deposit_numbers') }}">
            <h2>📱 Deposit Numbers</h2>
            <p>
                Manage payment numbers.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_users') }}">
            <h2>👥 Users & Admins</h2>
            <p>
                Manage accounts and administrators.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_notifications') }}">
            <h2>🔔 Notifications</h2>
            <p>
                Send updates to users.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_chat') }}">
            <h2>💬 User Chat</h2>
            <p>
                Reply to users.
            </p>
        </a>

        <a class="card"
           href="{{ url_for('admin_chart') }}">
            <h2>📊 Statistics</h2>
            <p>
                Deposit, withdrawal and joiner rates.
            </p>
        </a>

    </div>
    """

    return page(
        "Admin Panel",
        render_template_string(
            content,
            users_count=users_count,
            joined_today=joined_today,
            deposits_pending=deposits_pending,
            withdrawals_pending=withdrawals_pending,
            total_deposits=total_deposits,
            total_withdrawals=total_withdrawals,
            money=format_money
        )
    )


# ============================================================
# ADMIN DEPOSITS
# ============================================================

@app.route(
    "/admin/deposits",
    methods=["GET", "POST"]
)
@admin_required
def admin_deposits():

    if request.method == "POST":

        deposit_id = request.form.get(
            "deposit_id"
        )

        action = request.form.get(
            "action"
        )

        note = request.form.get(
            "note",
            ""
        ).strip()

        deposit_record = db.session.get(
            Deposit,
            int(deposit_id)
        )

        if deposit_record is None:
            flash(
                "Deposit not found.",
                "error"
            )

            return redirect(
                url_for("admin_deposits")
            )

        if deposit_record.status != "pending":
            flash(
                "This deposit has already been processed.",
                "error"
            )

            return redirect(
                url_for("admin_deposits")
            )

        if action == "approve":

            deposit_record.status = "approved"
            deposit_record.admin_note = note
            deposit_record.processed_at = utc_now()

            deposit_record.user.balance += (
                deposit_record.amount
            )

            db.session.add(
                ChatMessage(
                    user_id=deposit_record.user_id,
                    sender="admin",
                    message=(
                        "Your deposit of "
                        + format_money(deposit_record.amount)
                        + " has been approved."
                    )
                )
            )

        elif action == "reject":

            deposit_record.status = "rejected"
            deposit_record.admin_note = note
            deposit_record.processed_at = utc_now()

            db.session.add(
                ChatMessage(
                    user_id=deposit_record.user_id,
                    sender="admin",
                    message=(
                        "Your deposit of "
                        + format_money(deposit_record.amount)
                        + " was rejected."
                    )
                )
            )

        db.session.commit()

        flash(
            "Deposit updated.",
            "success"
        )

        return redirect(
            url_for("admin_deposits")
        )

    deposits = Deposit.query.order_by(
        Deposit.created_at.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Deposit Management</h1>
    </section>

    <div class="card">

    <div class="table-wrap">

    <table>

    <tr>
        <th>User</th>
        <th>Amount</th>
        <th>Number</th>
        <th>Transaction Message</th>
        <th>Status</th>
        <th>Action</th>
    </tr>

    {% for item in deposits %}

    <tr>

        <td>
            {{ item.user.phone }}
        </td>

        <td>
            {{ money(item.amount) }}
        </td>

        <td>
            {{ item.deposit_number }}
        </td>

        <td style="max-width:350px;">
            <pre style="white-space:pre-wrap;">
{{ item.transaction_message }}
            </pre>
        </td>

        <td>
            {{ item.status }}
        </td>

        <td>

        {% if item.status == "pending" %}

        <form method="POST">

            <input type="hidden"
                   name="deposit_id"
                   value="{{ item.id }}">

            <input name="note"
                   placeholder="Admin note">

            <button
                class="btn"
                name="action"
                value="approve">
                Approve
            </button>

            <button
                class="btn danger"
                name="action"
                value="reject">
                Reject
            </button>

        </form>

        {% else %}

            Processed:
            {{ item.processed_at }}

        {% endif %}

        </td>

    </tr>

    {% else %}

    <tr>
        <td colspan="6">
            No deposits.
        </td>
    </tr>

    {% endfor %}

    </table>

    </div>

    </div>
    """

    return page(
        "Admin Deposits",
        render_template_string(
            content,
            deposits=deposits,
            money=format_money
        )
    )


# ============================================================
# ADMIN WITHDRAWALS
# ============================================================

@app.route(
    "/admin/withdrawals",
    methods=["GET", "POST"]
)
@admin_required
def admin_withdrawals():

    if request.method == "POST":

        withdrawal_id = request.form.get(
            "withdrawal_id"
        )

        action = request.form.get(
            "action"
        )

        note = request.form.get(
            "note",
            ""
        ).strip()

        withdrawal = db.session.get(
            Withdrawal,
            int(withdrawal_id)
        )

        if withdrawal is None:
            flash(
                "Withdrawal not found.",
                "error"
            )

            return redirect(
                url_for("admin_withdrawals")
            )

        if withdrawal.status != "pending":
            flash(
                "This withdrawal is already processed.",
                "error"
            )

            return redirect(
                url_for("admin_withdrawals")
            )

        # 24-hour waiting period.
        if utc_now() < withdrawal.available_at:

            flash(
                "The 24-hour withdrawal processing period has not completed yet.",
                "error"
            )

            return redirect(
                url_for("admin_withdrawals")
            )

        if action == "approve":

            withdrawal.status = "approved"
            withdrawal.processed_at = utc_now()
            withdrawal.admin_note = note

            db.session.add(
                ChatMessage(
                    user_id=withdrawal.user_id,
                    sender="admin",
                    message=(
                        "Your withdrawal has been approved. "
                        "Net amount: "
                        + format_money(
                            withdrawal.net_amount
                        )
                    )
                )
            )

        elif action == "reject":

            withdrawal.status = "rejected"
            withdrawal.processed_at = utc_now()
            withdrawal.admin_note = note

            # Return reserved amount.
            withdrawal.user.balance += (
                withdrawal.amount
            )

            db.session.add(
                ChatMessage(
                    user_id=withdrawal.user_id,
                    sender="admin",
                    message=(
                        "Your withdrawal of "
                        + format_money(
                            withdrawal.amount
                        )
                        + " was rejected. "
                        "The reserved balance has been returned."
                    )
                )
            )

        db.session.commit()

        flash(
            "Withdrawal updated.",
            "success"
        )

        return redirect(
            url_for("admin_withdrawals")
        )

    withdrawals = Withdrawal.query.order_by(
        Withdrawal.created_at.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Withdrawal Management</h1>
    </section>

    <div class="card">

    <div class="table-wrap">

    <table>

    <tr>
        <th>User</th>
        <th>Amount</th>
        <th>Tax</th>
        <th>Net</th>
        <th>Name</th>
        <th>Number</th>
        <th>Status</th>
        <th>Action</th>
    </tr>

    {% for item in withdrawals %}

    <tr>

        <td>
            {{ item.user.phone }}
        </td>

        <td>
            {{ money(item.amount) }}
        </td>

        <td>
            {{ money(item.tax) }}
        </td>

        <td>
            {{ money(item.net_amount) }}
        </td>

        <td>
            {{ item.account_name }}
        </td>

        <td>
            {{ item.account_number }}
        </td>

        <td>
            {{ item.status }}

            {% if item.status == "pending" %}

            <br>

            {% if item.seconds_remaining > 0 %}

                <span
                  data-countdown="{{ item.seconds_remaining }}">
                </span>

            {% else %}

                Ready

            {% endif %}

            {% endif %}

        </td>

        <td>

        {% if item.status == "pending" %}

        <form method="POST">

            <input type="hidden"
                   name="withdrawal_id"
                   value="{{ item.id }}">

            <input name="note"
                   placeholder="Admin note">

            <button
                class="btn"
                name="action"
                value="approve"
                {% if item.seconds_remaining > 0 %}
                disabled
                {% endif %}>
                Approve
            </button>

            <button
                class="btn danger"
                name="action"
                value="reject">
                Reject
            </button>

        </form>

        {% else %}

            Processed:
            {{ item.processed_at }}

        {% endif %}

        </td>

    </tr>

    {% else %}

    <tr>
        <td colspan="8">
            No withdrawals.
        </td>
    </tr>

    {% endfor %}

    </table>

    </div>

    </div>

    <script>

    setInterval(function() {

        document.querySelectorAll(
            "[data-countdown]"
        ).forEach(function(el) {

            let s =
                parseInt(
                    el.getAttribute(
                        "data-countdown"
                    )
                );

            if (s <= 0) {
                el.textContent =
                    "Ready";
                return;
            }

            const h =
                Math.floor(
                    s / 3600
                );

            const m =
                Math.floor(
                    (s % 3600) / 60
                );

            const sec =
                s % 60;

            el.textContent =
                h + "h " +
                m + "m " +
                sec + "s remaining";

            el.setAttribute(
                "data-countdown",
                s - 1
            );

        });

    }, 1000);

    </script>
    """

    return page(
        "Admin Withdrawals",
        render_template_string(
            content,
            withdrawals=withdrawals,
            money=format_money
        )
    )


# ============================================================
# ADMIN DEPOSIT NUMBERS
# ============================================================

@app.route(
    "/admin/deposit-numbers",
    methods=["GET", "POST"]
)
@admin_required
def admin_deposit_numbers():

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        if action == "add":

            number = request.form.get(
                "number",
                ""
            ).strip()

            owner_name = request.form.get(
                "owner_name",
                ""
            ).strip()

            if number:

                db.session.add(
                    DepositNumber(
                        number=number,
                        owner_name=owner_name,
                        active=True
                    )
                )

                db.session.commit()

                flash(
                    "Deposit number added.",
                    "success"
                )

        elif action == "toggle":

            number_id = int(
                request.form.get(
                    "number_id"
                )
            )

            item = db.session.get(
                DepositNumber,
                number_id
            )

            if item:

                item.active = not item.active

                db.session.commit()

        elif action == "delete":

            number_id = int(
                request.form.get(
                    "number_id"
                )
            )

            item = db.session.get(
                DepositNumber,
                number_id
            )

            if item:

                db.session.delete(
                    item
                )

                db.session.commit()

    numbers = DepositNumber.query.order_by(
        DepositNumber.id.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Deposit Numbers</h1>
    </section>

    <div class="grid">

        <div class="card">

            <h2>Add Number</h2>

            <form class="form"
                  method="POST">

                <input type="hidden"
                       name="action"
                       value="add">

                <label>
                    Owner Name
                </label>

                <input
                    name="owner_name"
                    required>

                <label>
                    Deposit Number
                </label>

                <input
                    name="number"
                    required>

                <button class="btn"
                        type="submit">
                    Add Number
                </button>

            </form>

        </div>

        <div class="card">

            <h2>Existing Numbers</h2>

            {% for item in numbers %}

            <div class="alert">

                <strong>
                    {{ item.owner_name }}
                </strong>

                <br>

                {{ item.number }}

                <br>

                Status:
                {{ "Active" if item.active else "Disabled" }}

                <br><br>

                <form method="POST"
                      style="display:inline;">

                    <input type="hidden"
                           name="action"
                           value="toggle">

                    <input type="hidden"
                           name="number_id"
                           value="{{ item.id }}">

                    <button class="btn secondary">
                        Toggle
                    </button>

                </form>

                <form method="POST"
                      style="display:inline;">

                    <input type="hidden"
                           name="action"
                           value="delete">

                    <input type="hidden"
                           name="number_id"
                           value="{{ item.id }}">

                    <button class="btn danger">
                        Delete
                    </button>

                </form>

            </div>

            {% else %}

            <p>
                No deposit numbers.
            </p>

            {% endfor %}

        </div>

    </div>
    """

    return page(
        "Deposit Numbers",
        render_template_string(
            content,
            numbers=numbers
        )
    )


# ============================================================
# ADMIN MACHINE MANAGEMENT
# ============================================================

@app.route(
    "/admin/machines",
    methods=["GET", "POST"]
)
@admin_required
def admin_machines():

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        # ----------------------------------------------------
        # ADD MACHINE
        # ----------------------------------------------------
        if action == "add":

            name = request.form.get(
                "name",
                ""
            ).strip()

            description = request.form.get(
                "description",
                ""
            ).strip()

            try:
                price = float(
                    request.form.get(
                        "price",
                        0
                    )
                )

                daily_profit = float(
                    request.form.get(
                        "daily_profit",
                        0
                    )
                )

                duration_days = int(
                    request.form.get(
                        "duration_days",
                        20
                    )
                )

                stock = int(
                    request.form.get(
                        "stock",
                        0
                    )
                )

            except Exception:

                flash(
                    "Invalid machine values.",
                    "error"
                )

                return redirect(
                    url_for("admin_machines")
                )

            if not name:
                flash(
                    "Machine name is required.",
                    "error"
                )

                return redirect(
                    url_for("admin_machines")
                )

            image = request.files.get(
                "image"
            )

            filename = None

            if image and image.filename:

                if not allowed_image(
                    image.filename
                ):

                    flash(
                        "Invalid image type.",
                        "error"
                    )

                    return redirect(
                        url_for("admin_machines")
                    )

                original = secure_filename(
                    image.filename
                )

                extension = original.rsplit(
                    ".",
                    1
                )[1].lower()

                filename = (
                    uuid.uuid4().hex
                    + "."
                    + extension
                )

                image.save(
                    os.path.join(
                        MACHINE_DIR,
                        filename
                    )
                )

            machine = Machine(
                name=name,
                description=description,
                price=price,
                daily_profit=daily_profit,
                duration_days=max(
                    1,
                    duration_days
                ),
                stock=max(
                    0,
                    stock
                ),
                image_filename=filename,
                active=True
            )

            db.session.add(
                machine
            )

            db.session.commit()

            flash(
                "Machine added successfully. It is now available in the shop.",
                "success"
            )

            return redirect(
                url_for("admin_machines")
            )

        # ----------------------------------------------------
        # TOGGLE
        # ----------------------------------------------------
        elif action == "toggle":

            machine_id = int(
                request.form.get(
                    "machine_id"
                )
            )

            machine = db.session.get(
                Machine,
                machine_id
            )

            if machine:

                machine.active = not machine.active

                db.session.commit()

        # ----------------------------------------------------
        # DELETE
        # ----------------------------------------------------
        elif action == "delete":

            machine_id = int(
                request.form.get(
                    "machine_id"
                )
            )

            machine = db.session.get(
                Machine,
                machine_id
            )

            if machine:

                if machine.purchases:

                    flash(
                        "This machine has purchase records and cannot be deleted. Disable it instead.",
                        "error"
                    )

                else:

                    if machine.image_filename:

                        image_path = os.path.join(
                            MACHINE_DIR,
                            machine.image_filename
                        )

                        if os.path.exists(
                            image_path
                        ):
                            os.remove(
                                image_path
                            )

                    db.session.delete(
                        machine
                    )

                    db.session.commit()

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------
        elif action == "update":

            machine_id = int(
                request.form.get(
                    "machine_id"
                )
            )

            machine = db.session.get(
                Machine,
                machine_id
            )

            if machine:

                machine.name = request.form.get(
                    "name",
                    machine.name
                ).strip()

                machine.description = request.form.get(
                    "description",
                    machine.description
                ).strip()

                machine.price = float(
                    request.form.get(
                        "price",
                        machine.price
                    )
                )

                machine.daily_profit = float(
                    request.form.get(
                        "daily_profit",
                        machine.daily_profit
                    )
                )

                machine.duration_days = max(
                    1,
                    int(
                        request.form.get(
                            "duration_days",
                            machine.duration_days
                        )
                    )
                )

                machine.stock = max(
                    0,
                    int(
                        request.form.get(
                            "stock",
                            machine.stock
                        )
                    )
                )

                image = request.files.get(
                    "image"
                )

                if image and image.filename:

                    if allowed_image(
                        image.filename
                    ):

                        if machine.image_filename:

                            old_path = os.path.join(
                                MACHINE_DIR,
                                machine.image_filename
                            )

                            if os.path.exists(
                                old_path
                            ):
                                os.remove(
                                    old_path
                                )

                        original = secure_filename(
                            image.filename
                        )

                        extension = original.rsplit(
                            ".",
                            1
                        )[1].lower()

                        filename = (
                            uuid.uuid4().hex
                            + "."
                            + extension
                        )

                        image.save(
                            os.path.join(
                                MACHINE_DIR,
                                filename
                            )
                        )

                        machine.image_filename = filename

                db.session.commit()

                flash(
                    "Machine updated.",
                    "success"
                )

    machines = Machine.query.order_by(
        Machine.id.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Machine Management</h1>
        <p>
            Machines added here are immediately loaded from the database
            and displayed in the Shop when active and in stock.
        </p>
    </section>

    <div class="card">

        <h2>Add Machine</h2>

        <form class="form"
              method="POST"
              enctype="multipart/form-data">

            <input type="hidden"
                   name="action"
                   value="add">

            <label>
                Machine Name
            </label>

            <input
                name="name"
                required
                placeholder="Diamond Miner">

            <label>
                Description
            </label>

            <textarea
                name="description"></textarea>

            <label>
                Price (UGX)
            </label>

            <input
                type="number"
                name="price"
                min="0"
                step="1"
                required>

            <label>
                Daily Profit (UGX)
            </label>

            <input
                type="number"
                name="daily_profit"
                min="0"
                step="1"
                required>

            <label>
                Duration (days)
            </label>

            <input
                type="number"
                name="duration_days"
                min="1"
                value="20"
                required>

            <label>
                Stock
            </label>

            <input
                type="number"
                name="stock"
                min="0"
                value="10"
                required>

            <label>
                Machine Image
            </label>

            <input
                type="file"
                name="image"
                accept=".jpg,.jpeg,.png,.webp,.gif">

            <p class="muted small">
                Uploaded images are stored automatically in:
                static/machines/
            </p>

            <button class="btn"
                    type="submit">
                Add Machine
            </button>

        </form>

    </div>

    <br>

    <div class="grid">

    {% for machine in machines %}

        <div class="card">

            {% if machine.image_filename %}

                <img
                  class="machine-image"
                  src="{{ url_for(
                      'machine_image',
                      filename=machine.image_filename
                  ) }}"
                  alt="{{ machine.name }}">

            {% endif %}

            <h2>
                {{ machine.name }}
            </h2>

            <p>
                Price:
                {{ money(machine.price) }}
            </p>

            <p>
                Daily:
                {{ money(machine.daily_profit) }}
            </p>

            <p>
                Duration:
                {{ machine.duration_days }} days
            </p>

            <p>
                Stock:
                {{ machine.stock }}
            </p>

            <p>
                Expected total:
                {{ money(machine.total_return) }}
            </p>

            <p>
                Status:
                {{ "Active" if machine.active else "Disabled" }}
            </p>

            <form method="POST"
                  enctype="multipart/form-data"
                  class="form">

                <input type="hidden"
                       name="action"
                       value="update">

                <input type="hidden"
                       name="machine_id"
                       value="{{ machine.id }}">

                <input
                    name="name"
                    value="{{ machine.name }}"
                    required>

                <textarea
                    name="description">{{ machine.description }}</textarea>

                <input
                    type="number"
                    name="price"
                    value="{{ machine.price }}"
                    min="0"
                    step="1"
                    required>

                <input
                    type="number"
                    name="daily_profit"
                    value="{{ machine.daily_profit }}"
                    min="0"
                    step="1"
                    required>

                <input
                    type="number"
                    name="duration_days"
                    value="{{ machine.duration_days }}"
                    min="1"
                    required>

                <input
                    type="number"
                    name="stock"
                    value="{{ machine.stock }}"
                    min="0"
                    required>

                <input
                    type="file"
                    name="image"
                    accept=".jpg,.jpeg,.png,.webp,.gif">

                <button class="btn"
                        type="submit">
                    Save Changes
                </button>

            </form>

            <br>

            <form method="POST"
                  style="display:inline;">

                <input type="hidden"
                       name="action"
                       value="toggle">

                <input type="hidden"
                       name="machine_id"
                       value="{{ machine.id }}">

                <button class="btn secondary">
                    Toggle Active
                </button>

            </form>

            <form method="POST"
                  style="display:inline;">

                <input type="hidden"
                       name="action"
                       value="delete">

                <input type="hidden"
                       name="machine_id"
                       value="{{ machine.id }}">

                <button class="btn danger">
                    Delete
                </button>

            </form>

        </div>

    {% endfor %}

    </div>
    """

    return page(
        "Machine Management",
        render_template_string(
            content,
            machines=machines,
            money=format_money
        )
    )


# ============================================================
# ADMIN USERS / ADMINS
# ============================================================

@app.route(
    "/admin/users",
    methods=["GET", "POST"]
)
@admin_required
def admin_users():

    current_admin = current_user()

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        user_id = request.form.get(
            "user_id"
        )

        if action == "toggle":

            user = db.session.get(
                User,
                int(user_id)
            )

            if user and user.id != current_admin.id:

                user.is_active = not user.is_active

                db.session.commit()

        elif action == "make_admin":

            user = db.session.get(
                User,
                int(user_id)
            )

            if user:

                user.is_admin = True

                db.session.commit()

                flash(
                    "User is now an administrator.",
                    "success"
                )

        elif action == "remove_admin":

            user = db.session.get(
                User,
                int(user_id)
            )

            if user and user.id != current_admin.id:

                user.is_admin = False

                db.session.commit()

        elif action == "reset_password":

            user = db.session.get(
                User,
                int(user_id)
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            if user and new_password:

                user.set_password(
                    new_password
                )

                db.session.commit()

                flash(
                    "Password updated.",
                    "success"
                )

    users = User.query.order_by(
        User.created_at.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Users & Administrators</h1>
    </section>

    <div class="card">

    <div class="table-wrap">

    <table>

    <tr>
        <th>Phone</th>
        <th>Balance</th>
        <th>Admin</th>
        <th>Active</th>
        <th>Created</th>
        <th>Actions</th>
    </tr>

    {% for item in users %}

    <tr>

        <td>
            {{ item.phone }}
        </td>

        <td>
            {{ money(item.balance) }}
        </td>

        <td>
            {{ "Yes" if item.is_admin else "No" }}
        </td>

        <td>
            {{ "Yes" if item.is_active else "No" }}
        </td>

        <td>
            {{ item.created_at }}
        </td>

        <td>

            {% if item.id != current_admin.id %}

            <form method="POST"
                  style="margin-bottom:7px;">

                <input type="hidden"
                       name="action"
                       value="toggle">

                <input type="hidden"
                       name="user_id"
                       value="{{ item.id }}">

                <button class="btn secondary">
                    Enable / Disable
                </button>

            </form>

            {% if item.is_admin %}

            <form method="POST"
                  style="margin-bottom:7px;">

                <input type="hidden"
                       name="action"
                       value="remove_admin">

                <input type="hidden"
                       name="user_id"
                       value="{{ item.id }}">

                <button class="btn warning">
                    Remove Admin
                </button>

            </form>

            {% else %}

            <form method="POST"
                  style="margin-bottom:7px;">

                <input type="hidden"
                       name="action"
                       value="make_admin">

                <input type="hidden"
                       name="user_id"
                       value="{{ item.id }}">

                <button class="btn">
                    Make Admin
                </button>

            </form>

            {% endif %}

            <form method="POST">

                <input type="hidden"
                       name="action"
                       value="reset_password">

                <input type="hidden"
                       name="user_id"
                       value="{{ item.id }}">

                <input
                    name="new_password"
                    placeholder="New password"
                    required>

                <button class="btn secondary">
                    Reset Password
                </button>

            </form>

            {% endif %}

        </td>

    </tr>

    {% endfor %}

    </table>

    </div>

    </div>
    """

    return page(
        "Admin Users",
        render_template_string(
            content,
            users=users,
            current_admin=current_admin,
            money=format_money
        )
    )


# ============================================================
# ADMIN NOTIFICATIONS
# ============================================================

@app.route(
    "/admin/notifications",
    methods=["GET", "POST"]
)
@admin_required
def admin_notifications():

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        if action == "add":

            title = request.form.get(
                "title",
                ""
            ).strip()

            message = request.form.get(
                "message",
                ""
            ).strip()

            if title and message:

                db.session.add(
                    Notification(
                        title=title,
                        message=message,
                        active=True
                    )
                )

                db.session.commit()

                flash(
                    "Notification published.",
                    "success"
                )

        elif action == "toggle":

            notification_id = int(
                request.form.get(
                    "notification_id"
                )
            )

            item = db.session.get(
                Notification,
                notification_id
            )

            if item:

                item.active = not item.active

                db.session.commit()

        elif action == "delete":

            notification_id = int(
                request.form.get(
                    "notification_id"
                )
            )

            item = db.session.get(
                Notification,
                notification_id
            )

            if item:

                NotificationRead.query.filter_by(
                    notification_id=item.id
                ).delete()

                db.session.delete(
                    item
                )

                db.session.commit()

    notifications = Notification.query.order_by(
        Notification.created_at.desc()
    ).all()

    content = """
    <section class="hero">
        <h1>Notification Management</h1>
    </section>

    <div class="card">

        <h2>Publish Update</h2>

        <form class="form"
              method="POST">

            <input type="hidden"
                   name="action"
                   value="add">

            <label>
                Title
            </label>

            <input
                name="title"
                required>

            <label>
                Message
            </label>

            <textarea
                name="message"
                required></textarea>

            <button class="btn">
                Publish Notification
            </button>

        </form>

    </div>

    <br>

    <div class="grid">

    {% for item in notifications %}

        <div class="card">

            <h2>
                {{ item.title }}
            </h2>

            <p>
                {{ item.message }}
            </p>

            <p>
                Status:
                {{ "Active" if item.active else "Hidden" }}
            </p>

            <form method="POST"
                  style="display:inline;">

                <input type="hidden"
                       name="action"
                       value="toggle">

                <input type="hidden"
                       name="notification_id"
                       value="{{ item.id }}">

                <button class="btn secondary">
                    Toggle
                </button>

            </form>

            <form method="POST"
                  style="display:inline;">

                <input type="hidden"
                       name="action"
                       value="delete">

                <input type="hidden"
                       name="notification_id"
                       value="{{ item.id }}">

                <button class="btn danger">
                    Delete
                </button>

            </form>

        </div>

    {% endfor %}

    </div>
    """

    return page(
        "Notifications",
        render_template_string(
            content,
            notifications=notifications
        )
    )


# ============================================================
# ADMIN CHAT
# ============================================================

@app.route(
    "/admin/chat",
    methods=["GET", "POST"]
)
@admin_required
def admin_chat():

    if request.method == "POST":

        user_id = int(
            request.form.get(
                "user_id"
            )
        )

        message = request.form.get(
            "message",
            ""
        ).strip()

        user = db.session.get(
            User,
            user_id
        )

        if user and message:

            db.session.add(
                ChatMessage(
                    user_id=user.id,
                    sender="admin",
                    message=message
                )
            )

            db.session.commit()

            flash(
                "Reply sent.",
                "success"
            )

    users = User.query.filter(
        User.is_admin == False
    ).order_by(
        User.created_at.desc()
    ).all()

    selected_id = request.args.get(
        "user_id"
    )

    selected_user = None

    messages = []

    if selected_id:

        selected_user = db.session.get(
            User,
            int(selected_id)
        )

        if selected_user:

            messages = ChatMessage.query.filter_by(
                user_id=selected_user.id
            ).order_by(
                ChatMessage.created_at.asc()
            ).all()

    content = """
    <section class="hero">
        <h1>Admin Chat</h1>
    </section>

    <div class="grid">

        <div class="card">

            <h2>Users</h2>

            {% for item in users %}

            <p>
                <a class="btn secondary"
                   href="{{ url_for(
                       'admin_chat',
                       user_id=item.id
                   ) }}">
                    {{ item.phone }}
                </a>
            </p>

            {% endfor %}

        </div>

        <div class="card">

        {% if selected_user %}

            <h2>
                Chat:
                {{ selected_user.phone }}
            </h2>

            <div class="chat-box">

            {% for item in messages %}

                <div class="chat-message
                    {% if item.sender == 'admin' %}
                    admin
                    {% endif %}">

                    <strong>
                        {{ item.sender }}
                    </strong>

                    <p>
                        {{ item.message }}
                    </p>

                </div>

            {% endfor %}

            </div>

            <form method="POST"
                  class="form"
                  style="margin-top:15px;">

                <input type="hidden"
                       name="user_id"
                       value="{{ selected_user.id }}">

                <textarea
                    name="message"
                    required></textarea>

                <button class="btn">
                    Send Reply
                </button>

            </form>

        {% else %}

            <p class="muted">
                Select a user.
            </p>

        {% endif %}

        </div>

    </div>
    """

    return page(
        "Admin Chat",
        render_template_string(
            content,
            users=users,
            selected_user=selected_user,
            messages=messages
        )
    )


# ============================================================
# ADMIN CHART
# ============================================================

@app.route("/admin/chart")
@admin_required
def admin_chart():

    now = utc_now()

    labels = []
    deposit_values = []
    withdrawal_values = []
    joiner_values = []

    # Last 7 days.
    for offset in range(6, -1, -1):

        day = (
            now.date()
            - timedelta(days=offset)
        )

        start = datetime.combine(
            day,
            datetime.min.time()
        )

        end = start + timedelta(
            days=1
        )

        labels.append(
            day.strftime("%d %b")
        )

        deposits = db.session.query(
            db.func.coalesce(
                db.func.sum(
                    Deposit.amount
                ),
                0
            )
        ).filter(
            Deposit.status == "approved",
            Deposit.created_at >= start,
            Deposit.created_at < end
        ).scalar()

        withdrawals = db.session.query(
            db.func.coalesce(
                db.func.sum(
                    Withdrawal.net_amount
                ),
                0
            )
        ).filter(
            Withdrawal.status == "approved",
            Withdrawal.created_at >= start,
            Withdrawal.created_at < end
        ).scalar()

        joiners = User.query.filter(
            User.created_at >= start,
            User.created_at < end
        ).count()

        deposit_values.append(
            float(deposits or 0)
        )

        withdrawal_values.append(
            float(withdrawals or 0)
        )

        joiner_values.append(
            joiners
        )

    content = """
    <section class="hero">
        <h1>DATA4MINE Statistics</h1>
        <p>
            Seven-day deposit, withdrawal and joiner statistics.
        </p>
    </section>

    <div class="card">

        <canvas
            id="chart"
            height="120">
        </canvas>

    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script>

    const labels =
        {{ labels|tojson }};

    const deposits =
        {{ deposit_values|tojson }};

    const withdrawals =
        {{ withdrawal_values|tojson }};

    const joiners =
        {{ joiner_values|tojson }};

    new Chart(
        document.getElementById(
            "chart"
        ),
        {
            type: "line",

            data: {
                labels: labels,

                datasets: [

                    {
                        label:
                            "Approved Deposits",

                        data:
                            deposits,

                        tension: .3
                    },

                    {
                        label:
                            "Approved Withdrawals",

                        data:
                            withdrawals,

                        tension: .3
                    },

                    {
                        label:
                            "Joiners",

                        data:
                            joiners,

                        tension: .3
                    }

                ]
            },

            options: {
                responsive: true,

                plugins: {
                    legend: {
                        labels: {
                            color: "#ffffff"
                        }
                    }
                },

                scales: {
                    x: {
                        ticks: {
                            color: "#ffffff"
                        }
                    },

                    y: {
                        ticks: {
                            color: "#ffffff"
                        }
                    }
                }
            }
        }
    );

    </script>
    """

    return page(
        "Admin Statistics",
        render_template_string(
            content,
            labels=labels,
            deposit_values=deposit_values,
            withdrawal_values=withdrawal_values,
            joiner_values=joiner_values
        )
    )


# ============================================================
# ADMIN BACKGROUND IMAGE UPLOAD
# ============================================================

@app.route(
    "/admin/background",
    methods=["GET", "POST"]
)
@admin_required
def admin_background():

    if request.method == "POST":

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            if not allowed_image(
                image.filename
            ):

                flash(
                    "Invalid image type.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin_background"
                    )
                )

            original = secure_filename(
                image.filename
            )

            extension = original.rsplit(
                ".",
                1
            )[1].lower()

            filename = (
                "background."
                + extension
            )

            # Remove old background images.
            for existing in os.listdir(
                BACKGROUND_DIR
            ):

                existing_path = os.path.join(
                    BACKGROUND_DIR,
                    existing
                )

                if os.path.isfile(
                    existing_path
                ):

                    try:
                        os.remove(
                            existing_path
                        )
                    except Exception:
                        pass

            image.save(
                os.path.join(
                    BACKGROUND_DIR,
                    filename
                )
            )

            flash(
                "Background image uploaded.",
                "success"
            )

    content = """
    <section class="hero">
        <h1>Background Image</h1>
    </section>

    <div class="card">

        <p>
            Upload one machine/background image.
            The application looks for the latest
            background image in static/background/.
        </p>

        <form class="form"
              method="POST"
              enctype="multipart/form-data">

            <input
                type="file"
                name="image"
                accept=".jpg,.jpeg,.png,.webp,.gif"
                required>

            <button class="btn">
                Upload Background
            </button>

        </form>

    </div>
    """

    return page(
        "Background",
        content
    )


# ============================================================
# 404 / 500 ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    content = """
    <section class="hero">
        <h1>Page Not Found</h1>

        <p>
            The page you requested does not exist.
        </p>

        <a class="btn"
           href="{{ url_for('index') }}">
            Go Home
        </a>
    </section>
    """

    return page(
        "Page Not Found",
        content
    ), 404


@app.errorhandler(500)
def internal_error(error):

    # Roll back a failed database transaction.
    try:
        db.session.rollback()
    except Exception:
        pass

    content = """
    <section class="hero">
        <h1>Something Went Wrong</h1>

        <p>
            The server encountered an error.
            The database session has been reset.
        </p>

        <a class="btn"
           href="{{ url_for('index') }}">
            Return Home
        </a>
    </section>
    """

    return page(
        "Server Error",
        content
    ), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "app": "DATA4MINE"
    }


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )