import logging
import pandas as pd
import pandas_ta as ta
import numpy as np

from .signal_generator import SignalGenerator

class SimpleMMSignalGenerator(SignalGenerator):

    def signal(self, price, df):

        trend = None

        df.ta.ema(close=df["close"], length=13, append=True)
        df.ta.rsi(length=9, append=True)
        df.ta.atr(length=9, append=True)
        df.ta.natr(length=9, append=True)

        # drop empty EMA, SMA, ATR, RSI ...    
        df.dropna(inplace=True)

        ## print(df)
        recent_ema = df['EMA_13'].iloc[-1]
        recent_rsi = df['RSI_9'].iloc[-1]
        recent_atr = df['ATRr_9'].iloc[-1]
        recent_natr = df['NATR_9'].iloc[-1]

        # simple filtering ...
        if price < recent_ema and recent_rsi > 30:
            trend = 'sell'
        if price > recent_ema and recent_rsi < 70:
            trend = 'buy'

        if (recent_natr < 0.3 and (recent_rsi > 40 and recent_rsi < 60) ):
            logging.warning(f'({self.class_name()}.signal) natr very small {recent_natr:.2f}% trading in both directions')
            trend = 'both'

        logging.info(f'({self.class_name()}.signal) ema_5_13 {recent_ema:.4f} rsi {recent_rsi:.4f} mid {price} atr {recent_atr:.4f} natr {recent_natr:.2f}% trend {trend}')

        return trend
