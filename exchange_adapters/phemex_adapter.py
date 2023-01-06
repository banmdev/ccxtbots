import logging

import ccxt

from .exchange_adapter import ExchangeAdapter

class PhemexAdapter(ExchangeAdapter):

    def __init__(self, connect_params, exchange_params):
        exchange = ccxt.phemex(connect_params)
        super().__init__(exchange, exchange_params)

        # current defaults
        self._maker_fees = 0.0001
        self._taker_fees = 0.0006
        self._openpos_size_field = 'contracts'
        self._trade_params = { 'timeInForce': 'PostOnly' }

    def get_contract_size(self, symbol: str):
        return self._markets[symbol]['contractSize']

    def set_leverage_for_symbol(self, symbol, leverage):
        log_prefix = f"({self.class_name()}.set_leverage_for_symbol) symbol {symbol}:"

        initialMargin = self._markets[symbol]['info']['riskLimits'][0]['initialMargin']
        initialMargin = float(initialMargin.replace('%', '')) / 100
        maxLeverage = 1 / initialMargin
  
        # set margin and margin mode to cross
        try:
            logging.info(f'{log_prefix} Initial margin requirement {initialMargin:.2%} -> max leverage {maxLeverage}')
            logging.info(f'{log_prefix} Setting leverage mode to cross')
            leverageResponse  = self._exchange.set_margin_mode('cross', symbol)
        except Exception as e:
            logging.exception(log_prefix, e)
            raise e

        return maxLeverage

    def cancel_all_orders(self, symbol):

        self._exchange.cancel_all_orders(symbol, params=self._exchange_params)

        margincoin = self._exchange_params['code']
        
        params = { 'untriggered': True, 'code': margincoin }
        self._exchange.cancel_all_orders(symbol, params)

    def create_stop_loss_order_by_trigger_price(self, symbol, price, size, direction):
        log_prefix=f"({self.class_name()}.create_stop_loss_order_by_trigger_price) symbol {symbol}:"
        
        symbol_id = self._markets[symbol]['id']

        trigger_price_phe = int(round(price * 10000)) # hope this works with int ...
        sl_params = {
            'symbol': symbol_id, # resolved symbol_id 
            'ordType': 'Stop',   # phemex
            'triggerType': 'ByLastPrice', # phemex
            'stopPxEp': trigger_price_phe,  
        } 

        [ ask, bid ] = self.ask_bid(symbol)

        if direction == 'sell':

            if (price < ask):
                order = self._exchange.create_order(symbol, 'market', 'sell', size, price, sl_params) 
                logging.info(f'{log_prefix} Just made a SELL STOP LOSS order of {size} {symbol} at trigger price {price:.4f} phemex={trigger_price_phe}')
                return order
            else:
                logging.exception(f'{log_prefix} Trigger price {price} above {ask} - no order placed - would trigger immediately')
                raise Exception(f'{log_prefix} Trigger price {price} above {ask} - no order placed - would trigger immediately')

        elif direction == 'buy':

            if (price > bid):
                order = self._exchange.create_order(symbol, 'market', 'buy', size, price, sl_params)   
                logging.info(f'{log_prefix} Just made a BUY STOP LOSS order of {size} {symbol} at trigger price {price:.4f} phemex={trigger_price_phe}')
                return order
            else:
                logging.exception(f'{log_prefix} Trigger price {price} below {bid} - no order placed - would trigger immediately')
                raise Exception(f'{log_prefix} Trigger price {price} below {bid} - no order placed - would trigger immediately')
    
        else:
            raise ValueError(f'{log_prefix} +++ Parameter direction must be either sell or buy +++')   