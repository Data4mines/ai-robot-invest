import os, re, random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'data4mines_secret_key_2026_secure_uganda'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data4mines.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

def format_money(x): return f"UGX {int(x):,}"

REFERRAL_REWARD = 5000
JOIN_REWARD = 5000
WITHDRAW_TAX = 0.08

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=0)
    referral = db.Column(db.String(20))
    referral_code = db.Column(db.String(20), unique=True)
    got_join_reward = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

class MachineSeries(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_payout = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(200))
    series_id = db.Column(db.Integer)
    is_vip = db.Column(db.Boolean, default=False)

class UserMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    machine_id = db.Column(db.Integer, nullable=False)
    buy_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    earned = db.Column(db.Float, default=0)
    claimed = db.Column(db.Boolean, default=False)

class Deposit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tx_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100))
    number = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Withdraw(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, default=0)
    final_amount = db.Column(db.Float, default=0)
    name = db.Column(db.String(100))
    number = db.Column(db.String(20))
    network = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deposit_number = db.Column(db.String(20), default='0792759363')
    deposit_name = db.Column(db.String(100), default='DATA4MINES LTD')
    deposit_network = db.Column(db.String(20), default='MTN')

def get_user():
    if 'user_id' in session: return db.session.get(User, session['user_id'])
    return None

def parse_sms(sms_text):
    sms_text = sms_text.upper()
    tx = re.search(r'([A-Z0-9]{8,})', sms_text)
    amt = re.search(r'UGX\s?([\d,]+)', sms_text)
    num = re.search(r'TO\s?(\d{10})', sms_text)
    number = num.group(1) if num else ''
    if number and number.startswith('0'): number = '256' + number[1:]
    return {'tx_id': tx.group(1) if tx else '', 'amount': int(amt.group(1).replace(',','')) if amt else 0, 'number': number}

