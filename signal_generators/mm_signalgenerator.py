import logging
import pandas_ta as ta

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
        
        super().__init__()

        self.feeds = { 
                'default': {
                    'timeframe': '5m',
                    'num_bars': 80,
                    'refresh_timeout': 90, 
                    'only_closed': True,
                    'df': None
                    },
                }
        
        self.ask_spread = ask_spread
        self.bid_spread = bid_spread   
        self.sl_buffer = sl_buffer
        
    def prepare_df(self):
        
        if self.df is not None:
            # logging.warn(f'({self.class_name()}.prepare_df) No default dataframe available - exit function')
            # return
            self.df.ta.ema(close=self.df["close"], length=13, append=True)
            self.df.ta.rsi(length=9, append=True)
            self.df.ta.atr(length=9, append=True)
            self.df.ta.natr(length=9, append=True)
            
            # 5m SMA 20 Periods
            self.df['SMA_40'] = self.df.close.rolling(40).mean()
            
            self.df['HIGH_48'] = self.df.high.rolling(48).max()
            self.df['LOW_48'] = self.df.low.rolling(48).min()

            # drop empty EMA, SMA, ATR, RSI ...    
            self.df.dropna(inplace=True)
        
    def exit_signal(self, ask: float = None, bid: float = None) -> dict:
        
        
        signal = {}
        
        if self.df is None:
            logging.warn(f'({self.class_name()}.exit_signal) No default dataframe available - exit function')
            return signal
        else:
            df = self.df
            
        mid = float((ask + bid)/2)
        mid = round(mid,5)
            
        recent_sma = df['SMA_40'].iloc[-1]
        recent_rsi = df['RSI_9'].iloc[-1]
        last_close = df['close'].iloc[-1]
        
        # TODO - checks if meaningful ... considering current bid/ask
        if self.verbose:
            print(f"==== {self.class_name()}.exit_signal VERBOSE ====")
            print('Dataframe from My Exchange ====>')
            print(df)
            print(f'recent_sma  = {recent_sma}')
            print(f'recent_rsi  = {recent_rsi}')
            print(f'last_close  = {last_close}')
        
        if last_close < recent_sma:  # and recent_rsi < 70:
            signal['sell'] = { }
            trend = 'sell'
            
        if last_close > recent_sma: # and recent_sma > 30:
            signal['buy'] = { }
            trend = 'buy'
            
        logging.info(f'({self.class_name()}.exit_signal) sma_5_40 {recent_sma:.4f} rsi {recent_rsi:.4f} mid {mid} trend {trend}')

        return signal
            
  
    def signal(self, ask: float, bid: float):
        
        signal = {}
        
        if self.df is None:
            logging.warn(f'({self.class_name()}.signal) No default dataframe available - exit function')
            return signal
        else:
            df = self.df
        
        mid = float((ask + bid)/2)
        mid = round(mid,5)

        ## print(df)
        recent_ema = df['EMA_13'].iloc[-1]
        recent_rsi = df['RSI_9'].iloc[-1]
        recent_atr = df['ATRr_9'].iloc[-1]
        recent_natr = df['NATR_9'].iloc[-1]
        recent_swing_high = df['HIGH_48'].iloc[-1]
        recent_swing_low = df['LOW_48'].iloc[-1]
        recent_sma = df['SMA_40'].iloc[-1]
        
        sl_buy_price = recent_swing_low * (1 - self.sl_buffer)
        sl_sell_price = recent_swing_high * (1 + self.sl_buffer)
        
        # bid_limit = bid * (1 - self.bid_spread)
        # ask_limit = ask * (1 + self.ask_spread)
        
        trend = None
        
        # TODO - checks if meaningful ... considering current bid/ask
        if self.verbose:
            print(f"==== {self.class_name()}.signal VERBOSE ====")
            print('Dataframe from My Exchange ====>')
            print(df)
            print(f'recent_ema  = {recent_ema}')
            print(f'recent_sma  = {recent_sma}')
            print(f'recent_rsi  = {recent_rsi}')
            print(f'recent_atr  = {recent_atr}')
            print(f'recent_natr = {recent_natr}')
            print(f'recent_swing_high = {recent_swing_high}')
            print(f'recent_swing_low  = {recent_swing_low}')
            print(f'sl_buy_price  = {sl_buy_price}')
            print(f'sl_sell_price = {sl_sell_price}')

        # directional trading
        if mid < recent_ema and recent_ema < recent_sma and recent_rsi > 30:
            ask_limit = ask * (1 + self.ask_spread)
            signal['sell'] = { 'li': ask_limit, 'sl': sl_sell_price }
            trend = 'sell'
        if mid > recent_ema and recent_ema > recent_sma and recent_rsi < 70:
            bid_limit = bid * (1 - self.bid_spread)
            signal['buy'] = { 'li': bid_limit, 'sl': sl_buy_price }
            trend = 'buy'
           
        # market maker on both sides
        # if (recent_natr < 0.3 and (recent_rsi > 40 and recent_rsi < 60) ):
        #     logging.info(f'({self.class_name()}.signal) natr very small {recent_natr:.2f}% trading in both directions')
        #     bid_limit = bid * (1 - self.bid_spread * 1.5) if trend == 'buy' else bid * (1 - self.bid_spread)
        #     ask_limit = ask * (1 + self.ask_spread * 1.5) if trend == 'sell' else ask * (1 + self.ask_spread)
        #     signal['buy']  = { 'li': bid_limit, 'sl': sl_buy_price }
        #     signal['sell'] = { 'li': ask_limit, 'sl': sl_sell_price }
        #     trend = 'both'

        logging.info(f'({self.class_name()}.signal) ema_5_13 {recent_ema:.4f} rsi {recent_rsi:.4f} mid {mid} atr {recent_atr:.4f} natr {recent_natr:.2f}% trend {trend}')

        return signal