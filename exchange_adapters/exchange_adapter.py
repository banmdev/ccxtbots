import logging
import time
import pandas as pd

import ccxt

# import pprint
# pp = pprint.PrettyPrinter(indent=4)

from base import BaseClass

class ExchangeAdapter(BaseClass):

    def __init__(self, exchange, exchange_params):
        self._exchange = exchange
        self._exchange_params = exchange_params

        self._openpos_size_field = 'contracts'
        self._trade_params = { 'timeInForce': 'PostOnly' }
        self._trade_params_kill = { 'timeInForce': 'PostOnly', 'reduceOnly': True }

        self._markets = self._exchange.load_markets()

    @property
    def id(self) -> str:
        return self._exchange.id

    @property
    def exchange_params(self):
        return self._exchange_params

    @exchange_params.setter
    def exchange_params(self, value):
        self._exchange_params = value

    @property
    def maker_fees(self):
        return self._maker_fees

    @maker_fees.setter
    def maker_fees(self, value):
        self._maker_fees = value

    @property
    def taker_fees(self):
        return self._taker_fees

    @taker_fees.setter
    def taker_fees(self, value):
        self._taker_fees = value

    def price_to_precision(self, symbol, price):
        return self._exchange.price_to_precision(symbol, price)

    def amount_to_precision(self, symbol, amount):
        return self._exchange.amount_to_precision(symbol, amount)

    def get_total_balance(self):
        balance=self._exchange.fetch_balance(params=self._exchange_params)
        total = float(balance.get('total').get(self._exchange_params['code']))
        return total

    # order book ask and bid
    def ask_bid(self, symbol):

        ob = self._exchange.fetch_order_book(symbol)
        ask = ob['asks'][0][0]
        bid = ob['bids'][0][0]
        return ask, bid

    # pass through cancel order
    def cancel_order(self, order_id, symbol):
        self._exchange.cancel_order(order_id, symbol)

    def create_limit_buy_order(self, symbol, size, price):
        order = self._exchange.create_limit_buy_order(symbol, size, price, self._trade_params)
        return order

    def create_limit_sell_order(self, symbol, size, price):
        order = self._exchange.create_limit_sell_order(symbol, size, price, self._trade_params)
        return order
    
    def close_short_limit_order(self, symbol, size, price):
        order = self._exchange.create_limit_buy_order(symbol, size, price, self._trade_params_kill)
        return order

    def close_long_limit_order(self, symbol, size, price):
        order = self._exchange.create_limit_sell_order(symbol, size, price, self._trade_params_kill)
        return order

    # get open futures/contract positions
    def fetch_open_positions(self, symbol):
        log_prefix = f"({self.class_name()}.fetch_open_orders) symbol {symbol}:" 

        entry_price = 0.0
        openpos_size = 0.0
        leverage = 0
        position = None
        openpos_bool = False
        long = True

        try:
            positions = self._exchange.fetch_positions(symbols=[symbol], params=self._exchange_params)
        except Exception as err:
            # logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
            raise      
        else:

            # find the open position ... bitget with heding mode returns always two records, one for long and one for short
            for pos in positions:
                entry_price = float(pos['entryPrice'] or 0)
                if entry_price > 0:
                    position = pos
                    break

            # no position found
            if position is None:
                return None, openpos_bool, openpos_size, long, entry_price, leverage

            openpos_size = float(position[self._openpos_size_field] or 0)
            openpos_side = position['side']
        
            # some exchanges such as phemex returns negative levarage, convert to positve
            leverage = abs(float(position['leverage'] or 0))

            if openpos_size > 0:
                openpos_bool = True
                if openpos_side == 'long':
                    long = True
                elif openpos_side == 'short':
                    long = False
            else:
                openpos_bool = False
                long = None

            logging.debug(f'{log_prefix} openpos_bool: {openpos_bool}, openpos_size: {openpos_size}, long: {long}, entry_price: {entry_price}, leverage: {leverage}')

            return position, openpos_bool, openpos_size, long, entry_price, leverage

    def fetch_candles_df(self, symbol, timeframe='5m', num_bars=50, only_closed=True):
        log_prefix = f"({self.class_name()}.fetch_candles) symbol {symbol}:"

        logging.debug(f'{log_prefix} Fetching {num_bars} candles: {timeframe}')
        bars = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=num_bars)

        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # TODO: complete  
        tf_to_mins = { '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440 }

        # obtain only closed frames (5min * 60 * 1000)
        if only_closed == True:
            df = df[df.timestamp < int(time.time() * 1000) - tf_to_mins[timeframe] * 60 * 1000]
    
        df['datetime']= pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index(pd.DatetimeIndex(df['datetime']), inplace=True)

        return df

    # this needs to be implemented in each of the exchange adapters
    def create_stop_loss_order_by_trigger_price(self, symbol, price, size, direction):
        pass

    # standard call to fetch open orders
    def fetch_open_orders(self, symbol):
        log_prefix = f"({self.class_name()}.fetch_open_orders) symbol {symbol}:"

        try:
            open_orders = self._exchange.fetch_open_orders(symbol) 

        except Exception as err:
            logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
            raise

        else:
            return open_orders
    
    #
    def fetch_my_trades(self, symbol, since=None):
        
        log_prefix = f"({self.class_name()}.fetch_my_trades) symbol {symbol}:"
        trades=[]

        if self._exchange.has['fetchMyTrades']:
            trades = self._exchange.fetch_my_trades(symbol=symbol, since=since, limit=None, params={})
            return trades

    #
    def fetch_orders(self, symbol, since=None):
        log_prefix = f"({self.class_name()}.fetch_orders) symbol {symbol}:"
        orders=[]

        if self._exchange.has['fetchOrders']:
            orders = self._exchange.fetch_orders(symbol=symbol, since=since, limit=None, params={})
            return orders
    
    #
    def fetch_order(self, symbol, order_id):
        log_prefix = f"({self.class_name()}.fetch_order) symbol {symbol}:"
        order=None

        if self._exchange.has['fetchOrder']:
            order = self._exchange.fetch_order(order_id, symbol)
            return order


    # creates the orders based on the dataframe order record of an OrderModel
    def create_order_based_on_model(self, order):
        log_prefix = f"({self.class_name()}.create_order_based_on_model):"
    
        dir = order['direction']
        symbol = order['symbol']
        order_response = None

        if order['exchange_id'] == self._exchange.id:

            if order['type'] == 'limit':

                size = order['size']
                limit = order['price']

                logging.info(f'{log_prefix} Limit order of size {size} at {limit} for {symbol}')

                try:
                    if dir == 'sell':
                        order_response = self._exchange.create_limit_sell_order(symbol, size, limit, self._trade_params)

                    if dir == 'buy':
                        order_response = self._exchange.create_limit_buy_order(symbol, size, limit, self._trade_params)

                except Exception as e:
                    logging.exception(log_prefix, Exception(e))

                else:
                    return str(order_response['id'])
                
            if order['type'] == 'stop':

                stop_price = order['price']
                stop_size  = order['pos_size']
                                            
                logging.info(f'{log_prefix} Create stop {dir} order of size {stop_size} at {stop_price} for {symbol}')
                
                try:
                    order_response = self.create_stop_loss_order_by_trigger_price(symbol, stop_price, stop_size, dir)

                except Exception as e:
                    logging.exception(log_prefix, Exception(e))
                
                else:
                    return str(order_response['id'])
        
        return None

    # cancel orders based on the dataframe record of an OrderModel 
    def cancel_order_based_on_model(self, order):
        log_prefix = f"({self.class_name()}.cancel_order_based_on_model):"
        
        symbol = order['symbol']
        order_id = order['order_id']
        dir = order['direction']
        type = order['type']

        if order['exchange_id'] == self._exchange.id:
            logging.info(f'{log_prefix} Cancel {dir} {type} order of {symbol} with order_id {order_id}')
            try:
                self._exchange.cancel_order(order_id, symbol)

            except Exception as e:
                logging.exception(log_prefix, Exception(e))
    
