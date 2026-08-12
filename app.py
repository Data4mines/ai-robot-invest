from flask import Flask, request, redirect, session
import time, sqlite3, hashlib, re, uuid, os

app = Flask(__name__, static_folder='static')
app.secret_key = "data4mines_pro_v16_5"

DB = "data4mines.db"
ADMIN_PHONE = "0792759363"
TAX_RATE = 0.08
BUY_REWARD = 10000
REFER_REWARD = 5000
DEFAULT_IMG = "/static/machines/ai_titan.jpg"

def hash(p): return hashlib.sha256(p.encode()).hexdigest()

def init_db():
    print("CREATING DATABASE NOW...")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, phone TEXT UNIQUE, password TEXT, balance INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0, ref_code TEXT, referred_by INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS deposit_numbers (id INTEGER PRIMARY KEY, number TEXT, names TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, approval_msg TEXT, status TEXT, time REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER, tax INTEGER, net_amount INTEGER, phone TEXT, names TEXT, network TEXT, status TEXT, request_time REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, time REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, message TEXT, time REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY, name TEXT, price INTEGER, daily INTEGER, lock_days INTEGER, img TEXT, total_earn INTEGER, is_vip INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS user_machines (id INTEGER PRIMARY KEY, user_id INTEGER, machine_id INTEGER, buy_time REAL, end_time REAL, earned INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS admin_wallet (id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, pin TEXT)')

    c.execute("SELECT COUNT(*) FROM admin_wallet")
    if c.fetchone()[0] == 0: c.execute("INSERT INTO admin_wallet(balance,pin) VALUES(0,'1234')")

    c.execute("SELECT COUNT(*) FROM deposit_numbers")
    if c.fetchone()[0] == 0: c.execute("INSERT INTO deposit_numbers(number,names) VALUES(?,?)", ("0792759363", "NUWAHEREZA CHRISTINE"))

    c.execute("SELECT COUNT(*) FROM shop")
    if c.fetchone()[0] == 0:
        machines = []
        normal_imgs = ["/static/machines/ai_infinity.jpg","/static/machines/ai_master.jpg","/static/machines/ai_pro.jpg","/static/machines/ai_quantum.jpg","/static/machines/ai_super.jpg"]
        for i in range(20):
            price = 10000 + (i * 25000)
            daily = int(price * 0.15)
            lock = 15
            total = daily * lock
            img = normal_imgs[i % len(normal_imgs)]
            machines.append(("AI Miner #" + str(i+1), price, daily, lock, img, total, 0))

        vip_data = [
            ("VIP AI TITAN", 1000000, "/static/machines/ai_titan.jpg"),
            ("VIP AI ULTRA", 2000000, "/static/machines/ai_ultra.jpg"),
            ("VIP AI QUANTUM", 3500000, "/static/machines/ai_quantum.jpg"),
            ("VIP AI SUPER", 5000000, "/static/machines/ai_super.jpg"),
            ("VIP AI MASTER", 6500000, "/static/machines/ai_master.jpg"),
            ("VIP AI INFINITY", 7000000, "/static/machines/ai_infinity.jpg"),
            ("VIP AI PRO", 8000000, "/static/machines/ai_pro.jpg"),
            ("VIP AI ELITE", 9000000, "/static/machines/ai_titan.jpg"),
            ("VIP AI KING", 9500000, "/static/machines/ai_ultra.jpg"),
            ("VIP AI GOD", 10000000, "/static/machines/ai_quantum.jpg"),
        ]
        for i, (name, price, img) in enumerate(vip_data):
            daily = int(price * 0.20)
            lock = 7
            total = daily * lock
            machines.append((name, price, daily, lock, img, total, 1))
        c.executemany("INSERT INTO shop(name,price,daily,lock_days,img,total_earn,is_vip) VALUES(?,?,?,?,?,?,?)", machines)

    ref_code_admin = "ADMIN" + str(uuid.uuid4())[:4]
    c.execute("INSERT OR IGNORE INTO users(phone,password,is_admin,ref_code) VALUES(?,?,1,?)", (ADMIN_PHONE, hash("1234"), ref_code_admin))
    c.execute("UPDATE users SET is_admin=1, ref_code=? WHERE phone=?", (ref_code_admin, ADMIN_PHONE))
    conn.commit(); conn.close()
    print("DATABASE CREATED SUCCESSFULLY")

init_db()

def is_admin(uid):
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id=?", (uid,)); r = c.fetchone(); conn.close()
    return r and r[0] == 1
def notify_user(uid, msg):
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("INSERT INTO notifications(user_id,message,time) VALUES(?,?,?)", (uid, msg, time.time()))
    conn.commit(); conn.close()
def notify_all(msg):
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT id FROM users"); users = c.fetchall()
    for u in users: c.execute("INSERT INTO notifications(user_id,message,time) VALUES(?,?,?)", (u[0], msg, time.time()))
    conn.commit(); conn.close()
def get_deposit_numbers():
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT number,names FROM deposit_numbers"); nums = c.fetchall(); conn.close()
    return nums
def check_sms_valid(sms, expected_amount):
    sms = sms.upper()
    numbers = get_deposit_numbers()
    amount_found = re.findall(r'\d+', sms)
    amount_found = int(amount_found[0]) if amount_found else 0
    if amount_found!= expected_amount: return False, "Amount mismatch"
    number_ok = any(n[0] in sms for n in numbers)
    if not number_ok: return False, "Number not ours"
    name_ok = any(n[1].split()[0] in sms for n in numbers)
    if not name_ok: return False, "Name not ours"
    return True, "OK"
def safe_img(img_path):
    full_path = os.path.join("static/machines", os.path.basename(img_path))
    if not os.path.exists(full_path): return DEFAULT_IMG
    return img_path

def layout(title, body, uid=None):
    notes_html = ""
    if uid:
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("SELECT message FROM notifications WHERE user_id=? ORDER BY time DESC LIMIT 5", (uid,))
        notes = c.fetchall(); conn.close()
        for n in notes: notes_html += "<div class='alert'>📢 " + n[0] + "</div>"
        notes_html = "<div class='card'><h3>Notifications</h3>" + notes_html + "</div>"

    links = "<a href='/'>Home</a> <a href='/about'>About</a> <a href='/shop'>Shop</a> <a href='/my-machines'>My Machines</a> <a href='/referrals'>Referrals</a> <a href='/deposit'>Deposit</a> <a href='/withdraw'>Withdraw</a> <a href='/chat'>💬 Chat</a>"
    if uid and is_admin(uid): links += " <a href='/admin'>Admin</a>"
    if not uid: links = "<a href='/about'>About</a> <a href='/login'>Login</a> <a href='/register'>Register</a>"

    css = "body{background:#0a0a0a;color:#fff;font-family:Segoe UI;margin:0}header{background:linear-gradient(90deg,#FFD700,#FFA500);color:#000;text-align:center;padding:15px}nav{background:#111;text-align:center;padding:12px}a{color:#FFD700;margin:0 10px;text-decoration:none;font-weight:bold}.container{padding:20px;max-width:1200px;margin:auto}.card{background:#1a1a1a;padding:20px;border-radius:12px;margin:15px 0;text-align:center;border:1px solid #333}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}img{width:100%;height:150px;object-fit:cover;border-radius:8px;background:#222}button{background:#FFD700;color:#000;border:none;padding:10px 15px;border-radius:12px;font-weight:bold;cursor:pointer;margin:5px}button.del{background:#FF0000;color:#fff}input,select,textarea{padding:12px;background:#222;color:#fff;border:1px solid #444;border-radius:8px;width:90%;margin:5px 0}.balance{color:#00FF88;font-size:22px;font-weight:bold}.profit{color:#FFD700}.total{color:#00FFFF;font-size:24px}.tax{color:#FFA500}.vip{color:#FFD700;border:2px solid #FFD700;background:#2a1a00}.alert{background:#2a1a00;padding:10px;border-radius:8px;border:1px solid #FFD700;margin:8px 0}.copy-btn{background:#333;color:#FFD700}.chat-box{height:300px;overflow-y:auto;background:#111;padding:10px;border-radius:8px;text-align:left}.msg-me{text-align:right;color:#00FF88}.msg-them{text-align:left;color:#FFD700}"
    js = "<script>function copyNum(n){navigator.clipboard.writeText(n);alert('Copied: '+n)} function togglePass(){var x=document.getElementById('pass');x.type=x.type==='password'?'text':'password'} function copyRef(){var c=document.getElementById('ref');navigator.clipboard.writeText(c.value);alert('Referral Link Copied!')}</script>"
    return "<!DOCTYPE html><html><head><title>" + title + "</title><style>" + css + "</style></head><body>" + js + "<header><h1>DATA 4MINES</h1></header><nav>" + links + "</nav><div class='container'>" + notes_html + body + "</div></body></html>"

@app.route("/")
def dashboard():
    if not session.get("uid"): return redirect("/login")
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (session['uid'],))
row = c.fetchone()
bal = row[0] if row else 0.0 # This prevents the crash
conn.close()
    body = "<div class='card'><h2>Welcome to DATA 4MINES</h2><h3>For Real and Good Profits</h3><p>Balance: <span class='balance'>" + str(bal) + " UGX</span></p><a href='/shop'><button>Buy Machines</button></a></div>"
    return layout("Dashboard", body, session["uid"])

@app.route("/about")
def about():
    body = "<div class='card'><h2>About DATA 4MINES</h2><p>The company began in USA New York in 2015 and is spreading to every continent. It came to East Africa in 2022 and signed a contract of $17 Billions with East African banks and network systems.</p></div>"
    return layout("About Us", body, session.get("uid"))

@app.route("/referrals")
def referrals():
    if not session.get("uid"): return redirect("/login")
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT ref_code FROM users WHERE id=?", (session["uid"],)); row = c.fetchone()
    ref_code = row[0] if row and row[0] else None
    if not ref_code:
        ref_code = "REF" + str(uuid.uuid4())[:6]
        c.execute("UPDATE users SET ref_code=? WHERE id=?", (ref_code, session["uid"]))
        conn.commit()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (session["uid"],)); count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM user_machines um JOIN users u ON um.user_id=u.id WHERE u.referred_by=?", (session["uid"],)); bought = c.fetchone()[0]
    link = request.host_url + "register?ref=" + str(ref_code)
    conn.close()
    body = "<div class='card'><h2>Referral Program</h2><p>Earn <b class='balance'>" + str(REFER_REWARD) + " UGX</b> for each friend who buys</p><p>Your Referrals: " + str(count) + "</p><p>Friends who bought: " + str(bought) + "</p><p>Your Link:</p><input id='ref' value='" + link + "' readonly><br><button onclick='copyRef()'>Copy Link</button></div>"
    return layout("Referrals", body, session["uid"])

