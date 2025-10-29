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
            return "Invalid OTP or OTP expired!"

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

    conn = get_db_connection()
    try:
        if strategy_id:
            # Update existing strategy
            conn.execute(
                'UPDATE strategies SET strategy_name = ?, instrument = ?, candle_time = ?, start_time = ?, end_time = ?, stop_loss = ?, target_profit = ?, total_lot = ?, trailing_stop_loss = ?, segment = ?, trade_type = ?, strike_price = ?, expiry_type = ? WHERE id = ? AND user_id = ?',
                (strategy_name_input, instrument, candle_time, execution_start, execution_end, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, strategy_id, user_id)
            )
            message = 'Strategy updated successfully!'
        else:
            # Insert new strategy
            conn.execute(
                'INSERT INTO strategies (user_id, strategy_name, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (user_id, strategy_name_input, instrument, candle_time, execution_start, execution_end, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type)
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
        if running_strat_info['db_id'] == strategy_id and running_strat_info['status'] == 'running':
            return jsonify({'status': 'error', 'message': 'Strategy is already running'}), 400

    try:
        # Instantiate the ORB strategy with saved parameters
        strategy = ORB(
            kite,
            strategy_data['instrument'],
            strategy_data['candle_time'],
            strategy_data['start_time'],
            strategy_data['end_time'],
            strategy_data['stop_loss'],
            strategy_data['target_profit'],
            strategy_data['total_lot'], # quantity is now total_lot
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

    # Find the running strategy by its db_id
    for unique_run_id, running_strat_info in running_strategies.items():
        if running_strat_info['db_id'] == strategy_id:
            # Here you would implement logic to actually square off positions
            # For now, we just change its in-memory status and remove it from running strategies
            del running_strategies[unique_run_id]

            # Update status in DB
            conn = get_db_connection()
            conn.execute('UPDATE strategies SET status = ? WHERE id = ?', ('sq_off', strategy_id))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Strategy squared off successfully!'})
    return jsonify({'status': 'error', 'message': 'Running strategy not found'}), 404

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
            ticker = Ticker(user['app_key'], session['access_token'], list(running_strategies.values()), socketio)
            ticker.start()
    emit('my_response', {'data': 'Connected'})

@socketio.on('disconnect')
def disconnect():
    logging.info('Client disconnected')

if __name__ == "__main__":
    socketio.run(app, debug=True, port=8000, allow_unsafe_werkzeug=True)