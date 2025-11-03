from flask import Flask, request, redirect, render_template, jsonify, session, flash
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from kiteconnect import KiteConnect
import logging
import random
import time
from threading import Thread
from strategies.orb import ORB
from strategies.capture_mountain_signal import CaptureMountainSignal
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
from chat import chat_bp
from utils.backtest_metrics import calculate_all_metrics

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Configure CORS
CORS(app, 
     origins=config.CORS_ORIGINS,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'])

# Configure SocketIO with CORS - allow both frontend and backend origins for development
socketio_cors_origins = config.CORS_ORIGINS + ['http://localhost:8000', 'http://127.0.0.1:8000']
socketio = SocketIO(app, 
                    cors_allowed_origins=socketio_cors_origins,
                    async_mode='threading',
                    logger=False,  # Disable SocketIO verbose logging to reduce noise
                    engineio_logger=False)  # Disable EngineIO verbose logging to reduce noise

from apscheduler.schedulers.background import BackgroundScheduler

# Scheduler for automatic data collection
def start_data_collection():
    with app.app_context():
        conn = get_db_connection()
        conn.execute('UPDATE tick_data_status SET status = "Running"')
        conn.commit()
        conn.close()
        logging.info("Started automatic data collection.")

def stop_data_collection():
    with app.app_context():
        conn = get_db_connection()
        conn.execute('UPDATE tick_data_status SET status = "Stopped"')
        conn.commit()
        conn.close()
        logging.info("Stopped automatic data collection.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=start_data_collection, trigger="cron", day_of_week='mon-fri', hour=9, minute=15)
scheduler.add_job(func=stop_data_collection, trigger="cron", day_of_week='mon-fri', hour=15, minute=30)
scheduler.start()

@app.before_request
def make_session_permanent():
    session.permanent = False

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors with JSON response for API routes"""
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'message': 'Route not found'}), 404
    # For non-API routes, return a simple text response
    return 'Not Found', 404

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
    message["Subject"] = "Your OTP for DRP Infotech Trading Platform"
    message["From"] = f"DRP Infotech Pvt Ltd <{sender_email}>"
    message["To"] = receiver_email

    text = f"""
    DRP Infotech Pvt Ltd - Algorithmic Trading Platform
    
    Hi,
    Your OTP for login is: {otp}
    
    This OTP is valid for 10 minutes.
    
    If you didn't request this OTP, please ignore this email.
    
    Best regards,
    DRP Infotech Pvt Ltd
    Email: contact@drpinfotech.com
    Website: drpinfotech.com
    """
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0d6efd; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">DRP Infotech Pvt Ltd</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px;">Algorithmic Trading Platform</p>
                </div>
                <div style="background-color: #f8f9fa; padding: 30px; border-radius: 0 0 5px 5px;">
                    <h3 style="color: #0d6efd; margin-top: 0;">OTP Verification</h3>
                    <p>Hi,</p>
                    <p>Your OTP for login is:</p>
                    <div style="background-color: white; padding: 20px; text-align: center; border: 2px dashed #0d6efd; border-radius: 5px; margin: 20px 0;">
                        <h1 style="color: #0d6efd; margin: 0; font-size: 32px; letter-spacing: 5px;">{otp}</h1>
                    </div>
                    <p style="color: #666; font-size: 14px;">This OTP is valid for <strong>10 minutes</strong>.</p>
                    <p style="color: #666; font-size: 14px;">If you didn't request this OTP, please ignore this email.</p>
                    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 30px 0;">
                    <div style="text-align: center; color: #666; font-size: 12px;">
                        <p style="margin: 5px 0;"><strong>DRP Infotech Pvt Ltd</strong></p>
                        <p style="margin: 5px 0;">Email: <a href="mailto:contact@drpinfotech.com" style="color: #0d6efd; text-decoration: none;">contact@drpinfotech.com</a></p>
                        <p style="margin: 5px 0;">Website: <a href="https://drpinfotech.com" style="color: #0d6efd; text-decoration: none;">drpinfotech.com</a></p>
                    </div>
                </div>
            </div>
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

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/chart_data')
def api_chart_data():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    date_str = request.args.get('date')
    instrument = request.args.get('instrument', 'BANKNIFTY')  # Default: BANKNIFTY
    interval = request.args.get('interval', '5m')  # 1m,3m,5m,15m,30m,60m
    try:
        if not date_str:
            return jsonify({'candles': [], 'ema': []})
        # Parse selected date (YYYY-MM-DD)
        selected_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        # Build from/to with market timings 09:15 to 15:30
        start_dt = datetime.datetime.combine(selected_date, datetime.time(9, 15))
        end_dt = datetime.datetime.combine(selected_date, datetime.time(15, 30))

        # Resolve instrument token for index
        if instrument.upper() == 'NIFTY':
            token = 256265
        elif instrument.upper() == 'BANKNIFTY':
            token = 260105
        else:
            return jsonify({'candles': [], 'ema': []})

        # Map interval to Kite granularity
        interval_map = {
            '1m': 'minute',
            '3m': '3minute',
            '5m': '5minute',
            '15m': '15minute',
            '30m': '30minute',
            '60m': '60minute'
        }
        kite_interval = interval_map.get(interval, '5minute')

        # Fetch historical data from Kite
        try:
            hist = kite.historical_data(token, start_dt, end_dt, kite_interval)
        except Exception as e:
            logging.error(f"Error fetching historical data: {e}")
            return jsonify({'candles': [], 'ema': []})

        # Prepare candles and compute indicators
        candles = []
        closes = []
        ema5 = []
        ema20 = []
        rsi14 = []
        for row in hist:
            ts = row.get('date')
            # Kite returns datetime; serialize to ISO string
            if isinstance(ts, (datetime.datetime, datetime.date)):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)
            o = float(row.get('open', 0) or 0)
            h = float(row.get('high', 0) or 0)
            l = float(row.get('low', 0) or 0)
            c = float(row.get('close', 0) or 0)
            candles.append({'x': ts_str, 'o': o, 'h': h, 'l': l, 'c': c})
            closes.append(c)

        # EMA helper
        def compute_ema(values, period):
            if not values:
                return []
            mult = 2 / (period + 1)
            ema_vals = []
            ema_curr = float(values[0])
            for i, val in enumerate(values):
                ema_curr = (val - ema_curr) * mult + ema_curr if i > 0 else ema_curr
                ema_vals.append(ema_curr)
            return ema_vals

        # RSI(14) simple Wilder's method
        def compute_rsi(values, period=14):
            if len(values) < period + 1:
                return [None] * len(values)
            gains = []
            losses = []
            for i in range(1, period + 1):
                change = values[i] - values[i - 1]
                gains.append(max(change, 0))
                losses.append(abs(min(change, 0)))
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            rsi_series = [None] * period
            for i in range(period, len(values)):
                if i > period:
                    change = values[i] - values[i - 1]
                    gain = max(change, 0)
                    loss = abs(min(change, 0))
                    avg_gain = (avg_gain * (period - 1) + gain) / period
                    avg_loss = (avg_loss * (period - 1) + loss) / period
                rs = (avg_gain / avg_loss) if avg_loss != 0 else float('inf')
                rsi_series.append(100 - (100 / (1 + rs)))
            return rsi_series

        if closes:
            ema5_vals = compute_ema(closes, 5)
            ema20_vals = compute_ema(closes, 20)
            rsi_vals = compute_rsi(closes, 14)
            for i in range(len(candles)):
                ema5.append({'x': candles[i]['x'], 'y': float(ema5_vals[i]) if i < len(ema5_vals) else None})
                ema20.append({'x': candles[i]['x'], 'y': float(ema20_vals[i]) if i < len(ema20_vals) else None})
                rsi14.append({'x': candles[i]['x'], 'y': float(rsi_vals[i]) if rsi_vals[i] is not None else None})

        return jsonify({'candles': candles, 'ema5': ema5, 'ema20': ema20, 'rsi14': rsi14})
    except Exception as e:
        logging.error(f"/api/chart_data error: {e}", exc_info=True)
        return jsonify({'candles': [], 'ema': []}), 200

@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(f"{config.FRONTEND_URL}/dashboard")
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
            flash('Email already exists!', 'error')
            return redirect('/signup')

        otp = secrets.token_hex(3).upper()
        otp_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

        conn.execute('INSERT INTO users (mobile, email, app_key, app_secret, otp, otp_expiry) VALUES (?, ?, ?, ?, ?, ?)',
                     (mobile, email, app_key, app_secret, otp, otp_expiry))
        conn.commit()
        conn.close()

        send_email(email, otp)

        return redirect(f'/verify_otp?email={email}')
    return render_template('signup.html')

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """API endpoint for signup that accepts JSON"""
    try:
        if request.is_json:
            data = request.get_json()
            mobile = data.get('mobile')
            email = data.get('email')
            app_key = data.get('app_key')
            app_secret = data.get('app_secret')
        else:
            mobile = request.form.get('mobile')
            email = request.form.get('email')
            app_key = request.form.get('app_key')
            app_secret = request.form.get('app_secret')
        
        if not all([mobile, email, app_key, app_secret]):
            return jsonify({'status': 'error', 'message': 'All fields are required'}), 400

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Email already exists!'
            }), 400

        otp = secrets.token_hex(3).upper()
        otp_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

        conn.execute('INSERT INTO users (mobile, email, app_key, app_secret, otp, otp_expiry) VALUES (?, ?, ?, ?, ?, ?)',
                     (mobile, email, app_key, app_secret, otp, otp_expiry))
        conn.commit()
        conn.close()

        send_email(email, otp)
        
        return jsonify({
            'status': 'success',
            'message': 'Signup successful! OTP sent to your email. Please verify.',
            'redirect': '/login'
        })
    except Exception as e:
        logging.error(f"Error in api_signup: {e}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred. Please try again.'
        }), 500

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
                return redirect('/welcome')
        else:
            return render_template('verify_otp.html', email=email, error='Invalid OTP or OTP expired!')

    return render_template('verify_otp.html', email=email)

@app.route('/api/verify_otp', methods=['POST'])
@app.route('/api/verify-otp', methods=['POST'])
def api_verify_otp():
    """API endpoint for OTP verification that accepts JSON"""
    try:
        if request.is_json:
            data = request.get_json()
            otp_entered = data.get('otp')
            email = data.get('email')
        else:
            otp_entered = request.form.get('otp')
            email = request.form.get('email')
        
        if not all([otp_entered, email]):
            return jsonify({'status': 'error', 'message': 'OTP and email are required'}), 400

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if not user:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404

        # Check if OTP is valid and not expired
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if user['otp'] == otp_entered and user['otp_expiry'] > current_time:
            if not user['email_verified']:
                # First time verification - new registration
                conn.execute('UPDATE users SET email_verified = 1 WHERE email = ?', (email,))
                conn.commit()
                conn.close()
                return jsonify({
                    'status': 'success',
                    'message': 'Registration successful! Please log in.',
                    'redirect': '/login'  # Relative path for React Router
                })
            else:
                # Already verified - login
                conn.close()
                session['user_id'] = user['id']
                return jsonify({
                    'status': 'success',
                    'message': 'OTP verified successfully!',
                    'redirect': '/welcome'  # Relative path for React Router
                })
        else:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Invalid OTP or OTP expired!'
            }), 400
    except Exception as e:
        logging.error(f"Error in api_verify_otp: {e}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred. Please try again.'
        }), 500

@app.route('/welcome')
def welcome():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('welcome.html')

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
                         (otp, otp_expiry.strftime('%Y-%m-%d %H:%M:%S'), user['id']))
            conn.commit()
            conn.close()

            send_email(email, otp)
            return redirect(f'{config.FRONTEND_URL}/verify-otp?email={email}')
        else:
            flash('User not found. Please sign up.', 'error')
            return redirect(f'{config.FRONTEND_URL}/signup')

    return render_template("login.html")

@app.route("/api/login", methods=['POST'])
def api_login():
    """API endpoint for login that accepts JSON"""
    try:
        if request.is_json:
            data = request.get_json()
            email = data.get('email')
        else:
            email = request.form.get('email')
        
        if not email:
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            otp = secrets.token_hex(3).upper()
            otp_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

            conn = get_db_connection()
            conn.execute('UPDATE users SET otp = ?, otp_expiry = ? WHERE id = ?',
                         (otp, otp_expiry.strftime('%Y-%m-%d %H:%M:%S'), user['id']))
            conn.commit()
            conn.close()

            send_email(email, otp)
            return jsonify({
                'status': 'success',
                'message': 'OTP sent successfully! Please check your email.',
                'redirect': '/verify-otp'  # Relative path for React Router
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'User not found. Please sign up.'
            }), 404
    except Exception as e:
        logging.error(f"Error in api_login: {e}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred. Please try again.'
        }), 500


@app.route("/zerodha_login")
def zerodha_login():
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if not user or not user['app_key'] or not user['app_secret']:
        flash('Please set up your API key and secret during signup.', 'error')
        return redirect('/signup')

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
        return redirect(f"{config.FRONTEND_URL}/dashboard")
    except Exception as e:
        logging.error(f"Error generating session: {e}")
        return "Error generating session", 500

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect("/")

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    strategies = conn.execute('SELECT * FROM strategies WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()

    if not user['email_verified']:
        return redirect(f"/verify_otp?email={user['email']}")
        
    try:
        if 'access_token' not in session:
            return redirect('/welcome')

        kite.set_access_token(session['access_token'])
        profile = kite.profile()
        margins = kite.margins()
        user_name = profile.get("user_name")
        balance = margins.get("equity", {}).get("available", {}).get("live_balance")
        return render_template("dashboard.html", user_name=user_name, balance=balance, access_token=session.get('access_token'), strategies=strategies)
    except Exception as e:
        logging.error(f"Error fetching data for dashboard: {e}")
        # If the access token is invalid, redirect to the login page
        if "Invalid `api_key` or `access_token`" in str(e):
            session.pop('access_token', None)
            flash('Your Zerodha session is invalid or expired. Please log in again.', 'error')
            return redirect('/welcome')
        flash('An unexpected error occurred while fetching dashboard data.', 'error')
        return redirect('/welcome')


@app.route("/logout")
def logout():
    session.pop('access_token', None)
    session.pop('user_id', None)
    return redirect("/")

@app.route("/api/logout", methods=['POST'])
def api_logout():
    session.pop('access_token', None)
    session.pop('user_id', None)
    return jsonify({'status': 'success', 'message': 'Logged out successfully'})

@app.route("/api/user-data")
def api_user_data():
    if 'user_id' not in session:
        return jsonify({
            'status': 'error', 
            'message': 'User not logged in',
            'authenticated': False,
            'user_id': None
        }), 401
    
    try:
        user_id = session['user_id']
        if 'access_token' not in session:
            return jsonify({
                'status': 'success',
                'authenticated': True,
                'user_id': user_id,
                'user_name': 'Guest',
                'balance': 0,
                'access_token_present': False
            })
        
        kite.set_access_token(session['access_token'])
        profile = kite.profile()
        margins = kite.margins()
        user_name = profile.get("user_name", "Guest")
        balance = margins.get("equity", {}).get("available", {}).get("live_balance", 0)
        
        return jsonify({
            'status': 'success',
            'authenticated': True,
            'user_id': user_id,
            'user_name': user_name,
            'balance': balance,
            'access_token_present': True
        })
    except Exception as e:
        logging.error(f"Error fetching user data: {e}")
        if "Invalid `api_key` or `access_token`" in str(e) or "Incorrect `api_key` or `access_token`" in str(e):
            session.pop('access_token', None)
            return jsonify({
                'status': 'success',
                'authenticated': True,
                'user_id': session.get('user_id'),
                'user_name': 'Guest',
                'balance': 0,
                'access_token_present': False,
                'message': 'Zerodha session expired'
            })
        return jsonify({
            'status': 'success',
            'authenticated': True,
            'user_id': session.get('user_id'),
            'user_name': 'Guest',
            'balance': 0,
            'access_token_present': False
        })

@app.route("/strategy/save", methods=['POST'])
@app.route("/api/strategy/save", methods=['POST'])
def save_strategy():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    user_id = session['user_id']
    
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
        strategy_id = data.get('strategy_id')
        strategy_name_input = data.get('strategy-name') or data.get('strategy_name')
        strategy_type = data.get('strategy') or data.get('strategy_type')
        instrument = data.get('instrument')
        candle_time = data.get('candle-time') or data.get('candle_time')
        execution_start = data.get('execution-start') or data.get('execution_start')
        execution_end = data.get('execution-end') or data.get('execution_end')
        stop_loss = data.get('stop-loss') or data.get('stop_loss')
        target_profit = data.get('target-profit') or data.get('target_profit')
        total_lot = data.get('total-lot') or data.get('total_lot')
        trailing_stop_loss = data.get('trailing-stop-loss') or data.get('trailing_stop_loss')
        segment = data.get('segment')
        trade_type = data.get('trade-type') or data.get('trade_type')
        strike_price = data.get('strike-price') or data.get('strike_price')
        expiry_type = data.get('expiry-type') or data.get('expiry_type')
        ema_period = data.get('ema-period') or data.get('ema_period')
        # Enhanced strategy data (stored as JSON strings)
        indicators = data.get('indicators', [])
        entry_rules = data.get('entry_rules', [])
        exit_rules = data.get('exit_rules', [])
        
        import json
        indicators_json = json.dumps(indicators) if indicators else None
        entry_rules_json = json.dumps(entry_rules) if entry_rules else None
        exit_rules_json = json.dumps(exit_rules) if exit_rules else None
    else:
        strategy_id = request.form.get('strategy_id')
        strategy_name_input = request.form.get('strategy-name')
        strategy_type = request.form.get('strategy')
        instrument = request.form.get('instrument')
        candle_time = request.form.get('candle-time')
        execution_start = request.form.get('execution-start')
        execution_end = request.form.get('execution-end')
        stop_loss = request.form.get('stop-loss')
        target_profit = request.form.get('target-profit')
        total_lot = request.form.get('total-lot')
        trailing_stop_loss = request.form.get('trailing-stop-loss')
        segment = request.form.get('segment')
        trade_type = request.form.get('trade-type')
        strike_price = request.form.get('strike-price')
        expiry_type = request.form.get('expiry-type')
        ema_period = request.form.get('ema-period')

    conn = get_db_connection()
    try:
        import json
        
        # Prepare JSON data
        indicators_json = None
        entry_rules_json = None
        exit_rules_json = None
        
        if request.is_json:
            indicators = data.get('indicators', [])
            entry_rules = data.get('entry_rules', [])
            exit_rules = data.get('exit_rules', [])
            indicators_json = json.dumps(indicators) if indicators else None
            entry_rules_json = json.dumps(entry_rules) if entry_rules else None
            exit_rules_json = json.dumps(exit_rules) if exit_rules else None
        
        if strategy_id:
            # Update existing strategy
            conn.execute(
                '''UPDATE strategies SET strategy_name = ?, strategy_type = ?, instrument = ?, candle_time = ?, 
                   start_time = ?, end_time = ?, stop_loss = ?, target_profit = ?, total_lot = ?, 
                   trailing_stop_loss = ?, segment = ?, trade_type = ?, strike_price = ?, expiry_type = ?, 
                   ema_period = ?, indicators = ?, entry_rules = ?, exit_rules = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = ? AND user_id = ?''',
                (strategy_name_input, strategy_type, instrument, candle_time, execution_start, execution_end, 
                 stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, 
                 expiry_type, ema_period, indicators_json, entry_rules_json, exit_rules_json, strategy_id, user_id)
            )
            message = 'Strategy updated successfully!'
        else:
            # Insert new strategy
            conn.execute(
                '''INSERT INTO strategies (user_id, strategy_name, strategy_type, instrument, candle_time, start_time, 
                   end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, 
                   strike_price, expiry_type, ema_period, indicators, entry_rules, exit_rules) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, strategy_name_input, strategy_type, instrument, candle_time, execution_start, 
                 execution_end, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, 
                 strike_price, expiry_type, ema_period, indicators_json, entry_rules_json, exit_rules_json)
            )
            message = 'Strategy saved successfully!'
        conn.commit()
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving strategy: {e}")
        return jsonify({'status': 'error', 'message': f'Error saving strategy: {e}'}), 500
    finally:
        conn.close()

@app.route("/strategy/edit/<int:strategy_id>", methods=['GET'])
def edit_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    strategy = conn.execute('SELECT * FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id'])).fetchone()
    conn.close()

    if strategy:
        return jsonify({'status': 'success', 'strategy': dict(strategy)})
    else:
        return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404

@app.route("/strategy/delete/<int:strategy_id>", methods=['POST'])
@app.route("/api/strategy/delete/<int:strategy_id>", methods=['POST'])
def delete_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # If strategy is running, stop it first
    unique_run_id_to_del = None
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info.get('db_id') == strategy_id:
            unique_run_id_to_del = unique_run_id
            break
    
    if unique_run_id_to_del:
        del running_strategies[unique_run_id_to_del]

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id']))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Strategy deleted successfully!'})
    except Exception as e:
        conn.rollback()
        logging.error(f"Error deleting strategy: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error deleting strategy: {e}'}), 500
    finally:
        conn.close()

@app.route("/strategy/deploy/<int:strategy_id>", methods=['POST', 'OPTIONS'])
@app.route("/api/strategy/deploy/<int:strategy_id>", methods=['POST', 'OPTIONS'])
def deploy_strategy(strategy_id):
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401
    
    if 'access_token' not in session:
        return jsonify({'status': 'error', 'message': 'Zerodha not connected. Please connect your Zerodha account first.'}), 401

    conn = get_db_connection()
    strategy_data = conn.execute('SELECT * FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id'])).fetchone()
    conn.close()

    if not strategy_data:
        return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404

    # Handle both form and JSON requests - be lenient with parsing
    paper_trade = False
    try:
        if request.content_type and 'application/json' in request.content_type:
            # Try to parse JSON, but don't fail if it's empty or invalid
            data = request.get_json(silent=True, force=True)
            if data:
                paper_trade = data.get('paper_trade', False)
        elif request.form:
            paper_trade = request.form.get('paper_trade') == 'on'
    except Exception as e:
        logging.warning(f"Error parsing request data in deploy_strategy: {e}")
        paper_trade = False

    # Check if strategy is already running
    # Remove from running_strategies if it exists but is not actually running
    for unique_run_id, running_strat_info in list(running_strategies.items()):
        if running_strat_info['db_id'] == strategy_id:
            if running_strat_info['status'] == 'running' and strategy_data['status'] not in ['sq_off', 'paused']:
                return jsonify({'status': 'error', 'message': 'Strategy is already running'}), 400
            else:
                # Remove stale entries (paused, error, etc.) to allow redeployment
                del running_strategies[unique_run_id]
                logging.info(f"Removed stale strategy entry {unique_run_id} for strategy {strategy_id} before redeployment")

    # Access sqlite3.Row fields directly (they support dict-like access)
    try:
        strategy_type = strategy_data['strategy_type']
    except (KeyError, IndexError):
        strategy_type = None
    
    # Validate that strategy status allows deployment
    try:
        current_status = strategy_data['status']
    except (KeyError, IndexError):
        current_status = 'saved'
    if current_status not in ['saved', 'paused', 'error', 'sq_off']:
        if current_status == 'running':
            return jsonify({'status': 'error', 'message': 'Strategy is already running'}), 400
        else:
            return jsonify({'status': 'error', 'message': f'Cannot deploy strategy with status: {current_status}'}), 400

    # Validate strategy_type exists
    if not strategy_type:
        logging.error(f"Strategy {strategy_id} has no strategy_type")
        return jsonify({'status': 'error', 'message': 'Strategy type not found. Please edit and save the strategy first.'}), 400

    try:
        strategy_class = None
        if strategy_type == 'orb':
            strategy_class = ORB
        elif strategy_type == 'capture_mountain_signal':
            strategy_class = CaptureMountainSignal
        else:
            logging.error(f"Unknown strategy type: {strategy_type} for strategy {strategy_id}")
            return jsonify({'status': 'error', 'message': f'Unknown strategy type: {strategy_type}'}), 400

        # Instantiate the strategy with saved parameters
        strategy = strategy_class(
            kite,
            strategy_data['instrument'],
            strategy_data['candle_time'],
            strategy_data['start_time'],
            strategy_data['end_time'],
            strategy_data['stop_loss'],
            strategy_data['target_profit'],
            strategy_data['total_lot'],
            strategy_data['trailing_stop_loss'],
            strategy_data['segment'],
            strategy_data['trade_type'],
            strategy_data['strike_price'],
            strategy_data['expiry_type'],
            strategy_data['strategy_name'],
            paper_trade=paper_trade
        )
        strategy.run()

        # Store in-memory with a reference to the DB ID
        unique_run_id = str(uuid.uuid4())
        running_strategies[unique_run_id] = {
            'db_id': strategy_id,
            'name': strategy_data['strategy_name'],
            'instrument': strategy_data['instrument'],
            'status': 'running',
            'strategy_type': strategy_type, # Add strategy_type here
            'strategy': strategy, # Store the actual strategy object
            'user_id': session['user_id'] # Add user_id for WebSocket room management
        }

        # Update status in DB
        conn = get_db_connection()
        conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('running', strategy_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Strategy deployed successfully!'})
    except Exception as e:
        logging.error(f"Error deploying strategy {strategy_id}: {e}", exc_info=True)
        try:
            conn = get_db_connection()
            conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('error', strategy_id))
            conn.commit()
            conn.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': f'Error deploying strategy: {str(e)}'}), 500

@app.route("/strategy/pause/<int:strategy_id>", methods=['POST'])
@app.route("/api/strategy/pause/<int:strategy_id>", methods=['POST'])
def pause_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Find the running strategy by its db_id
    strategy_found_in_memory = False
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == strategy_id:
            strategy_found_in_memory = True
            # Here you would implement logic to actually pause the strategy
            # For now, we just change its in-memory status
            running_strat_info['status'] = 'paused'
            break
    
    # Update status in DB regardless of whether it's in memory or not
    conn = get_db_connection()
    try:
        # Check if strategy exists and belongs to user
        strategy_row = conn.execute(
            'SELECT status FROM strategies WHERE id = ? AND user_id = ?',
            (strategy_id, session['user_id'])
        ).fetchone()
        
        if strategy_row is None:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404
        
        current_status = strategy_row['status']
        
        # Only allow pause if strategy is currently running
        if current_status != 'running':
            conn.close()
            return jsonify({
                'status': 'error', 
                'message': f'Strategy is not running. Current status: {current_status}'
            }), 400
        
        # Update status in DB to paused
        conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('paused', strategy_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Strategy paused successfully!'})
    except Exception as e:
        conn.close()
        logging.error(f"Error pausing strategy {strategy_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error pausing strategy: {str(e)}'}), 500

@app.route("/strategy/squareoff/<int:strategy_id>", methods=['POST'])
@app.route("/api/strategy/squareoff/<int:strategy_id>", methods=['POST'])
def squareoff_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Find the running strategy by its db_id in the in-memory dict and remove it
    unique_run_id_to_del = None
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == strategy_id:
            unique_run_id_to_del = unique_run_id
            break
    
    if unique_run_id_to_del:
        del running_strategies[unique_run_id_to_del]

    # Update status in DB
    conn = get_db_connection()
    conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('sq_off', strategy_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Strategy squared off successfully!'})

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

@app.route("/api/strategies")
def api_get_strategies():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    strategies = conn.execute('SELECT * FROM strategies WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()

    # Convert Row objects to dictionaries for JSON serialization
    strategies_list = [dict(s) for s in strategies]
    return jsonify({'status': 'success', 'strategies': strategies_list})

@app.route("/api/running-strategies")
def api_get_running_strategies():
    """Get currently running strategies"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Get running strategies from database
    conn = get_db_connection()
    running_strategies = conn.execute(
        'SELECT * FROM strategies WHERE user_id = ? AND status = ?', 
        (session['user_id'], 'running')
    ).fetchall()
    conn.close()

    # Convert to list of dictionaries
    strategies_list = [dict(s) for s in running_strategies]
    return jsonify({'status': 'success', 'strategies': strategies_list})

@app.route("/strategy/cancel/<strategy_id>")
def cancel_strategy(strategy_id):
    if strategy_id in running_strategies:
        del running_strategies[strategy_id]
    return redirect("/dashboard")

@app.route("/backtest", methods=['POST'])
def backtest_strategy():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Extract strategy parameters from request form
    instrument = request.form.get('backtest-instrument')
    candle_time = request.form.get('candle-time') # Assuming this comes from the form
    execution_start = request.form.get('execution-start') # Assuming this comes from the form
    execution_end = request.form.get('execution-end') # Assuming this comes from the form
    stop_loss = float(request.form.get('stop-loss')) # Assuming this comes from the form
    target_profit = float(request.form.get('target-profit')) # Assuming this comes from the form
    total_lot = int(request.form.get('total-lot')) # Assuming this comes from the form
    trailing_stop_loss = float(request.form.get('trailing-stop-loss')) # Assuming this comes from the form
    segment = request.form.get('segment') # Assuming this comes from the form
    trade_type = request.form.get('trade-type') # Assuming this comes from the form
    strike_price = request.form.get('strike-price') # Assuming this comes from the form
    expiry_type = request.form.get('expiry-type') # Assuming this comes from the form
    from_date_str = request.form.get('backtest-from-date')
    to_date_str = request.form.get('backtest-to-date')

    # Convert date strings to datetime objects
    from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d').date()
    to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d').date()

    try:
        # Instantiate ORB strategy (using dummy kite for backtesting if not logged in)
        # In a real scenario, you might want to mock kite or ensure a valid connection for historical data
        current_kite = kite # Use the global kite instance

        orb_strategy = ORB(
            current_kite,
            instrument,
            candle_time,
            execution_start,
            execution_end,
            stop_loss,
            target_profit,
            total_lot,
            trailing_stop_loss,
            segment,
            trade_type,
            strike_price,
            expiry_type,
            "Backtest_ORB"
        )

        pnl, trades = orb_strategy.backtest(from_date, to_date)

        # Enhanced metrics calculation
        # Convert trades to format expected by metrics calculator
        trade_list = [{'pnl': pnl / trades if trades > 0 else 0, 'date': from_date} for _ in range(trades)]
        
        # Calculate comprehensive metrics
        metrics = calculate_all_metrics(trade_list, initial_capital=100000)
        metrics['simple_pnl'] = pnl
        metrics['simple_trades'] = trades

        return jsonify({
            'status': 'success',
            'pnl': pnl,
            'trades': trades,
            'metrics': metrics
        })
    except Exception as e:
        logging.error(f"Error during backtest: {e}")
        return jsonify({'status': 'error', 'message': f'Error during backtest: {e}'}), 500

@socketio.on('connect')
def connect(auth=None):
    """Handle SocketIO connection"""
    global ticker
    # Delay logging to avoid "write() before start_response" - log after connection is established
    user_id_from_session = None
    access_token_from_session = None
    access_token_present = False
    try:
        user_id_from_session = session.get('user_id')
        access_token_from_session = session.get('access_token')
        access_token_present = bool(access_token_from_session)
    except:
        pass  # Silently handle session access errors during handshake
    
    # Always accept connection to avoid WebSocket errors - handle invalid tokens gracefully
    try:
        access_token_valid = False
        if user_id_from_session and access_token_from_session:
            try:
                kite.set_access_token(access_token_from_session)
                kite.profile()  # Validate the token
                access_token_valid = True
            except Exception as e:
                error_msg = str(e)
                if "Invalid `api_key` or `access_token`" in error_msg or "Incorrect `api_key` or `access_token`" in error_msg:
                    try:
                        session.pop('access_token', None)
                    except:
                        pass  # Silently handle session errors
                    # Delay logging to avoid write() before start_response
                    try:
                        logging.warning("SocketIO: Invalid access token - accepting connection but not starting ticker")
                    except:
                        pass
                    # Accept connection but emit warning - don't start ticker
                    try:
                        emit('warning', {'message': 'Zerodha session expired. Please reconnect to Zerodha.'})
                    except:
                        pass  # If emit fails, connection is already established
                else:
                    # Delay logging to avoid write() before start_response
                    try:
                        logging.error(f"SocketIO: Error validating token: {e}")
                    except:
                        pass
                    # Accept connection but emit error
                    try:
                        emit('error', {'message': 'Error validating Zerodha session'})
                    except:
                        pass

            if access_token_valid:
                conn = get_db_connection()
                try:
                    # Use cached user_id to avoid accessing session during handshake
                    user_id = user_id_from_session
                    if not user_id:
                        conn.close()
                        return True  # Accept connection but don't proceed
                    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                    if user is None:
                        try:
                            logging.error(f"SocketIO connect error: User with ID {user_id} not found in DB.")
                        except:
                            pass
                        try:
                            emit('error', {'message': 'User not found'})
                        except:
                            pass
                    elif user['app_key'] is None or not access_token_present:
                        try:
                            logging.warning(f"SocketIO connect warning: User {user['id']} has no app_key or access_token.")
                        except:
                            pass
                        try:
                            emit('warning', {'message': 'Zerodha credentials not configured'})
                        except:
                            pass
                    else:
                        # Start ticker if not already started
                        if ticker is None:
                            try:
                                # Use cached access_token to avoid session access during handshake
                                if access_token_from_session:
                                    ticker = Ticker(user['app_key'], access_token_from_session, running_strategies, socketio, kite)
                                    ticker.start()
                                try:
                                    logging.info("SocketIO: Ticker started successfully")
                                except:
                                    pass
                            except Exception as e:
                                try:
                                    logging.error(f"SocketIO: Error starting ticker: {e}", exc_info=True)
                                except:
                                    pass  # Don't let logging errors break connection
                                try:
                                    emit('error', {'message': 'Failed to start market data feed'})
                                except:
                                    pass
                finally:
                    conn.close()
        else:
            try:
                logging.info("SocketIO: Connected without authentication (no user_id or access_token in session)")
            except:
                pass  # Don't let logging errors break connection
            try:
                emit('info', {'message': 'Connected. Please log in to receive real-time market data.'})
            except:
                pass
        
        # Always emit connection success
        try:
            emit('my_response', {'data': 'Connected'})
        except:
            pass  # If emit fails, connection might still work
        
        # Log after connection is established to avoid "write() before start_response"
        try:
            logging.info(f"SocketIO: Connection accepted - Session: user_id={user_id_from_session}, access_token={'present' if access_token_present else 'missing'}")
        except:
            pass  # Don't let logging errors break the connection
        
        return True  # Always accept connection to avoid WebSocket errors
    except Exception as e:
        # Don't log with exc_info during handshake - it might cause write() errors
        try:
            logging.error(f"SocketIO connect error: {e}")
        except:
            pass  # Silently handle logging errors during handshake
        # Always return True to avoid "write() before start_response" - errors are handled via emits
        return True  # Accept connection even on error

@socketio.on('disconnect')
def disconnect():
    try:
        logging.info('Client disconnected')
    except Exception as e:
        # Silently handle disconnect errors to prevent "write() before start_response"
        pass
    return True

from strategies.orb import ORB

@app.route("/market_replay", methods=['POST'])
def market_replay():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    strategy_id = request.form.get('strategy')
    instrument_name = request.form.get('instrument')
    from_date_str = request.form.get('from-date')
    to_date_str = request.form.get('to-date')

    from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
    to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d')

    global instruments_df
    if instruments_df is None:
        try:
            instruments_df = kite.instruments()
        except Exception as e:
            logging.error(f"Error fetching instruments: {e}")
            return jsonify({'status': 'error', 'message': 'Could not fetch instruments'}), 500

    instrument = next((item for item in instruments_df if item["name"] == instrument_name and item["exchange"] == "NFO"), None)
    if not instrument:
        return jsonify({'status': 'error', 'message': f'Instrument {instrument_name} not found'}), 404
    instrument_token = instrument['instrument_token']

    conn = get_db_connection()
    strategy_data = conn.execute('SELECT * FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id'])).fetchone()

    if not strategy_data:
        return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404

    ticks_rows = conn.execute(
        'SELECT * FROM tick_data WHERE instrument_token = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp',
        (instrument_token, from_date, to_date)
    ).fetchall()
    conn.close()

    if not ticks_rows:
        return jsonify({'status': 'error', 'message': 'No data found for the selected criteria'}), 404

    ticks = [dict(row) for row in ticks_rows]

    strategy_type = strategy_data['strategy_type']
    strategy_class = None
    if strategy_type == 'orb':
        strategy_class = ORB
    elif strategy_type == 'capture_mountain_signal':
        strategy_class = CaptureMountainSignal
    else:
        return jsonify({'status': 'error', 'message': 'Unknown strategy'}), 400

    strategy = strategy_class(
        None, # No kite object needed for replay
        strategy_data['instrument'],
        strategy_data['candle_time'],
        strategy_data['start_time'],
        strategy_data['end_time'],
        strategy_data['stop_loss'],
        strategy_data['target_profit'],
        strategy_data['total_lot'],
        strategy_data['trailing_stop_loss'],
        strategy_data['segment'],
        strategy_data['trade_type'],
        strategy_data['strike_price'],
        strategy_data['expiry_type'],
        strategy_data['strategy_name']
    )

    pnl, trades = strategy.replay(ticks)

    return jsonify({'status': 'success', 'pnl': pnl, 'trades': trades})