def base_template(content, user=None, msg=None):
    bottom_nav = '''<div class="bottom-nav">
    <a href="/">🏠<br>Home</a><a href="/shop">🛒<br>Shop</a><a href="/machines">⚙️<br>Machines</a>
    <a href="/deposit">💰<br>Deposit</a><a href="/about">ℹ️<br>About</a></div>''' if user else ''
    nav = '''<div class="nav"><a href="/">Home</a><a href="/shop">Shop</a><a href="/deposit">Deposit</a>
    <a href="/withdraw">Withdraw</a><a href="/machines">Machines</a><a href="/chat">💬 Chat</a><a href="/logout">Logout</a></div>''' if user else '''<div class="nav"><a href="/login">Login</a><a href="/register">Register</a></div>'''
    admin_link = '<a href="/admin" style="color:#fbbf24;font-weight:bold">👑 Admin Panel</a>' if user and user.is_admin else ''
    alert = f'<div class="alert">{msg}</div>' if msg else ''
    balance = f'<div class="balance">Balance: {format_money(user.balance)}</div>' if user else ''
    return f'''<!DOCTYPE html><html><head><title>DATA4MINES</title>
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
    <style>*{{box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial;background:#0f172a;color:#fff;margin:0;padding:0 0 85px 0;font-size:16px}}
   .nav{{background:#1e293b;padding:14px;display:flex;gap:16px;overflow-x:auto;font-size:16px;position:sticky;top:0;z-index:10}}
   .nav a{{color:#38bdf8;text-decoration:none;font-weight:600;white-space:nowrap}}
   .bottom-nav{{position:fixed;bottom:0;left:0;right:0;background:#1e293b;display:flex;justify-content:space-around;padding:12px 0;border-top:1px solid #334155;z-index:100}}
   .bottom-nav a{{color:#94a3b8;text-decoration:none;text-align:center;font-size:13px;font-weight:600}}
   .container{{padding:18px;max-width:950px;margin:auto}}
   .card{{background:#1e293b;padding:20px;border-radius:14px;margin:18px 0;box-shadow:0 2px 8px rgba(0,0,0,0.2)}}
   .btn{{background:#38bdf8;color:#000;padding:16px 22px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;font-size:17px;width:100%;margin-top:12px}}
   .btn:hover{{opacity:0.9}}.btn-green{{background:#22c55e}}.btn-red{{background:#ef4444}}.btn-gold{{background:#fbbf24}}
   .alert{{background:#fbbf24;color:#000;padding:16px;border-radius:10px;margin:14px 0;font-weight:600;font-size:16px}}
   .balance{{background:#22c55e;color:#000;padding:18px;text-align:center;font-weight:bold;font-size:20px;position:sticky;top:50px;z-index:9}}
    input,select,textarea{{width:100%;padding:16px;margin:12px 0;border-radius:12px;border:1px solid #334155;background:#0f172a;color:#fff;font-size:16px}}
    input:focus,textarea:focus{{border-color:#38bdf8;outline:none}}
    table{{width:100%;border-collapse:collapse}} td,th{{padding:14px;border-bottom:1px solid #334155;text-align:left;font-size:15px}}
   .stats{{display:flex;gap:14px;flex-wrap:wrap}}
   .stat-card{{flex:1;min-width:150px;background:#1e293b;padding:20px;border-radius:12px;text-align:center}}
   .stat-card h3{{font-size:28px;margin:8px 0;color:#38bdf8}}
   .vip{{border:2px solid #fbbf24;background:linear-gradient(135deg,#1e293b,#2a1f0e)}}
   .tax-info{{background:#334155;padding:16px;border-radius:10px;margin:14px 0;font-size:16px}}
   .countdown{{color:#22c55e;font-weight:bold;font-size:16px}}
   .chat-box{{background:#0f172a;padding:15px;border-radius:10px;max-height:400px;overflow-y:auto}}
   .chat-msg{{background:#1e293b;padding:12px;border-radius:10px;margin:10px 0}}
    img{{max-width:100%;border-radius:12px}}
    @media (max-width: 600px){{.container{{padding:14px}}.card{{padding:16px}}h2{{font-size:22px}}h3{{font-size:18px}}}}
    </style><script>
    function copyText(id){{let t=document.getElementById(id);t.select();document.execCommand('copy');alert('Copied to clipboard!')}}
    function calcTax(){{let amt=parseFloat(document.getElementById('amt').value)||0;let tax=amt*0.08;let final=amt-tax;document.getElementById('tax').innerText='Tax 8%: '+formatMoney(tax);document.getElementById('final').innerText='You will receive: '+formatMoney(final)}}
    function formatMoney(x){{return 'UGX '+Math.floor(x).toLocaleString()}}
    function countdown(end, id){{setInterval(()=>{{let d=new Date(end)-new Date();if(d<0){{document.getElementById(id).innerText='Ready to Claim';return}}let days=Math.floor(d/86400000);let h=Math.floor((d%86400000)/3600000);let m=Math.floor((d%3600000)/60000);document.getElementById(id).innerText=days+'d '+h+'h '+m+'m left'}},60000)}}
    </script></head><body>{balance}{nav}<div class="container">{admin_link}{alert}{content}</div>{bottom_nav}</body></html>'''

def generate_growth_chart():
    users = User.query.count()
    plt.figure(figsize=(9,3.5))
    plt.plot([1,2,3,4,5],[users/5,users/3,users/2,users*0.8,users], marker='o', color='#38bdf8', linewidth=3)
    plt.title('Company Growth Rate', color='white', fontsize=16)
    plt.gca().set_facecolor('#1e293b'); plt.gcf().set_facecolor('#1e293b')
    plt.xticks([]); plt.yticks([])
    path = os.path.join(app.config['UPLOAD_FOLDER'],'growth_chart.png')
    plt.savefig(path, facecolor='#1e293b', bbox_inches='tight'); plt.close()
    return f'/{path}'

