import logging
import pandas as pd
import pandas_ta as ta
import numpy as np

from .signal_generator import SignalGenerator
from .signal_generator import ExtendedSignalGenerator

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


class ExtMMSignalGenerator(ExtendedSignalGenerator):
    
    # capabilities
    generates_signal = True  # generates a signal: buy, sell, both
    generates_limit = True  # generates a limit price proposal with each signal
    generates_sl = True     # generates a stop loss price proposal with each signal
    generates_tp = False     # generates a take profit price proposal with each signal
    
    # 
    def __init__(self, ask_spread: float = 0.001, bid_spread: float = 0.001, sl_buffer: float = 0.001):
        
        self.ask_spread = ask_spread
        self.bid_spread = bid_spread
        
        self.sl_buffer = sl_buffer
        
    def signal(self, ask: float, bid: float, df):
        
        signal = {}
        
        mid = float((ask + bid)/2)
        mid = round(mid,5)

        df.ta.ema(close=df["close"], length=13, append=True)
        df.ta.rsi(length=9, append=True)
        df.ta.atr(length=9, append=True)
        df.ta.natr(length=9, append=True)
        
        df['HIGH_48'] = df.high.rolling(48).max()
        df['LOW_48'] = df.low.rolling(48).min()

        # drop empty EMA, SMA, ATR, RSI ...    
        df.dropna(inplace=True)

        ## print(df)
        recent_ema = df['EMA_13'].iloc[-1]
        recent_rsi = df['RSI_9'].iloc[-1]
        recent_atr = df['ATRr_9'].iloc[-1]
        recent_natr = df['NATR_9'].iloc[-1]
        recent_swing_high = df['HIGH_48'].iloc[-1]
        recent_swing_low = df['LOW_48'].iloc[-1]
        
        # bid_limit = bid * (1 - self.bid_spread)
        # ask_limit = ask * (1 + self.ask_spread)
        
        # TODO - checks if meaningful ... considering current bid/ask
        sl_sell_price = recent_swing_high * (1 + self.sl_buffer)
        sl_buy_price = recent_swing_low * (1 - self.sl_buffer)

        # directional trading
        if mid < recent_ema and recent_rsi > 30:
            ask_limit = recent_ema * (1 - self.ask_spread / 2)
            signal['sell'] = { 'li': ask_limit, 'sl': sl_sell_price }
            trend = 'sell'
        if mid > recent_ema and recent_rsi < 70:
            bid_limit = recent_ema * (1 + self.bid_spread / 2)
            signal['buy'] = { 'li': bid_limit, 'sl': sl_buy_price }
            trend = 'buy'
           
        # market maker on both sides
        if (recent_natr < 0.3 and (recent_rsi > 40 and recent_rsi < 60) ):
            logging.info(f'({self.class_name()}.signal) natr very small {recent_natr:.2f}% trading in both directions')
            bid_limit = bid * (1 - self.bid_spread * 1.5) if trend == 'buy' else bid * (1 - self.bid_spread)
            ask_limit = ask * (1 + self.ask_spread * 1.5) if trend == 'sell' else ask * (1 + self.ask_spread)
            signal['buy']  = { 'li': bid_limit, 'sl': sl_buy_price }
            signal['sell'] = { 'li': ask_limit, 'sl': sl_sell_price }
            trend = 'both'

        logging.info(f'({self.class_name()}.signal) ema_5_13 {recent_ema:.4f} rsi {recent_rsi:.4f} mid {mid} atr {recent_atr:.4f} natr {recent_natr:.2f}% trend {trend}')

        return signal