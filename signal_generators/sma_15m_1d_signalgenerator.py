import logging
import pandas as pd

from .signal_generator import ExtendedSignalGenerator

class SMA_15m_1d_SignalGenerator(ExtendedSignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = True  # generates a limit price proposal with each signal
    generates_sl = False     # generates a stop loss price proposal with each signal
    generates_tp = False     # generates a take profit price proposal with each signal
    
    # 
    def __init__(self, sma20_15_delta: float = 0.001):
        
        super().__init__()
        
        # this indicator requires two datafeeds
        self.feeds = { 
                'default': {
                    'timeframe': '15m',
                    'num_bars': 50, 
                    'only_closed': True,
                    'refresh_timeout': 180,
                    'df': None
                    },
                'daily': {
                    'timeframe': '1d',
                    'num_bars': 50, 
                    'only_closed': True,
                    'refresh_timeout': 300,
                    'df': None
                    },
                }
                
        self.sma20_15_delta = sma20_15_delta
        
    @property
    def df_daily(self) -> pd.DataFrame:
        return self.feeds['daily']['df']

    @df_daily.setter
    def df_daily(self, value: pd.DataFrame):
        self.feeds['daily']['df'] = value
        
        
    def prepare_df(self):
        
        if self.df is not None:
            # 15m SMA 20 Periods
            self.df['sma20_15m'] = self.df.close.rolling(20).mean()
            # maybe later?
            # df['HIGH_48'] = df.high.rolling(48).max()
            # df['LOW_48'] = df.low.rolling(48).min()
            self.df.dropna(inplace=True)
            # logging.warn(f'({self.class_name()}.prepare_df) No default dataframe available - exit function')
            # return
        
        if self.df_daily is not None:
            # Daily SMA 20 Days
            self.df_daily['sma20_d'] = self.df_daily.close.rolling(20).mean()
            self.df_daily.dropna(inplace=True)
            # logging.warn(f'({self.class_name()}.prepare_df) No daily dataframe available - exit function')
            # return
   
    # no specific exit signal
    def exit_signal(self, ask: float = None, bid: float = None) -> dict:
        
        return {}
        
    def signal(self, ask: float, bid: float) -> dict:
        
        signal = {}
        
        if self.df is None:
            logging.warn(f'({self.class_name()}.signal) No default dataframe available - exit function')
            return signal
            
        if self.df_daily is None:
            logging.warn(f'({self.class_name()}.signal) No daily dataframe available - exit function')
            return signal
        
        mid = float((ask + bid)/2)
        mid = round(mid,5)
                
        last_sma20_d = self.df_daily['sma20_d'].iloc[-1]
        last_sma20_15m = self.df['sma20_15m'].iloc[-1]
        
        if self.verbose:
            print(f"==== {self.class_name()}.signal VERBOSE ====")
            print('Daily Dataframe ====>:')
            print(self.df_daily)
            print(f'last_sma20_d = {last_sma20_d}')
            print('Dataframe from My Exchange ====>')
            print(self.df)
            print(f'last_sma20_15m = {last_sma20_15m}')

        if mid < last_sma20_d:
            # sell
            ask_limit = last_sma20_15m * (1 - self.sma20_15_delta )
            if ask_limit > ask:
                signal['sell'] = { 'li': ask_limit }
                logging.info(f'({self.class_name()}.signal) SELL last_sma20_d {last_sma20_d:.4f} last_sma20_15m {last_sma20_15m:.4f} ask_limit {ask_limit:.4f}')     
        else:
            # buy
            bid_limit = last_sma20_15m * (1 + self.sma20_15_delta )
            if bid_limit < bid:
                signal['buy'] = { 'li': bid_limit }
                logging.info(f'({self.class_name()}.signal) BUY last_sma20_d {last_sma20_d:.4f} last_sma20_15m {last_sma20_15m:.4f} bid_limit {bid_limit:.4f}')
                 
        return signal