
from .base_strategy import BaseStrategy
import logging
import datetime

class ORB(BaseStrategy):
    def __init__(self, kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, quantity, trailing_stop_loss):
        super().__init__(kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, quantity, trailing_stop_loss)
        self.instrument_token = self._get_instrument_token()
        self.opening_range_high = 0
        self.opening_range_low = 0
        self.trade_placed = False
        self.trailing_stop_loss_price = 0

    def _get_instrument_token(self):
        # In a real application, you would have a more robust way to get the instrument token.
        # This is just a simple example.
        if self.instrument == 'NIFTY':
            return 256265  # NIFTY 50
        elif self.instrument == 'BANKNIFTY':
            return 260105  # NIFTY BANK
        return None

    def run(self):
        logging.info(f"Running ORB strategy for {self.instrument}")

        if not self.instrument_token:
            logging.error(f"Could not find instrument token for {self.instrument}")
            return

        # Get historical data
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=5)  # Fetch data for the last 5 days
        historical_data = self.kite.historical_data(self.instrument_token, from_date, to_date, f"{self.candle_time}minute")

        if not historical_data:
            logging.error("Could not fetch historical data.")
            return

        # Determine opening range
        for candle in historical_data:
            candle_time = candle['date']
            if candle_time.time() >= datetime.datetime.strptime(self.start_time, '%H:%M').time():
                self.opening_range_high = candle['high']
                self.opening_range_low = candle['low']
                break

        logging.info(f"Opening Range for {self.instrument}: High={self.opening_range_high}, Low={self.opening_range_low}")

    def process_ticks(self, ticks):
        if self.trade_placed:
            # Trailing stop loss logic
            for tick in ticks:
                if tick['instrument_token'] == self.instrument_token:
                    ltp = tick['last_price']
                    if self.trailing_stop_loss_price > 0 and ltp < self.trailing_stop_loss_price:
                        logging.info(f"Trailing stop loss hit! LTP ({ltp}) < Trailing SL ({self.trailing_stop_loss_price})")
                        self._square_off()
                    elif ltp > self.trailing_stop_loss_price:
                        self.trailing_stop_loss_price = ltp - (ltp * (float(self.trailing_stop_loss) / 100))
            return

        for tick in ticks:
            if tick['instrument_token'] == self.instrument_token:
                ltp = tick['last_price']
                if ltp > self.opening_range_high:
                    logging.info(f"Breakout detected! LTP ({ltp}) > Opening Range High ({self.opening_range_high})")
                    self._place_order(ltp, 'CE')
                    self.trade_placed = True
                    self.trailing_stop_loss_price = ltp - (ltp * (float(self.trailing_stop_loss) / 100))
                elif ltp < self.opening_range_low:
                    logging.info(f"Breakdown detected! LTP ({ltp}) < Opening Range Low ({self.opening_range_low})")
                    self._place_order(ltp, 'PE')
                    self.trade_placed = True
                    self.trailing_stop_loss_price = ltp + (ltp * (float(self.trailing_stop_loss) / 100))

    def _get_atm_option_symbol(self, ltp, option_type):
        instruments = self.kite.instruments('NFO')
        
        # Find the nearest strike price
        strike_prices = [inst['strike'] for inst in instruments if inst['name'] == self.instrument and inst['instrument_type'] == option_type]
        atm_strike = min(strike_prices, key=lambda x:abs(x-ltp))

        # Find the corresponding trading symbol
        for inst in instruments:
            if inst['name'] == self.instrument and inst['strike'] == atm_strike and inst['instrument_type'] == option_type:
                return inst['tradingsymbol']
        return None

    def _place_order(self, ltp, option_type):
        trading_symbol = self._get_atm_option_symbol(ltp, option_type)
        if not trading_symbol:
            logging.error(f"Could not find ATM option for {self.instrument} {option_type}")
            return

        logging.info(f"Placing order for {trading_symbol} with quantity {self.quantity}")
        # self.kite.place_order(
        #     variety=self.kite.VARIETY_REGULAR,
        #     exchange=self.kite.EXCHANGE_NFO,
        #     tradingsymbol=trading_symbol,
        #     transaction_type=self.kite.TRANSACTION_TYPE_BUY,
        #     quantity=self.quantity,
        #     product=self.kite.PRODUCT_MIS,
        #     order_type=self.kite.ORDER_TYPE_MARKET
        # )

    def backtest(self, from_date, to_date):
        logging.info(f"Running backtest for {self.instrument} from {from_date} to {to_date}")

        if not self.instrument_token:
            logging.error(f"Could not find instrument token for {self.instrument}")
            return 0, 0

        historical_data = self.kite.historical_data(self.instrument_token, from_date, to_date, f"{self.candle_time}minute")

        if not historical_data:
            logging.error("Could not fetch historical data for backtest.")
            return 0, 0

        pnl = 0
        trades = 0
        trade_placed = False
        entry_price = 0

        for candle in historical_data:
            if not trade_placed:
                if candle['high'] > self.opening_range_high:
                    trades += 1
                    entry_price = self.opening_range_high
                    trade_placed = True
                elif candle['low'] < self.opening_range_low:
                    trades += 1
                    entry_price = self.opening_range_low
                    trade_placed = True
            else:
                if candle['high'] > entry_price + (entry_price * (float(self.target_profit) / 100)):
                    pnl += (entry_price * (float(self.target_profit) / 100)) * float(self.quantity)
                    trade_placed = False
                elif candle['low'] < entry_price - (entry_price * (float(self.stop_loss) / 100)):
                    pnl -= (entry_price * (float(self.stop_loss) / 100)) * float(self.quantity)
                    trade_placed = False

        return pnl, trades
