import logging
import hmac
import base64
import time
import requests
import json

import ccxt

from .exchange_adapter import ExchangeAdapter        

class BitgetAdapter(ExchangeAdapter):

    def __init__(self, connect_params, exchange_params):
        exchange = ccxt.bitget(connect_params)
        super().__init__(exchange, exchange_params)

        # current defaults
        self._maker_fees = 0.00017
        self._taker_fees = 0.00051
        self._openpos_size_field = 'contractSize'
        self._trade_params = { 'timeInForce': 'post_only', 'post_only': True }
        self._trade_params_kill = { 'timeInForce': 'post_only', 'post_only': True, 'reduceOnly': True }

        # for low level api access 
        self._api_endpoint = 'https://api.bitget.com'
        self._api_key = connect_params['apiKey']
        self._api_secret = connect_params['secret']
        self._api_password = connect_params['password']

    ### some low level functions to obtain plan orders directly from the api

    def sign(self, message: str, secret_key: str) -> str:
        mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return base64.b64encode(d)

    def pre_hash(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        return str(timestamp) + str.upper(method) + request_path + body

    def bitget_fetch_open_stoploss_orders(self, symbol: str) -> list:

        symbol_id = self._markets[symbol]['id']
        
        method = '/api/mix/v1/plan/currentPlan'
        get_params = f'?symbol={symbol_id}&isPlan=profit_loss'
        timestamp = str(int(time.time_ns() / 1000000))

        signStr = self.sign(self.pre_hash(timestamp, 'GET', method, get_params), self._api_secret)
        headers = {
            'ACCESS-KEY': self._api_key,
            'ACCESS-SIGN': signStr,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self._api_password,
            'locale': 'en-US',
            'Content-Type': 'application/json'
        }
        
        orders = []
        try:
            r = requests.get(f"{self._api_endpoint}{method}{get_params}", headers=headers)

            if r.status_code != 200:
                raise Exception(f'(bitget_fetch_open_stoploss_orders) Could not fetch open_stoploss_orders - HTTP status code: {r.status_code}: Response: {r.text}')

        except Exception as e:

            logging.exception ('(bitget_fetch_open_stoploss_orders) ERROR:', Exception(e))
            return None

        else:
            
            response_dict = json.loads(r.text)
            order_list = response_dict['data']

            if response_dict['msg'] == 'success':

                for o in order_list:

                    if o['planType'] == 'pos_loss':
                        order = {}

                        order['symbol'] = symbol
                        order['info'] = o

                        order['id'] = o['orderId']
                        order['amount'] = float(o['size'])
                        order['stopPrice'] = float(o['triggerPrice'])
                        order['timestamp'] = int(o['cTime'])

                        # market oder Stop?
                        # order['type'] = o['orderType']
                        order['type'] = 'Stop'
                        order['price'] = None
                        order['side'] = None

                        if o['status'] == 'not_trigger':
                            order['filled'] = 0
                            order['remaining'] = order['amount']
                        else:
                            order['filled'] = None
                            order['remaining'] = None

                        if o['side'] == 'close_short':
                            order['side'] = 'buy'
                        if o['side'] == 'close_long':
                            order['side'] = 'sell'
                        
                        orders.append(order)
            else:
                raise Exception(f"(bitget_fetch_open_sltp_orders) Could not fetch open_stoploss_orders - API message: {response_dict['msg']}")


            # pp.pprint(orders)
            return orders

    ### low level functions end

    def get_contract_size(self, symbol):
        return self._markets[symbol]['contractSize'] / float(self._markets[symbol]['info']['sizeMultiplier'])

    def set_leverage_for_symbol(self, symbol, leverage):
        log_prefix = f"({self.class_name()}.set_leverage_for_symbol) symbol {symbol}:"

        maxLeverage = leverage
        initialMargin = 1 / maxLeverage
  
        # set margin and margin mode to cross
        try:
            logging.info(f'{log_prefix} Initial margin requirement {initialMargin:.2%} -> max leverage {maxLeverage}')
            logging.info(f'{log_prefix} Setting leverage mode to crossed')
            marginModeResponse = self._exchange.set_margin_mode('crossed', symbol)
            leverageResponse = self._exchange.set_leverage(maxLeverage, symbol)
        except Exception as e:
            logging.exception(log_prefix, e)
            raise e

        return maxLeverage

    def cancel_all_orders(self, symbol):
        log_prefix = f"({self.class_name()}.cancel_all_orders) symbol {symbol}:"

        self._exchange.cancel_all_orders(symbol, params=self._exchange_params)

        margincoin = self._exchange_params['code']
        
        logging.info(f'{log_prefix} Cancelling bitget loss plan orders ...')

        bg_open_sl = self.bitget_fetch_open_stoploss_orders(symbol)
        params = { 'stop': True, 'code': margincoin, 'planType': 'loss_plan' }
        for o in bg_open_sl:
            logging.info(f"{log_prefix} Cancelling bitget loss plan order id {o['id']}")
            self._exchange.cancel_order(o['id'], symbol, params)

    def fetch_open_orders(self, symbol):
        log_prefix = f"({self.class_name()}.fetch_open_orders) symbol {symbol}:"
        
        # call the super class
        open_orders = super().fetch_open_orders(symbol)

        try:
            open_orders += self._exchange.fetch_open_orders(symbol, params={'stop': True})
            open_orders += self.bitget_fetch_open_stoploss_orders(symbol)
        except Exception as err:
            logging.exception(f"{log_prefix} Unexpected {err=}, {type(err)=}")
            raise err
        else:
            return open_orders

    def create_stop_loss_order_by_trigger_price(self, symbol, price, size, direction):
        log_prefix = f"({self.class_name()}.create_stop_loss_order_by_trigger_price) symbol {symbol}:"

        symbol_id = self._markets[symbol]['id']

        sl_params = {
            'symbol': symbol_id,
            'triggerType': 'fill_price', # bitget
            'planType': 'pos_loss', # bitget
            # 'triggerPrice': price,  # your stop loss price - bitget
            'reduceOnly': True, # bitget
            'stopLossPrice': price # try with stopLossPrice
        }

        [ ask, bid ] = self.ask_bid(symbol)

        if direction == 'sell':

            if (price < ask):
                # -- bitget plan logic: makes a stopLoss for existing buy_order
                order = self._exchange.create_order(symbol, 'market', 'buy', size, price, sl_params) 
                logging.info(f'{log_prefix} Just made a SELL STOP LOSS order of {size} {symbol} at trigger price {price:.2f}: ')
                return order
            else:
                raise Exception(f'{log_prefix} Trigger price {price} above {ask} - no order placed - would trigger immediately')

        elif direction == 'buy':

            if (price > bid):
                # -- bitget plan logic: makes a stopLoss for existing sell_orders 
                order = self._exchange.create_order(symbol, 'market', 'sell', size, price, sl_params)   
                logging.info(f'{log_prefix} Just made a BUY STOP LOSS order of {size} {symbol} at trigger price {price:.2f}: ')
                return order
            else:
                raise Exception(f'{log_prefix} Trigger price {price} below {bid} - no order placed - would trigger immediately')
    
        else:
            raise ValueError(f'{log_prefix} +++ Parameter direction must be either sell or buy +++')       

    # cancel orders based on the dataframe record of an OrderModel 
    def cancel_order_based_on_model(self, order):
        log_prefix = f"({self.class_name()}.cancel_order_based_on_model):"

        margincoin = self._exchange_params['code']

        symbol = order['symbol']
        order_id = order['order_id']
        dir = order['direction']
        type = order['type']

        if order['exchange_id'] == self._exchange.id:
            logging.info(f'{log_prefix} Cancel {dir} {type} order of {symbol} with order_id {order_id}')
            try:

                if type == 'stop':
                        params = { 'stop': True, 'code': margincoin, 'planType': 'loss_plan' }        
                        logging.info(f'{log_prefix} Cancelling bitget loss plan order id {order_id}')
                        self._exchange.cancel_order(order_id, symbol, params)
                else:
                    self._exchange.cancel_order(order_id, symbol)

            except Exception as e:
                logging.exception(log_prefix, Exception(e))
                raise e
