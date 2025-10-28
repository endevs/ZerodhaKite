
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, kite, instrument, candle_time, start_time, end_time, stop_loss, target_profit, quantity, trailing_stop_loss):
        self.kite = kite
        self.instrument = instrument
        self.candle_time = candle_time
        self.start_time = start_time
        self.end_time = end_time
        self.stop_loss = stop_loss
        self.target_profit = target_profit
        self.quantity = quantity
        self.trailing_stop_loss = trailing_stop_loss

    @abstractmethod
    def run(self):
        pass