@app.route("/shop")
def shop():
    if not session.get("uid"): return redirect("/login")
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT * FROM shop ORDER BY is_vip, price"); machines = c.fetchall(); conn.close()
    body = "<h2>Machine Shop - 30 Machines</h2><div class='grid'>"
    for m in machines:
        img = safe_img(m[5])
        vip_class = "vip" if m[7] == 1 else ""
        vip_tag = "<p class='vip'>VIP MACHINE - 7 DAYS</p>" if m[7] == 1 else "<p>Lock: " + str(m[4]) + " Days</p>"
        btn = "<form method=post action='/buy/" + str(m[0]) + "'><button>Buy Now</button></form>"
        body += "<div class='card " + vip_class + "'><img src='" + img + "'>" + vip_tag + "<h3>" + m[1] + "</h3><p>Cost: <b class='balance'>" + str(m[2]) + " UGX</b></p><p>Profit: <span class='profit'>" + str(m[6]) + " UGX</span></p><p>Total Return: <span class='total'>" + str(m[2] + m[6]) + " UGX</span></p><p>Earn: " + str(m[3]) + " UGX/day</p>" + btn + "</div>"
    return layout("Shop", body + "</div>", session["uid"])

@app.route("/buy/<int:mid>", methods=["POST"])
def buy(mid):
    if not session.get("uid"): return redirect("/login")
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT price,lock_days FROM shop WHERE id=?", (mid,)); price, lock = c.fetchone()
    c.execute("SELECT balance,referred_by FROM users WHERE id=?", (session["uid"],)); bal, ref = c.fetchone()
    if bal >= price:
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (price, session["uid"]))
        end_time = time.time() + (lock * 24 * 3600)
        c.execute("INSERT INTO user_machines(user_id,machine_id,buy_time,end_time) VALUES(?,?,?,?)", (session["uid"], mid, time.time(), end_time))
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (BUY_REWARD, session["uid"]))
        notify_user(session["uid"], "🎁 Reward: " + str(BUY_REWARD) + " UGX")
        if ref:
            c.execute("UPDATE users SET balance=balance+? WHERE id=?", (REFER_REWARD, ref))
            notify_user(ref, "🎁 Referral Reward: " + str(REFER_REWARD) + " UGX")
    conn.commit(); conn.close()
    return redirect("/my-machines")

