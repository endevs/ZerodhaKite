
from kiteconnect import KiteTicker
import logging
import datetime
from database import get_db_connection
from utils import get_option_symbols

class Ticker:
    def __init__(self, api_key, access_token, running_strategies, socketio, kite):
        self.kws = KiteTicker(api_key, access_token)
        self.running_strategies = running_strategies
        self.socketio = socketio
        self.kite = kite
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.db_connection = get_db_connection() # Initialize DB connection here

    def on_ticks(self, ws, ticks):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for tick in ticks:
                    instrument_token = tick['instrument_token']
                    status_row = cursor.execute('SELECT status FROM tick_data_status WHERE instrument_token = ?', (instrument_token,)).fetchone()
                    status = status_row[0] if status_row else 'Stopped'

                    if status == 'Running':
                        timestamp = None
                        if 'timestamp' in tick:
                            timestamp = tick['timestamp']
                        elif 'last_trade_time' in tick:
                            timestamp = tick['last_trade_time']
                        elif 'exchange_timestamp' in tick:
                            timestamp = tick['exchange_timestamp']
                        
                        if timestamp:
                            if isinstance(timestamp, datetime.datetime):
                                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                timestamp_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                            
                            cursor.execute(
                                "INSERT INTO tick_data (instrument_token, timestamp, last_price, volume) VALUES (?, ?, ?, ?)",
                                (tick['instrument_token'], timestamp_str, tick['last_price'], tick.get('volume', 0))
                            )
                        else:
                            logging.warning(f"Skipping tick because it has no timestamp: {tick}")
                conn.commit()
        except Exception as e:
            logging.error(f"Error storing tick data for replay: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        for tick in ticks:
            # Store tick data in the database
            instrument_token = tick['instrument_token']
            last_price = tick['last_price']
            volume = tick.get('volume', 0)  # Volume might not be present for all tick types
            
            timestamp = None
            if 'timestamp' in tick:
                timestamp = tick['timestamp']
            elif 'last_trade_time' in tick:
                timestamp = tick['last_trade_time']
            elif 'exchange_timestamp' in tick:
                timestamp = tick['exchange_timestamp']

            if timestamp:
                if isinstance(timestamp, datetime.datetime):
                    timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            else:
                logging.warning(f"Skipping tick because it has no timestamp: {tick}")
                continue

            # Determine trading_symbol and instrument_type based on instrument_token
            trading_symbol = ""
            instrument_type = ""
            if instrument_token == 256265: # NIFTY 50
                trading_symbol = "NIFTY 50"
                instrument_type = "INDEX"
            elif instrument_token == 260105: # NIFTY BANK
                trading_symbol = "BANKNIFTY"
                instrument_type = "INDEX"
            # Add more conditions for other instruments as needed

            if trading_symbol and instrument_type:
                try:
                    cursor.execute(
                        "INSERT INTO market_data (instrument_token, trading_symbol, timestamp, last_price, volume, instrument_type) VALUES (?, ?, ?, ?, ?, ?)",
                        (instrument_token, trading_symbol, timestamp, last_price, volume, instrument_type)
                    )
                    conn.commit()
                except Exception as e:
                    logging.error(f"Error storing tick data: {e}")
                    conn.rollback()

        conn.close()

        for strategy_info in self.running_strategies.values():
            strategy_info['strategy'].process_ticks(ticks)
        
        # Broadcast ticks to the frontend
        for tick in ticks:
            if tick['instrument_token'] == 256265: # NIFTY 50
                self.socketio.emit('market_data', {'nifty_price': tick['last_price']})
            elif tick['instrument_token'] == 260105: # NIFTY BANK
                self.socketio.emit('market_data', {'banknifty_price': tick['last_price']})

    def on_connect(self, ws, response):
        logging.info("Kite Ticker connected")
        instrument_tokens = [256265, 260105] # NIFTY 50 and NIFTY BANK

        # Get NIFTY weekly options
        nifty_weekly_options = get_option_symbols(self.kite, 'NIFTY', 'weekly', 10)
        instrument_tokens.extend(nifty_weekly_options)

        # Get NIFTY next weekly options
        nifty_next_weekly_options = get_option_symbols(self.kite, 'NIFTY', 'next_weekly', 10)
        instrument_tokens.extend(nifty_next_weekly_options)

        # Get BANKNIFTY monthly options
        banknifty_monthly_options = get_option_symbols(self.kite, 'BANKNIFTY', 'monthly', 10)
        instrument_tokens.extend(banknifty_monthly_options)

        for strategy_info in self.running_strategies.values():
            instrument_tokens.append(strategy_info['strategy'].instrument_token)
        
        # Remove duplicates
        instrument_tokens = list(set(instrument_tokens))

        ws.subscribe(instrument_tokens)
        ws.set_mode(ws.MODE_FULL, instrument_tokens)

        # Populate the tick_data_status table
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for token in instrument_tokens:
                    cursor.execute("INSERT OR IGNORE INTO tick_data_status (instrument_token, status) VALUES (?, ?)", (token, 'Running'))
                conn.commit()
        except Exception as e:
            logging.error(f"Error populating tick_data_status table: {e}")

    def on_close(self, ws, code, reason):
        logging.info(f"Kite Ticker connection closed: {code} - {reason}")

    def start(self):
        self.kws.connect(threaded=True)
