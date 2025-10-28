from flask import Flask, request, redirect, render_template, jsonify, session, flash
from flask_socketio import SocketIO, emit
from kiteconnect import KiteConnect
import logging
import random
import time
from threading import Thread
from strategies.orb import ORB
from ticker import Ticker
import uuid
import sqlite3
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
import secrets
import config
from database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management
socketio = SocketIO(app)

@app.before_request
def make_session_permanent():
    session.permanent = False

# Initialize KiteConnect
kite = KiteConnect(api_key="default_api_key") # The API key will be set dynamically

# In-memory storage for running strategies
running_strategies = {}

# Ticker instance
ticker = None

def send_email(to_email, otp):
    port = 465  # For SSL
    smtp_server = config.SMTP_SERVER
    sender_email = config.EMAIL_FROM
    receiver_email = to_email
    password = config.PASSWORD_EMAIL

    message = MIMEMultipart("alternative")
    message["Subject"] = "Your OTP for Login"
    message["From"] = sender_email
    message["To"] = receiver_email

    text = f"""
    Hi,
    Your OTP is {otp}
    """
    html = f"""
    <html>
        <body>
            <p>Hi,<br>
               Your OTP is <strong>{otp}</strong>
            </p>
        </body>
    </html>
    """

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    message.attach(part1)
    message.attach(part2)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

