import logging
import pandas as pd
import time

import ccxt

from .signal_generator import ExtendedSignalGenerator

class VectorCandleSignalGenerator(ExtendedSignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = True  # generates a limit price proposal with each signal
    generates_sl = False     # generates a stop loss price proposal with each signal
    generates_tp = True     # generates a take profit price proposal with each signal
    
    # 
    def __init__(self, binance_symbol: str):
        
        super().__init__()
        
        # get data for the corresponding spot symbol on binance
        # because the volume is and data accuracy is better
        self._binance_symbol = binance_symbol
        
        self.feeds = { 
                'default': {
                    'timeframe': '15m',
                    'num_bars': 30, 
                    'only_closed': True,
                    'df': None,
                    'refresh_timeout': 150
                    }
                }
                
        self.df_vector: pd.DataFrame = None
        
        # timeframe to obtain from binance ... should be consistent with
        # the actual exchange         
        self._buy_rsi: float = 30
        self._sell_rsi: float = 70
        self._min_change: float = 0.4/100 # change must be at least 0.4%  

    
    def vector_candles(self):
        
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

        # Average Volume Last 10 Bars
        df['averageVolume'] = df.volume.rolling(10).mean()
        df['volumeSpread'] = df['volume'] * (df['high'] - df['low'])
        df['highestVolumeSpread'] = df.volumeSpread.rolling(10).max().shift().bfill()
        df['changePercent'] = (df['close'] - df['open'])/df['open']
        # df['signal'] = 'none'
        
        # RSI 13
        df.ta.rsi(length=13, append=True)

        df.dropna(inplace=True)

        # The order of statements is important:

        # Blue Vector Candle
        df.loc[
            (
                ( df['close'] > df ['open'] ) &
                ( df['volume'] >= 1.5* df['averageVolume'] ) 
            ),
            'VectColor'
        ] = 'BLUE'

        # Green Vector Candle
        df.loc[
            (
                ( df['close'] > df ['open'] ) &
                ( ( df['volume'] >= 2* df['averageVolume']) | ( df['volumeSpread'] > df['highestVolumeSpread']) )
            ),
            'VectColor'
        ] = 'GREEN'

        # The order of statements is important:

        # Violet Vector Candle
        df.loc[
            (
                ( df['close'] < df ['open'] ) &
                ( df['volume'] >= 1.5* df['averageVolume'] ) 
            ),
            'VectColor'
        ] = 'VIOLET'

        # Red Vector Candle
        df.loc[
            (
                ( df['close'] < df ['open'] ) &
                ( ( df['volume'] >= 2* df['averageVolume']) | ( df['volumeSpread'] > df['highestVolumeSpread']) )
            ),
            'VectColor'
        ] = 'RED'

        # Buy red vector candle
        df.loc[
            (
                ( df['VectColor'] == 'RED' ) &
                ( abs(df['changePercent']) >= self._min_change ) &
                ( df['RSI_13'] < self._buy_rsi )
            ),
            'signal'
        ] = 'buy'

        # Sell green vector candle
        df.loc[
            (
                ( df['VectColor'] == 'GREEN' ) &
                ( abs(df['changePercent']) >= self._min_change ) &
                ( df['RSI_13'] > self._sell_rsi )
            ),
            'signal'
        ] = 'sell'
        
        return df

    def prepare_df(self):

        self.df_vector = self.vector_candles()
        
        # if self.df is None:
        #    logging.warn(f'({self.class_name()}.prepare_df) No default dataframe available - exit function')
        if self.df is not None:
            pass
        
        if self.df_vector is None:
            logging.warn(f'({self.class_name()}.prepare_df) No df_vector dataframe available')

            
    def signal(self, ask: float = None, bid: float = None):
        
        signal = {}
        
        if self.df is None:
            logging.warn(f'({self.class_name()}.signal) No default dataframe available - exit function')
            return signal
        
        if self.df_vector is None:
            logging.warn(f'({self.class_name()}.signal) No df_vector dataframe available - exit function')
            return signal
        
        # the vector df from binance
        last_vector_signal = self.df_vector['signal'].iloc[-1]
        last_vector_datetime = self.df_vector['datetime'].iloc[-1]
        
        # my dataframe from the exchange to obtain open, high, low, close and tp values ...
        last_df_datetime = self.df['datetime'].loc[ last_vector_datetime ] #.values[0]
        last_open = self.df['open'].loc[ last_vector_datetime ]
        last_close = self.df['close'].loc[ last_vector_datetime ]
        
        logging.info(f'({self.class_name()}.signal) Last Binance data frame: {last_vector_datetime} Last data frame: {last_df_datetime}')
        
        if self.verbose:
            print(f"==== {self.class_name()}.signal VERBOSE ====")
            print('Vector Candle Dataframe ====>:')
            print(self.df_vector)
            print(f'last_vector_signal = {last_vector_signal}')
            print(f'last_vector_datetime = {last_vector_datetime}')
            print('Dataframe from My Exchange ====>')
            print(self.df)
            print(f'last_df_datetime = {last_df_datetime}')
            print(f'last_open  = {last_open}')
            print(f'last_close = {last_close}')
        
        if last_vector_signal == 'sell':
            ask_limit = last_close
            tp = last_close - (last_close - last_open)/2
            
            signal['sell'] = { 'li': ask_limit, 'tp': tp }
            logging.info(f'({self.class_name()}.signal) GREEN Vector candle (sell) detected at binance at: {last_vector_datetime}')
            logging.info(f'({self.class_name()}.signal) GREEN Vector candle (sell) ask_limit {ask_limit} tp {tp}')
        
        elif last_vector_signal == 'buy':
            bid_limit = last_close
            tp = last_close + (last_open - last_close)/2
            
            signal['buy'] = { 'li': bid_limit, 'tp': tp }
            logging.info(f'({self.class_name()}.signal) RED Vector candle (buy) detected at binance at: {last_vector_datetime}')
            logging.info(f'({self.class_name()}.signal) RED Vector candle (buy) bid_limit {bid_limit} tp {tp}')

        else:
            logging.info(f'({self.class_name()}.signal) No vector candle detected at binance at: {last_vector_datetime}')
            logging.info(f'({self.class_name()}.signal) Ignoring last data frame: {last_df_datetime} open {last_open} close {last_close}')
          
        return signal
    
    def exit_signal(self, ask: float = None, bid: float = None) -> dict:
        
        return {}