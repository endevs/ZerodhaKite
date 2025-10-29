
from .base_strategy import BaseStrategy
import logging
import datetime

class ORB(BaseStrategy):
    def __init__(self, kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, strategy_name_input, paper_trade=False):
        super().__init__(kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, total_lot, trailing_stop_loss, segment, trade_type, strike_price, expiry_type, strategy_name_input)
        self.strategy_name_input = strategy_name_input
        self.segment = segment
        self.total_lot = int(total_lot)
        self.trade_type = trade_type
        self.strike_price = strike_price
        self.expiry_type = expiry_type
        self.instrument_token = self._get_instrument_token()
        self.opening_range_high = 0
        self.opening_range_low = 0
        self.trade_placed = False
        self.trailing_stop_loss_price = 0
        self.paper_trade = paper_trade

    def _get_instrument_token(self):
        # In a real application, you would have a more robust way to get the instrument token.
        # This is just a simple example.
        if self.instrument == 'NIFTY':
            return 256265  # NIFTY 50
        elif self.instrument == 'BANKNIFTY':
            return 260105  # NIFTY BANK
        return None

    def _get_atm_option_symbol(self, ltp, option_type):
        instruments = self.kite.instruments('NFO')
        
        # Filter instruments by expiry type
        today = datetime.date.today()
        if self.expiry_type == 'Weekly':
            # Find the next Thursday (weekly expiry)
            days_until_thursday = (3 - today.weekday() + 7) % 7
            if days_until_thursday == 0: # If today is Thursday, use next Thursday
                days_until_thursday = 7
            expiry_date = today + datetime.timedelta(days=days_until_thursday)
        elif self.expiry_type == 'Next Weekly':
            # Find the Thursday after next Thursday
            days_until_thursday = (3 - today.weekday() + 7) % 7
            if days_until_thursday == 0: # If today is Thursday, use next Thursday
                days_until_thursday = 7
            expiry_date = today + datetime.timedelta(days=days_until_thursday + 7)
        elif self.expiry_type == 'Monthly':
            # Find the last Thursday of the current month
            year = today.year
            month = today.month
            # Get the last day of the month
            last_day_of_month = datetime.date(year, month, 1) + datetime.timedelta(days=32) - datetime.timedelta(days=1)
            # Find the last Thursday
            while last_day_of_month.weekday() != 3: # 3 is Thursday
                last_day_of_month -= datetime.timedelta(days=1)
            expiry_date = last_day_of_month
        else:
            expiry_date = today # Default to today if expiry_type is not recognized

        # Format expiry date to match KiteConnect instrument format (YYYY-MM-DD)
        expiry_date_str = expiry_date.strftime('%Y-%m-%d')

        filtered_instruments = [inst for inst in instruments if 
                                inst['name'] == self.instrument and 
                                inst['instrument_type'] == option_type and
                                inst['expiry'].strftime('%Y-%m-%d') == expiry_date_str]

        # Find the nearest strike price
        strike_prices = [inst['strike'] for inst in filtered_instruments]
        if not strike_prices:
            logging.warning(f"No strike prices found for {self.instrument} {option_type} with expiry {expiry_date_str}")
            return None

        atm_strike = min(strike_prices, key=lambda x:abs(x-ltp))

        # Find the corresponding trading symbol
        for inst in filtered_instruments:
            if inst['strike'] == atm_strike:
                return inst['tradingsymbol']
        return None

    def _place_order(self, ltp, option_type):
        trading_symbol = self._get_atm_option_symbol(ltp, option_type)
        if not trading_symbol:
            logging.error(f"Could not find ATM option for {self.instrument} {option_type}")
            return

        transaction_type = self.kite.TRANSACTION_TYPE_BUY if self.trade_type == 'Buy' else self.kite.TRANSACTION_TYPE_SELL
        quantity = self.total_lot * 50 # Assuming 1 lot = 50 shares for NIFTY/BANKNIFTY

        if self.paper_trade:
            logging.info(f"[PAPER TRADE] Simulating order for {trading_symbol} with quantity {quantity} ({self.total_lot} lots)")
            # Here you would update a simulated P&L or log the trade in a simulated account
        else:
            logging.info(f"Placing LIVE order for {trading_symbol} with quantity {quantity} ({self.total_lot} lots)")
            # self.kite.place_order(
            #     variety=self.kite.VARIETY_REGULAR,
            #     exchange=self.kite.EXCHANGE_NFO,
            #     tradingsymbol=trading_symbol,
            #     transaction_type=transaction_type,
            #     quantity=quantity,
            #     product=self.kite.PRODUCT_MIS,
            #     order_type=self.kite.ORDER_TYPE_MARKET
            # )

    def run(self):
        logging.info(f"Running ORB strategy for {self.instrument}")
        # For now, we will just place an order based on the trade type.
        # In a real scenario, this would involve continuous monitoring and decision making.
        if self.trade_type == 'Buy':
            self._place_order(self.kite.ltp(self.instrument_token)[str(self.instrument_token)]['last_price'], 'CE')
        else:
            self._place_order(self.kite.ltp(self.instrument_token)[str(self.instrument_token)]['last_price'], 'PE')

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
                    pnl += (entry_price * (float(self.target_profit) / 100)) * float(self.total_lot * 50) # Use total_lot
                    trade_placed = False
                elif candle['low'] < entry_price - (entry_price * (float(self.stop_loss) / 100)):
                    pnl -= (entry_price * (float(self.stop_loss) / 100)) * float(self.total_lot * 50) # Use total_lot
                    trade_placed = False

        return pnl, trades
