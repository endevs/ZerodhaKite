from .base_strategy import BaseStrategy
import logging
import datetime
import pandas as pd
import numpy as np
import uuid

class CaptureMountainSignal(BaseStrategy):
    description = """
    ## Capture Mountain Signal Strategy

    **Instruments:** Nifty & BankNifty ATM Options
    **Timeframe:** 5-minute candles
    **Indicator:** 5-period EMA

    ### PE (Put Entry) Logic
    - **Signal Candle:** Candle's LOW > 5 EMA
    - **Entry Trigger:** Next candle CLOSE < signal candle's LOW
    - **Stop Loss:** Price closes above signal candle's HIGH
    - **Target:** Wait for at least 1 candle where HIGH < 5 EMA, then if 2 consecutive candles CLOSE > 5 EMA -> Exit PE trade

    ### CE (Call Entry) Logic
    - **Signal Candle:** Candle's HIGH < 5 EMA
    - **Entry Trigger:** Next candle CLOSE > signal candle's HIGH
    - **Stop Loss:** Price closes below signal candle's LOW
    - **Target:** Wait for at least 1 candle where LOW > 5 EMA, then if 2 consecutive candles CLOSE < 5 EMA -> Exit CE trade
    """
    def __init__(self, kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, strategy_name_input, paper_trade=False, ema_period=5):
        super().__init__(kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, strategy_name_input)
        self.strategy_name_input = strategy_name_input
        self.paper_trade = paper_trade
        self.ema_period = ema_period
        self.instrument_token = self._get_instrument_token()
        self.historical_data = [] # Stores 5-minute candles
        self.pe_signal_candle = None
        self.ce_signal_candle = None
        self.trade_placed = False
        self.position = 0  # 0: flat, 1: long, -1: short
        self.entry_price = 0
        self.exit_price = 0
        self.trade_history = []
        self.status = {
            'state': 'initializing',
            'message': 'Strategy is initializing.',
            'current_ltp': 0,
            'signal_status': 'Waiting for market data',
            'signal_candle_time': 'N/A',
            'signal_candle_high': 0,
            'signal_candle_low': 0,
            'pnl': 0,
            'paper_trade_mode': self.paper_trade,
            'position': self.position, # 0: flat, 1: long, -1: short
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'stop_loss_level': 0,
            'target_profit_level': 0,
            'traded_instrument': '',
            'entry_order_id': 'N/A',
            'sl_order_id': 'N/A',
            'tp_order_id': 'N/A',
            'trade_history': self.trade_history,
            'candle_time_frame': self.candle_time
        }
        self.last_candle_timestamp = None
        self.current_candle_data = None
        self.target_hit_candles = 0 # For target profit logic

    def _get_instrument_token(self):
        if self.instrument == 'NIFTY':
            return 256265
        elif self.instrument == 'BANKNIFTY':
            return 260105
        return None

    def _get_atm_option_symbol(self, ltp, option_type):
        # This is a placeholder. In a real scenario, you'd fetch actual ATM options.
        # For simplicity, we'll just return a dummy symbol.
        return f'{self.instrument}{option_type}{ltp}'

    def _place_order(self, ltp, option_type, transaction_type):
        trading_symbol = self._get_atm_option_symbol(ltp, option_type)
        quantity = self.total_lot * 50 # Assuming 1 lot = 50 shares
        order_id = str(uuid.uuid4())[:8]

        if self.paper_trade:
            logging.info(f"[PAPER TRADE] Simulating {transaction_type} order for {trading_symbol} with quantity {quantity}")
            return order_id, trading_symbol
        else:
            logging.info(f"Placing LIVE {transaction_type} order for {trading_symbol} with quantity {quantity}")
            # Actual KiteConnect order placement would go here
            # order_id = self.kite.place_order(...)
            return order_id, trading_symbol

    def run(self):
        logging.info(f"Running Capture Mountain Signal strategy for {self.instrument}")
        self.status['state'] = 'running'
        self.status['message'] = 'Strategy is running and waiting for ticks.'

    def process_ticks(self, ticks):
        if not ticks:
            return

        latest_tick = ticks[-1] # Assuming ticks are ordered by time
        current_ltp = latest_tick['last_price']
        tick_timestamp = latest_tick['timestamp']

        self.status['current_ltp'] = current_ltp

        # Convert tick_timestamp to datetime object if it's not already
        if isinstance(tick_timestamp, (int, float)):
            tick_datetime = datetime.datetime.fromtimestamp(tick_timestamp)
        elif isinstance(tick_timestamp, str):
            try:
                tick_datetime = datetime.datetime.strptime(tick_timestamp, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                tick_datetime = datetime.datetime.fromisoformat(tick_timestamp)
        else:
            tick_datetime = tick_timestamp # Assume it's already a datetime object

        # Determine the current 5-minute candle's start time
        candle_interval_minutes = int(self.candle_time)
        current_candle_start_time = tick_datetime - datetime.timedelta(minutes=tick_datetime.minute % candle_interval_minutes, seconds=tick_datetime.second, microseconds=tick_datetime.microsecond)

        # Initialize or update current candle data
        if self.current_candle_data is None or self.current_candle_data['date'] != current_candle_start_time:
            # New candle started
            if self.current_candle_data is not None: # Process the completed candle
                self._process_completed_candle(self.current_candle_data)
            
            self.current_candle_data = {
                'date': current_candle_start_time,
                'open': current_ltp,
                'high': current_ltp,
                'low': current_ltp,
                'close': current_ltp,
                'volume': 0 # Volume not available in ticks, keep as 0 or estimate
            }
            self.historical_data.append(self.current_candle_data) # Add new candle to historical data
        else:
            # Update existing candle
            self.current_candle_data['high'] = max(self.current_candle_data['high'], current_ltp)
            self.current_candle_data['low'] = min(self.current_candle_data['low'], current_ltp)
            self.current_candle_data['close'] = current_ltp
            # self.current_candle_data['volume'] += latest_tick.get('volume_delta', 0) # If volume delta is available

        # Keep historical_data to a manageable size (e.g., last 100 candles)
        if len(self.historical_data) > 100:
            self.historical_data.pop(0)

        # Update status message
        self.status['message'] = f"Processing ticks. Current candle: {self.current_candle_data['date'].strftime('%H:%M')} - {current_ltp:.2f}"

        # Only run strategy logic if we have enough historical data for EMA calculation
        if len(self.historical_data) > self.ema_period:
            self._apply_strategy_logic()

    def _process_completed_candle(self, candle):
        # This method is called when a candle closes. 
        # The main strategy logic will be applied here or in _apply_strategy_logic
        pass

    def _apply_strategy_logic(self):
        df = pd.DataFrame(self.historical_data)
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # Ensure we have at least two candles for signal/entry logic
        if len(df) < 2:
            self.status['signal_status'] = 'Not enough candles for signal identification.'
            return

        current_candle = df.iloc[-1]
        previous_candle = df.iloc[-2]
        current_ema = current_candle['ema']
        previous_ema = previous_candle['ema']

        # --- Signal Identification and Reset ---
        # PE Signal Candle Identification
        if previous_candle['low'] > previous_ema:
            # Check for signal reset condition for PE
            if self.pe_signal_candle is None or \
               (current_candle['close'] > self.pe_signal_candle['high'] and current_candle['low'] > current_ema):
                self.pe_signal_candle = previous_candle
                self.status['signal_status'] = f"PE Signal Candle Identified: {self.pe_signal_candle['date'].strftime('%H:%M')} (H:{self.pe_signal_candle['high']:.2f}, L:{self.pe_signal_candle['low']:.2f})"
                self.status['signal_candle_time'] = self.pe_signal_candle['date'].strftime('%H:%M') + '-' + (self.pe_signal_candle['date'] + datetime.timedelta(minutes=int(self.candle_time))).strftime('%H:%M')
                self.status['signal_candle_high'] = self.pe_signal_candle['high']
                self.status['signal_candle_low'] = self.pe_signal_candle['low']
                self.ce_signal_candle = None # Only one active signal type
                logging.info(self.status['signal_status'])

        # CE Signal Candle Identification
        if previous_candle['high'] < previous_ema:
            # Check for signal reset condition for CE
            if self.ce_signal_candle is None or \
               (current_candle['close'] < self.ce_signal_candle['low'] and current_candle['high'] < current_ema):
                self.ce_signal_candle = previous_candle
                self.status['signal_status'] = f"CE Signal Candle Identified: {self.ce_signal_candle['date'].strftime('%H:%M')} (H:{self.ce_signal_candle['high']:.2f}, L:{self.ce_signal_candle['low']:.2f})"
                self.status['signal_candle_time'] = self.ce_signal_candle['date'].strftime('%H:%M') + '-' + (self.ce_signal_candle['date'] + datetime.timedelta(minutes=int(self.candle_time))).strftime('%H:%M')
                self.status['signal_candle_high'] = self.ce_signal_candle['high']
                self.status['signal_candle_low'] = self.ce_signal_candle['low']
                self.pe_signal_candle = None # Only one active signal type
                logging.info(self.status['signal_status'])

        # --- Trade Entry Logic ---
        if not self.trade_placed:
            # PE Entry
            if self.pe_signal_candle is not None and current_candle['close'] < self.pe_signal_candle['low']:
                self.position = -1  # Short position (Buy PE)
                self.entry_price = current_candle['close']
                self.trade_placed = True
                self.status['state'] = 'position_open'
                self.status['traded_instrument'] = self._get_atm_option_symbol(self.entry_price, 'PE')
                self.status['stop_loss_level'] = self.pe_signal_candle['high'] # SL for PE is signal candle high
                self.status['target_profit_level'] = np.nan # Target calculated dynamically
                order_id, _ = self._place_order(self.entry_price, 'PE', 'BUY')
                self.status['entry_order_id'] = order_id
                self.status['message'] = f"PE trade initiated at {self.entry_price:.2f}. SL: {self.status['stop_loss_level']:.2f}"
                self.trade_history.append({
                    'time': current_candle['date'].strftime('%H:%M:%S'),
                    'action': 'BUY PE',
                    'price': self.entry_price,
                    'instrument': self.status['traded_instrument'],
                    'order_id': order_id
                })
                logging.info(self.status['message'])

            # CE Entry
            elif self.ce_signal_candle is not None and current_candle['close'] > self.ce_signal_candle['high']:
                self.position = 1  # Long position (Buy CE)
                self.entry_price = current_candle['close']
                self.trade_placed = True
                self.status['state'] = 'position_open'
                self.status['traded_instrument'] = self._get_atm_option_symbol(self.entry_price, 'CE')
                self.status['stop_loss_level'] = self.ce_signal_candle['low'] # SL for CE is signal candle low
                self.status['target_profit_level'] = np.nan # Target calculated dynamically
                order_id, _ = self._place_order(self.entry_price, 'CE', 'BUY')
                self.status['entry_order_id'] = order_id
                self.status['message'] = f"CE trade initiated at {self.entry_price:.2f}. SL: {self.status['stop_loss_level']:.2f}"
                self.trade_history.append({
                    'time': current_candle['date'].strftime('%H:%M:%S'),
                    'action': 'BUY CE',
                    'price': self.entry_price,
                    'instrument': self.status['traded_instrument'],
                    'order_id': order_id
                })
                logging.info(self.status['message'])

        # --- Position Management (SL/Target) ---
        elif self.position != 0: # If a position is open
            current_pnl = (current_candle['close'] - self.entry_price) * self.total_lot * 50 * self.position
            self.status['pnl'] = current_pnl
            self.status['message'] = f"Position open. Entry: {self.entry_price:.2f}, Current: {current_candle['close']:.2f}, P&L: {current_pnl:.2f}"

            # Check for Stop Loss
            if (self.position == 1 and current_candle['close'] <= self.status['stop_loss_level']) or \
               (self.position == -1 and current_candle['close'] >= self.status['stop_loss_level']):
                self.exit_price = current_candle['close']
                self._close_trade('SL', current_candle['date'])
                logging.info(self.status['message'])

            # Check for Target Profit (PE Logic)
            elif self.position == -1 and self.pe_signal_candle is not None: # Short position (PE)
                if current_candle['high'] < current_ema: # Wait for at least 1 candle where HIGH < 5 EMA
                    self.target_hit_candles += 1
                else:
                    self.target_hit_candles = 0 # Reset if condition not met
                
                if self.target_hit_candles >= 1: # If condition met for at least one candle
                    # Then if 2 consecutive candles CLOSE > 5 EMA -> Exit PE trade
                    if len(df) >= 3 and df.iloc[-1]['close'] > df.iloc[-1]['ema'] and df.iloc[-2]['close'] > df.iloc[-2]['ema']:
                        self.exit_price = current_candle['close']
                        self._close_trade('TP', current_candle['date'])
                        logging.info(self.status['message'])

            # Check for Target Profit (CE Logic)
            elif self.position == 1 and self.ce_signal_candle is not None: # Long position (CE)
                if current_candle['low'] > current_ema: # Wait for at least 1 candle where LOW > 5 EMA
                    self.target_hit_candles += 1
                else:
                    self.target_hit_candles = 0 # Reset if condition not met

                if self.target_hit_candles >= 1: # If condition met for at least one candle
                    # Then if 2 consecutive candles CLOSE < 5 EMA -> Exit CE trade
                    if len(df) >= 3 and df.iloc[-1]['close'] < df.iloc[-1]['ema'] and df.iloc[-2]['close'] < df.iloc[-2]['ema']:
                        self.exit_price = current_candle['close']
                        self._close_trade('TP', current_candle['date'])
                        logging.info(self.status['message'])

    def _close_trade(self, exit_type, timestamp):
        self.status['state'] = 'position_closed'
        self.status['message'] = f"Position closed by {exit_type} at {self.exit_price:.2f}. P&L: {self.status['pnl']:.2f}"
        
        order_id, _ = self._place_order(self.exit_price, 'PE' if self.position == -1 else 'CE', 'SELL')
        if exit_type == 'SL':
            self.status['sl_order_id'] = order_id
        elif exit_type == 'TP':
            self.status['tp_order_id'] = order_id

        self.trade_history.append({
            'time': timestamp.strftime('%H:%M:%S'),
            'action': f'EXIT ({exit_type})',
            'price': self.exit_price,
            'instrument': self.status['traded_instrument'],
            'order_id': order_id
        })
        self.position = 0
        self.trade_placed = False
        self.pe_signal_candle = None
        self.ce_signal_candle = None
        self.target_hit_candles = 0
        self.status['entry_order_id'] = 'N/A'
        self.status['sl_order_id'] = 'N/A'
        self.status['tp_order_id'] = 'N/A'

