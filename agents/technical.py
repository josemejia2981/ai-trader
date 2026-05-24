import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

def technical_analysis(state):

    print("📊 Obteniendo datos reales...")

    symbol = state.get("symbol", "AAPL")

    data = yf.download(symbol, period="10d", interval="1h")

    close = data["Close"].squeeze()

    # RSI
    rsi = RSIIndicator(close=close, window=14).rsi()

    # EMAs
    ema9 = EMAIndicator(close=close, window=9).ema_indicator()
    ema21 = EMAIndicator(close=close, window=21).ema_indicator()

    state["price"] = float(close.iloc[-1])
    state["rsi"] = float(rsi.iloc[-1])
    state["ema9"] = float(ema9.iloc[-1])
    state["ema21"] = float(ema21.iloc[-1])

    # tendencia base
    state["trend"] = "UP" if ema9.iloc[-1] > ema21.iloc[-1] else "DOWN"

    print(f"💰 Precio: {state['price']}")
    print(f"📉 RSI: {state['rsi']}")
    print(f"📊 EMA9: {state['ema9']}")
    print(f"📊 EMA21: {state['ema21']}")
    print(f"📈 Tendencia: {state['trend']}")

    return state