@app.route("/")
def index():
    if 'user_id' in session:
        return redirect("/dashboard")
    return render_template("login.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        mobile = request.form['mobile']
        email = request.form['email']
        app_key = request.form['app_key']
        app_secret = request.form['app_secret']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user:
            return "Email already exists!"

        otp = secrets.token_hex(3).upper()
        otp_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

        conn.execute('INSERT INTO users (mobile, email, app_key, app_secret, otp, otp_expiry) VALUES (?, ?, ?, ?, ?, ?)',
                     (mobile, email, app_key, app_secret, otp, otp_expiry))
        conn.commit()
        conn.close()

        send_email(email, otp)

        return redirect(f'/verify_otp?email={email}')
    return render_template('signup.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    email = request.args.get('email')
    if request.method == 'POST':
        otp_entered = request.form['otp']
        email = request.form['email']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user and user['otp'] == otp_entered and user['otp_expiry'] > datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
            if not user['email_verified']:
                conn.execute('UPDATE users SET email_verified = 1 WHERE email = ?', (email,))
                conn.commit()
                conn.close()
                flash('Registration successful! Please log in.', 'success')
                return redirect('/login')
            else:
                conn.close()
                session['user_id'] = user['id']
                return redirect('/dashboard')
        else:
            return "Invalid OTP or OTP expired!"

    return render_template('verify_otp.html', email=email)

@app.route('/zerodha_setup', methods=['GET', 'POST'])
def zerodha_setup():
    if 'user_id' not in session:
        return redirect('/')

    error = request.args.get('error')

    if request.method == 'POST':
        app_key = request.form['app_key']
        app_secret = request.form['app_secret']

        conn = get_db_connection()
        conn.execute('UPDATE users SET app_key = ?, app_secret = ? WHERE id = ?',
                     (app_key, app_secret, session['user_id']))
        conn.commit()
        conn.close()

        return redirect('/dashboard')

    return render_template('zerodha_setup.html', error=error)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            otp = secrets.token_hex(3).upper()
            otp_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

            conn = get_db_connection()
            conn.execute('UPDATE users SET otp = ?, otp_expiry = ? WHERE id = ?',
                         (otp, otp_expiry, user['id']))
            conn.commit()
            conn.close()

            send_email(email, otp)
            return redirect(f'/verify_otp?email={email}')
        else:
            flash('User not found. Please sign up.', 'error')
            return redirect('/signup')

    return render_template("login.html")


@app.route("/zerodha_login")
def zerodha_login():
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if not user or not user['app_key']:
        return redirect("/zerodha_setup?error=Please set up your API key")

    kite.api_key = user['app_key']
    login_url = kite.login_url()
    return redirect(login_url)


@app.route("/callback")
def callback():
    if 'user_id' not in session:
        return redirect('/')

    request_token = request.args.get("request_token")
    if not request_token:
        return "Request token not found", 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if not user or not user['app_key'] or not user['app_secret']:
        return "App key or secret not configured", 400

    kite.api_key = user['app_key']

    try:
        data = kite.generate_session(request_token, api_secret=user['app_secret'])
        session['access_token'] = data["access_token"]
        kite.set_access_token(data["access_token"])
        return redirect("/dashboard")
    except Exception as e:
        logging.error(f"Error generating session: {e}")
        return "Error generating session", 500

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect("/")

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if not user['email_verified']:
        return redirect(f"/verify_otp?email={user['email']}")

    if not user['app_key'] or not user['app_secret']:
        return redirect('/zerodha_setup')
        
    try:
        if 'access_token' not in session:
            return render_template("dashboard.html", user_name=None, balance='N/A', access_token=None)

        kite.set_access_token(session['access_token'])
        profile = kite.profile()
        margins = kite.margins()
        user_name = profile.get("user_name")
        balance = margins.get("equity", {}).get("available", {}).get("live_balance")
        return render_template("dashboard.html", user_name=user_name, balance=balance, access_token=session.get('access_token'))
    except Exception as e:
        logging.error(f"Error fetching data for dashboard: {e}")
        # If the access token is invalid, redirect to the login page
        if "Invalid `api_key` or `access_token`" in str(e):
            session.pop('access_token', None)
            return redirect("/zerodha_setup?error=Invalid API key or secret")
        return "Error fetching data for dashboard", 500


@app.route("/logout")
def logout():
    session.pop('access_token', None)
    session.pop('user_id', None)
    return redirect("/")

@app.route("/strategy/start", methods=['POST'])
def start_strategy():
    if 'access_token' not in session:
        return redirect("/")

    strategy_id = str(uuid.uuid4())
    strategy_name = request.form.get('strategy')
    instrument = request.form.get('instrument')
    candle_time = request.form.get('candle-time')
    start_time = request.form.get('start-time')
    end_time = request.form.get('end-time')
    stop_loss = request.form.get('stop-loss')
    target_profit = request.form.get('target-profit')
    quantity = request.form.get('quantity')
    trailing_stop_loss = request.form.get('trailing-stop-loss')

    if strategy_name == 'orb':
        strategy = ORB(kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, quantity, trailing_stop_loss)
        strategy.run()
        running_strategies[strategy_id] = {
            'name': 'ORB',
            'instrument': instrument,
            'status': 'running',
            'strategy': strategy
        }

    return redirect("/dashboard")

@app.route("/backtest", methods=['POST'])
def backtest():
    if 'access_token' not in session:
        return redirect("/")

    strategy_name = request.form.get('strategy')
    instrument = request.form.get('instrument')
    from_date = request.form.get('from_date')
    to_date = request.form.get('to_date')
    # Other parameters can be added here as needed

    if strategy_name == 'orb':
        # In a real application, you would get all the parameters from the form
        strategy = ORB(kite, instrument, '5', '09:15', '15:00', '1', '2', '50', '0.5')
        pnl, trades = strategy.backtest(from_date, to_date)
        return jsonify({'pnl': pnl, 'trades': trades})

    return jsonify({'pnl': 0, 'trades': 0})

@app.route("/strategies")
def get_strategies():
    # This needs to be made serializable
    strategies = {}
    for strategy_id, strategy_info in running_strategies.items():
        strategies[strategy_id] = {
            'name': strategy_info['name'],
            'instrument': strategy_info['instrument'],
            'status': strategy_info['status']
        }
    return jsonify(strategies)

@app.route("/strategy/cancel/<strategy_id>")
def cancel_strategy(strategy_id):
    if strategy_id in running_strategies:
        del running_strategies[strategy_id]
    return redirect("/dashboard")

@socketio.on('connect')
def connect(auth):
    global ticker
    if 'user_id' in session and 'access_token' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        if ticker is None:
            ticker = Ticker(user['app_key'], session['access_token'], list(running_strategies.values()), socketio)
            ticker.start()
    emit('my_response', {'data': 'Connected'})

@socketio.on('disconnect')
def disconnect():
    logging.info('Client disconnected')

if __name__ == "__main__":
    socketio.run(app, debug=True, port=8000, allow_unsafe_werkzeug=True)