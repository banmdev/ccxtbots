import logging
import os
from dotenv import load_dotenv

#from exchange_adapters import PhemexAdapter
from exchange_adapters import BitgetAdapter
from order_models import FixedTPSLModel
# from signal_generators import BuySignalGenerator
# from signal_generators import ExtMMSignalGenerator
# from signal_generators import SMA_15m_1d_SignalGenerator
# from signal_generators import VectorCandleSignalGenerator
from signal_generators import HeikinAshiSignalGenerator
from botlib import SimpleTPSLBot

load_dotenv()
# PHEMEX_API_KEY=os.getenv('PHEMEX_API_KEY')
# PHEMEX_API_SECRET=os.getenv('PHEMEX_API_SECRET')
# PHEMEX_MARGINCOIN=os.getenv('PHEMEX_MARGINCOIN')

BITGET_API_KEY=os.getenv('BITGET_API_KEY')
BITGET_API_SECRET=os.getenv('BITGET_API_SECRET')
BITGET_API_PASSWORD=os.getenv('BITGET_API_PASSWORD')
BITGET_MARGINCOIN=os.getenv('BITGET_MARGINCOIN')

# debugging and testing the models
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)s [%(process)d] %(message)s', level=logging.INFO)

    # connect_params = {
    #     'enableRateLimit': True,
    #     'apiKey': PHEMEX_API_KEY,
    #     'secret': PHEMEX_API_SECRET
    # }
    # params = {"type":"swap", "code":PHEMEX_MARGINCOIN}
    
    connect_params = {
        'enableRateLimit': True,
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_API_SECRET,
        'password': BITGET_API_PASSWORD
    }
    params = {"type":"swap", "code":BITGET_MARGINCOIN}
    symbol = 'ETH/USDT:USDT'

    # adapter = PhemexAdapter(connect_params, params)
    adapter = BitgetAdapter(connect_params, params)

    # initialize the model with a fixed tp / sl percentage as a starting point
    # based on the signals (if a stop loss price is generated) a fixed stop loss
    # and take profit can be applied
    model_long = FixedTPSLModel(adapter, symbol=symbol, direction='long', tp_perc=0.01, sl_perc=0.0066)
    model_short = FixedTPSLModel(adapter, symbol=symbol, direction='short', tp_perc=0.01, sl_perc=0.0066)
    # signal_generator = ExtMMSignalGenerator(ask_spread=0.0005, bid_spread=0.0005, sl_buffer=0.001)
    # signal_generator = SMA_15m_1d_SignalGenerator()
    # signal_generator = VectorCandleSignalGenerator(binance_symbol='BTCUSDT')
    signal_generator = HeikinAshiSignalGenerator(binance_symbol='ETHUSDT') 

    bot = SimpleTPSLBot(exchange_adapter=adapter,
                                symbol=symbol, 
                                signal_generator=signal_generator,
                                long_model=model_long,
                                short_model=model_short,
                                refresh_timeout=120,
                                not_trading=False)
    # for testing
    bot.max_account_risk_per_trade=0.01

    bot.main_loop()