instruments_df = None

@app.route("/tick_data/<instrument_token>")
def tick_data(instrument_token):
    if 'user_id' not in session:
        return jsonify([]), 401

    conn = get_db_connection()
    tick_data_rows = conn.execute('SELECT * FROM tick_data WHERE instrument_token = ? ORDER BY timestamp DESC LIMIT 100', (instrument_token,)).fetchall()
    conn.close()

    tick_data = [dict(row) for row in tick_data_rows]
    return jsonify(tick_data)

@app.route("/tick_data_status")
def tick_data_status():
    global instruments_df
    if 'user_id' not in session:
        return jsonify([]), 401

    if instruments_df is None:
        try:
            instruments_df = kite.instruments()
        except Exception as e:
            logging.error(f"Error fetching instruments: {e}")
            return jsonify([]), 500

    conn = get_db_connection()
    status_rows = conn.execute('SELECT * FROM tick_data_status').fetchall()

    status_data = []
    for row in status_rows:
        instrument_token = row['instrument_token']
        status = row['status']

        # Find trading symbol from the dataframe
        instrument_details = next((item for item in instruments_df if item["instrument_token"] == instrument_token), None)
        trading_symbol = instrument_details['tradingsymbol'] if instrument_details else f"Unknown ({instrument_token})"

        row_count = conn.execute('SELECT COUNT(*) FROM tick_data WHERE instrument_token = ?', (instrument_token,)).fetchone()[0]
        last_collected_at_row = conn.execute('SELECT MAX(timestamp) FROM tick_data WHERE instrument_token = ?', (instrument_token,)).fetchone()
        last_collected_at = last_collected_at_row[0] if last_collected_at_row and last_collected_at_row[0] else 'N/A'

        status_data.append({
            'instrument': trading_symbol,
            'instrument_token': instrument_token,
            'status': status,
            'row_count': row_count,
            'last_collected_at': last_collected_at
        })

    conn.close()
    return jsonify(status_data)

