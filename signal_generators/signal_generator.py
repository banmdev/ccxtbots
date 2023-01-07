from base import BaseClass

class SignalGenerator(BaseClass):

    # returns buy, sell, both or none
    def signal(self):
        return None

class BuySignalGenerator(BaseClass):
    
    # returns buy only
    def signal(self):
        return 'buy'

class SellSignalGenerator(BaseClass):
    
    # returns sell only
    def signal(self):
        return 'sell'
     
class ExtendedSignalGenerator(SignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = False  # generates a limit price proposal with each signal
    generates_sl = False     # generates a stop loss price proposal with each signal
    generates_tp = False     # generates a take profit price proposal with each signal
    
    def __init__(self):
        
        self._timeframe: str = '5m'
        self._num_bars: int = 50
        self._only_closed: bool = True # pls change with caution
     
    @property
    def timeframe(self) -> str:
        return self._timeframe

    @timeframe.setter
    def timeframe(self, value: str):
        self._timeframe = value

    @property
    def num_bars(self) -> int:
        return self._num_bars

    @num_bars.setter
    def num_bars(self, value: int):
        self._num_bars = value
        
    @property
    def only_closed(self) -> bool:
        return self._only_closed

    @only_closed.setter
    def only_closed(self, value: bool):
        self._only_closed = value
        
    def signal(self, ask: float, bid: float, df) -> dict:
    
        signal = {}
        
        # signal dict structure:
        # can be a json object later to be published via a pub / sub architecuture
        # signal = {
        #     'buy': { 'li': 234.56, 'sl': 123.45, 'tp': 345.67 },   # complete record
        #     'buy': {} # signal only
        # }
        
        return signal
