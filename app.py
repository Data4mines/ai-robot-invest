from flask import Flask, request, redirect, session
import time, sqlite3, hashlib, uuid, os, re
from datetime import datetime

app = Flask(__name__, static_folder='static')
app.secret_key = "data4mines_final_v31_full"

DB = "data4mines.db"
WITHDRAW_TAX = 0.08
REFER_REWARD = 5000
BUY_REWARD = 2000
BG_COLOR = "#000"
TEXT_COLOR = "#87CEFA" # LIGHT BLUE
ADMIN_USERNAME = "Twix"
ADMIN_PASSWORD = "1831"

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def get_db(): conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; return conn

def init_db():
    if not os.path.exists('static/machines'): os.makedirs('static/machines')
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, balance REAL DEFAULT 0.0, phone TEXT, refer_code TEXT UNIQUE, referred_by TEXT, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, created_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, network TEXT, proof TEXT, tx_id TEXT, sender_number TEXT, sender_name TEXT, deposit_date TEXT, status TEXT DEFAULT 'approved', created_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdraws(id INTEGER PRIMARY KEY, user_id INTEGER, amount_requested REAL, amount_to_send REAL, phone TEXT, network TEXT, status TEXT DEFAULT 'pending', created_at REAL, approved_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS machines(id INTEGER PRIMARY KEY, name TEXT, price REAL, profit REAL, days INTEGER, img TEXT, stock INTEGER DEFAULT 100, is_vip INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_machines(id INTEGER PRIMARY KEY, user_id INTEGER, machine_id INTEGER, bought_at REAL, days_left INTEGER, daily_profit REAL, last_paid REAL, total_earned REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, message TEXT, created_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS about(id INTEGER PRIMARY KEY, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals(id INTEGER PRIMARY KEY, referrer_code TEXT, referee_id INTEGER, has_bought INTEGER DEFAULT 0, created_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_numbers(id INTEGER PRIMARY KEY, network TEXT, account_name TEXT, number TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, user_id INTEGER, sender TEXT, message TEXT, created_at REAL)''')

    c.execute("INSERT OR IGNORE INTO about(id,content) VALUES(1,?)",("DATA 4MINES VIP 3-7 Days",))
    c.execute("INSERT OR IGNORE INTO deposit_numbers(network,account_name,number) VALUES(?,?,?)",("MTN Mobile Money","Nuwahereza Christine","+256792759363"))
    c.execute("INSERT OR IGNORE INTO users(username,password,phone,refer_code,is_admin,created_at) VALUES(?,?,?,?,?,?)",(ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "0792759363", "ADMIN123", 1, time.time()))
    conn.commit(); conn.close()

init_db()

def scan_sms(sms):
    amount = re.search(r'(?:deposited|received)\s*([0-9,]+)\s*UGX', sms, re.I)
    tx_id = re.search(r'(?:TX|Ref|Transaction)\s*ID[:\s]*([A-Z0-9]+)', sms, re.I)
    number = re.search(r'(?:to|from)\s*(\+?256[0-9]{9}|07[0-9]{8})', sms, re.I)
    name = re.search(r'(?:to|from)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)', sms)
    return {'amount': int(amount.group(1).replace(',','')) if amount else 0,'tx_id': tx_id.group(1) if tx_id else 'N/A','number': number.group(1) if number else 'N/A','name': name.group(1).strip() if name else 'N/A','date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def update_profits():
    conn = get_db(); c = conn.cursor(); now = time.time()
    c.execute("SELECT id,user_id,daily_profit,days_left,last_paid,total_earned FROM user_machines WHERE days_left>0")
    for um in c.fetchall():
        um_id, user_id, daily, days, last, earned = um
        if last is None: last = now - 86400
        if now - last >= 86400:
            c.execute("UPDATE users SET balance = balance +? WHERE id=?",(daily,user_id))
            c.execute("UPDATE user_machines SET days_left = days_left -1, last_paid=?, total_earned=total_earned+? WHERE id=?",(now,daily,um_id))
    conn.commit(); conn.close()

def auto_approve_withdraws():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM withdraws WHERE status='pending' AND created_at <?", (time.time() - 86400,))
    for row in c.fetchall(): c.execute("UPDATE withdraws SET status='approved', approved_at=? WHERE id=?",(time.time(),row['id']))
    conn.commit(); conn.close()

def get_user():
    if 'uid' in session:
        update_profits(); auto_approve_withdraws()
        conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM users WHERE id=?", (session['uid'],)); u = c.fetchone(); conn.close(); return u
    return None

def format_number(n): return f"{n:,.0f}"
def time_left(seconds):
    if seconds < 0: return "0d 0h"
    d = int(seconds // 86400); h = int((seconds % 86400) // 3600)
    return f"{d}d {h}h"

def page_wrap(content, u=None, show_notif=True):
    top = f'<div style="display:flex;justify-content:space-between;padding:12px 20px;background:#000;position:fixed;top:0;width:100%;border-bottom:2px solid #ffcc00;"><h3 style="color:{TEXT_COLOR}">DATA4MINES</h3><a href="/notifications" style="color:white;font-size:28px;">🔔</a></div>' if u and show_notif else ''
    bottom = f'''<div style="display:flex;justify-content:space-around;padding:12px;background:#000;position:fixed;bottom:0;width:100%;border-top:2px solid #ffcc00;">
    <a href="/dashboard" style="color:{TEXT_COLOR}">🏠<br><span style="font-size:11px;">Home</span></a>
    <a href="/machines" style="color:{TEXT_COLOR}">🏪<br><span style="font-size:11px;">Shop</span></a>
    <a href="/my_machines" style="color:{TEXT_COLOR}">🤖<br><span style="font-size:11px;">Mine</span></a>
    <a href="/chat" style="color:{TEXT_COLOR}">💬<br><span style="font-size:11px;">Chat</span></a>
    <a href="/deposit" style="color:{TEXT_COLOR}">💰<br><span style="font-size:11px;">Deposit</span></a>
    <a href="/withdraw" style="color:{TEXT_COLOR}">💸<br><span style="font-size:11px;">Withdraw</span></a>
    <a href="/refer" style="color:{TEXT_COLOR}">🔗<br><span style="font-size:11px;">Refer</span></a>
    {'<a href="/admin" style="color:'+TEXT_COLOR+'">⚙️<br><span style="font-size:11px;">Admin</span></a>' if u and u['is_admin']==1 else ''}
    </div>''' if u else ''
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>DATA4MINES</title><style>body{{background:#000;color:{TEXT_COLOR};font-size:16px;font-family:Arial;padding:70px 20px 90px;}}a{{color:{TEXT_COLOR};text-decoration:none;}}input,button,textarea,select{{font-size:16px;width:100%;padding:14px;margin:10px 0;border-radius:10px;border:1px solid #ffcc00;background:#111;color:{TEXT_COLOR};}}.btn{{padding:16px;background:#ffcc00;color:black;border:none;font-weight:bold;border-radius:10px;width:100%;}}.card{{background:#111;padding:18px;border-radius:15px;margin:15px 0;border:1px solid #ffcc00;}}.success{{background:#005500;padding:12px;border-radius:8px;color:#00ff00;}}.warning{{background:#550000;padding:12px;border-radius:8px;color:yellow;}}.total-return{{color:#00ff00;font-weight:bold;}}table{{width:100%;border-collapse:collapse;font-size:14px;}}td,th{{border:1px solid #ffcc00;padding:8px;text-align:left;}}.soldout{{background:#550000;color:red;}}</style></head><body>{top}<div>{content}</div>{bottom}</body></html>'

@app.route('/')
def home(): return redirect('/register')
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']; p = hash_password(request.form['password']); phone = request.form['phone']; code = str(uuid.uuid4())[:8].upper(); ref = request.form.get('refer_code','')
        conn = get_db(); c = conn.cursor()
        try: c.execute("INSERT INTO users(username,password,phone,refer_code,referred_by,created_at) VALUES(?,?,?,?,?,?)",(u,p,phone,code,ref,time.time())); session['uid'] = c.lastrowid
        except: conn.close(); return page_wrap('<div class="card"><h3>Username taken</h3></div>', None, False)
        if ref: c.execute("INSERT INTO referrals(referrer_code,referee_id,created_at) VALUES(?,?,?)",(ref,c.lastrowid,time.time()))
        conn.commit(); conn.close(); return redirect('/dashboard')
    return page_wrap(f'<div class="card"><h2>Register</h2><form method=post>Username: <input name=username required>Password: <input name=password required>Phone: <input name=phone required>Refer Code: <input name=refer_code placeholder="Optional"><button class="btn">Register</button></form><p><a href=/login>Login</a></p></div>', None, False)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']; p = hash_password(request.form['password'])
        conn = get_db(); c = conn.cursor(); c.execute("SELECT id FROM users WHERE username=? AND password=?",(u,p)); user = c.fetchone(); conn.close()
        if user: session['uid']=user['id']; return redirect('/dashboard')
    return page_wrap('<div class="card"><h2>Login</h2><form method=post>Username: <input name=username required>Password: <input name=password required><button class="btn">Login</button></form></div>', None, False)

@app.route('/dashboard')
def dashboard():
    u = get_user();
    if not u: return redirect('/login')
    return page_wrap(f'<h2>Welcome {u["username"]}</h2><div class="card"><h3>Balance: {format_number(u["balance"])} UGX</h3></div>', u)

@app.route('/deposit', methods=['GET','POST'])
def deposit():
    u = get_user()
    if request.method == 'POST':
        try: entered_amount = float(request.form['amount'])
        except: return page_wrap('<div class="card"><h3>Enter valid amount</h3></div>', u)
        proof = request.form['proof']; data = scan_sms(proof); scanned_amount = data['amount']
        if scanned_amount == 0: return page_wrap('<div class="card"><h3>Could not read amount from SMS</h3></div>', u)
        if scanned_amount!= entered_amount: return page_wrap(f'<div class="card"><h3 style="color:red;">❌ Amount Mismatch!</h3></div>', u)
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM deposit_numbers WHERE number=?",(data['number'],))
        if not c.fetchone(): conn.close(); return page_wrap(f'<div class="card"><h3 style="color:red;">❌ Invalid Number!</h3></div>', u)
        c.execute("UPDATE users SET balance = balance +? WHERE id=?",(scanned_amount,u['id']))
        c.execute("INSERT INTO deposits(user_id,amount,network,proof,tx_id,sender_number,sender_name,deposit_date,status,created_at) VALUES(?,?,?,?,?,?)",
                  (u['id'],scanned_amount,'Scanned',proof,data['tx_id'],data['number'],data['name'],data['date'],'approved',time.time()))
        conn.commit(); conn.close()
        return page_wrap(f'''<div class="success"><h3>✅ Deposit Approved!</h3><p>Amount: {format_number(scanned_amount)} UGX<br>TX ID: {data['tx_id']}</p></div><a href=/dashboard class="btn">Back</a>''', u)
    conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM deposit_numbers"); numbers = c.fetchall(); conn.close()
    numbers_html = ''.join([f'<div class="card"><b>{n["network"]}</b><br>{n["account_name"]}<br><span style="color:#ffcc00;">{n["number"]}</span></div>' for n in numbers])
    return page_wrap(f'''<div class="card"><h2>Deposit Money</h2><div class="warning">1. Send money 2. Enter exact amount 3. Paste FULL SMS</div>{numbers_html}<form method=post>Amount: <input name=amount type=number required>SMS: <textarea name=proof rows=5 required></textarea><button class="btn" style="background:#00cc00;">Scan & Approve</button></form></div>''', u)

@app.route('/withdraw', methods=['GET','POST'])
def withdraw():
    u = get_user()
    if request.method == 'POST':
        amount = float(request.form['amount']); phone = request.form['phone']; network = request.form['network']
        if amount < 10000: return page_wrap('<div class="card"><h3>Min withdraw 10,000</h3></div>', u)
        if u['balance'] < amount: return page_wrap('<div class="card"><h3>No Balance</h3></div>', u)
        to_send = amount * (1 - WITHDRAW_TAX)
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE users SET balance = balance -? WHERE id=?",(amount,u['id']))
        c.execute("INSERT INTO withdraws(user_id,amount_requested,amount_to_send,phone,network,status,created_at) VALUES(?,?,?,?,?,?,?)",(u['id'],amount,to_send,phone,network,'pending',time.time()))
        conn.commit(); conn.close()
        return page_wrap(f'<div class="success"><h3>Withdraw Requested</h3><p>Requested: {format_number(amount)}<br>You will receive: {format_number(to_send)} after tax</p></div>', u)
    return page_wrap(f'''<div class="card"><h2>Withdraw Money</h2><div class="warning">8% Tax. Auto-approved in 24 hours</div><form method=post>Amount: <input name=amount type=number required>Network: <select name=network><option>MTN Mobile Money</option><option>Airtel Money</option></select>Phone: <input name=phone required><button class="btn">Withdraw</button></form></div>''', u)

@app.route('/machines')
def machines_page():
    u = get_user(); conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM machines ORDER BY is_vip DESC, price ASC"); machines = c.fetchall(); conn.close()
    html = ''
    for m in machines:
        total = m['price'] + (m['profit']*m['days'])
        vip_badge = '<span style="color:gold;">👑 VIP</span>' if m['is_vip']==1 else ''
        if m['stock'] <= 0: btn = '<button class="btn soldout" disabled>SOLD OUT</button>'
        else: btn = f'<form method=post action=/buy><input type=hidden name=m_id value={m["id"]}><button class="btn">Buy</button></form>'
        html += f'<div class="card"><h4>{m["name"]} {vip_badge}</h4><p>Price: {format_number(m["price"])}<br>Daily: {format_number(m["profit"])}<br>Days: {m["days"]}<br>Stock: {m["stock"]}<br><span class="total-return">Total Return: {format_number(total)} UGX</span></p>{btn}</div>'
    return page_wrap(f'<h2>All Machines</h2>{html}', u)

@app.route('/buy', methods=['POST'])
def buy():
    u = get_user(); m_id = int(request.form['m_id']); conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM machines WHERE id=?",(m_id,)); m = c.fetchone()
    if m['stock'] <= 0: conn.close(); return page_wrap('<div class="card"><h3>SOLD OUT</h3></div>', u)
    if u['balance'] < m['price']: conn.close(); return page_wrap('<div class="card"><h3>No Balance</h3></div>', u)
    c.execute("UPDATE users SET balance = balance -? +? WHERE id=?",(m['price'],BUY_REWARD,u['id']))
    c.execute("UPDATE machines SET stock = stock -1 WHERE id=?",(m_id,))
    c.execute("INSERT INTO user_machines(user_id,machine_id,bought_at,days_left,daily_profit,last_paid,total_earned) VALUES(?,?,?,?,?,?,?)",(u['id'],m_id,time.time(),m['days'],m['profit'],time.time(),0))
    c.execute("SELECT * FROM referrals WHERE referee_id=? AND has_bought=0",(u['id'],))
    ref = c.fetchone()
    if ref: c.execute("UPDATE users SET balance = balance +? WHERE refer_code=?",(REFER_REWARD,ref['referrer_code'])); c.execute("UPDATE referrals SET has_bought=1 WHERE id=?",(ref['id'],))
    conn.commit(); conn.close(); return redirect('/my_machines')

@app.route('/my_machines')
def my_machines():
    u = get_user(); conn = get_db(); c = conn.cursor()
    c.execute("SELECT um.*,m.name FROM user_machines um JOIN machines m ON um.machine_id=m.id WHERE um.user_id=?",(u['id'],))
    machines = c.fetchall(); conn.close()
    rows = ''
    for m in machines:
        left = m['bought_at'] + (m['days_left']*86400) - time.time()
        rows += f'<div class="card"><h4>{m["name"]}</h4><p>Daily: {format_number(m["daily_profit"])}<br>Time Left: {time_left(left)}<br>Total Earned: {format_number(m["total_earned"])} UGX</p></div>'
    return page_wrap(f'<h2>My Machines</h2>{rows if rows else "<div class=card>No machines</div>"}', u)

@app.route('/chat', methods=['GET','POST'])
def chat():
    u = get_user()
    if request.method == 'POST':
        msg = request.form['message']; conn = get_db(); c = conn.cursor()
        sender = 'admin' if u['is_admin']==1 else 'user'
        c.execute("INSERT INTO chats(user_id,sender,message,created_at) VALUES(?,?,?,?)",(u['id'],sender,msg,time.time())); conn.commit(); conn.close(); return redirect('/chat')
    conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM chats WHERE user_id=? ORDER BY created_at ASC",(u['id'],)); chats = c.fetchall(); conn.close()
    chat_html = ''.join([f'<div class="card"><b>{c["sender"]}</b>: {c["message"]}</div>' for c in chats])
    return page_wrap(f'<h2>Support Chat</h2>{chat_html}<form method=post><input name=message placeholder="Type message..." required><button class="btn">Send</button></form>', u)

@app.route('/refer')
def refer():
    u = get_user(); return page_wrap(f'<div class="card"><h2>Refer & Earn</h2><p>Get {format_number(REFER_REWARD)} UGX when your friend buys a machine</p><p>Your Code: <b>{u["refer_code"]}</b></p></div>', u)

@app.route('/notifications', methods=['GET','POST'])
def notifications():
    u = get_user()
    if request.method == 'POST' and u['is_admin']==1:
        msg = request.form['message']; conn = get_db(); c = conn.cursor(); c.execute("INSERT INTO notifications(message,created_at) VALUES(?,?)",(msg,time.time())); conn.commit(); conn.close(); return redirect('/notifications')
    conn = get_db(); c = conn.cursor(); c.execute("SELECT * FROM notifications ORDER BY created_at DESC"); notifs = c.fetchall(); conn.close()
    notif_html = ''.join([f'<div class="card">{n["message"]}</div>' for n in notifs])
    admin_form = '<div class="card"><h3>Post Update</h3><form method=post><textarea name=message required></textarea><button class="btn">Post</button></form></div>' if u['is_admin']==1 else ''
    return page_wrap(f'<h2>Notifications</h2>{admin_form}{notif_html}', u)

@app.route('/admin', methods=['GET','POST'])
def admin():
    u = get_user();
    if not u or u['is_admin']!=1: return "Access Denied"
    conn = get_db(); c = conn.cursor()
    if request.method == 'POST':
        if 'add_number' in request.form: c.execute("INSERT INTO deposit_numbers(network,account_name,number) VALUES(?,?,?)",(request.form['network'],request.form['acc_name'],request.form['number']))
        if 'remove_number' in request.form: c.execute("DELETE FROM deposit_numbers WHERE id=?",(request.form['remove_number'],))
        if 'add_admin' in request.form: c.execute("INSERT INTO users(username,password,is_admin,created_at) VALUES(?,?,?,?)",(request.form['new_user'],hash_password(request.form['new_pass']),1,time.time()))
        if 'add_machine' in request.form: c.execute("INSERT INTO machines(name,price,profit,days,stock,is_vip) VALUES(?,?,?,?,?,?)",(request.form['m_name'],request.form['m_price'],request.form['m_profit'],request.form['m_days'],request.form['m_stock'],request.form['m_vip']))
        if 'approve_w' in request.form: c.execute("UPDATE withdraws SET status='approved', approved_at=? WHERE id=?",(time.time(),request.form['approve_w']))
        conn.commit()

    c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM user_machines"); total_purchases = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM deposits WHERE status='approved'"); total_deposits = c.fetchone()[0] or 0
    c.execute("SELECT d.*,u.username FROM deposits d JOIN users u ON d.user_id=u.id ORDER BY d.created_at DESC LIMIT 50"); deposits = c.fetchall()
    c.execute("SELECT w.*,u.username FROM withdraws w JOIN users u ON w.user_id=u.id ORDER BY w.created_at DESC"); withdraws = c.fetchall()
    c.execute("SELECT * FROM deposit_numbers"); numbers = c.fetchall()
    c.execute("SELECT * FROM machines ORDER BY id DESC"); machines = c.fetchall()
    c.execute("SELECT * FROM chats ORDER BY created_at DESC LIMIT 50"); all_chats = c.fetchall()
    conn.close()

    dep_rows = ''.join([f'<tr><td>{d["username"]}</td><td>{format_number(d["amount"])}</td><td>{d["tx_id"]}</td><td>{d["sender_name"]}</td><td>{d["deposit_date"]}</td></tr>' for d in deposits])
    w_rows = ''.join([f'<tr><td>{w["username"]}</td><td>{format_number(w["amount_requested"])}</td><td>{w["phone"]}</td><td>{w["status"]}</td><td>{"<form method=post><button name=approve_w value="+str(w["id"])+">Approve</button></form>" if w["status"]=="pending" else "Approved"}</td></tr>' for w in withdraws])
    m_rows = ''.join([f'<tr><td>{m["name"]}</td><td>{format_number(m["price"])}</td><td>{m["stock"]}</td><td>{"VIP" if m["is_vip"] else "REG"}</td></tr>' for m in machines])
    num_rows = ''.join([f'<tr><td>{n["network"]}</td><td>{n["account_name"]}</td><td>{n["number"]}</td><td><form method=post><button name=remove_number value={n["id"]}>Remove</button></form></td></tr>' for n in numbers])

    content = f'''<h2>Admin Panel</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
    <div class="card"><h3>{total_users}</h3><p>Total Users</p></div>
    <div class="card"><h3>{total_purchases}</h3><p>Machines Bought</p></div>
    <div class="card"><h3>{format_number(total_deposits)}</h3><p>Total Deposits</p></div>
    </div>

    <div class="card"><h3>Add Admin</h3><form method=post>Username: <input name=new_user>Password: <input name=new_pass><button name=add_admin class="btn">Add Admin</button></form></div>

    <div class="card"><h3>Add Machine</h3><form method=post>Name: <input name=m_name required>Price: <input name=m_price type=number required>Daily Profit: <input name=m_profit type=number required>Days: <input name=m_days type=number required>Stock: <input name=m_stock type=number required>VIP: <select name=m_vip><option value=0>Regular</option><option value=1>VIP</option></select><button name=add_machine class="btn">Add Machine</button></form></div>

    <div class="card"><h3>Deposit Numbers</h3><form method=post>Network: <select name=network><option>MTN Mobile Money</option><option>Airtel Money</option></select>Account: <input name=acc_name>Number: <input name=number><button name=add_number class="btn">Add</button></form><table><tr><th>Network</th><th>Account</th><th>Number</th><th>Action</th></tr>{num_rows}</table></div>

    <div class="card"><h3>All Machines</h3><table><tr><th>Name</th><th>Price</th><th>Stock</th><th>Type</th></tr>{m_rows}</table></div>

    <div class="card"><h3>Last 50 Deposits</h3><table><tr><th>User</th><th>Amount</th><th>TX ID</th><th>Name</th><th>Date</th></tr>{dep_rows}</table></div>

    <div class="card"><h3>Withdraw Requests</h3><table><tr><th>User</th><th>Amount</th><th>Phone</th><th>Status</th><th>Action</th></tr>{w_rows}</table></div>'''
    return page_wrap(content, u)

if __name__ == '__main__': app.run(debug=False, host='0.0.0.0', port=5000)