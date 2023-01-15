import logging
import pandas as pd
import time

import ccxt

from .signal_generator import ExtendedSignalGenerator

class HeikinAshiSignalGenerator(ExtendedSignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = False  # generates a limit price proposal with each signal
    generates_sl = True      # generates a stop loss price proposal with each signal
    generates_tp = False     # generates a take profit price proposal with each signal
    
    # 
    def __init__(self, binance_symbol: str, sl_buffer: float = 0.001):
        
        super().__init__()
        
        # get data for the corresponding spot symbol on binance
        # because the volume is and data accuracy is better
        self._binance_symbol = binance_symbol
        
        self.feeds = { 
                'default': {
                    'timeframe': '5m',
                    'num_bars': 300, 
                    'only_closed': True,
                    'df': None,
                    'refresh_timeout': 90
                    }
                }
        
        self._ema_fast_slow_delta: float = 0.03 / 100
        self._volume_treshold: float = 5.0
        self._ema_fast_close_delta: float = 0.06 / 100
        
        self.df_ha: pd.DataFrame = None
        
        self._sl_buffer = sl_buffer
        
    def heikinashi_signal(self):
        
        # get data from binance
        exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        
        bars = exchange.fetch_ohlcv(self._binance_symbol, timeframe=self.timeframe, limit=self.num_bars)

        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        tf_to_mins = { '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440 }
    
        # make sure to obtain only closed frames (15min * 60 * 1000)
        if self.only_closed:
            df = df[df.timestamp < int(time.time() * 1000) - tf_to_mins[self.timeframe] * 60 * 1000]

        df['datetime']= pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index(pd.DatetimeIndex(df['datetime']), inplace=True)

        # create Heikin-Ashi Candles
        df.ta.ha(append=True)

        # Apply EMA 50 and 200 to HA_Close (Heikin-Ashi close value)
        df.ta.ema(close=df["HA_close"], length=50, append=True)
        df.ta.ema(close=df["HA_close"], length=200, append=True)

        # Percentage Volume Oscilator
        df.ta.pvo(fast=5, slow=10, append=True)

        # drop empty EMA, SMA ...    
        df.dropna(inplace=True)

        df['EMA_delta_perc'] = abs((df['EMA_50'] - df['EMA_200'])/df['EMA_200'])
        df['EMA_fast_trsh'] = df['EMA_50'] * self._ema_fast_close_delta

        # long signal
        df.loc[
            (
                ( df['EMA_50'] > df['EMA_200'] ) &
                ( df['EMA_delta_perc'] > self._ema_fast_slow_delta ) &
                ( df['HA_close'] > df ['HA_open'] ) &
                ( df['HA_low'] == df ['HA_open'] ) &
                ( df['HA_open'] >= (df['EMA_50'] - df['EMA_fast_trsh'])) & (df['HA_open'] < (df['EMA_50'] + df['EMA_fast_trsh'])) &
                ( df['PVO_5_10_9'] >= self._volume_treshold )
            ),
            'signal'
        ] = 'buy'

        df.loc[
            (
                ( df['EMA_50'] < df['EMA_200'] ) &
                ( df['EMA_delta_perc'] > self._ema_fast_slow_delta ) &
                ( df['HA_close'] < df ['HA_open'] ) &
                ( df['HA_high'] == df ['HA_open'] ) &
                ( df['HA_open'] > (df['EMA_50'] - df['EMA_fast_trsh'])) & (df['HA_open'] <= (df['EMA_50'] + df['EMA_fast_trsh'])) &
                ( df['PVO_5_10_9'] >= self._volume_treshold )
            ),
            'signal'
        ] = 'sell'

        return df

    def prepare_df(self):

        self.df_ha = self.heikinashi_signal()
        
        if self.df is not None:
            # logging.warn(f'({self.class_name()}.prepare_df) No default dataframe available - exit function')
            # my dataframe from the exchange to obtain open, high, low, close and tp values ...
            self.df['HIGH_48'] = self.df.high.rolling(48).max()
            self.df['LOW_48'] = self.df.low.rolling(48).min()
            self.df.dropna(inplace=True)
            
        if self.df_ha is None:
            logging.warn(f'({self.class_name()}.prepare_df) No df_ha dataframe available')
   
   
    def signal(self, ask: float = None, bid: float = None):
        
        signal = {}
        
        if self.df is None:
            logging.warn(f'({self.class_name()}.signal) No default dataframe available - exit function')
            return signal
        
        if self.df_ha is None:
            logging.warn(f'({self.class_name()}.signal) No default df_ha dataframe available - exit function')
            return signal
        
        # the vector df from binance
        last_ha_signal = self.df_ha['signal'].iloc[-1]
        last_ha_datetime = self.df_ha['datetime'].iloc[-1]
                
        # for stop loss
        recent_swing_high = self.df['HIGH_48'].iloc[-1]
        recent_swing_low = self.df['LOW_48'].iloc[-1]
               
        logging.info(f'({self.class_name()}.signal) Last Binance data frame: {last_ha_datetime} Last data frame: {last_ha_datetime}')
        
        if self.verbose:
            print(f"==== {self.class_name()}.signal VERBOSE ====")
            print('HeikinAshi Dataframe ====>:')
            print(self.df_ha)
            print(f'last_ha_signal = {last_ha_signal}')
            print(f'last_ha_datetime = {last_ha_datetime}')
            print('Dataframe from My Exchange ====>')
            print(self.df)
            print(f'recent_swing_high = {recent_swing_high}')
            print(f'recent_swing_low  = {recent_swing_low}')
        
        if last_ha_signal == 'sell':
            sl_sell_price = recent_swing_high * (1 + self._sl_buffer)
            signal['sell'] = {  'sl': sl_sell_price }
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (sell) detected at binance at: {last_ha_datetime}')
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (sell) sl {sl_sell_price}')
        
        elif last_ha_signal == 'buy':
            sl_buy_price = recent_swing_low * (1 - self._sl_buffer)
            signal['buy'] = { 'sl': sl_buy_price }
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (buy) detected at binance at: {last_ha_datetime}')
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (buy) sl {sl_buy_price}')
            
        else:
            logging.info(f'({self.class_name()}.signal) No Heikin Ashi signal detected at binance at: {last_ha_datetime}')
         
        return signal
    
    def exit_signal(self, ask: float = None, bid: float = None) -> dict:
        
        return {}