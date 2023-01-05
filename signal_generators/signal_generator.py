from base import BaseClass

class SignalGenerator(BaseClass):

    # returns buy, sell, both or none
    def signal(self):
        return None

class BuySignalGenerator(BaseClass):
    # returns buy only
    def signal(self, price, df):
        return 'buy'

class SellSignalGenerator(BaseClass):
    # returns sell only
    def signal(self, price, df):
        return 'sell'
        