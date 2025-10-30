from .base_strategy import BaseStrategy
import logging
import datetime
import pandas as pd

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
        self.historical_data = []
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
            'pnl': 0,
            'paper_trade_mode': self.paper_trade,
            'position': self.position,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'stop_loss_level': 0,
            'target_profit_level': 0,
            'traded_instrument': '',
            'trade_history': self.trade_history,
            'candle_time_frame': self.candle_time
        }

    def _get_instrument_token(self):
        if self.instrument == 'NIFTY':
            return 256265
        elif self.instrument == 'BANKNIFTY':
            return 260105
        return None

    def run(self):
        logging.info(f"Running Capture Mountain Signal strategy for {self.instrument}")
        self.status['state'] = 'running'
        self.status['message'] = 'Strategy is running and waiting for ticks.'
        # from_date = datetime.date.today() - datetime.timedelta(days=10)
        # to_date = datetime.date.today()
        # self.historical_data = self.kite.historical_data(self.instrument_token, from_date, to_date, f"{self.candle_time}minute")


    def process_ticks(self, ticks):
        if not self.historical_data:
            self.status['message'] = "Waiting for historical data..."
            return

        df = pd.DataFrame(self.historical_data)
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        for i in range(1, len(df)):
            current_candle = df.iloc[i]
            previous_candle = df.iloc[i-1]
            ema_value = current_candle['ema']

            # PE Logic
            if self.pe_signal_candle is None and previous_candle['low'] > ema_value:
                self.pe_signal_candle = previous_candle
                logging.info(f"PE Signal candle identified at {self.pe_signal_candle['date']}")

            if self.pe_signal_candle is not None:
                if current_candle['close'] < self.pe_signal_candle['low'] and not self.trade_placed:
                    self.position = -1
                    self.entry_price = current_candle['close']
                    self.trade_placed = True
                    logging.info(f"PE trade triggered at {self.entry_price}")
                    # Place order logic here

                if current_candle['close'] > self.pe_signal_candle['high']:
                    if self.position == -1:
                        # Stop Loss
                        self.exit_price = current_candle['close']
                        self.trade_placed = False
                        self.position = 0
                        logging.info(f"PE trade stopped out at {self.exit_price}")
                    if current_candle['low'] > ema_value:
                        self.pe_signal_candle = current_candle
                        logging.info(f"PE Signal candle reset at {self.pe_signal_candle['date']}")

            # CE Logic
            if self.ce_signal_candle is None and previous_candle['high'] < ema_value:
                self.ce_signal_candle = previous_candle
                logging.info(f"CE Signal candle identified at {self.ce_signal_candle['date']}")

            if self.ce_signal_candle is not None:
                if current_candle['close'] > self.ce_signal_candle['high'] and not self.trade_placed:
                    self.position = 1
                    self.entry_price = current_candle['close']
                    self.trade_placed = True
                    logging.info(f"CE trade triggered at {self.entry_price}")
                    # Place order logic here

                if current_candle['close'] < self.ce_signal_candle['low']:
                    if self.position == 1:
                        # Stop Loss
                        self.exit_price = current_candle['close']
                        self.trade_placed = False
                        self.position = 0
                        logging.info(f"CE trade stopped out at {self.exit_price}")
                    if current_candle['high'] < ema_value:
                        self.ce_signal_candle = current_candle
                        logging.info(f"CE Signal candle reset at {self.ce_signal_candle['date']}")
