import logging
import time

from .basebot import BaseBot
from order_models import DCAOrderModel
from exchange_adapters import ExchangeAdapter
from signal_generators import SimpleMMSignalGenerator

class MarketMakerBot(BaseBot):

    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, signal_generator: SimpleMMSignalGenerator, 
                 long_model: DCAOrderModel, short_model: DCAOrderModel, ticks: int = 1, refresh_timeout: int = 120):

        self._dca_model_long  = long_model
        self._dca_model_short = short_model
        self._signal_generator = signal_generator

        # used in the prepration handler
        self._leverage = 50            # default leverage - TODO: always try to obtain from exchange for a symbol

        # used in the noposition handler - could potentially be changed between trades
        self._max_account_risk_per_trade = 0.01 # 1% very small default
        self._min_roe = 0.01           # minimum roe 1%
        self._min_ask_spread = 0.0002  # minimum ask spread 0.02%
        self._min_bid_spread = 0.0002  # minimum bid spread 0.02%
        self._crv=0.525                # chance/risk value

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

    @property
    def min_roe(self):
        return self._min_roe

    @min_roe.setter
    def min_roe(self, value):
        self._min_roe = value

    @property
    def min_bid_spread(self):
        return self._min_bid_spread

    @min_bid_spread.setter
    def min_bid_spread(self, value):
        self._min_bid_spread = value

    @property
    def min_ask_spread(self):
        return self._min_ask_spread

    @min_ask_spread.setter
    def min_ask_spread(self, value):
        self._min_ask_spread = value

    @property
    def crv(self):
        return self._crv

    @crv.setter
    def crv(self, value):
        self._crv = value

    def shutdown_handler(self):

        log_prefix = f"({self.class_name()}.shutdown_handler) symbol {self.symbol}:"
  
        logging.info(f'{log_prefix} Shuttig down the bot ...')
        
        # only cancel orders and delete files when not on a position
        if self._open_position_bool == False:
            self.housekeeping_handler()

    def housekeeping_handler(self):

        super().housekeeping_handler()

        log_prefix = f"({self.class_name()}.housekeeping) symbol {self.symbol}:"

        try:
            # cancel all orders first - only existing from the bot ...
            if self._dca_model_long.model_df is not None:
                self.cancel_orders_based_on_model(self._dca_model_long.model_df)

            if self._dca_model_short.model_df is not None:
                self.cancel_orders_based_on_model(self._dca_model_short.model_df)
                        
        except Exception as e:
            logging.exception(f'{log_prefix} WARN: Could not cancel existing orders', Exception(e))
        else:
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

            # also check if an open tp_order needs to be canceled
            if 'tp_order_id' in o:
                tp_dir = 'sell' if o['direction'] == 'buy' else 'buy'
                if self.matching_order_by_id(o['tp_order_id'], 'limit', tp_dir):
                    tp_order = { 'symbol': o['symbol'], 
                                 'id': o['tp_order_id'], 
                                 'type': 'limit', 
                                 'direction': tp_dir, 
                                 'exchange_id': self._ea.id}
                    self._ea.cancel_order_based_on_model(tp_order)

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

        # REFRESH OPEN POSITIONS
        # query open positions again, things may have changed, e.g. take profit executed
        self.refresh_open_position()
        if self._open_position_bool == False:
            logging.warning(f'{log_prefix} I am NOT in a position anymore ... do nothing with orders and exit this function')
            return

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

        log_prefix=f"({self.class_name()}.noposition_handler) symbol {self.symbol}:"

        time.sleep(2)
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


    def noposition_handler(self):

        logging.info(f'({self.class_name()}.noposition_handler) symbol {self.symbol}: I am not in a position - waiting for entry signals and new order checks!')
 
        try:
            # check balance
            total_balance = self._ea.get_total_balance()
        except Exception as e:

            logging.exception(f'({self.class_name()}.noposition_handler) symbol {self.symbol} ERROR: Could not check current balance')
            raise Exception(e)

        else:
            max_risk_per_trade = ( total_balance * self.max_account_risk_per_trade ) 
            logging.info(f'({self.class_name()}.noposition_handler) symbol {self.symbol} Total account balance: {total_balance} Max risk per trade: {max_risk_per_trade}')

        try:

            # get indicators
            candles_df = self._ea.fetch_candles_df(self.symbol, timeframe='5m', num_bars=50, only_closed=True)

            # get bid, ask and mid
            [ask, bid] = self._ea.ask_bid(self.symbol)
            mid = float(self._ea.price_to_precision(self.symbol, (ask + bid)/2))

        except Exception as e:

            logging.exception(f'({self.class_name()}.inposition_handler) symbol {self.symbol} WARN:', Exception(e))
            return

        else:

            # signal: buy, sell, both, none
            self.trend = self._signal_generator.signal(mid, candles_df)

            # pricing calculations, spread and roi calc
            ob_spread = ask - bid 
            ob_spread_perc = ob_spread / mid
            roe = ob_spread_perc * self.leverage - self._ea.maker_fees * 2

            logging.info(f'({self.class_name()}.noposition_handler) symbol {self.symbol} bid {bid} ask {ask} spread {ob_spread:.5f} ob_spread_perc {ob_spread_perc:.3%} roi {roe:.2%} at leverage {self.leverage}')
                        
            # trading only if min_roi is possible
            if roe < self.min_roe:
                logging.warning(f'({self.class_name()}.noposition_handler) symbol {self.symbol} roe: {roe:.3%} < min_roi: {self.min_roe:.3%}! Not market making now!')
                return
                        
            # simple spread calculation
            spread_calc = roe / self.leverage
            bid_spread_calc = spread_calc / 2
            ask_spread_calc = bid_spread_calc

            if bid_spread_calc < self.min_bid_spread:
                logging.warning(f'({self.class_name()}.noposition_handler) symbol {self.symbol} bid_spread_calc: {bid_spread_calc:.3%} < min_bid_spread: {self.min_bid_spread:.3%}! Not market making!')
                return

            if ask_spread_calc < self.min_ask_spread:
                logging.warning(f'({self.class_name()}.noposition_handler) symbol {self.symbol} ask_spread_calc: {ask_spread_calc:.3%} < min_ask_spread: {self.min_ask_spread:.3%}! Not market making!')
                return

            logging.info(f'({self.class_name()}.noposition_handler) symbol {self.symbol} bid_spread_calc {bid_spread_calc:.3%} ask_spread_calc {ask_spread_calc:.3%}')

            try:
                # creating the ask bid orders considering the trend (from strategy)
                if self.trend == 'sell' or self.trend == 'both':

                    # calc ask value - based on mid price
                    ask_limit = float(self._ea.price_to_precision(self.symbol, mid * (1 + ask_spread_calc + self._ea.maker_fees)))
                    self._dca_model_short.build_order_model(asset_price=ask_limit, risk_per_trade=max_risk_per_trade, crv=self.crv, leverage=self.leverage, min_roe=self.min_roe)
                    
                    self.create_orders_based_on_model(self._dca_model_short.model_df)

                    print(f'({self.class_name()}.noposition_handler) symbol {self.symbol} DCA Model Order Dataframe for asks:')
                    print(self._dca_model_short.model_df)

                    self._dca_model_short.store_df()

                if self.trend == 'buy' or self.trend == 'both':

                    # calc bid value - based on mid price
                    bid_limit = float(self._ea.price_to_precision(self.symbol, mid * (1 - bid_spread_calc - self._ea.maker_fees)))
                    self._dca_model_long.build_order_model(asset_price=bid_limit, risk_per_trade=max_risk_per_trade, crv=self.crv, leverage=self.leverage, min_roe=self.min_roe)

                    self.create_orders_based_on_model(self._dca_model_long.model_df)
                    print(f'({self.class_name()}.noposition_handler) symbol {self.symbol} DCA Model Order Dataframe for bids:')
                    print(self._dca_model_long.model_df)

                    self._dca_model_long.store_df()

                if self.trend is None:

                     logging.info(f'({self.class_name()}.noposition_handler) symbol {self.symbol} Not trading because trend = None')

            except Exception as e:

                logging.exception(f'({self.class_name()}.inposition_handler) symbol {self.symbol} WARN:', Exception(e))

