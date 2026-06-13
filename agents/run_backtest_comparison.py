"""
run_backtest_comparison.py  –  Backtest amplio + comparación de riesgo
Corre el backtest sobre 40 activos y compara 1% / 2% / 5% de riesgo.

USO:  python agents\run_backtest_comparison.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
import logging

from backtest_engine import OptionsBacktest, BacktestConfig
from yfinance_provider import (
    make_yfinance_provider,
    generate_sma_crossover_signals,
    preload_history,
)

logging.basicConfig(level=logging.WARNING, format="%(message)s")

SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "INTC", "QCOM", "AVGO", "MU", "ORCL", "CRM", "ADBE",
    "JPM", "BAC", "GS", "MS", "V", "MA",
    "UNH", "JNJ", "PFE", "LLY", "ABBV",
    "WMT", "HD", "COST", "MCD", "NKE", "DIS", "KO",
    "PLTR", "SOFI", "COIN", "UBER", "SHOP",
    "SPY", "QQQ",
]

START = "2023-01-01"
END = "2024-12-31"
RISK_LEVELS = [0.01, 0.02, 0.05]


def run_one(signals, fechas, provider, risk_pct):
    cfg = BacktestConfig(
        initial_capital=10_000,
        risk_per_trade_pct=risk_pct,
        take_profit_pct=0.50,
        stop_loss_pct=0.30,
    )
    bt = OptionsBacktest(cfg)
    bt.set_data_provider(provider)
    return bt.run(signals, fechas)


def main():
    print("=" * 60)
    print("BACKTEST AMPLIO  -  40 activos, 2 anios, 3 niveles de riesgo")
    print("=" * 60)

    print(f"\nPrecargando historicos de {len(SYMBOLS)} activos...")
    print("   (tarda 1-3 min la primera vez; luego va en cache)")
    preload_history(SYMBOLS, START, END)

    print("\nGenerando senales (cruce SMA 20/50)...")
    signals = generate_sma_crossover_signals(SYMBOLS, START, END, fast=20, slow=50)
    print(f"   -> {len(signals)} senales en {signals['symbol'].nunique()} activos")

    if signals.empty:
        print("Sin senales. Revisa el rango de fechas.")
        return

    fechas = pd.date_range(START, END, freq="B").strftime("%Y-%m-%d").tolist()
    provider = make_yfinance_provider(vol_window=30, spread_pct=0.05)

    resultados = {}
    for risk in RISK_LEVELS:
        print(f"\nCorriendo backtest con riesgo {risk:.0%} por trade...")
        resultados[risk] = run_one(signals, fechas, provider, risk)

    print("\n" + "=" * 60)
    print("COMPARACION DE RESULTADOS")
    print("=" * 60)

    metricas = [
        ("capital_final",      "Capital final ($)"),
        ("retorno_total_pct",  "Retorno total (%)"),
        ("num_trades",         "Num. trades"),
        ("win_rate_pct",       "Win rate (%)"),
        ("ganancia_promedio",  "Ganancia prom. ($)"),
        ("perdida_promedio",   "Perdida prom. ($)"),
        ("profit_factor",      "Profit factor"),
        ("max_drawdown_pct",   "Max drawdown (%)"),
    ]

    header = f"{'Metrica':<22}" + "".join(f"{f'Riesgo {r:.0%}':>16}" for r in RISK_LEVELS)
    print(header)
    print("-" * len(header))

    for key, label in metricas:
        row = f"{label:<22}"
        for risk in RISK_LEVELS:
            res = resultados[risk]
            val = res.get(key, "-") if "error" not in res else "-"
            if isinstance(val, float):
                row += f"{val:>16,.2f}"
            else:
                row += f"{str(val):>16}"
        print(row)

    print("\n" + "=" * 60)
    print("ANALISIS")
    print("=" * 60)

    base = resultados[RISK_LEVELS[0]]
    if "error" in base:
        print("No se ejecutaron trades. Revisa senales/fechas.")
        return

    n = base.get("num_trades", 0)
    print(f"\n- Muestra: {n} trades cerrados.")
    if n < 30:
        print(f"  AUN POCOS TRADES (<30). Los resultados todavia son ruido.")
    else:
        print(f"  Muestra razonable para empezar a interpretar.")

    print("\n- Efecto del nivel de riesgo:")
    for risk in RISK_LEVELS:
        res = resultados[risk]
        ret = res.get("retorno_total_pct", 0)
        dd = res.get("max_drawdown_pct", 0)
        print(f"    {risk:.0%} -> retorno {ret:+.1f}%  |  drawdown max {dd:.1f}%")

    out_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(out_dir, exist_ok=True)
    for risk in RISK_LEVELS:
        eq = resultados[risk].get("equity_curve")
        if eq is not None:
            path = os.path.join(out_dir, f"backtest_equity_riesgo_{int(risk*100)}pct.csv")
            eq.to_csv(path, index=False)
    print(f"\nCurvas de equity guardadas en reports/")

    print("\nRECORDATORIO: precios RECONSTRUIDOS con Black-Scholes (sesgo optimista).")
    print("Valida con datos reales antes de arriesgar dinero.")


if __name__ == "__main__":
    main()