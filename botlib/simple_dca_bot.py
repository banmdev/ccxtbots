import logging
import time

from .basebot import BaseBot
from order_models import DCAOrderModel
from exchange_adapters import ExchangeAdapter
from signal_generators import ExtendedSignalGenerator

# import pprint
# pp = pprint.PrettyPrinter(indent=4)

class SimpleDCABot(BaseBot):

    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, signal_generator: ExtendedSignalGenerator, 
                 long_model: DCAOrderModel, short_model: DCAOrderModel, ticks: int = 1, refresh_timeout: int = 120,
                 not_trading: bool = False) -> None:

        self._dca_model_long  = long_model
        self._dca_model_short = short_model

        # used in the prepration handler
        self._leverage = 50            # default leverage - TODO: always try to obtain from exchange for a symbol

        # used in the noposition handler - could potentially be changed between trades
        self._max_account_risk_per_trade = 0.01 # 1% very small default


        self._crv=0.525                # chance/risk value
        self._min_roe = 0.01           # minimum roe 1%
        
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

    @property
    def crv(self):
        return self._crv

    @crv.setter
    def crv(self, value):
        self._crv = value
        
    @property
    def min_roe(self):
        return self._min_roe

    @min_roe.setter
    def min_roe(self, value):
        self._min_roe = value

    def housekeeping_handler(self):

        # the parent class takes care for stop loss and take profit orders
        super().housekeeping_handler()

        log_prefix = f"({self.class_name()}.housekeeping) symbol {self.symbol}:"

        logging.info(f'{log_prefix} Cancel current DCA Orders ... ')
        try:
            # cancel all orders first - only existing from the bot ...
            if self._dca_model_long.model_df is not None:
                self.cancel_orders_based_on_model(self._dca_model_long.model_df)

            if self._dca_model_short.model_df is not None:
                self.cancel_orders_based_on_model(self._dca_model_short.model_df)
                        
        except Exception as e:
            logging.exception(f'{log_prefix} WARN: Could not cancel existing DCA orders')
        else:
            logging.info(f'{log_prefix} Success Current DCA Orders canceled... ')
            self._dca_model_long.remove_df_file()
            self._dca_model_short.remove_df_file()
            self._dca_model_long.model_df = None
            self._dca_model_short.model_df = None

    def create_orders_based_on_model(self, df):

        for index, order in df.iterrows():

            order_id = self._ea.create_order_based_on_model(order)
            if order_id is not None:
                df.loc[index,'order_id'] = order_id

    def cancel_orders_based_on_model(self, df):

        for index, o in df.iterrows():
            # do we have a matching open order?
            if self.matching_order_by_id(o['order_id'], o['type'], o['direction']):
                self._ea.cancel_order_based_on_model(o)

    def preparation_handler(self):
        log_prefix=f"({self.class_name()}.preparation_handler) symbol {self.symbol}:"

        logging.debug(f'{log_prefix} Prepare to run the main loop')
        self.leverage = self._ea.set_leverage_for_symbol(self.symbol, 50)
        logging.info(f'{log_prefix} Leverage is now {self.leverage}')

    def inposition_handler(self):
        log_prefix = f"({self.class_name()}.inposition_handler) symbol {self.symbol}:"
        
        logging.debug(f'{log_prefix} I am in a position (1): current_size: {self._current_size}, long: {self._current_long}, entryPrice: {self._entryPrice}, leverage {self._position_leverage}')
        logging.debug(f'{log_prefix} I am in a position (2): last_tp_order_id: {self._last_tp_order_id}, last_sl_order_id: {self._last_sl_order_id}')

        # TODO - Find order with the longest delta (max aks, min bid) and use this order as id
        # TODO - Dont query the _open_sl_orders_[long|short] lists directly
        sl_order_bid = self._open_sl_orders_long[0] if len(self._open_sl_orders_long) > 0 else None
        sl_order_ask = self._open_sl_orders_short[0] if len(self._open_sl_orders_short) > 0 else None
        was_restored = False

        # RESTORE
        # trying to restore last long and short models in case of a restart
        if self._dca_model_long.model_df is None:
            if sl_order_bid is not None:
                o_id = sl_order_bid['id']
                logging.info(f'{log_prefix} Have an open sl_order_bid {o_id} ... restoring df ...')
                self._dca_model_long.restore_df(o_id)
                was_restored = True
        else:
            logging.debug(f'{log_prefix} Have an existing long model from previous run...')

        if self._dca_model_short.model_df is None:
            if sl_order_ask is not None:
                o_id = sl_order_ask['id']
                logging.info(f'{log_prefix} Have an open sl_order_ask {o_id} ... restoring df ...')
                self._dca_model_short.restore_df(o_id)
                was_restored = True
        else:
            logging.debug(f'{log_prefix} Have an existing short model from previous run...')

        # CLEAN UP OPPOSITE ORDERS
        # point to the right model and clean up the opposite side, this is not a grid bot
        if self._current_long == True:

            long_short = 'long'
            model = self._dca_model_long

            # clean up the short side if needed
            if self._dca_model_short.model_df is not None:
                logging.info(f'{log_prefix} I entered a long position ... cleaning up opposite sell orders ...')
                self.cancel_orders_based_on_model(self._dca_model_short.model_df)
                sl_order_ask = None
                self._dca_model_short.model_df = None

        elif self._current_long == False:

            long_short = 'short'
            model = self._dca_model_short

            # clean up the long side if needed
            if self._dca_model_long.model_df is not None:
                logging.info(f'{log_prefix} I entered a short position ... cleaning up opposite buy orders ...')
                self.cancel_orders_based_on_model(self._dca_model_long.model_df)
                sl_order_bid = None
                self._dca_model_long.model_df = None
        else:
            logging.warning(f'{log_prefix} WARN 1: SOMETHING WRONG IN MMR FUNCTION +++')
            raise

        # ONLY OVERRIDE IF THE MODEL WAS RESTORED FROM FILE
        if was_restored:
            self.last_sl_order_id = model.get_identifier()
            self.last_tp_order_id = model.get_latest_tp_order_id_by_size(self._current_size)      

        # MAINTAIN THE STOP LOSS
        limit_sl, size_sl = model.get_sl_price_size()
        last_sl_id = self.last_sl_order_id
        sl_order = self.maintain_sl_order(limit_sl, size_sl)

        # MAINTAIN THE TAKE PROFIT
        limit_tp, size_tp = model.get_tp_price_size(self._current_size)
        last_tp_id = self.last_tp_order_id
        tp_order = self.maintain_tp_order(limit_tp, size_tp)

        # UPDATE THE MODEL
        # Save tp_order_id and sl_order_id in the respective model 
        if last_tp_id != tp_order['id']:
            model.update_tp_order_id_by_price(limit_tp, tp_order['id'])
        
        if last_sl_id != sl_order['id']:
            model.update_sl_order_id_by_price(limit_sl, sl_order['id'])

        # PRINT INFO
        if self._current_size != self._last_position_size:
            logging.info(f'{log_prefix} I am in a {long_short} position at {self._entryPrice} with size {self._current_size}, take profit at {limit_tp} and stop loss at {limit_sl}')
    

    def finishtrade_handler(self):

        super().finishtrade_handler()

        log_prefix=f"({self.class_name()}.finishtrade_handler) symbol {self.symbol}:"

        r_pnl = 0
        chk_tp_order = None
        chk_sl_order = None

        try:
            if self.last_tp_order_id is not None: 
                chk_tp_order = self._ea.fetch_order(self.symbol, self.last_tp_order_id)
            if self.last_sl_order_id is not None:
                chk_sl_order = self._ea.fetch_order(self.symbol, self.last_sl_order_id)
        except Exception as err:
            logging.warning(f'{log_prefix} Cannot fetch order: {err} ...')    
        else:
            if chk_tp_order and chk_tp_order['status'] == 'closed':
                logging.info(f'{log_prefix}: TAKE PROFIT ORDER GOT EXECUTED :-) ...')
                if self._last_current_long == True:
                    df = self._dca_model_long.model_df
                    r_pnl = df['r_pnl'].loc[ (df['tp_order_id'] == self._last_tp_order_id) ].values[0]
                elif self._last_current_long == False:
                    df = self._dca_model_short.model_df
                    r_pnl = df['r_pnl'].loc[ (df['tp_order_id'] == self._last_tp_order_id) ].values[0]
                else:
                    logging.warning(f'{log_prefix}: Something wrong with {self._last_current_long} ...')

            elif chk_sl_order and chk_sl_order['status'] == 'closed':
                logging.info(f'{log_prefix}: STOP LOSS ORDER GOT EXECUTED :-( ...')
                if self._last_current_long == True:
                    df = self._dca_model_long.model_df
                    r_pnl = df['r_pnl'].loc[ (df['order_id'] == self._last_sl_order_id) ].values[0]
                elif self._last_current_long == False:
                    df = self._dca_model_short.model_df
                    r_pnl = df['r_pnl'].loc[ (df['order_id'] == self._last_sl_order_id) ].values[0]
                else:
                    logging.warning(f'{log_prefix}: Something wrong with {self._last_current_long} ...')
            else:
                logging.warning(f'{log_prefix}: Something else has happend ...')

            pl = "profit" if r_pnl > 0 else "loss"
            self._cum_pnl = self._cum_pnl + r_pnl
            logging.info(f'{log_prefix}: Potential {pl} of last trade {r_pnl}. Cumulative PNL while running the bot: {self._cum_pnl}')


    def enter_position_handler(self):
        
        log_prefix=f"({self.class_name()}.enter_position_handler) symbol {self.symbol}:"

        logging.info(f'{log_prefix} I am not in a position - waiting for entry signals and new order checks!')
 
        try:
            # check balance
            total_balance = self._ea.get_total_balance()
        except Exception as e:

            logging.exception(f'{log_prefix} ERROR: Could not check current balance')
            raise Exception(e)

        else:
            max_risk_per_trade = ( total_balance * self.max_account_risk_per_trade ) 
            logging.info(f'{log_prefix} symbol {self.symbol} Total account balance: {total_balance} Max risk per trade: {max_risk_per_trade}')

            try:
                
                # get bid, ask and mid
                [ask, bid] = self._ea.ask_bid(self.symbol)
                signal = self.signal(ask, bid)

            except Exception as e:
                logging.exception(f'{log_prefix} WARN: Could not get bid ask price or signal')
                return                
                
            # creating the ask bid orders considering the trend (from strategy)
            if 'sell' in signal:
                
                # sl, tp ignored in the DCA Model
                [ price, sl, tp ] = self.parse_signal(signal, 'sell', ask)

                self._dca_model_short.build_order_model(asset_price=price, 
                                                        risk_per_trade=max_risk_per_trade, 
                                                        crv=self.crv, 
                                                        leverage=self.leverage, 
                                                        min_roe=self.min_roe)
                
                if self._not_trading:
                    logging.info(f'{log_prefix} NOT TRADING: DCA Model Order Dataframe for asks (simulation):')
                    print(self._dca_model_short.model_df)
                else:
                    try:
                        self.create_orders_based_on_model(self._dca_model_short.model_df)
                    except:
                        logging.exception(f'{log_prefix} WARN: Could not create sell orders')
                    else:
                        print(f'{log_prefix} DCA Model Order Dataframe for asks (executed):')
                        print(self._dca_model_short.model_df)
                        self._dca_model_short.store_df()

            if 'buy' in signal:
                    
                # sl, tp ignored in the DCA Model
                [ price, sl, tp ] = self.parse_signal(signal, 'buy', bid)
                    
                self._dca_model_long.build_order_model(asset_price=price, 
                                                       risk_per_trade=max_risk_per_trade, 
                                                       crv=self.crv, 
                                                       leverage=self.leverage, 
                                                       min_roe=self.min_roe)

                if self._not_trading:
                    logging.info(f'{log_prefix} NOT TRADING: DCA Model Order Dataframe for bids (simulation):')
                    print(self._dca_model_long.model_df)
                else:
                    try:
                        self.create_orders_based_on_model(self._dca_model_long.model_df)
                    except:
                        logging.exception(f'{log_prefix} WARN: Could not create buy orders')
                    else:
                        print(f'{log_prefix} DCA Model Order Dataframe for bids (executed):')
                        print(self._dca_model_long.model_df)
                        self._dca_model_long.store_df()