@app.route("/my-machines")
def my_machines():
    if not session.get("uid"): return redirect("/login")
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT um.id,s.name,s.price,s.daily,s.lock_days,s.is_vip,s.total_earn FROM user_machines um JOIN shop s ON um.machine_id=s.id WHERE um.user_id=?", (session["uid"],))
    machines = c.fetchall(); conn.close()
    body = "<h2>My Machines</h2><div class='grid'>"
    for m in machines:
        vip_tag = "<p class='vip'>VIP - 7 DAYS</p>" if m[5] == 1 else "<p>Normal - 15 Days</p>"
        total_return = m[2] + m[6]
        body += "<div class='card'><h3>" + m[1] + "</h3>" + vip_tag + "<p>Cost: <b class='balance'>" + str(m[2]) + " UGX</b></p><p>Profit: <span class='profit'>" + str(m[6]) + " UGX</span></p><p>Total Return: <span class='total'>" + str(total_return) + " UGX</span></p><p>Earn: " + str(m[3]) + " UGX/day</p></div>"
    return layout("My Machines", body + "</div>", session["uid"])

@app.route("/withdraw", methods=["GET","POST"])
def withdraw():
    if not session.get("uid"): return redirect("/login")
    if request.method == "POST":
        amt = int(request.form["amount"])
        tax = int(amt * TAX_RATE)
        net = amt - tax
        phone = request.form["phone"]
        names = request.form["names"]
        network = request.form["network"]
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amt, session["uid"]))
        c.execute("INSERT INTO withdrawals(user_id,amount,tax,net_amount,phone,names,network,status,request_time) VALUES(?,?,?,?,?,?,?,?,?)", (session["uid"], amt, tax, net, phone, names, network, "PENDING", time.time()))
        conn.commit(); conn.close()
        notify_user(session["uid"], "Withdrawal request of " + str(amt) + " UGX submitted. 8% tax: " + str(tax) + " UGX")
        return layout("Success", "<div class='card'><h2>Withdrawal Requested</h2><p>Requested: " + str(amt) + " UGX</p><p class='tax'>Tax 8%: " + str(tax) + " UGX</p><p>You will receive: " + str(net) + " UGX</p></div>", session["uid"])
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id=?", (session["uid"],)); bal = c.fetchone()[0]; conn.close()
    body = "<h2>Withdraw</h2><div class='card'><p>Your Balance: " + str(bal) + " UGX</p><p class='tax'>⚠️ 8% tax deducted</p><form method=post><input name=amount type=number placeholder='Amount' required><br><input name=phone placeholder='Number' required><br><input name=names placeholder='Full Names' required><br><select name=network><option>MTN</option><option>AIRTEL</option></select><br><button>Request</button></form></div>"
    return layout("Withdraw", body, session["uid"])

