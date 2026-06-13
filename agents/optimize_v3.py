"""
optimize_v3.py  –  Búsqueda de parámetros + régimen + bootstrap MC
═══════════════════════════════════════════════════════════════════
USO:   python agents/optimize_v3.py

QUÉ HACE
────────
  1. Aplica los parches al engine v2 (bootstrap MC + regime mode)
  2. Genera señales de Momentum (la que mostró edge en walk-forward)
  3. Barre 24 combinaciones de parámetros:
        IV Rank max   ∈ {35, 50, 65}
        VIX max       ∈ {22, 28}
        Hold days     ∈ {10, 14, 21}
        TP / SL ratio ∈ {0.40/0.25,  0.50/0.30}
  4. Para el TOP 3:
        - Monte Carlo con bootstrap (1000 muestras)
        - Walk-forward 70/30
        - Versión regime-only (solo opera con tendencia)
  5. Reporta la configuración ganadora con todas sus métricas
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import logging
from itertools import product

logging.basicConfig(level=logging.WARNING, format="%(message)s")

from backtest_engine_v2       import OptionsBacktestV2, BacktestConfigV2
from backtest_engine_v2_patch import patch_engine
from signal_filters           import apply_all_filters
from signals_momentum         import generate_momentum_breakout_signals

try:
    from yfinance_provider import preload_history
    PROVIDER_OK = True
except ImportError:
    PROVIDER_OK = False

# ── Parámetros ────────────────────────────────────────────────────────────────
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

GRID = list(product(
    [35, 50, 65],         # iv_rank_max
    [22, 28],             # vix_max
    [10, 14, 21],         # max_hold_days
    [(0.40, 0.25), (0.50, 0.30)],  # tp / sl
))
W = 78


# ══════════════════════════════════════════════════════════════════════════════
# Score: combina PF, número de trades y retorno en una métrica única
# ══════════════════════════════════════════════════════════════════════════════
def score(res: dict) -> float:
    """
    Métrica compuesta: PF penalizado por muestras chicas + retorno.

    Sistemas con n<30 quedan penalizados (poca evidencia estadística).
    PF<1 → score negativo (no cubre costos).
    """
    pf  = res.get("profit_factor",   0.0)
    n   = res.get("num_trades",      0)
    ret = res.get("retorno_total_pct", 0.0)
    if n < 5:
        return -999.0
    confidence = min(n / 50.0, 1.0)         # llega a 1.0 con n≥50
    return (pf - 1.0) * confidence * 100 + ret * 0.5


def run_one(sig_filtered, cfg):
    bt = OptionsBacktestV2(cfg)
    return bt.run(sig_filtered), bt


def fmt(v, pct=False, places=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:+.{places}f}%" if pct else f"{v:.{places}f}"
    return str(v)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    patch_engine()
    print("=" * W)
    print(f"  OPTIMIZACIÓN PARAMÉTRICA  ·  Momentum/Ruptura")
    print(f"  {START} → {END}  ·  {len(SYMBOLS)} activos  ·  {len(GRID)} combinaciones")
    print("=" * W)

    # ── Datos + señales ───────────────────────────────────────────────────────
    print("\n[0] Precargando datos...")
    if PROVIDER_OK:
        preload_history(SYMBOLS, START, END)

    print("\n[1] Generando señales base (Momentum/Ruptura)...")
    sig_mom = generate_momentum_breakout_signals(SYMBOLS, START, END)
    print(f"    → {len(sig_mom)} señales generadas")

    # ── Pre-calcular filtros base (régimen y volumen son comunes) ────────────
    print("\n[2] Filtros base (régimen + volumen + earnings)...")
    sig_base, base_stats = apply_all_filters(
        sig_mom, START, END,
        use_regime   = True,  vix_max     = 28.0,    # el menos restrictivo
        use_iv_rank  = False,                         # se variará en el grid
        use_earnings = True,  earnings_window = 5,
        use_volume   = True,  vol_mult    = 1.2,
        verbose      = False,
    )
    print(f"    {base_stats['original']} → {len(sig_base)} señales tras filtros base")

    # ══════════════════════════════════════════════════════════════════════════
    # BARRIDO DE GRID
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n[3] Probando {len(GRID)} combinaciones de parámetros...")
    print()
    print(f"  {'#':>3}  {'IVmax':>5}  {'VIX':>4}  {'Hold':>4}  "
          f"{'TP/SL':>9}  {'N':>4}  {'WR':>6}  {'PF':>5}  {'Ret':>7}  {'Score':>7}")
    print("  " + "─" * (W - 4))

    results = []
    for i, (iv_max, vix_max, hold, (tp, sl)) in enumerate(GRID, 1):
        # ── Re-filtrar según el VIX y IV Rank de esta config ────────────
        sig_x, _ = apply_all_filters(
            sig_mom, START, END,
            use_regime   = True,  vix_max     = float(vix_max),
            use_iv_rank  = True,  iv_rank_max = float(iv_max),
            use_earnings = True,  earnings_window = 5,
            use_volume   = True,  vol_mult    = 1.2,
            verbose      = False,
        )
        if sig_x.empty:
            print(f"  {i:>3}  {iv_max:>5}  {vix_max:>4}  {hold:>4}  "
                  f"{tp:.2f}/{sl:.2f}  (sin señales tras filtros)")
            continue

        cfg = BacktestConfigV2(
            initial_capital   = 10_000,
            risk_per_trade_pct= RISK,
            take_profit_pct   = tp,
            stop_loss_pct     = sl,
            max_hold_days     = hold,
            spread_pct        = 0.02,
            commission        = 1.30,
            theta_daily_pct   = 0.007,
            leverage_factor   = 10.0,
            max_concurrent    = 8,
        )
        res, bt = run_one(sig_x, cfg)
        s       = score(res)
        results.append({
            "i": i, "iv_max": iv_max, "vix_max": vix_max, "hold": hold,
            "tp": tp, "sl": sl, "res": res, "score": s,
            "signals": sig_x,
        })
        print(f"  {i:>3}  {iv_max:>5}  {vix_max:>4}  {hold:>4}  "
              f"{tp:.2f}/{sl:.2f}  "
              f"{res.get('num_trades',0):>4}  "
              f"{res.get('win_rate_pct',0):>5.1f}%  "
              f"{res.get('profit_factor',0):>5.2f}  "
              f"{res.get('retorno_total_pct',0):>+6.2f}%  "
              f"{s:>+7.2f}")

    if not results:
        print("\n  Ninguna combinación produjo trades.")
        return

    # ══════════════════════════════════════════════════════════════════════════
    # TOP 3
    # ══════════════════════════════════════════════════════════════════════════
    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:3]

    print("\n" + "=" * W)
    print("  TOP 3 — Análisis profundo")
    print("=" * W)

    for rank, item in enumerate(top, 1):
        res, sig_x = item["res"], item["signals"]
        cfg = BacktestConfigV2(
            initial_capital   = 10_000,
            risk_per_trade_pct= RISK,
            take_profit_pct   = item["tp"],
            stop_loss_pct     = item["sl"],
            max_hold_days     = item["hold"],
            spread_pct        = 0.02,
            commission        = 1.30,
            theta_daily_pct   = 0.007,
            leverage_factor   = 10.0,
            max_concurrent    = 8,
        )
        bt = OptionsBacktestV2(cfg)
        _  = bt.run(sig_x)   # re-hidratar el caché interno

        print(f"\n  ━━━ #{rank}  IV≤{item['iv_max']}  VIX≤{item['vix_max']}  "
              f"Hold={item['hold']}d  TP/SL={item['tp']:.2f}/{item['sl']:.2f}  "
              f"·  Score {item['score']:+.2f}")
        print(f"    Trades: {res.get('num_trades',0)}  ·  "
              f"WR: {res.get('win_rate_pct',0):.1f}%  ·  "
              f"PF: {res.get('profit_factor',0):.2f}  ·  "
              f"Retorno: {res.get('retorno_total_pct',0):+.2f}%  ·  "
              f"Sharpe: {res.get('sharpe_ratio',0):.2f}")
        print(f"    Max DD: {res.get('max_drawdown_pct',0):+.2f}%  ·  "
              f"Hold prom: {res.get('avg_hold_days',0):.1f}d")

        # ── Monte Carlo BOOTSTRAP (arreglado) ─────────────────────────
        mc = bt.run_monte_carlo(res, n_runs=1_000)
        if mc:
            print(f"\n    [Monte Carlo bootstrap, {mc['n_runs']} muestras]")
            print(f"      Retorno P5 → P50 → P95: "
                  f"{mc['p5_pct']:+.2f}%  →  {mc['median_pct']:+.2f}%  →  {mc['p95_pct']:+.2f}%")
            print(f"      Prob. positivo: {mc['prob_pos_pct']:.1f}%   ·   "
                  f"Sharpe mediano: {mc['median_sharpe']:.2f}")
            print(f"      Peor escenario: {mc['worst_pct']:+.2f}%  ·  "
                  f"Peor DD: {mc['worst_dd_pct']:+.2f}%")

        # ── Walk-forward ──────────────────────────────────────────────
        wf = bt.run_walk_forward(sig_x, train_pct=0.70)
        if wf:
            print(f"\n    [Walk-forward 70/30]")
            print(f"      Train  n={wf['train_n']:>3}  PF={wf['train_pf']:.2f}  "
                  f"WR={wf['train_wr']:.1f}%  Ret={wf['train_return']:+.2f}%")
            print(f"      Test   n={wf['test_n']:>3}  PF={wf['test_pf']:.2f}  "
                  f"WR={wf['test_wr']:.1f}%  Ret={wf['test_return']:+.2f}%")

        # ── Regime-only ───────────────────────────────────────────────
        print(f"\n    [Regime-only: solo opera con SPY>SMA50 y VIX≤{item['vix_max']}]")
        bt2 = OptionsBacktestV2(cfg)
        res_reg = bt2.run_regime_filtered(sig_x, vix_max=float(item['vix_max']))
        if res_reg.get("num_trades", 0) > 0:
            print(f"      Trades: {res_reg.get('num_trades')}  ·  "
                  f"PF: {res_reg.get('profit_factor',0):.2f}  ·  "
                  f"WR: {res_reg.get('win_rate_pct',0):.1f}%  ·  "
                  f"Ret: {res_reg.get('retorno_total_pct',0):+.2f}%")

    # ── Veredicto final ───────────────────────────────────────────────────────
    print("\n" + "=" * W)
    best = top[0]
    bres = best["res"]
    print(f"  CONFIGURACIÓN ÓPTIMA:")
    print(f"     IV Rank ≤ {best['iv_max']}  ·  VIX ≤ {best['vix_max']}  ·  "
          f"Hold {best['hold']}d  ·  TP/SL = {best['tp']:.2f}/{best['sl']:.2f}")
    print(f"     N={bres.get('num_trades',0)}  ·  "
          f"PF={bres.get('profit_factor',0):.2f}  ·  "
          f"WR={bres.get('win_rate_pct',0):.1f}%  ·  "
          f"Ret={bres.get('retorno_total_pct',0):+.2f}%")

    pf = bres.get("profit_factor", 0)
    n  = bres.get("num_trades",     0)
    if   pf >= 1.5 and n >= 50:
        verdict = "EDGE REAL — proceder a paper trading con datos de opciones reales"
    elif pf >= 1.2 and n >= 30:
        verdict = "EDGE PROBABLE — ampliar universo o periodo antes de paper trading"
    elif pf >= 1.0:
        verdict = "MARGINAL — cubre costos pero el edge es muy fino"
    else:
        verdict = "SIN EDGE — considerar pivot a otra estrategia (spreads, sell-side)"
    print(f"\n     → {verdict}")
    print("=" * W)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n  Tiempo total: {time.time()-t0:.1f}s")
