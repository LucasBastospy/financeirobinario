import yfinance as yf
from curl_cffi import requests

session = requests.Session(impersonate="chrome120")
pares = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]

for par in pares:
    ticker = yf.Ticker(par, session=session)
    info = ticker.info
    market_state = info.get('market_state', 'N/A')
    print(f"{par}: {market_state}")