import logging
import os
from dotenv import load_dotenv

from exchange_adapters import PhemexAdapter
from order_models import FixedTPSLModel
from signal_generators import BuySignalGenerator
from botlib import SimpleBuyBot

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
    symbol = 'SOL/USD:USD'

    adapter = PhemexAdapter(connect_params, params)

    model_long = FixedTPSLModel(adapter, symbol=symbol, direction='long', tp_perc=0.01, sl_perc=0.0075 )
    signal_generator = BuySignalGenerator()

    bot = SimpleBuyBot(exchange_adapter=adapter,
                                symbol=symbol, 
                                signal_generator=signal_generator,
                                long_model=model_long,
                                refresh_timeout=30)
    # for testing
    bot.max_account_risk_per_trade=0.002

    bot.main_loop()