@app.route("/chat", methods=["GET","POST"])
def chat():
    if not session.get("uid"): return redirect("/login")
    admin_id = 1
    if request.method == "POST":
        msg = request.form["message"]
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("INSERT INTO chat(sender_id,receiver_id,message,time) VALUES(?,?,?,?)", (session["uid"], admin_id, msg, time.time()))
        conn.commit(); conn.close()
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT sender_id,message FROM chat WHERE sender_id=? OR receiver_id=? ORDER BY time", (session["uid"], session["uid"]))
    msgs = c.fetchall(); conn.close()
    body = "<h2>Chat with Admin</h2><div class='card'><div class='chat-box'>"
    for m in msgs: cls = "msg-me" if m[0] == session["uid"] else "msg-them"; body += "<div class='" + cls + "'>" + m[1] + "</div>"
    body += "</div><form method=post><input name=message placeholder='Type message'><button>Send</button></form></div>"
    return layout("Chat", body, session["uid"])

@app.route("/admin")
def admin():
    if not session.get("uid") or not is_admin(session["uid"]): return "Access Denied"
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT balance FROM admin_wallet WHERE id=1"); wallet = c.fetchone()[0]
    c.execute("SELECT id,user_id,amount,tax,net_amount,phone,names,network FROM withdrawals WHERE status='PENDING'"); wd = c.fetchall()
    c.execute("SELECT * FROM shop ORDER BY id"); machines = c.fetchall(); conn.close()

    body = "<h2>Admin Panel</h2>"
    body += "<div class='card'><h3>Company Wallet: " + str(wallet) + " UGX</h3></div>"
    body += "<div class='card'><h3>Add New Machine</h3><form method=post action='/add_machine'><input name=name placeholder='Machine Name' required><br><input name=price type=number placeholder='Price' required><br><input name=daily type=number placeholder='Daily Earn' required><br><input name=lock type=number placeholder='Lock Days' required><br><input name=img placeholder='Image path'><br><select name=is_vip><option value=0>Normal</option><option value=1>VIP</option></select><br><button>Add Machine</button></form></div>"

    body += "<div class='card'><h3>Manage Machines</h3><div class='grid'>"
    for m in machines:
        img = safe_img(m[5])
        body += "<div class='card'><img src='" + img + "'><h4>" + m[1] + "</h4><p>" + str(m[2]) + " UGX</p><form method=post action='/delete_machine/" + str(m[0]) + "'><button class='del'>Delete</button></form></div>"
    body += "</div></div>"

    body += "<div class='card'><h3>Pending Withdrawals</h3>"
    for w in wd: body += "<form method=post action='/approve_wd/" + str(w[0]) + "'><p>UserID: " + str(w[1]) + " | Requested: " + str(w[2]) + " UGX</p><p class='tax'>Tax 8%: " + str(w[3]) + " UGX | You Send: " + str(w[4]) + " UGX</p><p>To: " + w[5] + " | " + w[6] + " | " + w[7] + "</p><input name=pin type=password placeholder='PIN' required><button>Approve</button></form>"
    body += "</div><div class='card'><h3>Send Notification to All</h3><form method=post action='/notify_all'><textarea name=msg placeholder='Update message' rows=3 required></textarea><br><button>Send</button></form></div>"
    return layout("Admin", body, session["uid"])

