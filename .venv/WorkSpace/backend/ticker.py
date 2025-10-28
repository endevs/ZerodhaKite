
from kiteconnect import KiteTicker
import logging

class Ticker:
    def __init__(self, api_key, access_token, strategies, socketio):
        self.kws = KiteTicker(api_key, access_token)
        self.strategies = strategies
        self.socketio = socketio
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close

    def on_ticks(self, ws, ticks):
        for strategy in self.strategies:
            strategy.process_ticks(ticks)
        
        # Broadcast ticks to the frontend
        for tick in ticks:
            if tick['instrument_token'] == 256265: # NIFTY 50
                self.socketio.emit('market_data', {'nifty_price': tick['last_price']})
            elif tick['instrument_token'] == 260105: # NIFTY BANK
                self.socketio.emit('market_data', {'banknifty_price': tick['last_price']})

    def on_connect(self, ws, response):
        logging.info("Kite Ticker connected")
        instrument_tokens = [256265, 260105] # NIFTY 50 and NIFTY BANK
        for strategy in self.strategies:
            instrument_tokens.append(strategy.instrument_token)
        ws.subscribe(instrument_tokens)
        ws.set_mode(ws.MODE_FULL, instrument_tokens)

    def on_close(self, ws, code, reason):
        logging.info(f"Kite Ticker connection closed: {code} - {reason}")

    def start(self):
        self.kws.connect(threaded=True)