@app.route('/')
def home():
    user = get_user()
    notifs = Notification.query.filter_by(user_id=user.id if user else None).order_by(Notification.id.desc()).limit(6).all() if user else Notification.query.order_by(Notification.id.desc()).limit(6).all()
    n_html = ''.join([f'<div class="card"><p style="font-size:16px">{n.message}</p>{f"<a href={n.link} target=_blank style=color:#38bdf8;font-size:16px>Join WhatsApp Group</a>" if n.link else ""}<br><small style="color:#94a3b8;font-size:14px">{n.created_at.strftime("%Y-%m-%d %H:%M")}</small></div>' for n in notifs])
    return base_template(f'<h2 style="font-size:24px">DATA4MINES - WELCOME</h2>{n_html if n_html else "<div class=card><p style=font-size:16px>No notifications yet</p></div>"}', user)

@app.route('/about')
def about(): return base_template('<h2 style="font-size:24px">About DATA4MINES</h2><div class="card"><p style="font-size:16px"><b>DATA4MINES</b> is a mining investment platform in Uganda. Buy virtual mining machines, earn daily profits, and withdraw anytime to Mobile Money MTN/Airtel.</p><p style="font-size:16px"><b>Founded:</b> 2015 in USA NEW YORK BY CHARLIE DIKENS and it came in Uganda in 2022 and it has signed contracts with big companies in data minings and software and even banks for sefty of customer money so if your a company come and invest with us for big profits plus individuals it is a registered company licenced to work in Uganda and in Africa</p></div>', get_user())

@app.route('/chat', methods=['GET','POST'])
def chat():
    user = get_user()
    if not user: return redirect('/login')
    msg = None
    if request.method == 'POST':
        db.session.add(ChatMessage(user_id=user.id, message=request.form['message']))
        db.session.commit(); msg = 'Message sent to Admin'
    
    chats = ChatMessage.query.filter_by(user_id=user.id).order_by(ChatMessage.id.desc()).all()
    chat_html = ''.join([f'<div class="chat-msg"><b>You:</b> {c.message}<br><b>Admin:</b> {c.reply if c.reply else "Waiting for reply..."}</div>' for c in chats])
    return base_template(f'<h2 style="font-size:24px">Chat with Admin</h2><div class="chat-box">{chat_html if chat_html else "<p>No messages yet</p>"}</div><form method="post"><textarea name="message" placeholder="Type your message here..." rows="3" required></textarea><button class="btn">Send Message</button></form>', user, msg)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        if User.query.filter_by(phone=request.form['phone']).first(): return base_template('<div class=alert>Phone number already exists</div>')
        ref_code = str(random.randint(100000,999999))
        u = User(phone=request.form['phone'], password=generate_password_hash(request.form['password']), referral=request.form.get('ref'), referral_code=ref_code)
        db.session.add(u); db.session.commit()
        return redirect('/login')
    return base_template('''<h2 style="font-size:24px">Create Account</h2><form method="post">
    <input name="phone" placeholder="Phone Number e.g 078xxxxxxx" required>
    <input name="password" type="password" placeholder="Create Password" required>
    <input name="ref" placeholder="Referral Code Optional">
    <button class="btn">Register Now</button></form>''')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u = User.query.filter_by(phone=request.form['phone']).first()
        if u and check_password_hash(u.password, request.form['password']):
            session['user_id']=u.id
            return redirect('/admin' if u.is_admin else '/')
        else: return base_template('<div class=alert>Wrong phone or password</div>')
    return base_template('''<h2 style="font-size:24px">Login</h2><form method="post">
    <input name="phone" placeholder="Phone Number" required>
    <input name="password" type="password" placeholder="Password" required>
    <button class="btn">Login</button></form>''')

@app.route('/logout')
def logout(): session.pop('user_id',None); return redirect('/login')