@app.route("/add_machine", methods=["POST"])
def add_machine():
    if not is_admin(session["uid"]): return "Access Denied"
    name = request.form["name"]
    price = int(request.form["price"])
    daily = int(request.form["daily"])
    lock = int(request.form["lock"])
    img = request.form["img"] or DEFAULT_IMG
    is_vip = int(request.form["is_vip"])
    total = daily * lock
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("INSERT INTO shop(name,price,daily,lock_days,img,total_earn,is_vip) VALUES(?,?,?,?,?,?,?)", (name, price, daily, lock, img, total, is_vip))
    conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/delete_machine/<int:mid>", methods=["POST"])
def delete_machine(mid):
    if not is_admin(session["uid"]): return "Access Denied"
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("DELETE FROM shop WHERE id=?", (mid,))
    conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/approve_wd/<int:w_id>", methods=["POST"])
def approve_wd(w_id):
    if not is_admin(session["uid"]): return "Access Denied"
    pin = request.form["pin"]
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("SELECT pin,balance FROM admin_wallet WHERE id=1"); db_pin, wallet_bal = c.fetchone()
    c.execute("SELECT user_id,amount,tax,net_amount FROM withdrawals WHERE id=?", (w_id,)); w = c.fetchone()
    if pin!= db_pin: return layout("Error", "<div class='card'><h2 class='rejected'>Wrong PIN</h2></div>", session["uid"])
    if wallet_bal < w[3]: return layout("Error", "<div class='card'><h2 class='rejected'>Wallet Low</h2></div>", session["uid"])
    c.execute("UPDATE admin_wallet SET balance=balance-?", (w[3],))
    c.execute("UPDATE admin_wallet SET balance=balance+?", (w[2],))
    c.execute("UPDATE withdrawals SET status='APPROVED' WHERE id=?", (w_id,))
    notify_user(w[0], "✅ Withdrawal SUCCESSFUL. Requested: " + str(w[1]) + " UGX. Tax 8%: " + str(w[2]) + " UGX. You received: " + str(w[3]) + " UGX")
    conn.commit(); conn.close()
    return redirect("/admin")

