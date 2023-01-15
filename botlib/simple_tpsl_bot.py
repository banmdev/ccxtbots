import logging

from .basebot import BaseBot
from exchange_adapters import ExchangeAdapter
from signal_generators import ExtendedSignalGenerator
from order_models import FixedTPSLModel

# import pprint
# pp = pprint.PrettyPrinter(indent=4)

class SimpleTPSLBot(BaseBot):
    
    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, 
                 signal_generator: ExtendedSignalGenerator, long_model: FixedTPSLModel, 
                 short_model: FixedTPSLModel,
                 ticks: int = 3, refresh_timeout: int = 120, not_trading=False) -> None:
        
        if long_model.direction != 'long':
            raise ValueError(f"""({self.class_name()}.__init__) Invalid trade direction for long model: {long_model.direction}, must be long""")
        
        if short_model.direction != 'short':
            raise ValueError(f"""({self.class_name()}.__init__) Invalid trade direction for short model: {short_model.direction}, must be short""")

        # self._signal_generator: ExtendedSignalGenerator = signal_generator
        self._long_model: FixedTPSLModel = long_model
        self._short_model: FixedTPSLModel = short_model
        
        self._leverage: int = 50
        self._max_account_risk_per_trade: float = 0.01
        self._current_buy_order_id: str = None
        self._current_sell_order_id: str = None
        self._not_trading: bool = not_trading
        
        super().__init__(exchange_adapter, symbol, signal_generator, ticks, refresh_timeout)
            
    @property
    def leverage(self):
        return self._leverage

    @leverage.setter
    def leverage(self, value):
        self._leverage = value

    @property
    def max_account_risk_per_trade(self):
        return self._max_account_risk_per_trade

    @max_account_risk_per_trade.setter
    def max_account_risk_per_trade(self, value):
        self._max_account_risk_per_trade = value
        
    def preparation_handler(self):
        log_prefix=f"({self.class_name()}.preparation_handler) symbol {self.symbol}:"

        logging.debug(f'{log_prefix} Prepare to run the main loop')
        self.leverage = self._ea.set_leverage_for_symbol(self.symbol, self.leverage)
        logging.info(f'{log_prefix} Leverage is now {self.leverage}')
    
    def _cancel_current_buy(self):
        
        log_prefix = f"({self.class_name()}._cancel_current_buy) symbol {self.symbol}:"
        
       
        if self._current_buy_order_id is not None:

            if self.matching_order_by_id(self._current_buy_order_id, 'limit', 'buy'):

                logging.info(f'{log_prefix} Cancel current buy order {self._current_buy_order_id}')
                
                try:
                    self._ea.cancel_order(self._current_buy_order_id, self.symbol)
                except Exception as e:
                    logging.exception(f'{log_prefix} WARN: Could not cancel existing buy order {self._current_buy_order_id}')
                else:
                    logging.info(f'{log_prefix} Current buy order {self._current_buy_order_id} cancelled')
                    self._current_buy_order_id = None
        
    def _cancel_current_sell(self):
        
        log_prefix = f"({self.class_name()}._cancel_current_sell) symbol {self.symbol}:"
        
        if self._current_sell_order_id is not None:

            if self.matching_order_by_id(self._current_sell_order_id, 'limit', 'sell'):

                logging.info(f'{log_prefix} Cancel current sell order {self._current_sell_order_id}')
                
                try:
                    self._ea.cancel_order(self._current_sell_order_id, self.symbol)
                except Exception as e:
                    logging.exception(f'{log_prefix} WARN: Could not cancel existing sell order {self._current_sell_order_id}')
                else:
                    logging.info(f'{log_prefix} Current sell order {self._current_sell_order_id} cancelled')
                    self._current_sell_order_id = None
                

        
        
        
    def housekeeping_handler(self):
        log_prefix = f"({self.class_name()}.housekeeping) symbol {self.symbol}:"
        
        super().housekeeping_handler()
        
        self._cancel_current_buy()
        
        self._cancel_current_sell()
                    
        
    def inposition_handler(self):
        log_prefix = f"({self.class_name()}.inposition_handler) symbol {self.symbol}:"
        
        # only support long:
        if self._current_long == True:
            
            long_short = 'long'
            
            self._cancel_current_sell()
            
            # MAINTAIN SL
            price_sl, size_sl = self._long_model.get_sl_price_size(self._current_size, self._entryPrice)
            self.maintain_sl_order(price_sl, size_sl)
            
            # MAINTAIN TP
            price_tp, size_tp = self._long_model.get_tp_price_size(self._current_size, self._entryPrice)
            self.maintain_tp_order(price_tp, size_tp)
            
            # PRINT INFO
            if self._open_position_bool and self._current_size != self._last_position_size:
                logging.info(f"""{log_prefix} I am in a {long_short} position at {self._entryPrice} with size {self._current_size}, take profit at {price_tp} and stop loss at {price_sl}""")
    
        if self._current_long == False:
            
            long_short = 'short'
            
            self._cancel_current_buy()
            
            # MAINTAIN SL
            price_sl, size_sl = self._short_model.get_sl_price_size(self._current_size, self._entryPrice)
            self.maintain_sl_order(price_sl, size_sl)
            
            # MAINTAIN TP
            price_tp, size_tp = self._short_model.get_tp_price_size(self._current_size, self._entryPrice)
            self.maintain_tp_order(price_tp, size_tp)
            
            # PRINT INFO
            if self._current_size != self._last_position_size:
                logging.info(f"""{log_prefix} I am in a {long_short} position at {self._entryPrice} with size {self._current_size}, take profit at {price_tp} and stop loss at {price_sl}""")
                    
    def enter_position_handler(self):
        
        log_prefix = f"({self.class_name()}.noposition_handler) symbol {self.symbol}:"

        logging.info(f'{log_prefix} I am not in a position - waiting for entry signals and new order checks!')
 
        try:
            # check balance
            total_balance = self._ea.get_total_balance()
        except Exception as e:

            logging.exception(f'{log_prefix} ERROR: Could not check current balance')
            raise Exception(e)

        else:
            max_risk_per_trade = ( total_balance * self.max_account_risk_per_trade ) 
            logging.info(f'{log_prefix} Total account balance: {total_balance} Max risk per trade: {max_risk_per_trade}')

            try:
                [ask, bid] = self._ea.ask_bid(self.symbol)
                signal = self.signal(ask, bid)
                
            except Exception as e:
                logging.exception(f'{log_prefix} WARN: Could not get bid ask price or signal')
                return

            if 'buy' in signal:
                try:
                    [ price, self._long_model.sl_fixed, self._long_model.tp_fixed ] = self.parse_signal(signal, 'buy', bid)

                    size  = self._long_model.get_order_size(price, max_risk_per_trade)
                    tp = self._long_model.get_tp_price_size(size, price)[0]
                    sl = self._long_model.get_sl_price_size(size, price)[0]
                    
                    if self._not_trading:
                        logging.info(f'{log_prefix} NOT TRADING: Buy order of size: {size} at price: {price} would have been created - with fixed sl at {sl} and tp at {tp}')
                    else:
                        logging.info(f'{log_prefix} Create Buy order of size: {size} at price: {price} created - with fixed sl at {sl} and tp at {tp}')
                        order = self._ea.create_limit_buy_order(self.symbol, size=size, price=price)
                        self._current_buy_order_id = order['id']
                        logging.info(f'{log_prefix} Buy order id: {self._current_buy_order_id}')
                                    
                except Exception as e:
                    logging.exception(f'{log_prefix} WARN: Could not execute the buy order')

            if 'sell' in signal:
                try:

                    [ price, self._short_model.sl_fixed, self._short_model.tp_fixed ] = self.parse_signal(signal, 'sell', ask)
                    
                    size  = self._short_model.get_order_size(price, max_risk_per_trade)
                    tp = self._short_model.get_tp_price_size(size, price)[0]
                    sl = self._short_model.get_sl_price_size(size, price)[0]
                    
                    if self._not_trading:
                        logging.info(f'{log_prefix} NOT TRADING: Sell order of size: {size} at price: {price} would have been created - with fixed sl at {sl} and tp at {tp}')    
                    else:
                        logging.info(f'{log_prefix} Create Sell order of size: {size} at price: {price} created - with fixed sl at {sl} and tp at {tp}')
                        order = self._ea.create_limit_sell_order(self.symbol, size=size, price=price)
                        self._current_sell_order_id = order['id']
                        logging.info(f'{log_prefix} Sell order id: {self._current_sell_order_id}')
                                    
                except Exception as e:
                    logging.exception(f'{log_prefix} WARN: Could not execute the sell order')

    def exit_position_handler(self):
        
        log_prefix = f"({self.class_name()}.exit_position_handler) symbol {self.symbol}:"
        
        exit_signal = False
        
        # PROCESSING EXIT SIGNALS ...
        [ask, bid] = self._ea.ask_bid(self.symbol)
        signal = self.exit_signal(ask, bid)
        
        if self._current_long == True:
            long_short = "long"
            model = self._long_model
            logging.debug(f'{log_prefix} Long Exit signal? {signal}')
            if 'sell' in signal and not 'buy' in signal:
                self.maintain_tp_order(ask)
                exit_signal = True
                self._exiting = True          
        else:
            long_short = "short"
            model = self._short_model
            logging.debug(f'{log_prefix} Short Exit signal? {signal}')
            if 'buy' in signal and not 'sell' in signal:
                self.maintain_tp_order(bid)
                exit_signal = True
                self._exiting = True
                
        if not exit_signal:
            # MAINTAIN TRAILING SL TO TAKE MININUM PROFIT
            [trig_price, tr_value] = model.get_trsl_price_value(self._current_size, self._entryPrice)
            logging.debug(f'{log_prefix} {long_short} Trailing stop loss will be triggered at {trig_price} with trail value of {tr_value}')
            
            self.maintain_trail_sl(trigger_price=trig_price, trail_value=tr_value)
        
        if self._exiting:
            logging.info(f'{log_prefix} Exiting the {long_short} position at {self._entryPrice} with size {self._current_size}')
            

    