@app.route('/shop', methods=['GET','POST'])
def shop():
    user = get_user()
    if not user: return redirect('/login')
    msg=None
    if request.method=='POST':
        m = db.session.get(Machine, int(request.form['machine_id']))
        if user.balance>=m.price and m.stock>0:
            user.balance-=m.price; m.stock-=1
            um = UserMachine(user_id=user.id,machine_id=m.id,end_date=datetime.utcnow()+timedelta(days=m.duration_days))
            db.session.add(um)
            if user.referral:
                ref_user = User.query.filter_by(referral_code=user.referral).first()
                if ref_user:
                    ref_user.balance += REFERRAL_REWARD
                    db.session.add(Notification(user_id=ref_user.id, message=f'You earned {format_money(REFERRAL_REWARD)} referral bonus from {user.phone}'))
            if not user.got_join_reward:
                user.balance += JOIN_REWARD
                user.got_join_reward = True
                db.session.add(Notification(user_id=user.id, message=f'Welcome! You received {format_money(JOIN_REWARD)} join bonus'))
            db.session.commit(); msg=f'Machine Bought Successfully! Rewards Added'
        else: msg='Not enough balance or out of stock'

    ref_link = request.host_url + f"register?ref={user.referral_code}"
    ref_box = f'<div class="card"><h3 style="font-size:18px">Refer & Earn {format_money(REFERRAL_REWARD)}</h3><p style="font-size:16px">Invite friends. You get reward when they buy a machine.</p><div style="display:flex;gap:10px"><input id="ref" value="{ref_link}" readonly><button onclick="copyText(\'ref\')" class="btn" style="width:120px;font-size:15px">Copy</button></div></div>'

    normal_machines = ''.join([machine_card(m) for m in Machine.query.filter_by(is_vip=False).all()])
    vip_machines = ''.join([machine_card(m, True) for m in Machine.query.filter_by(is_vip=True).all()])

    content = f'<h2 style="font-size:24px">Shop Machines</h2>{ref_box}<h3 style="font-size:20px">Regular Machines</h3>{normal_machines if normal_machines else "<div class=card><p style=font-size:16px>No regular machines</p></div>"}<h3 style="font-size:20px">VIP Machines</h3>{vip_machines if vip_machines else "<div class=card><p style=font-size:16px>No VIP machines</p></div>"}'
    return base_template(content, user, msg)

def machine_card(m, vip=False):
    vip_class = 'vip' if vip else ''
    vip_tag = '<p style="color:#fbbf24;font-weight:bold;font-size:16px">⭐ VIP MACHINE</p>' if vip else ''
    return f'''<div class="card {vip_class}">
    <img src="{m.image_url}" style="width:100%;height:220px;object-fit:cover;margin-bottom:12px;">
    {vip_tag}<h3 style="font-size:18px">{m.name}</h3>
    <p style="font-size:16px"><b>Invest:</b> {format_money(m.price)}</p>
    <p style="font-size:16px"><b>Total Payout:</b> {format_money(m.total_payout)}</p>
    <p style="font-size:16px"><b>Duration:</b> {m.duration_days} Days</p>
    <p style="font-size:16px"><b>Stock Left:</b> {m.stock}</p>
    <form method="post"><input type="hidden" name="machine_id" value="{m.id}">
    <button class="btn">Buy Now</button></form></div>'''

