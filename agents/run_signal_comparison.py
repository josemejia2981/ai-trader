"""
run_signal_comparison.py - Comparar SMA 20/50 vs Momentum/Ruptura
USO:  python agents\run_signal_comparison.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
import logging

from backtest_engine import OptionsBacktest, BacktestConfig
from yfinance_provider import make_yfinance_provider, generate_sma_crossover_signals, preload_history
from signals_momentum import generate_momentum_breakout_signals

logging.basicConfig(level=logging.WARNING, format="%(message)s")

SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "INTC", "QCOM", "AVGO", "MU", "ORCL", "CRM", "ADBE",
    "JPM", "BAC", "GS", "MS", "V", "MA",
    "UNH", "JNJ", "PFE", "LLY", "ABBV",
    "WMT", "HD", "COST", "MCD", "NKE", "DIS", "KO",
    "PLTR", "SOFI", "COIN", "UBER", "SHOP", "SPY", "QQQ",
]
START = "2023-01-01"
END = "2024-12-31"
RISK = 0.01


def run_with_signals(signals, fechas, provider):
    cfg = BacktestConfig(initial_capital=10_000, risk_per_trade_pct=RISK,
                         take_profit_pct=0.50, stop_loss_pct=0.30)
    bt = OptionsBacktest(cfg)
    bt.set_data_provider(provider)
    return bt.run(signals, fechas)


def main():
    print("=" * 64)
    print("COMPARACION DE SENALES  -  SMA 20/50  vs  Momentum/Ruptura")
    print("=" * 64)
    print(f"\nPrecargando historicos de {len(SYMBOLS)} activos...")
    preload_history(SYMBOLS, START, END)

    print("\nGenerando senales...")
    sig_sma = generate_sma_crossover_signals(SYMBOLS, START, END, fast=20, slow=50)
    sig_mom = generate_momentum_breakout_signals(SYMBOLS, START, END)
    print(f"  SMA 20/50:        {len(sig_sma)} senales")
    print(f"  Momentum/ruptura: {len(sig_mom)} senales")

    fechas = pd.date_range(START, END, freq="B").strftime("%Y-%m-%d").tolist()
    provider = make_yfinance_provider(vol_window=30, spread_pct=0.05)

    print("\nCorriendo backtest con SMA 20/50...")
    res_sma = run_with_signals(sig_sma, fechas, provider)
    print("Corriendo backtest con Momentum/ruptura...")
    res_mom = run_with_signals(sig_mom, fechas, provider)

    print("\n" + "=" * 64)
    print(f"RESULTADOS  (riesgo {RISK:.0%} por trade, +50%/-30% salida)")
    print("=" * 64)
    metricas = [
        ("capital_final", "Capital final ($)"), ("retorno_total_pct", "Retorno total (%)"),
        ("num_trades", "Num. trades"), ("win_rate_pct", "Win rate (%)"),
        ("ganancia_promedio", "Ganancia prom. ($)"), ("perdida_promedio", "Perdida prom. ($)"),
        ("profit_factor", "Profit factor"), ("max_drawdown_pct", "Max drawdown (%)"),
    ]
    header = f"{'Metrica':<22}{'SMA 20/50':>18}{'Momentum':>18}"
    print(header); print("-" * len(header))

    def fmt(res, key):
        if "error" in res: return "-"
        v = res.get(key, "-")
        return f"{v:,.2f}" if isinstance(v, float) else str(v)

    for key, label in metricas:
        print(f"{label:<22}{fmt(res_sma, key):>18}{fmt(res_mom, key):>18}")

    print("\n" + "=" * 64)
    print("VEREDICTO")
    print("=" * 64)
    if "error" in res_mom:
        print("La senal de momentum no genero trades. Revisar parametros.")
        return

    ret_sma = res_sma.get("retorno_total_pct", 0)
    ret_mom = res_mom.get("retorno_total_pct", 0)
    pf_mom = res_mom.get("profit_factor", 0)
    print(f"\n- Retorno:       SMA {ret_sma:+.1f}%   vs   Momentum {ret_mom:+.1f}%")
    print(f"- Profit factor momentum: {pf_mom}  ({res_mom.get('num_trades',0)} trades, win {res_mom.get('win_rate_pct',0):.1f}%)")

    try: pf = float(pf_mom)
    except: pf = 0
    print("\n- Interpretacion:")
    if pf > 1.3 and ret_mom > ret_sma:
        print("  Momentum muestra VENTAJA. Siguiente: validar en otro periodo (out-of-sample).")
    elif pf > 1.0 and ret_mom > ret_sma:
        print("  Momentum es mejor que SMA pero la ventaja es pequena. Seguir afinando.")
    else:
        print("  Momentum NO mejora claramente. Comprar opciones sigue sin ventaja clara.")

    print("\nRECORDATORIO: precios reconstruidos (sesgo optimista).")


if __name__ == "__main__":
    main()