@app.route("/tick_data/start", methods=['POST'])
def start_tick_collection():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    conn.execute('UPDATE tick_data_status SET status = \'Running\'')
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route("/tick_data/pause", methods=['POST'])
def pause_tick_collection():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    conn.execute('UPDATE tick_data_status SET status = \'Paused\'')
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route("/tick_data/stop", methods=['POST'])
def stop_tick_collection():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    conn.execute('UPDATE tick_data_status SET status = \'Stopped\'')
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route("/strategy/status/<strategy_id>")
@app.route("/api/strategy/status/<strategy_id>")
def strategy_status(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    try:
        strategy_id_int = int(strategy_id)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid strategy ID'}), 400

    # Find the running strategy by its db_id
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info.get('db_id') == strategy_id_int:
            try:
                strategy_obj = running_strat_info.get('strategy')
                status_data = {}
                
                if strategy_obj and hasattr(strategy_obj, 'status'):
                    status_dict = strategy_obj.status
                    if isinstance(status_dict, dict):
                        # Safely convert status dict to JSON-serializable format
                        for key, value in status_dict.items():
                            try:
                                # Handle None first
                                if value is None:
                                    status_data[key] = None
                                # Convert datetime objects to strings
                                elif isinstance(value, datetime.datetime):
                                    status_data[key] = value.isoformat()
                                # Convert date objects to strings
                                elif isinstance(value, datetime.date):
                                    status_data[key] = value.isoformat()
                                # Handle numpy types BEFORE basic types (np.float64 is not a regular float)
                                elif hasattr(value, '__class__'):
                                    try:
                                        import numpy as np
                                        if isinstance(value, (np.integer, np.floating)):
                                            status_data[key] = None if np.isnan(value) else value.item()
                                        elif hasattr(value, 'item'):
                                            status_data[key] = value.item()
                                        elif isinstance(value, dict):
                                            # Nested dict
                                            status_data[key] = {}
                                            for k, v in value.items():
                                                if isinstance(v, (datetime.datetime, datetime.date)):
                                                    status_data[key][k] = v.isoformat()
                                                elif hasattr(v, '__class__'):
                                                    try:
                                                        if isinstance(v, (np.integer, np.floating)):
                                                            status_data[key][k] = None if np.isnan(v) else v.item()
                                                        elif hasattr(v, 'item'):
                                                            status_data[key][k] = v.item()
                                                        else:
                                                            status_data[key][k] = str(v) if v is not None else None
                                                    except:
                                                        status_data[key][k] = str(v) if v is not None else None
                                                else:
                                                    status_data[key][k] = v
                                        elif isinstance(value, list):
                                            # List with numpy items
                                            processed_list = []
                                            for item in value:
                                                if isinstance(item, (datetime.datetime, datetime.date)):
                                                    processed_list.append(item.isoformat())
                                                elif hasattr(item, '__class__'):
                                                    try:
                                                        if isinstance(item, (np.integer, np.floating)):
                                                            processed_list.append(None if np.isnan(item) else item.item())
                                                        elif hasattr(item, 'item'):
                                                            processed_list.append(item.item())
                                                        else:
                                                            processed_list.append(str(item))
                                                    except:
                                                        processed_list.append(str(item) if item is not None else None)
                                                else:
                                                    processed_list.append(item)
                                            status_data[key] = processed_list
                                        else:
                                            status_data[key] = str(value) if value is not None else None
                                    except Exception as conv_err:
                                        logging.debug(f"Could not convert value for key '{key}': {conv_err}")
                                        status_data[key] = None
                                # Handle basic JSON-serializable types
                                elif isinstance(value, (bool, str)):
                                    status_data[key] = value
                                elif isinstance(value, int):
                                    status_data[key] = value
                                elif isinstance(value, float):
                                    # Check for NaN
                                    if value != value:  # NaN check
                                        status_data[key] = None
                                    else:
                                        status_data[key] = value
                                # Handle nested dicts (non-numpy)
                                elif isinstance(value, dict):
                                    status_data[key] = {k: (v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else v) 
                                                       for k, v in value.items()}
                                # Handle lists (non-numpy)
                                elif isinstance(value, list):
                                    status_data[key] = [item.isoformat() if isinstance(item, (datetime.datetime, datetime.date)) else item 
                                                       for item in value]
                                # For unknown types, try string conversion or skip
                                else:
                                    try:
                                        status_data[key] = str(value) if value is not None else None
                                    except:
                                        pass  # Skip if can't convert
                            except Exception as e:
                                logging.warning(f"Error serializing status key '{key}': {e}")
                                continue
                
                status_data['strategy_type'] = running_strat_info.get('strategy_type', 'unknown')
                status_data['strategy_name_display'] = running_strat_info.get('name', 'Unknown Strategy')
                status_data['status'] = running_strat_info.get('status', 'running')
                status_data['running'] = True
                # Prefer aligned execution time from strategy if available
                try:
                    status_data['last_execution_time'] = strategy_obj.status.get('last_execution_time', datetime.datetime.now().isoformat())
                except Exception:
                    status_data['last_execution_time'] = datetime.datetime.now().isoformat()
                
                # Add historical candles if available
                if hasattr(strategy_obj, 'historical_data'):
                    candles = getattr(strategy_obj, 'historical_data', [])
                    historical_candles = []
                    for candle in candles[-50:]:  # Last 50 candles
                        try:
                            candle_date = candle.get('date') if isinstance(candle, dict) else getattr(candle, 'date', None)
                            if candle_date:
                                if isinstance(candle_date, datetime.datetime):
                                    date_str = candle_date.isoformat()
                                else:
                                    date_str = str(candle_date)
                            else:
                                date_str = datetime.datetime.now().isoformat()
                            
                            candle_dict = {
                                'time': date_str,
                                'open': candle.get('open') if isinstance(candle, dict) else getattr(candle, 'open', 0),
                                'high': candle.get('high') if isinstance(candle, dict) else getattr(candle, 'high', 0),
                                'low': candle.get('low') if isinstance(candle, dict) else getattr(candle, 'low', 0),
                                'close': candle.get('close') if isinstance(candle, dict) else getattr(candle, 'close', 0),
                                'volume': candle.get('volume', 0) if isinstance(candle, dict) else getattr(candle, 'volume', 0)
                            }
                            historical_candles.append(candle_dict)
                        except Exception as e:
                            logging.debug(f"Error processing candle for status: {e}")
                            continue
                    
                    # Calculate 5 EMA
                    if len(historical_candles) > 0 and hasattr(strategy_obj, 'ema_period'):
                        ema_period = getattr(strategy_obj, 'ema_period', 5)
                        if len(historical_candles) >= ema_period:
                            closes = [c['close'] for c in historical_candles]
                            multiplier = 2 / (ema_period + 1)
                            ema_values = []
                            ema = closes[0]
                            for close in closes:
                                ema = (close - ema) * multiplier + ema
                                ema_values.append(ema)
                            
                            for i, candle in enumerate(historical_candles):
                                if i < len(ema_values):
                                    candle['ema5'] = ema_values[i]
                    
                    status_data['historical_candles'] = historical_candles
                # Include today's signal history for UI
                try:
                    status_data['signal_history_today'] = strategy_obj.status.get('signal_history_today', [])
                except Exception:
                    status_data['signal_history_today'] = []
                return jsonify(status_data)
            except Exception as e:
                logging.error(f"Error getting strategy status for {strategy_id}: {e}", exc_info=True)
                return jsonify({
                    'status': 'error', 
                    'message': f'Error retrieving strategy status: {str(e)}',
                    'running': False
                }), 500
    
    # Strategy not in running_strategies - check database to see if it exists
    conn = get_db_connection()
    try:
        strategy_row = conn.execute(
            'SELECT strategy_name, status FROM strategies WHERE id = ? AND user_id = ?',
            (strategy_id_int, session['user_id'])
        ).fetchone()
        
        if strategy_row:
            # Strategy exists but is not currently running
            return jsonify({
                'status': 'not_running',
                'strategy_name_display': strategy_row['strategy_name'],
                'db_status': strategy_row['status'],
                'running': False,
                'message': f"Strategy '{strategy_row['strategy_name']}' is not currently running. Status: {strategy_row['status']}"
            })
        else:
            return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404
    except Exception as e:
        logging.error(f"Error checking database for strategy {strategy_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Error checking strategy status'}), 500
    finally:
        conn.close()

# WebSocket handlers for strategy monitoring
@socketio.on('subscribe_strategy')
def handle_subscribe_strategy(data):
    """Subscribe to real-time updates for a specific strategy"""
    try:
        user_id = None
        try:
            user_id = session.get('user_id')
        except Exception:
            user_id = None
        if not user_id:
            try:
                emit('error', {'message': 'User not authenticated'})
            except Exception:
                pass
            return True

        strategy_id = (data or {}).get('strategy_id')
        if not strategy_id:
            try:
                emit('error', {'message': 'Strategy ID required'})
            except Exception:
                pass
            return True

        # Join a room for this strategy
        from flask_socketio import join_room
        room_name = f"strategy_{user_id}_{strategy_id}"
        try:
            join_room(room_name)
        except Exception:
            pass
        try:
            logging.info(f"User {user_id} subscribed to strategy {strategy_id}")
        except Exception:
            pass
        try:
            emit('subscribed', {'strategy_id': str(strategy_id), 'message': 'Subscribed to strategy updates'})
        except Exception:
            pass
        return True
    except Exception:
        return True

@socketio.on('unsubscribe_strategy')
def handle_unsubscribe_strategy(data):
    """Unsubscribe from strategy updates"""
    try:
        user_id = None
        try:
            user_id = session.get('user_id')
        except Exception:
            user_id = None
        if not user_id:
            return True

        strategy_id = (data or {}).get('strategy_id')
        if strategy_id:
            from flask_socketio import leave_room
            room_name = f"strategy_{user_id}_{strategy_id}"
            try:
                leave_room(room_name)
            except Exception:
                pass
            try:
                logging.info(f"User {user_id} unsubscribed from strategy {strategy_id}")
            except Exception:
                pass
        return True
    except Exception as e:
        logging.debug(f"Error in unsubscribe_strategy: {e}")
        return True  # Silently handle errors during disconnect

@socketio.on('subscribe_market_data')
def handle_subscribe_market_data(data):
    """Subscribe to market data for strategy monitoring"""
    try:
        user_id = None
        try:
            user_id = session.get('user_id')
        except Exception:
            user_id = None
        if not user_id:
            try:
                emit('error', {'message': 'User not authenticated'})
            except Exception:
                pass
            return True

        # Join market data room
        from flask_socketio import join_room
        room_name = f"market_data_{user_id}"
        try:
            join_room(room_name)
        except Exception:
            pass
        try:
            emit('subscribed', {'message': 'Subscribed to market data'})
        except Exception:
            pass
        return True
    except Exception:
        return True

app.register_blueprint(chat_bp)

if __name__ == "__main__":
    socketio.run(
        app,
        debug=config.DEBUG,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        allow_unsafe_werkzeug=True
    )