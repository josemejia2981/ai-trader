"""
signals_momentum.py - Senal de momentum/ruptura con filtro de tendencia
Ruptura del max/min de N dias + confirmacion de volumen + filtro SMA 200.
"""
import pandas as pd
import numpy as np
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)
from yfinance_provider import _get_price_history


def generate_momentum_breakout_signals(
    symbols, start, end,
    breakout_window=20, volume_window=20, volume_mult=1.3,
    trend_sma=200, use_trend_filter=True, cooldown_days=10,
):
    all_signals = []
    start_dt = (pd.to_datetime(start) - timedelta(days=trend_sma * 2)).strftime("%Y-%m-%d")

    for sym in symbols:
        hist = _get_price_history(sym, start_dt, end)
        if hist.empty or len(hist) < trend_sma + breakout_window + 5:
            continue

        close = hist["Close"]; high = hist["High"]; low = hist["Low"]; volume = hist["Volume"]
        sma_trend = close.rolling(trend_sma).mean()
        avg_volume = volume.rolling(volume_window).mean()
        prior_high = high.rolling(breakout_window).max().shift(1)
        prior_low = low.rolling(breakout_window).min().shift(1)

        last_signal_date = None
        for i in range(len(hist)):
            d = pd.to_datetime(hist.index[i])
            if d < pd.to_datetime(start):
                continue
            c = close.iloc[i]; vol = volume.iloc[i]; avgvol = avg_volume.iloc[i]
            ph = prior_high.iloc[i]; pl = prior_low.iloc[i]; trend = sma_trend.iloc[i]
            if pd.isna(ph) or pd.isna(pl) or pd.isna(avgvol) or pd.isna(trend):
                continue
            if last_signal_date is not None and (d - last_signal_date).days < cooldown_days:
                continue

            volume_ok = vol >= avgvol * volume_mult
            if c > ph and volume_ok:
                if not use_trend_filter or c > trend:
                    all_signals.append({"date": d.strftime("%Y-%m-%d"), "symbol": sym, "direction": "bullish"})
                    last_signal_date = d
                    continue
            if c < pl and volume_ok:
                if not use_trend_filter or c < trend:
                    all_signals.append({"date": d.strftime("%Y-%m-%d"), "symbol": sym, "direction": "bearish"})
                    last_signal_date = d

    df = pd.DataFrame(all_signals)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


if __name__ == "__main__":
    from yfinance_provider import preload_history
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMD", "TSLA"]
    START, END = "2024-01-01", "2024-12-31"
    print("Precargando...")
    preload_history(SYMBOLS, START, END)
    print("\nGenerando senales momentum/ruptura...")
    sig = generate_momentum_breakout_signals(SYMBOLS, START, END)
    print(f"  -> {len(sig)} senales")
    if not sig.empty:
        print(sig.to_string(index=False))
        print(f"\nReparto: {sig['direction'].value_counts().to_dict()}")