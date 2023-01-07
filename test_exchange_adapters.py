import logging
import time
import os
from dotenv import load_dotenv

from exchange_adapters import BitgetAdapter
from exchange_adapters import PhemexAdapter

# load environment variables
load_dotenv()
BITGET_API_KEY=os.getenv('BITGET_API_KEY')
BITGET_API_SECRET=os.getenv('BITGET_API_SECRET')
BITGET_API_PASSWORD=os.getenv('BITGET_API_PASSWORD')
BITGET_MARGINCOIN=os.getenv('BITGET_MARGINCOIN')

PHEMEX_API_KEY=os.getenv('PHEMEX_API_KEY')
PHEMEX_API_SECRET=os.getenv('PHEMEX_API_SECRET')
PHEMEX_MARGINCOIN=os.getenv('PHEMEX_MARGINCOIN')

# debugging and testing the adapters
if __name__ == '__main__':

    import pprint

    pp = pprint.PrettyPrinter(indent=4)

    logging.basicConfig(format='%(asctime)s %(levelname)s [%(process)d] %(message)s', level=logging.INFO)

    bitget_connect_params = {
        'enableRateLimit': True,
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_API_SECRET,
        'password': BITGET_API_PASSWORD
    }
    bitget_params = {"type":"swap", "code":BITGET_MARGINCOIN}
    bitget_symbol = 'BTC/USDT:USDT'
    bitget_adapter = BitgetAdapter(bitget_connect_params, bitget_params)
    
    phemex_connect_params = {
        'enableRateLimit': True,
        'apiKey': PHEMEX_API_KEY,
        'secret': PHEMEX_API_SECRET
    }
    phemex_params= {"type":"swap", "code":PHEMEX_MARGINCOIN}
    phemex_symbol = 'ETH/USD:USD'
    phemex_adapter = PhemexAdapter(phemex_connect_params, phemex_params)

    since = int(time.time() * 1000) - 600 * 60 * 1000
    
    [ position, open_position_bool, current_size, current_long, entryPrice, position_leverage ] = phemex_adapter.fetch_open_positions(phemex_symbol)
    print("=== Phemex tests: ===")
    total_balance = phemex_adapter.get_total_balance()
    print(f'total_balance = {total_balance}')

    print("Current Position: ")
    pp.pprint(position)

    # print("Trades: ")
    # my_trades = phemex_adapter.fetch_my_trades(phemex_symbol, since)
    # pp.pprint(my_trades)

    print("Orders: ")
    orders = phemex_adapter.fetch_orders(phemex_symbol, since)
    pp.pprint(orders)

    [ position, open_position_bool, current_size, current_long, entryPrice, position_leverage ] = bitget_adapter.fetch_open_positions(bitget_symbol)
    print("=== Bitget tests: ===")
    total_balance = bitget_adapter.get_total_balance()
    print(f'total_balance = {total_balance}')
    pp.pprint(position)
    orders = bitget_adapter.fetch_orders(bitget_symbol, since)
    pp.pprint(orders)
    orders_sl = bitget_adapter.bitget_fetch_open_stoploss_orders(bitget_symbol)




 