@app.route('/machines', methods=['GET','POST'])
def machines():
    user = get_user()
    if not user: return redirect('/login')
    msg=None
    if request.method=='POST' and 'claim' in request.form:
        um = db.session.get(UserMachine, int(request.form['claim']))
        if datetime.utcnow() >= um.end_date and not um.claimed:
            m = db.session.get(Machine, um.machine_id)
            user.balance += m.total_payout
            um.claimed = True; um.earned = m.total_payout
            db.session.commit(); msg='Income Claimed Successfully to Balance'

    html=''
    for um in UserMachine.query.filter_by(user_id=user.id).order_by(UserMachine.id.desc()).all():
        m = db.session.get(Machine, um.machine_id)
        end_str = um.end_date.strftime("%Y-%m-%d %H:%M:%S")
        btn = f'<form method="post"><button class="btn btn-green" name="claim" value="{um.id}">Receive Income</button></form>' if not um.claimed and datetime.utcnow() >= um.end_date else '<p style="color:#22c55e;font-size:16px">Claimed</p>' if um.claimed else ''
        html += f'''<div class="card"><h3 style="font-size:18px">{m.name}</h3><p style="font-size:16px">Start: {um.buy_date.strftime("%Y-%m-%d")}</p>
        <p style="font-size:16px">Ends: {um.end_date.strftime("%Y-%m-%d %H:%M")}</p>
        <p class="countdown" id="c{um.id}"></p><p style="font-size:16px">Earned: {format_money(um.earned)}</p>{btn}</div>
        <script>countdown('{end_str}', 'c{um.id}')</script>'''
    return base_template(f'<h2 style="font-size:24px">My Machines</h2>{html if html else "<div class=card><p style=font-size:16px>You have no machines yet. Go to Shop</p></div>"}', user, msg)

@app.route('/deposit', methods=['GET','POST'])
def deposit():
    user = get_user()
    if not user: return redirect('/login')
    settings = Settings.query.first()
    msg=None
    if request.method=='POST':
        if 'sms_text' in request.form and request.form['sms_text'].strip():
            data = parse_sms(request.form['sms_text'])
            today = datetime.utcnow().date()
            dep = Deposit.query.filter_by(user_id=user.id, tx_id=request.form['tx'], status='Pending').order_by(Deposit.id.desc()).first()
            admin_num = settings.deposit_number.replace('0','256',1)
            if dep and data['tx_id']==dep.tx_id and data['amount']==dep.amount and data['number']==admin_num and dep.created_at.date()==today:
                dep.status='Approved'; user.balance += dep.amount; db.session.commit()
                msg = f'✅ Auto Approved! {format_money(dep.amount)} added to your balance instantly'
            else:
                msg = '❌ SMS does not match. Make sure TXID, Amount, and To Number are correct.'
        else:
            dep = Deposit(user_id=user.id, amount=float(request.form['amount']), tx_id=request.form['tx'], name=request.form['name'], number=request.form['number'])
            db.session.add(dep); db.session.commit()
            msg='Deposit Submitted. Now paste your SMS below to auto-approve instantly'

    return base_template(f'''<h2 style="font-size:24px">Deposit Funds</h2><div class="card">
    <p style="font-size:16px"><b>Network:</b> {settings.deposit_network}</p>
    <p style="font-size:16px"><b>Number:</b> {settings.deposit_number}</p>
    <p style="font-size:16px"><b>Account Name:</b> {settings.deposit_name}</p></div>
    <form method="post"><h3 style="font-size:18px">Step 1: Submit Details</h3>
    <input name="amount" type="number" placeholder="Amount UGX" required>
    <input name="name" placeholder="Your Full Names" required>
    <input name="number" placeholder="Your Mobile Money Number" required>
    <input name="tx" placeholder="Transaction ID from SMS" required>
    <button class="btn">Submit Deposit</button></form>
    <form method="post"><h3 style="font-size:18px">Step 2: Paste MTN/Airtel SMS for Auto Approval</h3>
    <p style="font-size:14px;color:#94a3b8">Example: You have deposited UGX 50,000 to 0792759363. TXID: ABC12345</p>
    <textarea name="sms_text" placeholder="Paste the full SMS you received here" rows="3"></textarea>
    <button class="btn btn-green">Check & Approve Automatically</button></form>''', user, msg)

