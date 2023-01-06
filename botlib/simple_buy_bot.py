import logging

from .basebot import BaseBot
from exchange_adapters import ExchangeAdapter
from signal_generators import BuySignalGenerator
from order_models import FixedTPSLModel


class SimpleBuyBot(BaseBot):
    
    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, 
                 signal_generator: BuySignalGenerator, long_model: FixedTPSLModel, 
                 ticks: int = 1, refresh_timeout: int = 120) -> None:
        
        if long_model.direction != 'long':
            raise ValueError(f"""({self.class_name()}.__init__) Invalid trade direction {long_model.direction}, must be either long or short""")

        self._signal_generator: BuySignalGenerator = signal_generator
        self._model: FixedTPSLModel = long_model
        
        self._leverage: int = 50
        self._max_account_risk_per_trade: float = 0.01
        self._current_buy_order_id: str = None
        
        super().__init__(exchange_adapter, symbol, ticks, refresh_timeout)
            
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
        
    def housekeeping_handler(self):
        log_prefix = f"({self.class_name()}.housekeeping) symbol {self.symbol}:"
        
        super().housekeeping_handler()
        
        try:
            if self._current_buy_order_id is not None:
                if self.matching_order_by_id(self._current_buy_order_id, 'limit', 'buy'):
                    logging.info(f'{log_prefix} Cancel current buy order {self._current_buy_order_id}')
                    self._ea.cancel_order(self._current_buy_order_id, self.symbol)
                
                self._current_buy_order_id = None
                
        except Exception as e:
            logging.exception(f'{log_prefix} WARN: Could not cancel existing buy order', Exception(e))
            raise
            
        
    def inposition_handler(self):
        log_prefix = f"({self.class_name()}.inposition_handler) symbol {self.symbol}:"
        
        # only support long:
        if self._current_long == True:
            
            long_short = 'long'
            
            # MAINTAIN SL
            price_sl, size_sl = self._model.get_sl_price_size(self._current_size, self._entryPrice)
            self.maintain_sl_order(price_sl, size_sl)
            
            # MAINTAIN TP
            price_tp, size_tp = self._model.get_tp_price_size(self._current_size, self._entryPrice)
            self.maintain_tp_order(price_tp, size_tp)
            
            # PRINT INFO
            if self._current_size != self._last_position_size:
                logging.info(f"""{log_prefix} I am in a {long_short} position at {self._entryPrice} with size {self._current_size}, take profit at {price_tp} and stop loss at {price_sl}""")
                
    def noposition_handler(self):
        
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
            self.trend = self._signal_generator.signal()
            [ask, bid] = self._ea.ask_bid(self.symbol)
                
            if self.trend == 'buy':
                try:
                    # get bid, ask and mid
                    price = float(self._ea.price_to_precision(self.symbol, bid)) # just for simplicity ... need to ask the model?
                    size  = self._model.get_order_size(price, max_risk_per_trade) 
                    order = self._ea.create_limit_buy_order(self.symbol, size=size, price=price)
                    self._current_buy_order_id = order['id']
                    logging.info(f'{log_prefix} Buy order of size: {size} at price: {price} created, id {self._current_buy_order_id}')
                                    
                except Exception as e:
                    logging.exception(f'{log_prefix} WARN: Could not execute the order')

            if self.trend is None:

                logging.info(f'{log_prefix} Not trading because trend = None')

    