@app.route("/notify_all", methods=["POST"])
def notify_all_route():
    if not is_admin(session["uid"]): return "Access Denied"
    msg = request.form["msg"]
    notify_all(msg)
    return redirect("/admin")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        phone = request.form["phone"]; password = request.form["password"]
        ref = request.args.get("ref") or request.form.get("ref")
        ref_id = None
        if ref:
            conn = sqlite3.connect(DB); c = conn.cursor()
            c.execute("SELECT id FROM users WHERE ref_code=?", (ref,)); r = c.fetchone()
            if r: ref_id = r[0]; conn.close()
        conn = sqlite3.connect(DB); c = conn.cursor()
        try:
            ref_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users(phone,password,ref_code,referred_by) VALUES(?,?,?,?)", (phone, hash(password), ref_code, ref_id))
            c.execute("SELECT id FROM users WHERE phone=?", (phone,)); user = c.fetchone()
            conn.commit(); conn.close()
            session["uid"] = user[0]
            return redirect("/")
        except:
            conn.close()
            return layout("Error", "<div class='card'><h2 class='rejected'>Phone already registered</h2></div>", None)
    return layout("Register", "<h2>Register</h2><div class='card'><form method=post><input name=phone placeholder='Phone'><br><input id='pass' name=password type=password placeholder='Password'> <button type='button' onclick='togglePass()'>👁️</button><br><input name=ref placeholder='Referral Code Optional'><br><button>Register</button></form></div>", None)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"]; password = request.form["password"]
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute("SELECT id FROM users WHERE phone=? AND password=?", (phone, hash(password))); user = c.fetchone(); conn.close()
        if user: session["uid"] = user[0]; return redirect("/")
    return layout("Login", "<h2>Login</h2><div class='card'><form method=post><input name=phone placeholder='Phone'><br><input id='pass' name=password type=password placeholder='Password'> <button type='button' onclick='togglePass()'>👁️</button><br><button>Login</button></form></div>", None)

import re
from datetime import datetime

def create_deposit_table():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS deposit
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  sms_text TEXT,
                  status TEXT DEFAULT "approved",
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

create_deposit_table() # runs once when app starts

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'uid' not in session:
        return redirect('/login')
        
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Get current balance
    c.execute("SELECT balance FROM user WHERE id =?", (session['uid'],))
    row = c.fetchone()
    balance = row[0] if row and row[0] else 0.0
    success_amount = request.args.get('success')

    if request.method == 'POST':
        sms = request.form['sms']
        amount_input = float(request.form['amount'])
        
        # Auto-read amount from SMS
        match = re.search(r'(\d[\d,]*)\s*UGX', sms, re.IGNORECASE)
        amount = amount_input
        if match:
            amount = float(match.group(1).replace(',', ''))

        # 1. Add to user balance
        c.execute("UPDATE user SET balance = balance +? WHERE id =?", (amount, session['uid']))
        
        # 2. Save deposit record
        c.execute("INSERT INTO deposit (user_id, amount, sms_text) VALUES (?,?,?)", 
                  (session['uid'], amount, sms))
        
        conn.commit()
        conn.close()
        
        return redirect('/deposit?success=' + str(amount))
    
    conn.close()
    return render_template('deposit.html', balance=balance, success=float(success_amount) if success_amount else None)

if __name__=="__main__": app.run(debug=True)