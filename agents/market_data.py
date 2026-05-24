import pandas as pd
import numpy as np
import yfinance as yf

def get_market_data(symbol):
    print("📊 Obteniendo datos reales...")

    data = yf.download(
        symbol,
        period="3mo",
        interval="1d",
        auto_adjust=True
    )

    if data.empty:
        raise ValueError(f"No se encontraron datos para {symbol}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    close = data["Close"]
    high = data["High"]
    low = data["Low"]
    volume = data["Volume"]

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # EMA
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    # ATR
    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(14).mean()

    # Soporte y resistencia
    support = low.tail(20).min()
    resistance = high.tail(20).max()

    # Volumen promedio
    avg_volume = volume.tail(20).mean()

    current_price = float(close.iloc[-1])
    current_rsi = float(rsi.iloc[-1])
    current_ema9 = float(ema9.iloc[-1])
    current_ema21 = float(ema21.iloc[-1])
    current_macd = float(macd.iloc[-1])
    current_macd_signal = float(macd_signal.iloc[-1])
    current_atr = float(atr.iloc[-1])
    current_volume = float(volume.iloc[-1])
    current_avg_volume = float(avg_volume)
    current_support = float(support)
    current_resistance = float(resistance)

    trend = "UP" if current_ema9 > current_ema21 else "DOWN"

    print(f"💰 Precio: {current_price}")
    print(f"📉 RSI: {current_rsi}")
    print(f"📊 EMA9: {current_ema9}")
    print(f"📊 EMA21: {current_ema21}")
    print(f"📈 MACD: {current_macd}")
    print(f"📈 MACD Signal: {current_macd_signal}")
    print(f"⚠️ ATR: {current_atr}")
    print(f"📦 Volumen: {current_volume}")
    print(f"📦 Volumen Promedio: {current_avg_volume}")
    print(f"🟢 Soporte: {current_support}")
    print(f"🔴 Resistencia: {current_resistance}")
    print(f"📈 Tendencia: {trend}")

    return {
        "symbol": symbol,
        "price": current_price,
        "rsi": current_rsi,
        "ema9": current_ema9,
        "ema21": current_ema21,
        "macd": current_macd,
        "macd_signal": current_macd_signal,
        "atr": current_atr,
        "volume": current_volume,
        "avg_volume": current_avg_volume,
        "support": current_support,
        "resistance": current_resistance,
        "trend": trend
    }