import logging
import os
from dotenv import load_dotenv

from exchange_adapters import PhemexAdapter
from order_models import DCAOrderModel
from signal_generators import SimpleMMSignalGenerator
from botlib import MarketMakerBot

load_dotenv()
PHEMEX_API_KEY=os.getenv('PHEMEX_API_KEY')
PHEMEX_API_SECRET=os.getenv('PHEMEX_API_SECRET')
PHEMEX_MARGINCOIN=os.getenv('PHEMEX_MARGINCOIN')


# debugging and testing the models
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(levelname)s [%(process)d] %(message)s', level=logging.INFO)

    connect_params = {
        'enableRateLimit': True,
        'apiKey': PHEMEX_API_KEY,
        'secret': PHEMEX_API_SECRET
    }

    params = {"type":"swap", "code":PHEMEX_MARGINCOIN}
    symbol = 'DYDX/USD:USD'

    adapter = PhemexAdapter(connect_params, params)

    dca_model_long  = DCAOrderModel(adapter, symbol=symbol, direction='long',  num_trades=4, price_dev=0.0030, save_scale=2.0)
    dca_model_short = DCAOrderModel(adapter, symbol=symbol, direction='short', num_trades=4, price_dev=0.0030, save_scale=2.0)
    signal_generator = SimpleMMSignalGenerator()

    bot = MarketMakerBot(exchange_adapter=adapter,
                                symbol=symbol, 
                                signal_generator=signal_generator, 
                                long_model=dca_model_long, 
                                short_model=dca_model_short)

    bot.main_loop()