@app.route('/withdraw', methods=['GET','POST'])
def withdraw():
    user = get_user()
    if not user: return redirect('/login')
    msg=None
    if request.method=='POST':
        amt=float(request.form['amount'])
        tax = amt * WITHDRAW_TAX
        final = amt - tax
        if user.balance>=amt:
            user.balance-=amt
            db.session.add(Withdraw(user_id=user.id,amount=amt,tax=tax,final_amount=final,name=request.form['name'],number=request.form['number'],network=request.form['network']))
            db.session.commit(); msg=f'Withdraw Request Submitted. You will receive {format_money(final)} after 8% tax.  receive within 24 hours.'
        else: msg='Insufficient Balance'

    return base_template('''<h2 style="font-size:24px">Withdraw Funds</h2><form method="post">
    <input name="amount" id="amt" type="number" placeholder="Amount UGX" onkeyup="calcTax()" required>
    <div class="tax-info"><p id="tax" style="font-size:16px">Tax 8%: UGX 0</p><p id="final" style="font-size:16px"><b>You will receive: UGX 0</b></p></div>
    <input name="name" placeholder="Full Names on Mobile Money" required>
    <input name="number" placeholder="Mobile Money Number" required>
    <select name="network"><option>MTN</option><option>Airtel</option></select>
    <button class="btn">Request Withdraw - Admin Approval in 24Hrs</button></form>''', user, msg)

