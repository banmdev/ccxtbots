import logging
import os
from dotenv import load_dotenv

from exchange_adapters import BitgetAdapter
from order_models import DCAOrderModel
from signal_generators import SimpleMMSignalGenerator
from botlib import MarketMakerBot

# load environment variables
load_dotenv()
BITGET_API_KEY=os.getenv('BITGET_API_KEY')
BITGET_API_SECRET=os.getenv('BITGET_API_SECRET')
BITGET_API_PASSWORD=os.getenv('BITGET_API_PASSWORD')
BITGET_MARGINCOIN=os.getenv('BITGET_MARGINCOIN')

# debugging and testing the models
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)s [%(process)d] %(message)s', level=logging.INFO)

    connect_params = {
        'enableRateLimit': True,
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_API_SECRET,
        'password': BITGET_API_PASSWORD
    }
    params = {"type":"swap", "code":BITGET_MARGINCOIN}
    symbol = 'DYDX/USDT:USDT'

    adapter = BitgetAdapter(connect_params, params)

    dca_model_long  = DCAOrderModel(adapter, symbol=symbol, direction='long',  num_trades=4, price_dev=0.0050, save_scale=2.0)
    dca_model_short = DCAOrderModel(adapter, symbol=symbol, direction='short', num_trades=4, price_dev=0.0050, save_scale=2.0)
    signal_generator = SimpleMMSignalGenerator()

    bot = MarketMakerBot(exchange_adapter=adapter,
                                symbol=symbol, 
                                signal_generator=signal_generator, 
                                long_model=dca_model_long, 
                                short_model=dca_model_short)

    bot.main_loop()

