from flask import Flask, request, redirect, render_template, jsonify, session, flash
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

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session management
socketio = SocketIO(app)

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

@app.route("/strategy/save", methods=['POST'])
def save_strategy():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    user_id = session['user_id']
    strategy_id = request.form.get('strategy_id') # Will be present if editing an existing strategy
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
        if strategy_id:
            # Update existing strategy
            conn.execute(
                'UPDATE strategies SET strategy_name = ?, strategy_type = ?, instrument = ?, candle_time = ?, start_time = ?, end_time = ?, stop_loss = ?, target_profit = ?, total_lot = ?, trailing_stop_loss = ?, segment = ?, trade_type = ?, strike_price = ?, expiry_type = ?, ema_period = ? WHERE id = ? AND user_id = ?',
                (strategy_name_input, strategy_type, instrument, candle_time, execution_start, execution_end, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, ema_period, strategy_id, user_id)
            )
            message = 'Strategy updated successfully!'
        else:
            # Insert new strategy
            conn.execute(
                'INSERT INTO strategies (user_id, strategy_name, strategy_type, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, ema_period) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (user_id, strategy_name_input, strategy_type, instrument, candle_time, execution_start, execution_end, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, ema_period)
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
def delete_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id']))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Strategy deleted successfully!'})
    except Exception as e:
        conn.rollback()
        logging.error(f"Error deleting strategy: {e}")
        return jsonify({'status': 'error', 'message': f'Error deleting strategy: {e}'}), 500
    finally:
        conn.close()

@app.route("/strategy/deploy/<int:strategy_id>", methods=['POST'])
def deploy_strategy(strategy_id):
    if 'user_id' not in session or 'access_token' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in or Zerodha not connected'}), 401

    conn = get_db_connection()
    strategy_data = conn.execute('SELECT * FROM strategies WHERE id = ? AND user_id = ?', (strategy_id, session['user_id'])).fetchone()
    conn.close()

    if not strategy_data:
        return jsonify({'status': 'error', 'message': 'Strategy not found'}), 404

    paper_trade = request.form.get('paper_trade') == 'on'

    # Check if strategy is already running
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == strategy_id and running_strat_info['status'] == 'running' and strategy_data['status'] != 'sq_off':
            return jsonify({'status': 'error', 'message': 'Strategy is already running'}), 400

    strategy_type = strategy_data['strategy_type']

    try:
        strategy_class = None
        if strategy_type == 'orb':
            strategy_class = ORB
        elif strategy_type == 'capture_mountain_signal':
            strategy_class = CaptureMountainSignal
        else:
            return jsonify({'status': 'error', 'message': 'Unknown strategy'}), 400

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
            'strategy': strategy # Store the actual strategy object
        }

        # Update status in DB
        conn = get_db_connection()
        conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('running', strategy_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Strategy deployed successfully!'})
    except Exception as e:
        logging.error(f"Error deploying strategy {strategy_id}: {e}")
        conn = get_db_connection()
        conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('error', strategy_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'error', 'message': f'Error deploying strategy: {e}'}), 500

@app.route("/strategy/pause/<int:strategy_id>", methods=['POST'])
def pause_strategy(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Find the running strategy by its db_id
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == strategy_id:
            # Here you would implement logic to actually pause the strategy
            # For now, we just change its in-memory status
            running_strat_info['status'] = 'paused'
            
            # Update status in DB
            conn = get_db_connection()
            conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('paused', strategy_id))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Strategy paused successfully!'})
    return jsonify({'status': 'error', 'message': 'Running strategy not found'}), 404

@app.route("/strategy/squareoff/<int:strategy_id>", methods=['POST'])
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

        return jsonify({'status': 'success', 'pnl': pnl, 'trades': trades})
    except Exception as e:
        logging.error(f"Error during backtest: {e}")
        return jsonify({'status': 'error', 'message': f'Error during backtest: {e}'}), 500

@socketio.on('connect')
def connect(auth=None):
    global ticker
    if 'user_id' in session and 'access_token' in session:
        try:
            kite.set_access_token(session['access_token'])
            kite.profile() # Validate the token
        except Exception as e:
            if "Invalid `api_key` or `access_token`" in str(e) or "Incorrect `api_key` or `access_token`" in str(e):
                session.pop('access_token', None)
                emit('unauthorized', {'message': 'Your Zerodha session has expired. Please log in again.'})
                return

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()

        if user is None:
            logging.error(f"SocketIO connect error: User with ID {session['user_id']} not found in DB.")
            return

        if user['app_key'] is None or session['access_token'] is None:
            logging.warning(f"SocketIO connect warning: User {user['id']} has no app_key or access_token.")
            return

        if ticker is None:
            # Pass strategy_name_input as the name parameter to Ticker
            ticker = Ticker(user['app_key'], session['access_token'], running_strategies, socketio, kite)
            ticker.start()
    emit('my_response', {'data': 'Connected'})

@socketio.on('disconnect')
def disconnect():
    logging.info('Client disconnected')

from strategies.orb import ORB

@app.route("/market_replay", methods=['POST'])
def market_replay():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    strategy_name = request.form.get('strategy')
    instrument_token = request.form.get('instrument')
    from_date_str = request.form.get('from-date')
    to_date_str = request.form.get('to-date')

    from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
    to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d')

    conn = get_db_connection()
    ticks_rows = conn.execute(
        'SELECT * FROM tick_data WHERE instrument_token = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp',
        (instrument_token, from_date, to_date)
    ).fetchall()
    conn.close()

    if not ticks_rows:
        return jsonify({'status': 'error', 'message': 'No data found for the selected criteria'}), 404

    # Convert rows to list of dictionaries
    ticks = [dict(row) for row in ticks_rows]

    # Instantiate the strategy
    # TODO: Get strategy parameters from the database or form
    orb_strategy = ORB(
        None, # No kite object needed for replay
        'NIFTY', # Dummy value
        '15', # Dummy value
        '09:15', # Dummy value
        '15:00', # Dummy value
        1, # Dummy value
        2, # Dummy value
        1, # Dummy value
        0.5, # Dummy value
        'Option', # Dummy value
        'Buy', # Dummy value
        'ATM', # Dummy value
        'Weekly', # Dummy value
        'Replay_ORB'
    )

    pnl, trades = orb_strategy.replay(ticks)

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
def strategy_status(strategy_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    # Find the running strategy by its db_id
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == int(strategy_id):
            strategy_obj = running_strat_info['strategy']
            status_data = strategy_obj.status
            status_data['strategy_type'] = running_strat_info['strategy_type'] # Add strategy type
            status_data['strategy_name_display'] = running_strat_info['name'] # Add strategy display name
            return jsonify(status_data)
    
    return jsonify({'status': 'error', 'message': 'Strategy not running'}), 404

if __name__ == "__main__":
    socketio.run(app, debug=True, port=8000, allow_unsafe_werkzeug=True)