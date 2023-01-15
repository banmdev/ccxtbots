from base import BaseClass

import pandas as pd

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
        
        self.feeds = { 
                      'default': {
                          'timeframe': '5m',
                          'num_bars': 50, 
                          'only_closed': True,
                          'refresh_timeout': 150,
                          'df': None 
                        } 
                      }
        
        self.verbose = False
        
    @property
    def timeframe(self) -> str:
        return self.feeds['default']['timeframe']

    @timeframe.setter
    def timeframe(self, value: str):
        self.feeds['default']['timeframe'] = value

    @property
    def num_bars(self) -> int:
        return self.feeds['default']['num_bars']

    @num_bars.setter
    def num_bars(self, value: int):
        self.feeds['default']['num_bars'] = value
        
    @property
    def refresh_timeout(self) -> int:
        return self.feeds['default']['refresh_timeout']

    @num_bars.setter
    def refresh_timeout(self, value: int):
        self.feeds['default']['refresh_timeout'] = value
        
    @property
    def only_closed(self) -> bool:
        return self.feeds['default']['only_closed']

    @only_closed.setter
    def only_closed(self, value: bool):
        self.feeds['default']['only_closed'] = value
        
    @property
    def df(self) -> pd.DataFrame:
        return self.feeds['default']['df']

    @df.setter
    def df(self, value: pd.DataFrame):
        self.feeds['default']['df'] = value
        
    def prepare_df(self):
        # function to prepare the dataframes after loading
        pass
        
    def exit_signal(self, ask: float = None, bid: float = None) -> dict:
        
        return { }
        
    def signal(self, ask: float = None, bid: float = None) -> dict:
    
        signal = {}
        
        # signal dict structure:
        # can be a json object later to be published via a pub / sub architecuture
        # signal = {
        #     'buy': { 'li': 234.56, 'sl': 123.45, 'tp': 345.67 },   # complete record
        #     'buy': {} # signal only
        # }
        
        return signal