@app.route('/admin', methods=['GET','POST'])
def admin():
    user = get_user()
    if not user or not user.is_admin: return 'Access Denied'
    settings = Settings.query.first()
    msg = None
    if request.method == 'POST':
        if 'reply_chat' in request.form:
            c = db.session.get(ChatMessage, int(request.form['reply_chat']))
            c.reply = request.form['reply_text']; msg = 'Reply Sent'
        if 'approve_deposit' in request.form:
            d = db.session.get(Deposit, int(request.form['approve_deposit']))
            d.status='Approved'; u=db.session.get(User, d.user_id); u.balance+=d.amount; msg='Deposit Approved Manually'
        if 'approve_withdraw' in request.form:
            w = db.session.get(Withdraw, int(request.form['approve_withdraw'])); w.status = 'Approved'; msg = f'Withdraw {format_money(w.amount)} Approved'
        if 'reject_withdraw' in request.form:
            w = db.session.get(Withdraw, int(request.form['reject_withdraw'])); w.status = 'Rejected'; u = db.session.get(User, w.user_id); u.balance += w.amount; msg = 'Withdraw Rejected and Amount Refunded'
        if 'delete_machine' in request.form:
            db.session.delete(db.session.get(Machine, int(request.form['delete_machine']))); msg='Machine Deleted Successfully'
        if 'update_deposit' in request.form:
            settings.deposit_number = request.form['deposit_number']; settings.deposit_name = request.form['deposit_name']; settings.deposit_network = request.form['deposit_network']; msg = 'Deposit Number Updated'
        if 'send_notification' in request.form:
            db.session.add(Notification(message=request.form['notification_msg'], link=request.form.get('whatsapp_link'))); msg = 'Notification Sent to All Users'
        if 'series' in request.form: db.session.add(MachineSeries(name=request.form['series'])); msg = 'Series Added'
        if 'machine' in request.form:
            f = request.files['image']; filename = secure_filename(f.filename); filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename); f.save(filepath)
            is_vip = 'is_vip' in request.form
            db.session.add(Machine(name=request.form['machine'], price=float(request.form['price']), total_payout=float(request.form['payout']), duration_days=int(request.form['days']), stock=int(request.form['stock']), image_url=url_for('static', filename=f'uploads/{filename}'), series_id=int(request.form['series_id']), is_vip=is_vip)); msg = 'Machine Added Successfully'
        if 'new_admin_phone' in request.form:
            if not User.query.filter_by(phone=request.form['new_admin_phone']).first():
                db.session.add(User(phone=request.form['new_admin_phone'], password=generate_password_hash(request.form['new_admin_pass']), is_admin=True)); msg = 'New Admin Created'
        db.session.commit()

    total_users = User.query.count()
    total_depositors = db.session.query(Deposit.user_id).distinct().count()
    total_transactions = Deposit.query.count() + Withdraw.query.count()
    total_deposits = db.session.query(db.func.sum(Deposit.amount)).scalar() or 0
    chart_url = generate_growth_chart()
    series_options = "".join([f'<option value="{s.id}">{s.name}</option>' for s in MachineSeries.query.all()])

    pending_deps = Deposit.query.filter_by(status='Pending').order_by(Deposit.id.desc()).all()
    dep_rows = "".join([f'''<div class="card" style="border-left:4px solid #fbbf24"><p style="font-size:16px"><b>User:</b> {db.session.get(User, d.user_id).phone}</p><p style="font-size:16px"><b>Amount:</b> {format_money(d.amount)}</p><p style="font-size:16px"><b>TXID:</b> {d.tx_id}</p><p style="font-size:16px"><b>Names:</b> {d.name}</p><p style="font-size:16px"><b>Date:</b> {d.created_at.strftime('%Y-%m-%d %H:%M')}</p>
    <form method="post"><button class="btn btn-green" name="approve_deposit" value="{d.id}">Manual Approve</button></form></div>''' for d in pending_deps])

    withdraws = ""
    for w in Withdraw.query.filter_by(status='Pending').order_by(Withdraw.id.desc()).all():
        u = db.session.get(User, w.user_id)
        hours_left = max(0, 24 - int((datetime.utcnow() - w.created_at).total_seconds()/3600))
        withdraws += f'''<div class="card"><p style="font-size:16px"><b>Phone:</b> {u.phone}</p><p style="font-size:16px"><b>Amount:</b> {format_money(w.amount)}</p>
        <p style="font-size:16px"><b>Tax 8%:</b> {format_money(w.tax)}</p><p style="font-size:16px"><b>Final Send:</b> {format_money(w.final_amount)}</p>
        <p style="font-size:16px"><b>To:</b> {w.network} {w.number}</p><p style="font-size:16px"><b>Time Left:</b> {hours_left} Hours</p>
        <form method="post" style="display:flex;gap:10px"><button class="btn btn-green" name="approve_withdraw" value="{w.id}">Approve</button>
        <button class="btn btn-red" name="reject_withdraw" value="{w.id}">Reject + Refund</button></form></div>'''

    machines_list = "".join([f'<div class="card"><img src="{m.image_url}" style="width:100px;height:100px"><p style="font-size:16px">{"⭐ VIP - " if m.is_vip else ""}{m.name} - {format_money(m.price)}</p><form method="post"><button class="btn btn-red" name="delete_machine" value="{m.id}">Delete</button></form></div>' for m in Machine.query.all()])

    chat_msgs = "".join([f'<div class="chat-msg"><b>{db.session.get(User, c.user_id).phone}:</b> {c.message}<form method="post"><textarea name="reply_text" placeholder="Reply..."></textarea><button class="btn btn-green" name="reply_chat" value="{c.id}">Reply</button></form></div>' for c in ChatMessage.query.order_by(ChatMessage.id.desc()).limit(10).all()])

    content = f'''<h2 style="font-size:24px">👑 Admin Panel</h2>
    <div class="card"><h3 style="font-size:18px">User Chats</h3>{chat_msgs if chat_msgs else "<p>No messages</p>"}</div>
    <div class="card"><h3 style="font-size:18px">Send Notification to All Users</h3><form method="post">
    <textarea name="notification_msg" placeholder="Message" rows="3" required></textarea>
    <input name="whatsapp_link" placeholder="WhatsApp Group Link Optional">
    <button class="btn btn-green" name="send_notification" value="1">Send Notification</button></form></div>
    <div class="card"><h3 style="font-size:18px">Company Growth Chart</h3><img src="{chart_url}" style="width:100%"></div>
    <div class="stats">
    <div class="stat-card"><h3>{total_users}</h3><p style="font-size:15px">Total Users</p></div>
    <div class="stat-card"><h3>{total_depositors}</h3><p style="font-size:15px">Total Depositors</p></div>
    <div class="stat-card"><h3>{total_transactions}</h3><p style="font-size:15px">Total Transactions</p></div>
    <div class="stat-card"><h3>{format_money(total_deposits)}</h3><p style="font-size:15px">Total Deposited</p></div></div>
    <div class="card"><h3 style="font-size:18px">Pending Deposits - Manual Only</h3>{dep_rows if dep_rows else "<p style=font-size:16px>No pending deposits</p>"}</div>
    <div class="card"><h3 style="font-size:18px">Pending Withdraws - 24Hr Approval</h3>{withdraws if withdraws else "<p style=font-size:16px>No pending withdraws</p>"}</div>
    <div class="card"><h3 style="font-size:18px">Manage Deposit Number</h3><form method="post">
    <input name="deposit_network" value="{settings.deposit_network}">
    <input name="deposit_number" value="{settings.deposit_number}">
    <input name="deposit_name" value="{settings.deposit_name}">
    <button class="btn" name="update_deposit" value="1">Update</button></form></div>
    <div class="card"><h3 style="font-size:18px">Manage Machines</h3>{machines_list if machines_list else "<p style=font-size:16px>No machines</p>"}</div>
    <div class="card"><h3 style="font-size:18px">Add Series</h3><form method="post"><input name="series" placeholder="Series Name" required><button class="btn">Add Series</button></form></div>
    <div class="card"><h3 style="font-size:18px">Add Machine - Regular or VIP</h3><form method="post" enctype="multipart/form-data">
    <select name="series_id" required>{series_options}</select>
    <input name="machine" placeholder="Machine Name" required>
    <input name="price" type="number" placeholder="Price UGX" required>
    <input name="payout" type="number" placeholder="Total Payout UGX" required>
    <input name="days" type="number" placeholder="Duration Days" required>
    <input name="stock" type="number" placeholder="Stock" required>
    <input name="image" type="file" accept="image/*" required>
    <label style="display:flex;gap:10px;align-items:center;font-size:16px"><input type="checkbox" name="is_vip"> Mark as VIP Machine</label>
    <button class="btn" name="machine" value="1">Add Machine</button></form></div>
    <div class="card"><h3 style="font-size:18px">Add New Admin</h3><form method="post">
    <input name="new_admin_phone" placeholder="Admin Phone" required>
    <input name="new_admin_pass" type="password" placeholder="Password" required>
    <button class="btn">Create Admin</button></form></div>'''
    return base_template(content, user, msg)
