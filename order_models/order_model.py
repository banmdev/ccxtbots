from base import BaseClass

class OrderModel(BaseClass):

    def __init__(self, exchange_adapter, symbol, direction):

        if direction != 'long' and direction != 'short':
            raise ValueError(f'({self.class_name()}.__init__) Invalid trade direction {direction}, must be either long or short')

        # ea stands for Exchange Adapter
        self.ea = exchange_adapter
        self.symbol = symbol
        self.direction = direction

    @property
    def exchange_symbol_str(self):
        return self.ea.id + "_" + self.symbol