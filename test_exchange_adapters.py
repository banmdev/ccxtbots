import logging
import time

from exchange_adapters import BitgetAdapter
from exchange_adapters import PhemexAdapter

# debugging and testing the adapters
if __name__ == '__main__':

    import dontshare_config as ds
    import pprint

    pp = pprint.PrettyPrinter(indent=4)

    logging.basicConfig(format='%(asctime)s %(levelname)s [%(process)d] %(message)s', level=logging.INFO)

    bitget_connect_params = {
        'enableRateLimit': True,
        'apiKey': ds.bP_KEY,
        'secret': ds.bP_SECRET,
        'password': ds.bP_PASSWORD,
    }
    bitget_params={"type":"swap", "code":ds.bP_MARGINCOIN}
    bitget_symbol = 'BTC/USDT:USDT'
    bitget_adapter = BitgetAdapter(bitget_connect_params, bitget_params)
    
    phemex_connect_params = {
        'enableRateLimit': True,
        'apiKey': ds.xP_KEY,
        'secret': ds.xP_SECRET,
    }
    phemex_params={"type":"swap", "code":ds.xP_MARGINCOIN}
    phemex_symbol = 'ETH/USD:USD'
    phemex_adapter = PhemexAdapter(phemex_connect_params, phemex_params)

    since = int(time.time() * 1000) - 600 * 60 * 1000
    
    [ position, open_position_bool, current_size, current_long, entryPrice, position_leverage ] = phemex_adapter.fetch_open_positions(phemex_symbol)
    print("=== Phemex tests: ===")

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
    pp.pprint(position)
    orders = bitget_adapter.fetch_orders(bitget_symbol, since)
    pp.pprint(orders)
    orders_sl = bitget_adapter.bitget_fetch_open_stoploss_orders(bitget_symbol)




 
