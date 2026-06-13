"""
run_comparison_v2.py  –  Comparación avanzada SMA / Momentum con filtros
═════════════════════════════════════════════════════════════════════════
USO:  python agents/run_comparison_v2.py

Fases
─────
  0  Baseline original     (engine v1 si disponible; v2 sin costos si no)
  1  Señales filtradas      (4 filtros: régimen, HV rank, earnings, volumen)
  2  Engine v2 completo     (costos reales + salidas adaptativas)
  3  Monte Carlo            (1 000 shuffles del orden de trades)
  4  Walk-Forward           (75% train / 25% test out-of-sample)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import logging
from datetime import timedelta

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ─── Módulos nuevos ───────────────────────────────────────────────────────────
from backtest_engine_v2 import OptionsBacktestV2, BacktestConfigV2
from signal_filters     import apply_all_filters
from signals_momentum   import generate_momentum_breakout_signals

# ─── Módulos legacy (opcionales) ─────────────────────────────────────────────
try:
    from yfinance_provider import (
        make_yfinance_provider,
        generate_sma_crossover_signals,
        preload_history,
    )
    PROVIDER_OK = True
except ImportError:
    PROVIDER_OK = False

try:
    from backtest_engine import OptionsBacktest, BacktestConfig
    ENGINE1_OK = True
except ImportError:
    ENGINE1_OK = False

LEGACY_OK = PROVIDER_OK and ENGINE1_OK

# ─── Parámetros ───────────────────────────────────────────────────────────────
SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "INTC", "QCOM", "AVGO", "MU",   "ORCL", "CRM",  "ADBE",
    "JPM",  "BAC",  "GS",   "MS",   "V",    "MA",
    "UNH",  "JNJ",  "PFE",  "LLY",  "ABBV",
    "WMT",  "HD",   "COST", "MCD",  "NKE",  "DIS",  "KO",
    "PLTR", "SOFI", "COIN", "UBER", "SHOP", "SPY",  "QQQ",
]
START = "2023-01-01"
END   = "2024-12-31"
RISK  = 0.01
W     = 70   # ancho de columnas de output


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de formato
# ══════════════════════════════════════════════════════════════════════════════

def _bar(ch: str = "=") -> None:
    print(ch * W)


def _fmt(v, pct: bool = False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "  —"
    if isinstance(v, float):
        return f"{v:>+8.2f}%" if pct else f"{v:>10,.2f}"
    return str(v)


def _print_side_by_side(rows, res1: dict, res2: dict,
                         col1: str = "SIN FILTROS",
                         col2: str = "CON FILTROS+V2") -> None:
    W_L, W_C = 24, 16
    head = f"  {'Métrica':<{W_L}} {col1:>{W_C}} {col2:>{W_C}}"
    print(head)
    _bar("-")
    for key, label, pct in rows:
        v1 = _fmt(res1.get(key), pct)
        v2 = _fmt(res2.get(key), pct)
        print(f"  {label:<{W_L}} {v1:>{W_C}} {v2:>{W_C}}")


# ══════════════════════════════════════════════════════════════════════════════
# Generador SMA de respaldo (cuando yfinance_provider no está)
# ══════════════════════════════════════════════════════════════════════════════

def _sma_fallback(symbols, start, end, fast=20, slow=50):
    """SMA crossover sin depender de yfinance_provider."""
    import yfinance as yf
    sigs = []
    ext = (pd.to_datetime(start) - timedelta(days=slow * 2)).strftime("%Y-%m-%d")
    for sym in symbols:
        try:
            df = yf.download(sym, start=ext, end=end,
                             auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty:
                continue
            c  = df["Close"]
            sf = c.rolling(fast).mean()
            ss = c.rolling(slow).mean()
            cross_up   = (~(sf.shift(1) > ss.shift(1))) & (sf > ss)
            cross_down = (sf.shift(1) > ss.shift(1)) & (~(sf > ss))
            start_dt = pd.to_datetime(start)
            for d, u, dn in zip(df.index, cross_up, cross_down):
                if pd.to_datetime(d) < start_dt:
                    continue
                if u:
                    sigs.append({"date": str(d.date()), "symbol": sym, "direction": "bullish"})
                elif dn:
                    sigs.append({"date": str(d.date()), "symbol": sym, "direction": "bearish"})
        except Exception:
            pass
    out = pd.DataFrame(sigs)
    return out.sort_values("date").reset_index(drop=True) if not out.empty else out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    _bar()
    print(f"  BACKTEST AVANZADO v2  ·  {START} → {END}  ·  {len(SYMBOLS)} activos")
    print(f"  Riesgo {RISK:.0%}/trade  ·  Spread 2%  ·  Comisión $1.30  ·  Theta 0.7%/día")
    _bar()

    # ── [0] Datos ─────────────────────────────────────────────────────────────
    print("\n[0] Precargando históricos...")
    if PROVIDER_OK:
        preload_history(SYMBOLS, START, END)
    print("    Listo")

    # ── [1] Señales ───────────────────────────────────────────────────────────
    print("\n[1] Generando señales de entrada...")
    sig_sma = (generate_sma_crossover_signals(SYMBOLS, START, END, fast=20, slow=50)
               if PROVIDER_OK else _sma_fallback(SYMBOLS, START, END))
    sig_mom = generate_momentum_breakout_signals(SYMBOLS, START, END)

    print(f"    SMA 20/50         : {len(sig_sma):>4} señales")
    print(f"    Momentum/Ruptura  : {len(sig_mom):>4} señales")

    fechas  = pd.date_range(START, END, freq="B").strftime("%Y-%m-%d").tolist()
    cfg_v2  = BacktestConfigV2(
        initial_capital   = 10_000,
        risk_per_trade_pct= RISK,
        take_profit_pct   = 0.50,
        stop_loss_pct     = 0.30,
        spread_pct        = 0.02,
        commission        = 1.30,
        theta_daily_pct   = 0.007,
        leverage_factor   = 10.0,
        max_hold_days     = 21,
        max_concurrent    = 8,
    )

    ROWS = [
        ("capital_final",     "Capital final ($)",    False),
        ("retorno_total_pct", "Retorno (%)",           True),
        ("num_trades",        "N° trades",             False),
        ("win_rate_pct",      "Win rate (%)",          True),
        ("ganancia_promedio", "Ganancia prom. ($)",    False),
        ("perdida_promedio",  "Pérdida prom. ($)",     False),
        ("profit_factor",     "Profit factor",         False),
        ("max_drawdown_pct",  "Max drawdown (%)",      True),
        ("sharpe_ratio",      "Sharpe ratio",          False),
        ("avg_hold_days",     "Hold prom. (días)",     False),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # Bucle por estrategia
    # ══════════════════════════════════════════════════════════════════════════
    for sig_label, sig_df in [("SMA 20/50", sig_sma), ("Momentum/Ruptura", sig_mom)]:
        if sig_df is None or (hasattr(sig_df, "empty") and sig_df.empty):
            continue

        _bar()
        print(f"\n  ══ ESTRATEGIA: {sig_label}  ({len(sig_df)} señales originales) ══")
        _bar()

        # ── FASE 0: Baseline ─────────────────────────────────────────────────
        print(f"\n[FASE 0]  Baseline — sin filtros, engine original")
        if LEGACY_OK:
            cfg0    = BacktestConfig(initial_capital=10_000, risk_per_trade_pct=RISK,
                                     take_profit_pct=0.50, stop_loss_pct=0.30)
            prov    = make_yfinance_provider(vol_window=30, spread_pct=0.05)
            bt0     = OptionsBacktest(cfg0)
            bt0.set_data_provider(prov)
            res0    = bt0.run(sig_df, fechas)
        else:
            # Reproducir el baseline con v2 sin costos (lo más parecido al v1)
            cfg0nc  = BacktestConfigV2(initial_capital=10_000, risk_per_trade_pct=RISK,
                                       take_profit_pct=0.50, stop_loss_pct=0.30,
                                       spread_pct=0.0, commission=0.0, theta_daily_pct=0.0)
            res0    = OptionsBacktestV2(cfg0nc).run(sig_df, fechas)

        print(f"  Capital: {res0.get('capital_final', 0):>10,.2f}  |  "
              f"Retorno: {res0.get('retorno_total_pct', 0):>+6.2f}%  |  "
              f"Trades: {res0.get('num_trades', 0)}  |  "
              f"WR: {res0.get('win_rate_pct', 0):.1f}%  |  "
              f"PF: {res0.get('profit_factor', 0):.2f}")

        # ── FASE 1: Filtros de calidad ────────────────────────────────────────
        print(f"\n[FASE 1]  Aplicando 4 filtros de calidad...")
        sig_f, fstats = apply_all_filters(
            sig_df, START, END,
            use_regime   = True,  vix_max        = 25.0,
            use_iv_rank  = True,  iv_rank_max    = 50.0,
            use_earnings = True,  earnings_window= 5,
            use_volume   = True,  vol_mult       = 1.2,
            verbose      = True,
        )
        pct_kept = sig_f.__len__() / max(fstats["original"], 1) * 100
        print(f"\n  Resumen: {fstats['original']} → {fstats['final']} señales "
              f"({pct_kept:.0f}% del original)\n")
        if sig_f.empty:
            print("  (Sin señales tras filtros, saltando fases 2-4)")
            continue

        # ── FASE 2: Engine v2 ──────────────────────────────────────────────────
        print(f"[FASE 2]  Engine v2 — costos reales + salidas adaptativas")
        bt = OptionsBacktestV2(cfg_v2)

        print("  Corriendo sin filtros + v2...")
        res_raw = bt.run(sig_df, fechas)
        print("  Corriendo filtrado  + v2...")
        res_flt = bt.run(sig_f,  fechas)

        print()
        _print_side_by_side(ROWS, res_raw, res_flt,
                             col1="SIN FILTROS+V2", col2="FILTRADO+V2")

        er_r = res_raw.get("exit_reasons", {})
        er_f = res_flt.get("exit_reasons", {})
        print(f"\n  Razones de salida (sin filtros):  "
              f"TP={er_r.get('take_profit',0)}  SL={er_r.get('stop_loss',0)}  "
              f"Trail={er_r.get('trailing_stop',0)}  Time={er_r.get('time_exit',0)}")
        print(f"  Razones de salida (filtrado):     "
              f"TP={er_f.get('take_profit',0)}  SL={er_f.get('stop_loss',0)}  "
              f"Trail={er_f.get('trailing_stop',0)}  Time={er_f.get('time_exit',0)}")

        # ── FASE 3: Monte Carlo ───────────────────────────────────────────────
        print(f"\n[FASE 3]  Monte Carlo — 1 000 shuffles del orden de trades")
        mc = bt.run_monte_carlo(res_flt, n_runs=1_000)
        if mc:
            print(f"  {'Retorno medio / mediana':30} {mc['mean_pct']:>+7.2f}%  /  {mc['median_pct']:>+7.2f}%")
            print(f"  {'Rango P5 – P95':30} {mc['p5_pct']:>+7.2f}%  →  {mc['p95_pct']:>+7.2f}%")
            print(f"  {'Probabilidad de ser positivo':30} {mc['prob_pos_pct']:>7.1f}%")
            print(f"  {'Mejor / Peor escenario':30} {mc['best_pct']:>+7.2f}%  /  {mc['worst_pct']:>+7.2f}%")

            if   mc["prob_pos_pct"] > 65:
                mc_v = "✓  EDGE PROBABLE  — positivo en la mayoría de escenarios"
            elif mc["prob_pos_pct"] > 50:
                mc_v = "~  INCIERTO       — edge débil, poco por encima del 50%"
            else:
                mc_v = "✗  SIN EDGE       — la mayoría de escenarios son negativos"
            print(f"\n  → {mc_v}")
        else:
            print("  (Trades insuficientes para Monte Carlo)")

        # ── FASE 4: Walk-Forward ──────────────────────────────────────────────
        print(f"\n[FASE 4]  Walk-Forward — 75% train / 25% test (out-of-sample)")
        wf_input = sig_f if len(sig_f) >= 10 else sig_df
        wf = bt.run_walk_forward(wf_input, train_pct=0.75)

        if wf:
            print(f"\n  {'':30} {'TRAIN (75%)':>12} {'TEST (25%)':>12}")
            _bar("-")
            print(f"  {'N° señales':30} {wf['train_n']:>12} {wf['test_n']:>12}")
            print(f"  {'Retorno (%)':30} {wf['train_return']:>+11.2f}% {wf['test_return']:>+11.2f}%")
            print(f"  {'Profit factor':30} {wf['train_pf']:>12.2f} {wf['test_pf']:>12.2f}")
            print(f"  {'Win rate (%)':30} {wf['train_wr']:>11.1f}% {wf['test_wr']:>11.1f}%")
            d = wf["degradation_pct"]
            if   wf["test_return"] > 0 and abs(d) < 2.0: wf_v = "✓  ROBUSTO   — edge persiste out-of-sample"
            elif wf["test_return"] > 0:                   wf_v = "~  ACEPTABLE — edge se degrada pero persiste"
            else:                                         wf_v = "✗  OVERFITTING— edge desaparece out-of-sample"
            print(f"\n  → {wf_v}  (degradación: {d:+.2f}%)")
        else:
            print(f"  (Señales insuficientes: {len(wf_input)} < 10)")

        # ── Veredicto por estrategia ──────────────────────────────────────────
        pf  = res_flt.get("profit_factor",   0)
        n   = res_flt.get("num_trades",       0)
        ret = res_flt.get("retorno_total_pct",0)
        sh  = res_flt.get("sharpe_ratio",     0)

        print(f"\n  {'─'*W}")
        print(f"  VEREDICTO ({sig_label} + filtros + v2):")
        print(f"    PF={pf:.2f}  N={n}  Retorno={ret:+.2f}%  Sharpe={sh:.2f}")
        if   pf >= 1.5 and n >= 30:
            verdict = "EDGE REAL — considerar paper trading con capital mínimo"
        elif pf >= 1.2 and n >= 15:
            verdict = "SEÑAL MODERADA — ajustar parámetros y ampliar muestra"
        elif pf >= 1.0:
            verdict = "EDGE DÉBIL — el sistema cubre costos pero el margen es escaso"
        else:
            verdict = "SIN EDGE CON COSTOS REALES — revisar estrategia de señales"
        print(f"    → {verdict}")
        print()

    # ── Notas finales ─────────────────────────────────────────────────────────
    _bar()
    print("""
  GUÍA DE INTERPRETACIÓN
  ─────────────────────────────────────────────────────────────────────
  Qué significan los costos v2:
    • Spread 2%:   sobre $333 de allocation → $6.66 por trade
    • Comisión:    $1.30 fija por trade
    • Theta 0.7%:  ~21% de erosión si se lleva 30 días a vencimiento
    • Total fric.: ~$8 por trade (≈8% de la ganancia media esperada)

  Próximos ajustes si el PF es bajo:
    1. Reducir IV Rank máximo: 50 → 40 o 35  (opciones más baratas)
    2. Subir VIX máximo: 25 → 30  (más señales en mercados volátiles)
    3. Acortar hold: max_hold_days 21 → 14  (menos theta decay)
    4. Ampliar universo: añadir más activos para N ≥ 200 trades

  Con PF ≥ 1.5 y N ≥ 100:
    → Obtener datos reales de opciones (ORATS, OptionsDX, CBOE)
    → Paper trading 2-3 meses antes de capital real
  ─────────────────────────────────────────────────────────────────────
  AVISO: precios de opciones son estimados. Siempre validar con datos
         reales antes de operar con capital real.
""")
    _bar()


if __name__ == "__main__":
    main()
