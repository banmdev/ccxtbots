from .order_model import OrderModel
from exchange_adapters import ExchangeAdapter

class FixedTPSLModel(OrderModel):
    
    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, 
                 direction: str, tp_perc: float, sl_perc: float):
        
        self._tp_perc: float = tp_perc
        self._sl_perc: float = sl_perc
        
        super().__init__(exchange_adapter, symbol, direction)
                     
    def get_sl_price_size(self, input_size: float = None, input_price: float = None) -> tuple[float, float]:
        
        sl_price = input_price * (1 - self._sl_perc) if self.direction == 'long' else input_price * (1 + self._sl_perc)
        sl_price = float(self.ea.price_to_precision(self.symbol, sl_price))
        
        return sl_price, input_size
    
    def get_tp_price_size(self, input_size: float = None, input_price: float = None) -> tuple[float, float]:
        
        tp_price = input_price * (1 + self._tp_perc) if self.direction == 'long' else input_price * (1 - self._tp_perc)
        tp_price = float(self.ea.price_to_precision(self.symbol, tp_price))
        
        return tp_price, input_size
    
    def get_order_size(self, asset_price: float, risk_per_trade: float):
        
        log_prefix=f"({self.class_name()}.get_order_size) symbol {self.symbol}:"
        
        if not isinstance(risk_per_trade, float):
            raise TypeError(f"{log_prefix} Argument risk_per_trade must be of type float, not {type(risk_per_trade)}")

        if not isinstance(asset_price, float) and not isinstance(asset_price, int):
            raise TypeError(f"{log_prefix} Argument asset_price must be of type int or float, not {type(asset_price)}")

        delta = abs(asset_price - self.get_sl_price_size(input_price = asset_price)[0])
        
        if delta > 0:
            
            amount_per_trade = risk_per_trade / delta
            size = amount_per_trade / self.ea.get_contract_size(self.symbol)
            size = float(self.ea.amount_to_precision(self.symbol, size))
            return size
        
        else:
            raise ZeroDivisionError(f'{log_prefix} Delta between sl_price and asset_price is Zero(0)')
    