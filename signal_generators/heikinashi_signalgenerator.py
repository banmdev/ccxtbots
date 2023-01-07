import logging
import pandas as pd
import time

import ccxt

from .signal_generator import ExtendedSignalGenerator

class HeikinAshiSignalGenerator(ExtendedSignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = False  # generates a limit price proposal with each signal
    generates_sl = True     # generates a stop loss price proposal with each signal
    generates_tp = False     # generates a take profit price proposal with each signal
    
    # 
    def __init__(self, binance_symbol: str, sl_buffer: float = 0.001):
        
        # get data for the corresponding spot symbol on binance
        # because the volume is and data accuracy is better
        self._binance_symbol = binance_symbol
        
        # timeframe to obtain from binance ... should be consistent with
        # the actual exchange 
        self._timeframe: str = '5m'
        self._num_bars: int = 300
        self._only_closed: bool = True # pls do not change because some exchanges only deliver closed candles
        
        self._ema_fast_slow_delta: float = 0.24 / 100
        self._volume_treshold: float = 0.0
        self._ema_fast_close_delta: float = 0.03 / 100
        
        self._sl_buffer = sl_buffer
        
    def heikinashi_signal(self):
        
        # get data from binance
        exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        
        bars = exchange.fetch_ohlcv(self._binance_symbol, timeframe=self._timeframe, limit=self._num_bars)

        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        tf_to_mins = { '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440 }
    
        # make sure to obtain only closed frames (15min * 60 * 1000)
        if self._only_closed:
            df = df[df.timestamp < int(time.time() * 1000) - tf_to_mins[self._timeframe] * 60 * 1000]

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

        # Input Params
        # EMAFastSlowDelta = 0.24
        # VolThreshHold = 0.0
        # EMAFastCloseDelta = 0.03

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

   
    def signal(self, ask: float, bid: float, df: pd.DataFrame):
        
        signal = {}
        
        df_ha = self.heikinashi_signal()
        
        # the vector df from binance
        last_ha_signal = df_ha['signal'].iloc[-1]
        last_ha_datetime = df_ha['datetime'].iloc[-1]
        
        # my dataframe from the exchange to obtain open, high, low, close and tp values ...
        df['HIGH_48'] = df.high.rolling(48).max()
        df['LOW_48'] = df.low.rolling(48).min()
        df.dropna(inplace=True)
        
        # for stop loss
        recent_swing_high = df['HIGH_48'].iloc[-1]
        recent_swing_low = df['LOW_48'].iloc[-1]
        
        # TODO - checks if meaningful ... considering current bid/ask
        sl_sell_price = recent_swing_high * (1 + self._sl_buffer)
        sl_buy_price = recent_swing_low * (1 - self._sl_buffer)
        
        logging.info(f'({self.class_name()}.signal) Last Binance data frame: {last_ha_datetime} Last data frame: {last_ha_datetime}')
        
        # DEBUG: 
        # last_ha_signal = 'buy'
        
        if last_ha_signal == 'sell':

            signal['sell'] = {  'sl': sl_sell_price }
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (sell) detected at binance at: {last_ha_datetime}')
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (sell) sl {sl_sell_price}')
        
        elif last_ha_signal == 'buy':

            signal['buy'] = { 'sl': sl_buy_price }
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (buy) detected at binance at: {last_ha_datetime}')
            logging.info(f'({self.class_name()}.signal) HeikinAshi signal (buy) sl {sl_buy_price}')

        else:
            logging.info(f'({self.class_name()}.signal) No Heikin Ashi signal detected at binance at: {last_ha_datetime}')
         
        return signal