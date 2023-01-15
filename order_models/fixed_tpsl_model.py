from .order_model import OrderModel
from exchange_adapters import ExchangeAdapter

class FixedTPSLModel(OrderModel):
    
    def __init__(self, exchange_adapter: ExchangeAdapter, symbol: str, 
                 direction: str, tp_perc: float, sl_perc: float, 
                 tp_trigger_perc: float, tp_trail_perc: float):
        
        self._tp_perc: float = tp_perc
        self._sl_perc: float = sl_perc
        
        self._tp_trigger_perc: float = tp_trigger_perc
        self._tp_trail_perc: float = tp_trail_perc
        
        self._sl_fixed: float = None
        self._tp_fixed: float = None
        
        # crv based on the percentages
        self._desired_crv = self._tp_perc / self._sl_perc
        
        super().__init__(exchange_adapter, symbol, direction)
        
    
    @property
    def sl_fixed(self) -> float:
        return self._sl_fixed

    @sl_fixed.setter
    def sl_fixed(self, value: float):
        self._sl_fixed = value
        
    @property
    def tp_fixed(self) -> float:
        return self._tp_fixed

    @tp_fixed.setter
    def tp_fixed(self, value: float):
        self._tp_fixed = value
        
    @property
    def sl_perc(self) -> float:
        return self._sl_perc

    @sl_perc.setter
    def sl_perc(self, value: float):
        self._sl_perc = value
        
    @property
    def tp_perc(self) -> float:
        return self._tp_perc

    @sl_perc.setter
    def tp_perc(self, value: float):
        self._tp_perc = value
    
    
    def get_trsl_price_value(self, input_size: float = None, input_price: float = None) -> tuple[float, float]:
        
        trigger_price = input_price * (1 + self._tp_trigger_perc) if self.direction == 'long' else input_price * (1 - self._tp_trigger_perc)
        trigger_price = float(self.ea.price_to_precision(self.symbol, trigger_price))
        
        trail_value = trigger_price * self._tp_trail_perc
        trail_value = float(self.ea.price_to_precision(self.symbol, trail_value))
        
        return trigger_price, trail_value
        
                     
    def get_sl_price_size(self, input_size: float = None, input_price: float = None) -> tuple[float, float]:
        
        if self._sl_fixed:
            sl_price = float(self.ea.price_to_precision(self.symbol, self._sl_fixed))
        else:
            sl_price = input_price * (1 - self._sl_perc) if self.direction == 'long' else input_price * (1 + self._sl_perc)
            sl_price = float(self.ea.price_to_precision(self.symbol, sl_price))
            
        return sl_price, input_size
    
    def get_tp_price_size(self, input_size: float = None, input_price: float = None) -> tuple[float, float]:
        
        if self._tp_fixed:
            tp_price =  float(self.ea.price_to_precision(self.symbol, self._tp_fixed))
        else:
            tp_price = input_price * (1 + self._tp_perc) if self.direction == 'long' else input_price * (1 - self._tp_perc)
            tp_price = float(self.ea.price_to_precision(self.symbol, tp_price))
        
        return tp_price, input_size
    
    def get_order_size(self, asset_price: float, risk_per_trade: float, fixed_sl_price: float = None):
        
        log_prefix=f"({self.class_name()}.get_order_size) symbol {self.symbol}:"
        
        if fixed_sl_price:
            self._sl_fixed = fixed_sl_price
        
        if not isinstance(risk_per_trade, float):
            raise TypeError(f"{log_prefix} Argument risk_per_trade must be of type float, not {type(risk_per_trade)}")

        if not isinstance(asset_price, float) and not isinstance(asset_price, int):
            raise TypeError(f"{log_prefix} Argument asset_price must be of type int or float, not {type(asset_price)}")

        delta = abs(asset_price - self.get_sl_price_size(input_price = asset_price)[0])
        
        if delta > 0:
            
            amount_per_trade = risk_per_trade / delta
            size = amount_per_trade / self.ea.get_contract_size(self.symbol)
            size = float(self.ea.amount_to_precision(self.symbol, size))
            
            # keep the tp target a the desired crv level if a fixed sl price was given
            if self._sl_fixed:
                if self.direction == 'long':
                    self._tp_fixed = asset_price + ( delta * self._desired_crv) 
                else: 
                    self._tp_fixed = asset_price - ( delta * self._desired_crv)
            
            return size
        
        else:
            raise ZeroDivisionError(f'{log_prefix} Delta between sl_price and asset_price is Zero(0)')
    