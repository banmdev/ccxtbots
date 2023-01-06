import logging
import time

from base import BaseClass
from exchange_adapters import ExchangeAdapter

class BaseBot(BaseClass):

    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, ticks: int = 1, refresh_timeout: int = 120):

        # ticks and refresh timeout in seconds
        self._ticks: int = ticks
        self._refresh_timeout: int = int(refresh_timeout * 1000) 
        
        # _ea stands for Exchange Adapter
        self._ea: ExchangeAdapter = exchange_adapter

        # symbol to trade
        self._symbol: str = symbol

        # state vars 
        self._open_orders_bool: bool = False
        self._open_position_bool: bool = False
        self._last_open_position_bool: bool = False
        self._last_current_long: bool = None
        self._last_position_size: float = 0
        self._cum_pnl: float = 0

        # last tp and order id
        self._last_tp_order_id: str = None
        self._last_sl_order_id: str = None
        
        # open orders by price and id dicts
        self._open_limit_orders_by_price = { 'sell': {}, 'buy': {} }
        self._open_limit_orders_by_id = { 'sell': {}, 'buy': {} }
        self._open_stop_orders_by_price = { 'sell': {}, 'buy': {} }
        self._open_stop_orders_by_id = { 'sell': {}, 'buy': {} }

    @property
    def ticks(self) -> int:
        return self._ticks

    @ticks.setter
    def ticks(self, value: int):
        self._ticks = value

    @property
    def refresh_timeout(self) -> int:
        return self._refresh_timeout

    @refresh_timeout.setter
    def refresh_timeout(self, value: int):
        self._refresh_timeout = int(value * 1000)

    @property
    def symbol(self) -> str:
        return self._symbol

    @symbol.setter
    def symbol(self, value):
        self._symbol = value

    @property
    def last_tp_order_id(self) -> str:
        return self._last_tp_order_id

    @last_tp_order_id.setter
    def last_tp_order_id(self, value):
        self._last_tp_order_id = value

    @property
    def last_sl_order_id(self) -> str:
        return self._last_sl_order_id

    @last_sl_order_id.setter
    def last_sl_order_id(self, value):
        self._last_sl_order_id = value

    # TODO- implement all other setters and getters

    def tick(self):
        time.sleep(self.ticks)

    
    # All event handlers:
    
    def preparation_handler(self):

        logging.debug(f'({self.class_name()}.preparation_handler) symbol {self.symbol}: Prepare to run the main loop')

    def housekeeping_handler(self):

        logging.debug(f'({self.class_name()}.housekeeping_handler) symbol {self.symbol}: I am not in a position - cleaning up previous orders, files and dataframes')

    def noposition_handler(self):

        logging.debug(f'({self.class_name()}.noposition_handler) symbol {self.symbol}: I am not in a position - waiting for entry signals and new order checks!')

    def inposition_handler(self):
        
        logging.debug(f'({self.class_name()}.inposition_handler) symbol {self.symbol}: I am in a position, current_size: {self._current_size}, long: {self._current_long}, entryPrice: {self._entryPrice}, leverage {self._position_leverage}')
        
    def exitposition_handler(self):
        
         logging.debug(f'({self.class_name()}.exitposition_handler) symbol {self.symbol}: Exit position handler, current_size: {self._current_size}, long: {self._current_long}, entryPrice: {self._entryPrice}, leverage {self._position_leverage}')

    def finishtrade_handler(self):
        log_prefix = f"({self.class_name()}.finishtrade_handler) symbol {self.symbol}:"

        logging.info(f'{log_prefix}: Finish trade handler, current_size: {self._current_size}, long: {self._current_long}, entryPrice: {self._entryPrice}, leverage {self._position_leverage}')

    def refresh_open_position(self):
        
        [ self._position, self._open_position_bool, self._current_size, self._current_long, self._entryPrice, self._position_leverage ] = self._ea.fetch_open_positions(self.symbol)
    
    def shutdown_handler(self):
        log_prefix = f"({self.class_name()}.shutdown_handler) symbol {self.symbol}:"

        logging.info(f'{log_prefix} Shutdown the bot')


    # General functions for order management:

    def matching_limit_order(self, side: str, price: float, amount: float) -> dict:
        log_prefix = f"({self.class_name()}.maintain_tp_order) symbol {self.symbol}:"
        
        if side != 'buy' and side != 'sell':
            raise ValueError(f'{log_prefix} Invalid side param {side}, must be either buy or sell')

        order = None

        if price in self._open_limit_orders_by_price[side]:
            if self._open_limit_orders_by_price[side][price]['amount'] == amount:
                order = self._open_limit_orders_by_price[side][price]
        
        return order

    def matching_stop_order(self, side: str, stopprice: float, amount: float) -> dict:
        log_prefix = f"({self.class_name()}.maintain_tp_order) symbol {self.symbol}:"

        if side != 'buy' and side != 'sell':
            raise ValueError(f'{log_prefix} Invalid side param {side}, must be either buy or sell')

        order = None

        if stopprice in self._open_stop_orders_by_price[side]:
            if self._open_stop_orders_by_price[side][stopprice]['amount'] == amount:
                order = self._open_stop_orders_by_price[side][stopprice]
        
        return order

    def matching_order_by_id(self, order_id: str, type: str, side: str) -> bool:
        log_prefix = f"({self.class_name()}.matching_order_by_id) symbol {self.symbol}:"

        if side != 'buy' and side != 'sell':
            raise ValueError(f'{log_prefix} Invalid side param {side}, must be either buy or sell')

        if type != 'limit' and type != 'stop':
            raise ValueError(f'{log_prefix} Invalid side param {type}, must be either limit or stop')

        if type == 'limit':
            return order_id in self._open_limit_orders_by_id[side]

        if type == 'stop':
            return order_id in self._open_stop_orders_by_id[side]

        return False

    def maintain_sl_order(self, stopprice, size=None):
        log_prefix = f"({self.class_name()}.maintain_sl_order) symbol {self.symbol}:"

        if size == None:
            size = self._current_size

        order = None

        if self._open_position_bool == True:

            buy_sell = 'sell' if self._current_long == True else 'buy'

            order = self.matching_stop_order(buy_sell, stopprice, size)

            if order is None:
                try:
                    # cancel outdated sl order
                    if self.last_sl_order_id is not None and self.last_sl_order_id in self._open_stop_orders_by_id[buy_sell]:
                        logging.info(f"{log_prefix} Cancelling existing {buy_sell} stop order because size differs from size {size} or price {stopprice}")
                        o = { 'symbol': self.symbol, 
                              'order_id': self.last_sl_order_id, 
                              'direction': buy_sell, 
                              'type': 'stop',
                              'exchange_id': self._ea.id }
                        self._ea.cancel_order_based_on_model(o)
                
                    logging.info(f'{log_prefix} Create {buy_sell} stop loss order of size {size} at {stopprice}')

                    order = self._ea.create_stop_loss_order_by_trigger_price(self.symbol, stopprice, size, buy_sell)
            
                except Exception as err:
                    logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
                    raise err
                else:
                    logging.info(f"{log_prefix} Stop loss {buy_sell} order with id {order['id']} of size {size} at {stopprice} created")

            else:
                logging.debug(f'{log_prefix} Matching active stop loss ({buy_sell}) order already exists at {stopprice}')

            self.last_sl_order_id = order['id']

        return order

        
    def maintain_tp_order(self, price, size=None):
        log_prefix = f"({self.class_name()}.maintain_tp_order) symbol {self.symbol}:"
        
        if size == None:
            size = self._current_size

        order = None

        if self._open_position_bool == True:

            buy_sell = 'sell' if self._current_long == True else 'buy'

            order = self.matching_limit_order(buy_sell, price, self._current_size)

            if order is None:
                try:
                    # print(f'{log_prefix} self.last_tp_order_id: {self.last_tp_order_id}')
                    # cancel outdated tp order
                    if self.last_tp_order_id is not None and self.last_tp_order_id in self._open_limit_orders_by_id[buy_sell]:
                        logging.info(f"{log_prefix} Cancelling existing {buy_sell} take profit order because size differs from current_size {self._current_size} or price {price}")
                        self._ea.cancel_order(self.last_tp_order_id, self.symbol)
                
                    logging.info(f'{log_prefix} Create opposite {buy_sell} order (take profit) of size {self._current_size} at {price}')
                    if self._current_long == True:
                        order = self._ea.create_limit_sell_order(self.symbol, self._current_size, price)
                    else:
                        order = self._ea.create_limit_buy_order(self.symbol, self._current_size, price)
            
                except Exception as err:
                    logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
                    raise err
                else:
                    logging.info(f"{log_prefix} Opposite {buy_sell} order (take profit) with id {order['id']} of size {self._current_size} at {price} created")
            else:
                logging.debug(f'{log_prefix} Matching active opposite close ({buy_sell}) limit order already exists at {price}')

            self.last_tp_order_id = order['id']
        
        return order


    def refresh_active_orders(self):
        log_prefix = f"({self.class_name()}.refresh_active_orders) symbol {self.symbol}:"

        logging.debug(f'{log_prefix} Obtaining active orders and return in lists')

        open_orders = []

        # active orders
        self._open_orders_bool = False
        self._open_ask_orders = [] # limit, sell
        self._open_bid_orders = [] # limit, buy
        self._open_sl_orders_long = [] # Stop, sell
        self._open_sl_orders_short = [] # Stop, buy

        self._open_limit_orders_by_price = { 'sell': {}, 'buy': {} }
        self._open_limit_orders_by_id = { 'sell': {}, 'buy': {} }

        self._open_stop_orders_by_price = { 'sell': {}, 'buy': {} }
        self._open_stop_orders_by_id = { 'sell': {}, 'buy': {} }

        last_tp_order_found = False
        last_sl_order_found = False
        
        try:
            open_orders = self._ea.fetch_open_orders(self.symbol) 

            if len(open_orders) > 0:
                ## pp.pprint (open_orders)
                self._open_orders_bool = True
                # print (f'(refresh_active_orders) INFO: Open orders for symbol {self.symbol}:')
                # pp.pprint(open_orders)
            
                for order in open_orders:
                    o_id = order['id']

                    if o_id == self.last_tp_order_id:
                        last_tp_order_found = True

                    if o_id == self.last_sl_order_id:
                        last_sl_order_found = True
                    
                    o_type = order['type']
                    o_side = order['side']
                    o_amount = order['amount']
                    o_filled = order['filled']
                    o_remaining = order['remaining']
                    o_price = order['price']
                    o_timestamp = order['timestamp']
                    o_stopprice = order['stopPrice']

                    if o_type == 'limit' and o_side == 'sell':
                        self._open_limit_orders_by_price['sell'][o_price]=order
                        self._open_limit_orders_by_id['sell'][o_id]=order
                        self._open_ask_orders.append(order)
                    
                    if o_type == 'limit' and o_side == 'buy':
                        self._open_limit_orders_by_price['buy'][o_price]=order
                        self._open_limit_orders_by_id['buy'][o_id]=order
                        self._open_bid_orders.append(order)
                    
                    if o_type == 'Stop' and o_side == 'sell':
                        self._open_stop_orders_by_price['sell'][o_stopprice]=order
                        self._open_stop_orders_by_id['sell'][o_id]=order
                        self._open_sl_orders_long.append(order)

                    if o_type == 'Stop' and o_side == 'buy':
                        self._open_stop_orders_by_price['buy'][o_stopprice]=order
                        self._open_stop_orders_by_id['buy'][o_id]=order
                        self._open_sl_orders_short.append(order)

                    if o_type == 'Stop':
                        logging.debug(f'{log_prefix} Order detected: {o_id} Type: {o_type} Side: {o_side} Price {o_stopprice} Filled: {o_filled} Remaining: {o_remaining} Timestamp: {o_timestamp}')
                    else: 
                        logging.debug(f'{log_prefix} Order detected: {o_id} Type: {o_type} Side: {o_side} Amount: {o_amount} at Price {o_price} Filled: {o_filled} Remaining: {o_remaining} Timestamp: {o_timestamp}')
            
                # was deleted manually by trader
                if last_tp_order_found != True:
                    self.last_tp_order_id = None

                if last_sl_order_found != True:
                    self.last_sl_order_id = None

            else:
                self._open_orders_bool = False
                logging.debug(f'{log_prefix} No open orders for symbol {self.symbol}')

        except Exception as err:
            logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
            raise err


    # the bot main loop calling the different event handlers
    # the goal is that child classes only implement the handlers

    def main_loop(self):

        next_refresh = 0

        self.preparation_handler()

        while True:

            timestamp = int(time.time()*1000)

            try:

                logging.debug(f'({self.class_name()}.main_loop) Mainloop start')

                self.refresh_active_orders()

                self.refresh_open_position()

                if self._open_position_bool == False:

                    # triggering orders to enter positions after timeout
                    if (timestamp < next_refresh):
                        logging.debug(f'({self.class_name()}.main_loop) Waiting for refresh!')

                    else:
                        logging.debug(f'({self.class_name()}.main_loop) Do the refresh tasks!')
                        next_refresh = timestamp + self.refresh_timeout

                        # call the finishtrade_handler to record trade data, e.g. pnl
                        if self._last_open_position_bool == True:
                            self.finishtrade_handler()

                            # resetting all main state variables
                            # I dont want touch them in child classes
                            self._last_open_position_bool = False
                            self._last_current_long = None
                            self._last_position_size = None
                            self.last_sl_order_id = None
                            self.last_tp_order_id = None

                        # call the housekeeping handler
                        self.housekeeping_handler()
                        
                        # call no position handler
                        self.noposition_handler()

                else:
                    
                    next_refresh = 0

                    # exit_handler to process exit signals ...
                    self.exitposition_handler()

                    # in position handler ...
                    self.inposition_handler()
                    
                    # update state vars
                    # I dont want to touch them in child classes
                    self._last_position_size = self._current_size
                    self._last_open_position_bool = True
                    self._last_current_long = self._current_long

                    # print(f'({self.class_name()}.main_loop) Mainloop: self.last_tp_order_id {self.last_tp_order_id}')

                logging.debug(f'({self.class_name()}.main_loop) Mainloop end')
                self.tick()

            except KeyboardInterrupt:
                self.shutdown_handler()
                return
