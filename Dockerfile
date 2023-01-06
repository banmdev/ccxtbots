# syntax=docker/dockerfile:1

FROM python:3.11.1

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY base/ base/
COPY botlib/ botlib/
COPY exchange_adapters/ exchange_adapters/
COPY order_models/ order_models/
COPY signal_generators/ signal_generators/
COPY test_bots_phemex.py test_bots_phemex.py
COPY test_bots_bitget.py test_bots_bitget.py
COPY test_exchange_adapters.py test_exchange_adapters.py 

CMD [ "python3", "test_bots_phemex.py" ] 