with app.app_context():
    db.create_all()
    if not Settings.query.first(): db.session.add(Settings())
    if not User.query.filter_by(phone='0792759363').first():
        admin = User(phone='0792759363', password=generate_password_hash('1831'), is_admin=True, balance=50000000, referral_code='ADMIN001')
        db.session.add(admin); db.session.commit()

@app.route('/my_machines')
def my_machines():
    user = get_user()
    if not user: return redirect('/login')
    
    user_machines = []
    for um in user.machines:
        m = um.machine
        if m: # THIS FIXES THE NoneType ERROR
            user_machines.append({
                'name': m.name, 
                'image': m.image, 
                'daily': m.daily, 
                'days_left': um.days_left,
                'series': m.series.name if m.series else 'N/A'
            })
    
    cards = ''.join([f'<div class="card"><img src="/static/uploads/{m["image"]}" style="width:100%;height:180px;object-fit:cover;border-radius:10px"><h3 style="font-size:18px">{m["name"]}</h3><p style="font-size:16px">Series: {m["series"]}</p><p style="font-size:16px">Daily: UGX {m["daily"]}</p><p style="font-size:16px">Days Left: {m["days_left"]}</p></div>' for m in user_machines]) if user_machines else '<div class="card"><p style="font-size:16px">You have no machines yet. Go to Shop to buy one.</p></div>'
    
    content = f'<h2 style="font-size:24px">My Machines</h2>{cards}'
    return base_template(content, user)

import os
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)  