# agents/market_data.py
import pandas as pd
import numpy as np
import yfinance as yf
import sys
sys.path.insert(0, '.')
try:
    from config.settings import DATA_PERIOD, DATA_INTERVAL
except Exception:
    DATA_PERIOD = "1y"
    DATA_INTERVAL = "1d"


def _wilder_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    k = 100 * (close - lowest_low) / denom
    d = k.rolling(d_period).mean()
    return k, d


def _adx(high, low, close, period=14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.ewm(com=period - 1, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(com=period - 1, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(com=period - 1, adjust=False).mean() / atr
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(com=period - 1, adjust=False).mean()
    return adx, plus_di, minus_di


def _bollinger_bands(close, period=20, std_dev=2):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return mid, upper, lower, pct_b


def _pivot_sr(high, low, close, lookback=20):
    pivot = (high.iloc[-1] + low.iloc[-1] + close.iloc[-1]) / 3
    r1 = 2 * pivot - low.iloc[-1]
    s1 = 2 * pivot - high.iloc[-1]
    r2 = pivot + (high.iloc[-1] - low.iloc[-1])
    s2 = pivot - (high.iloc[-1] - low.iloc[-1])
    return {
        "pivot": round(float(pivot), 2),
        "resistance_1": round(float(r1), 2),
        "resistance_2": round(float(r2), 2),
        "support_1": round(float(s1), 2),
        "support_2": round(float(s2), 2),
        "swing_resistance": round(float(high.tail(lookback).max()), 2),
        "swing_support": round(float(low.tail(lookback).min()), 2),
    }


def _volume_trend(volume, period=20):
    avg_vol = volume.tail(period).mean()
    current = float(volume.iloc[-1])
    ratio = current / float(avg_vol) if float(avg_vol) > 0 else 1.0
    recent_5 = float(volume.tail(5).mean())
    prior_5 = float(volume.tail(10).head(5).mean())
    if float(prior_5) > 0:
        vol_trend = "INCREASING" if recent_5 > prior_5 * 1.1 else \
                    "DECREASING" if recent_5 < prior_5 * 0.9 else "STABLE"
    else:
        vol_trend = "STABLE"
    return current, float(avg_vol), ratio, vol_trend


def get_market_data(symbol):
    print("  Descargando datos...")
    data = yf.download(symbol, period=DATA_PERIOD, interval=DATA_INTERVAL,
                       auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError("Sin datos para " + symbol)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    close = data["Close"].squeeze()
    high = data["High"].squeeze()
    low = data["Low"].squeeze()
    volume = data["Volume"].squeeze()

    if len(close) < 30:
        raise ValueError("Insuficientes datos: " + str(len(close)))

    rsi = _wilder_rsi(close, 14)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_sig
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.ewm(com=13, adjust=False).mean()
    bb_mid, bb_upper, bb_lower, bb_pct_b = _bollinger_bands(close, 20, 2)
    stoch_k, stoch_d = _stochastic(high, low, close, 14, 3)
    adx, plus_di, minus_di = _adx(high, low, close, 14)
    current_vol, avg_vol, vol_ratio, vol_trend = _volume_trend(volume, 20)
    sr = _pivot_sr(high, low, close, 20)

    def sf(s): return float(s.iloc[-1]) if not pd.isna(s.iloc[-1]) else 0.0

    price = float(close.iloc[-1])
    cur_rsi = sf(rsi)
    cur_ema9 = sf(ema9)
    cur_ema21 = sf(ema21)
    cur_ema50 = sf(ema50)
    cur_ema200 = float(ema200.iloc[-1]) if not pd.isna(ema200.iloc[-1]) else 0.0
    cur_macd = sf(macd)
    cur_macd_s = sf(macd_sig)
    cur_macd_h = sf(macd_hist)
    cur_atr = sf(atr)
    cur_bb_pct = sf(bb_pct_b) if not pd.isna(bb_pct_b.iloc[-1]) else 0.5
    cur_stk = sf(stoch_k) if not pd.isna(stoch_k.iloc[-1]) else 50.0
    cur_std = sf(stoch_d) if not pd.isna(stoch_d.iloc[-1]) else 50.0
    cur_adx = sf(adx) if not pd.isna(adx.iloc[-1]) else 20.0
    cur_pdi = sf(plus_di) if not pd.isna(plus_di.iloc[-1]) else 20.0
    cur_mdi = sf(minus_di) if not pd.isna(minus_di.iloc[-1]) else 20.0

    short_trend = "UP" if cur_ema9 > cur_ema21 else "DOWN"
    medium_trend = "UP" if cur_ema21 > cur_ema50 else "DOWN"
    trend = "UP" if short_trend == "UP" and medium_trend == "UP" else \
            "DOWN" if short_trend == "DOWN" and medium_trend == "DOWN" else short_trend

    bb_position = "NEAR_UPPER" if cur_bb_pct > 0.8 else \
                  "NEAR_LOWER" if cur_bb_pct < 0.2 else "MIDDLE"
    prev_h = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0
    macd_momentum = "BULLISH" if cur_macd_h > prev_h else "BEARISH"
    atr_pct = round(cur_atr / price * 100, 2) if price > 0 else 0

    print("  Precio: $" + str(round(price, 2)))
    print("  RSI: " + str(round(cur_rsi, 1)) + " | ADX: " + str(round(cur_adx, 1)))
    print("  Tendencia: " + trend + " (corto:" + short_trend + " medio:" + medium_trend + ")")
    print("  EMA50:" + str(round(cur_ema50, 2)) + " EMA200:" + str(round(cur_ema200, 2)) + " | MACD: " + str(round(cur_macd, 4)))
    print("  BB%B: " + str(round(cur_bb_pct, 2)) + " | Stoch K/D: " + str(round(cur_stk, 1)) + "/" + str(round(cur_std, 1)))
    print("  ATR: $" + str(round(cur_atr, 2)) + " (" + str(atr_pct) + "%) | Vol ratio: " + str(round(vol_ratio, 2)) + "x")

    return {
        "symbol": symbol, "price": price,
        "rsi": cur_rsi, "ema9": cur_ema9, "ema21": cur_ema21, "ema50": cur_ema50, "ema200": cur_ema200,
        "macd": cur_macd, "macd_signal": cur_macd_s, "macd_hist": cur_macd_h,
        "macd_momentum": macd_momentum,
        "atr": cur_atr, "atr_pct": atr_pct,
        "bb_mid": float(bb_mid.iloc[-1]), "bb_upper": float(bb_upper.iloc[-1]),
        "bb_lower": float(bb_lower.iloc[-1]),
        "bb_pct_b": cur_bb_pct, "bb_position": bb_position,
        "stoch_k": cur_stk, "stoch_d": cur_std,
        "adx": cur_adx, "plus_di": cur_pdi, "minus_di": cur_mdi,
        "volume": current_vol, "avg_volume": avg_vol,
        "vol_ratio": vol_ratio, "vol_trend": vol_trend,
        "trend": trend, "short_trend": short_trend, "medium_trend": medium_trend,
        "support": sr["support_1"], "resistance": sr["resistance_1"],
        "support_2": sr["support_2"], "resistance_2": sr["resistance_2"],
        "swing_support": sr["swing_support"], "swing_resistance": sr["swing_resistance"],
        "pivot": sr["pivot"],
    }
