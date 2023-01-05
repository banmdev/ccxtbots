import logging
import pandas as pd
import numpy as np
from hashlib import sha512
import os
from dotenv import load_dotenv

from .order_model import OrderModel

load_dotenv()
DCAORDERMODEL_DATADIR=os.getenv('DCAORDERMODEL_DATADIR', 'data_dir')

class DCAOrderModel(OrderModel):

    # internal representation of the model as a dataframe 
    
    def __init__(self, exchange_adapter, symbol, direction, num_trades, price_dev, save_scale, base_to_save_mult = 1.0) -> None:

        super().__init__(exchange_adapter, symbol, direction)

        self.model_df = None

        if num_trades < 3:
            raise ValueError(f'({self.class_name()}.__init__) Number of trades {num_trades} to small, must be at least 3')

        if not isinstance(price_dev, float):
            raise TypeError(f"({self.class_name()}.__init__) Argument price_dev must be of type float, not {type(price_dev)}")

        if not isinstance(base_to_save_mult, float):
            raise TypeError(f"({self.class_name()}.__init__) Argument base_to_save_mult must be of type float, not {type(base_to_save_mult)}")

        if not isinstance(save_scale, float):
            raise TypeError(f"({self.class_name()}.__init__) Argument save_scale must be of type float, not {type(save_scale)}")

        if not isinstance(num_trades, int):
            raise TypeError(f"({self.class_name()}.__init__) Argument num_trades must be of type int, not {type(num_trades)}")

        self.price_dev = price_dev
        self.num_trades = num_trades
        self.base_to_save_mult = base_to_save_mult
        self.save_scale = save_scale

        # safe the dataframe of the model in a csv file
        self.file_prefix = 'bids_' if self.direction == 'long' else 'asks_'
        self.file_save_name = None
        self.file_path = DCAORDERMODEL_DATADIR
        os.makedirs(self.file_path, exist_ok=True)
        
        [ self.delta_factor, self.size_divisor, self.base_df ] = self._dca_model_coefficients(init=True)


    # print params
    def print_param_summary(self):

        print(f'direction         = {self.direction}')
        print(f'price_dev         = {self.price_dev:.2%}')
        print(f'num_trades        = {self.num_trades}')
        print(f'base_to_save_mult = {self.base_to_save_mult}')
        print(f'save_scale        = {self.save_scale}')
        print(f'contract_size     = {self.ea.get_contract_size(self.symbol)}')
        print(f'maker_fees        = {self.ea.maker_fees:.2%}')
        print(f'taker_fees        = {self.ea.taker_fees:.2%}')

        if self.symbol is not None:
            print(f'symbol            = {self.symbol}')

        if self.ea is not None:
            print(f'exchange          = {self.ea.id}')

        print(f'delta_factor      = {self.delta_factor}')
        print(f'size_divisor      = {self.size_divisor}')
        
        print("=== My base dataframe ===")
        print(self.base_df)

    # calc asset price after given number of periods with deviation set and based on direction
    def _dca_price_after_periods(self, period, asset_price=1, init=False):

        if not isinstance(asset_price, float) and not isinstance(asset_price, int):
            raise TypeError(f"({self.class_name()}._dca_price_after_periods) Argument asset_price must be of type int or float, not {type(asset_price)}")

        if not isinstance(period, int):
            raise TypeError(f"({self.class_name()}._dca_price_after_periods) Argument period must be of type int, not {type(period)}")
        
        if self.direction == 'long':
            o_price = asset_price * (1 - self.price_dev) ** period
        elif self.direction == 'short':
            o_price = asset_price * (1 + self.price_dev) ** period
        
        # not loosely coupled any more
        if (init != True):
            logging.debug(f'({self.class_name()}._dca_price_after_periods) Symbol {self.symbol} Calc price with exchange precision')
            o_price = self.ea.price_to_precision(self.symbol, o_price)
        
        logging.debug(f'({self.class_name()}._dca_price_after_periods) start price {asset_price} o_price: {o_price} after periods: {period}')

        return float(o_price)

    # internal function calc dca_model_coefficents to scale the 
    # actual base dca order to the proper size
    def _dca_model_coefficients(self, base_size=1, asset_price=1, init=False):

        if not isinstance(base_size, float) and not isinstance(base_size, int):
            raise TypeError(f"({self.class_name()}._dca_model_coefficients) Argument base_size must be of type int or float, not {type(base_size)}")

        if not isinstance(asset_price, float) and not isinstance(asset_price, int):
            raise TypeError(f"({self.class_name()}._dca_model_coefficients) Argument asset_price must be of type int or float, not {type(asset_price)}")

        # if base_size < 1:
        #    raise ValueError(f'DCAOrderModel (_dca_model_coefficients) Invalid base size {base_size}, must be 1 or more')

        # base_size = base_size                          # * self.contract_size
        save_size = base_size * self.base_to_save_mult # * self.contract_size

        pos_size = 0
        pos_vol = 0
        o_size = 0
        o_prices = []
        o_volumes = []
        o_sizes = []
        o_pos_sizes = []
        o_pos_volumes = []
        o_dirs = []
        o_types = []
        o_idxs = []

        if self.direction == 'long':
            o_dir = 'buy'
        else:
            o_dir = 'sell'

        o_type = 'limit'

        for o_num in range(0, self.num_trades):

            o_price = self._dca_price_after_periods(period=o_num, asset_price=asset_price, init=init)

            # base order
            if o_num == 0:
                o_size = base_size

            # first save order
            if o_num == 1:
                o_size = save_size

            # next save orders
            if o_num > 1 and o_num < (self.num_trades - 1):
                o_size = o_size * self.save_scale    

            # last order is stop loss, no new order
            if o_num == self.num_trades - 1:
                o_size = 0
                o_type = 'stop'
                if self.direction == 'long':
                    o_dir = 'sell'
                else:
                    o_dir = 'buy'

            o_vol = o_size * o_price * self.ea.get_contract_size(self.symbol)
            pos_size += o_size
            pos_vol += o_vol
            o_idxs.append(o_num)
            o_prices.append(o_price)
            o_sizes.append(o_size)
            o_volumes.append(o_vol)
            o_pos_sizes.append(pos_size)
            o_pos_volumes.append(pos_vol)
            o_dirs.append(o_dir)
            o_types.append(o_type)

        avg_entry = np.dot(o_prices, o_sizes) / pos_size
        delta = avg_entry / o_price
        logging.debug(f'{self.class_name()}._dca_base_size) symbol {self.symbol} Model coefficents: Average entry price: {avg_entry} pos_size: {pos_size} last price: {o_price} delta: {delta}')
        d = { 'idx': o_idxs, 'type': o_types, 'direction': o_dirs, 'price': o_prices, 'size': o_sizes, 'pos_size': o_pos_sizes, 'o_vol': o_volumes, 'open_volume': o_pos_volumes}
        df = pd.DataFrame(data=d)
        df.set_index('idx', inplace=True)

        return delta, pos_size, df

    # internal function to calc the risk oriented base size in number of contracts of an dca trade based on risk_per_trade
    # based on the delta between the the current asset_price and the stop loss price
    def _dca_base_size(self, asset_price, risk_per_trade):

        if not isinstance(risk_per_trade, float):
            raise TypeError(f"({self.class_name()}._dca_base_size) Argument risk_per_trade must be of type float, not {type(risk_per_trade)}")

        if not isinstance(asset_price, float) and not isinstance(asset_price, int):
            raise TypeError(f"({self.class_name()}._dca_model_coefficients) Argument asset_price must be of type int or float, not {type(asset_price)}")

        periods = self.num_trades - 1
        sl_price = self._dca_price_after_periods(period=periods, asset_price=asset_price)
        avg_entry_price = sl_price * self.delta_factor

        delta = abs(avg_entry_price - sl_price)
        if delta > 0:
            
            asset_last_size = (risk_per_trade / delta) 
            asset_base_size = float(asset_last_size / self.size_divisor / self.ea.get_contract_size(self.symbol))

            logging.debug(f'({self.class_name()}._dca_base_size) Symbol {self.symbol} sl_price: {sl_price} avg_entry_price: {avg_entry_price} delta: {delta} asset_base_size: {asset_base_size}')

            return asset_base_size
        else:
            raise ZeroDivisionError(f'({self.class_name()}._dca_base_size) Delta between sl_price and avg_entry_price is Zero(0)')

    # Documentation: 
    #  build dca model based on given asset_price, risk per trade and desired crv
    #  fees are calulated afterwards, so realized crv is a bit lower
    #  added min_roe to calc minimum take profit target and min_roe_trigger_distance on top of min_roe take profit 
    #   ... based on delta between entry_price and tp_price_min_roe
    def build_order_model(self, asset_price, risk_per_trade, crv, leverage=25, min_roe=0.05, min_roe_trigger_distance=0.75):
        
        base_size = self._dca_base_size(asset_price=asset_price, risk_per_trade=risk_per_trade)
        base_size = float(self.ea.amount_to_precision(self.symbol, base_size))

        # run model with actual base_size and asset_price data
        [ delta_factor, size_divisor, order_df ] = self._dca_model_coefficients(base_size=base_size, asset_price=asset_price)

        order_df['symbol'] = self.symbol
        order_df['exchange_id'] = self.ea.id
        order_df['maker_fees'] = order_df['open_volume'] * self.ea.maker_fees
        order_df['entry_price'] = order_df['open_volume'] / order_df['pos_size'] / self.ea.get_contract_size(self.symbol)
        order_df['close_volume'] = order_df['price'] * order_df['pos_size'] * self.ea.get_contract_size(self.symbol)

        order_df.loc[(
                ( order_df['type'] == 'stop' ) 
            ),
            'taker_fees'
        ] = order_df['close_volume'] * self.ea.taker_fees

        if self.direction == 'long':
            order_df['u_pnl'] = order_df['close_volume'] - order_df['open_volume'] - order_df['maker_fees']
            # crv based calc
            order_df['tp_volume'] = order_df['open_volume'] + abs(order_df['u_pnl'].shift(-1) * crv)
            order_df['tp_maker_fees'] = order_df['tp_volume'] * self.ea.maker_fees
            order_df['r_pnl'] = ( order_df['tp_volume'] - order_df['open_volume'] ) - ( order_df['maker_fees'] + order_df['tp_maker_fees'] )

            order_df['tp_price_min_roe'] = order_df['entry_price'] * (1 + min_roe/leverage + self.ea.maker_fees)
            order_df['tp_price_min_trigger'] = order_df['tp_price_min_roe'] + ( order_df['tp_price_min_roe'] - order_df['entry_price'] )

        elif self.direction == 'short':
            order_df['u_pnl'] = order_df['open_volume'] - order_df['close_volume'] - order_df['maker_fees']
            # crv based calc
            order_df['tp_volume'] = order_df['open_volume'] - abs(order_df['u_pnl'].shift(-1) * crv)
            order_df['tp_maker_fees'] = order_df['tp_volume'] * self.ea.maker_fees
            order_df['r_pnl'] = ( order_df['open_volume'] - order_df['tp_volume'] ) - ( order_df['maker_fees'] + order_df['tp_maker_fees'] ) * min_roe_trigger_distance

            order_df['tp_price_min_roe'] = order_df['entry_price'] * (1 - min_roe/leverage - self.ea.maker_fees)
            order_df['tp_price_min_trigger'] = order_df['tp_price_min_roe'] - ( order_df['entry_price'] - order_df['tp_price_min_roe'] ) * min_roe_trigger_distance
        else:
            raise ValueError(f'({self.class_name()}.build_dca_order_model) Invalid trade direction {self.direction}, must be either long or short')
        
        order_df.loc[(
                ( order_df['type'] == 'stop' ) 
            ),
            'r_pnl'
        ] = order_df['u_pnl'] - order_df['taker_fees']

        order_df['tp_price'] = order_df['tp_volume'] / order_df['pos_size'] / self.ea.get_contract_size(self.symbol)
        order_df['crv'] = order_df['r_pnl'] / abs(order_df['u_pnl'].shift(-1))
        order_df['roi'] = order_df['r_pnl'] / order_df['open_volume']
        order_df['roe'] = order_df['roi'] * leverage

        # some styling
        # order_df.style.format({'roi': "{:.2%}",'roe': "{:.2%}")

        if (self.ea is not None and self.symbol is not None):
            
            for price_col in [ 'tp_price', 'tp_price_min_roe', 'tp_price_min_trigger' ]:
                order_df[price_col]= pd.Series([float(self._get_exchange_price_to_precision_or_nan(val)) for val in order_df[price_col]], index = order_df.index)
            
        # save the model in class
        self.model_df = order_df

        # return order_df

    # convert prices in a given dataframe with exchange precisions
    def _get_exchange_price_to_precision_or_nan(self, val):

        if (self.ea is not None and self.symbol is not None):
            if val > 0:
                return float(self.ea.price_to_precision(self.symbol, val))
            else:
                return np.nan
        else:
            raise ValueError(f'({self.class_name()}.get_exchange_price_to_precision_or_nan) Exchange and Symbol cannot be None')

    # distance between first and last price of the model
    def get_max_drawdown(self):

        first_price = self.model_df['price'].iloc[0]
        last_price = self.model_df['price'].iloc[-1]
        return abs(first_price - last_price) / first_price

    # return stop loss price and size based on the input vars
    # in the DCA model query the model and ignore the inputs
    def get_sl_price_size(self, input_size: float = None, input_price: float = None):

        limit_sl = self.model_df['price'].loc[ ( self.model_df['type'] == 'stop' ) ].values[0]
        limit_sl = float(self.ea.price_to_precision(self.symbol, limit_sl))
        size_sl =  self.model_df['pos_size'].loc[ (  self.model_df['type'] == 'stop' ) ].values[0]

        return limit_sl, size_sl

    # return take profit price and size based on the input vars
    # in the DCA model query the model based on position size and ignore the inputs_price
    def get_tp_price_size(self, input_size: float, input_price: float = None):
        size_tp = input_size
        limit_tp = self.model_df['tp_price'].loc[ ( ( self.model_df['pos_size'] >= size_tp ) & ( self.model_df['type'] == 'limit' ) ) ].values[0]
        limit_tp = float(self.ea.price_to_precision(self.symbol, limit_tp))

        return limit_tp, size_tp

    # the identifier is the order id of the longest lasting order in the df - price with the highest distance
    def get_identifier(self):
        
        if 'order_id' in self.model_df.columns:
            return str(self.model_df['order_id'].iloc[-1])
        else:
            raise Exception('Cannot get last order id as identifier, data frame ready to store?')
    
    # return last matching tp order id for a given size 
    def get_latest_tp_order_id_by_size(self, size: float) -> str:
        o_id = None
        if 'tp_order_id' in self.model_df.columns:
            o_id = self.model_df['tp_order_id'].loc[ ( ( self.model_df['pos_size'] >= size ) & ( self.model_df['type'] == 'limit' ) ) ].values[0]
        return o_id 

    # update the tp order id by using a price
    def update_tp_order_id_by_price(self, price: float, new_id: str):

        self.model_df.loc[ ( self.model_df['tp_price'] == price), 'tp_order_id' ] = new_id
        self.store_df()

    # update the sl order id by using a price
    def update_sl_order_id_by_price(self, price: float, new_id: str):
        
        self.model_df.loc[ ( self.model_df['price'] == price), 'order_id' ] = new_id
        self.store_df()

    # the following four functions manage the persistence of the specific data frame for this model:
    # 1. create a unique file name hash
    def _file_name_hash(self, identifier):

        file_name_with_id = self.exchange_symbol_str + "_" + identifier
        file_hash = sha512(file_name_with_id.encode('utf-8')).hexdigest()
        return file_hash

    # 2. remove old files from previous trades
    def remove_df_file(self):
        
        if self.file_save_name and os.path.exists(self.file_path + "/" + self.file_save_name):
            logging.debug(f'({self.class_name()}.remove_df_file) symbol {self.symbol} Removing df file: {self.file_save_name}')
            os.remove(self.file_path + "/" + self.file_save_name)

    # 3. store a dataframe with an order model to a csv file
    def store_df(self, identifier=None):

        identifier = self.get_identifier()

        file_hash = self._file_name_hash(identifier)
        self.file_save_name = self.file_prefix + file_hash + ".csv"
        logging.info(f'({self.class_name()}.store_df) symbol {self.symbol} Saving orders df to {self.file_save_name}')
        try:
            self.model_df.to_csv(self.file_path + "/" + self.file_save_name)
        except Exception as err:
            logging.exception(f"({self.class_name()}.store_df) symbol {self.symbol} Unexpected {err}, {type(err)}")
            raise Exception(err)

    # 4. restore a dataframe with an order model from a csv file
    def restore_df(self, identifier):

        file_hash = self._file_name_hash(identifier)
        self.file_save_name = self.file_prefix + file_hash + ".csv"

        if os.path.exists(self.file_path + "/" + self.file_save_name):
            logging.info(f'({self.class_name()}.restore_df) symbol {self.symbol}: Trying to restore last matching order model from {self.file_save_name} ...')
            self.model_df = pd.read_csv(self.file_path + "/" + self.file_save_name)
            self.model_df.set_index('idx', inplace=True)
            print (self.model_df)
        else:
            logging.exception(f'({self.class_name()}.restore_df) symbol {self.symbol}: No valid file for last orders found {self.file_save_name} ...')
            raise Exception(f'({self.class_name()}.restore_df) symbol {self.symbol}: No valid file for last orders found {self.file_save_name} ...') 


