"""
stress_test_v4.py  –  Validación final antes de paper trading
════════════════════════════════════════════════════════════════════
USO:   python agents/stress_test_v4.py

LA PREGUNTA QUE RESPONDE
────────────────────────
"¿Esto vale más que comprar SPY y dormir tranquilo?"

Toma la configuración óptima de optimize_v3.py:
    IV Rank ≤ 35  ·  VIX ≤ 22  ·  Hold 14d  ·  TP/SL = 0.50/0.30

Y la somete a 4 pruebas. Solo si pasa las 4 vale la pena pasar a paper.

  TEST 1  Bear market 2022 (out-of-sample temporal)
          → ¿Preserva capital cuando SPY cae?
          → Esta es LA prueba. Si pierde más que SPY en 2022, no sirve.

  TEST 2  Activos no entrenados (out-of-sample en universo)
          → Sector ETFs: XLF XLE XLK XLV XLI XLY XLP XLU XLB XLRE
          → Si solo funciona en mega-caps tech, es overfitting

  TEST 3  Costos pesimistas (3% spread + $2 comisión)
          → ¿Aún tiene edge si la realidad es peor que el modelo?

  TEST 4  Atribución del filtro IV Rank
          → Sin el filtro, ¿cuánto del retorno desaparece?
          → Confirma de dónde viene el edge

Al final compara contra SPY buy-and-hold del mismo periodo.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import timedelta

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

W = 78
patch_engine()


# ─── Configuración óptima del paso anterior ──────────────────────────────────
OPTIMAL = BacktestConfigV2(
    initial_capital   = 10_000,
    risk_per_trade_pct= 0.01,
    take_profit_pct   = 0.50,
    stop_loss_pct     = 0.30,
    max_hold_days     = 14,
    spread_pct        = 0.02,
    commission        = 1.30,
    theta_daily_pct   = 0.007,
    leverage_factor   = 10.0,
    max_concurrent    = 8,
)

OPT_FILTERS = dict(
    use_regime   = True,  vix_max     = 22.0,
    use_iv_rank  = True,  iv_rank_max = 35.0,
    use_earnings = True,  earnings_window = 5,
    use_volume   = True,  vol_mult    = 1.2,
    verbose      = False,
)

UNIVERSE_TRAIN = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "INTC", "QCOM", "AVGO", "MU",   "ORCL", "CRM",  "ADBE",
    "JPM",  "BAC",  "GS",   "MS",   "V",    "MA",
    "UNH",  "JNJ",  "PFE",  "LLY",  "ABBV",
    "WMT",  "HD",   "COST", "MCD",  "NKE",  "DIS",  "KO",
    "SPY",  "QQQ",
]

UNIVERSE_HOLDOUT = [
    "XLF", "XLE", "XLK", "XLV", "XLI",
    "XLY", "XLP", "XLU", "XLB", "XLRE",
]


# ══════════════════════════════════════════════════════════════════════════════
def spy_benchmark(start: str, end: str) -> dict:
    """Retorno y Sharpe de SPY buy-and-hold."""
    df = yf.download("SPY", start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        return {"retorno": 0.0, "max_dd": 0.0, "sharpe": 0.0}
    close = df["Close"]
    ret_total = (close.iloc[-1] / close.iloc[0] - 1) * 100
    rets = close.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    peak = close.cummax()
    dd = ((close - peak) / peak).min() * 100
    return {
        "retorno":  round(float(ret_total), 2),
        "max_dd":   round(float(dd), 2),
        "sharpe":   round(float(sharpe), 2),
    }


def run_strategy(universe, start, end, cfg, filters):
    """Genera señales y corre el backtest con la config dada."""
    if PROVIDER_OK:
        try:
            preload_history(universe, start, end)
        except Exception:
            pass
    sig = generate_momentum_breakout_signals(universe, start, end)
    if sig.empty:
        return {"num_trades": 0, "error": "sin señales"}, 0
    sig_f, _ = apply_all_filters(sig, start, end, **filters)
    if sig_f.empty:
        return {"num_trades": 0, "error": "sin señales tras filtros"}, 0
    bt = OptionsBacktestV2(cfg)
    res = bt.run(sig_f)
    return res, len(sig_f)


def fmt_pct(v, places=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "  —"
    return f"{v:+.{places}f}%"


def verdict_line(passed: bool, label: str, detail: str = "") -> str:
    mark = "✓ PASA" if passed else "✗ FALLA"
    return f"  {mark}  {label}{('  —  ' + detail) if detail else ''}"


# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * W)
    print(f"  STRESS TEST FINAL  ·  Configuración óptima del paso anterior")
    print(f"  IV≤35  ·  VIX≤22  ·  Hold 14d  ·  TP/SL 0.50/0.30")
    print("=" * W)

    verdicts = []

    # ════════════════════════════════════════════════════════════════════════════
    # TEST 1 — Bear market 2022
    # ════════════════════════════════════════════════════════════════════════════
    print("\n[TEST 1]  Bear market 2022 — ¿preserva capital cuando SPY cae?")
    print("─" * W)
    res22, n22 = run_strategy(UNIVERSE_TRAIN, "2022-01-01", "2022-12-31",
                              OPTIMAL, OPT_FILTERS)
    spy22 = spy_benchmark("2022-01-01", "2022-12-31")
    print(f"  SPY 2022:        ret {fmt_pct(spy22['retorno'])}  "
          f"DD {fmt_pct(spy22['max_dd'])}  Sharpe {spy22['sharpe']:.2f}")
    if res22.get("num_trades", 0) > 0:
        ret = res22.get("retorno_total_pct", 0)
        dd  = res22.get("max_drawdown_pct", 0)
        pf  = res22.get("profit_factor", 0)
        n   = res22.get("num_trades", 0)
        print(f"  Sistema 2022:    ret {fmt_pct(ret)}  DD {fmt_pct(dd)}  "
              f"PF {pf:.2f}  N={n}")

        passed = (ret > spy22["retorno"]) or (ret > -10 and dd > spy22["max_dd"])
        if   ret > 0 and spy22["retorno"] < 0:
            detail = "ret positivo en bear market — protección real"
        elif ret > spy22["retorno"]:
            detail = f"perdió menos que SPY ({ret:+.1f}% vs {spy22['retorno']:+.1f}%)"
        else:
            detail = f"perdió igual o más que SPY ({ret:+.1f}% vs {spy22['retorno']:+.1f}%)"
        verdicts.append((passed, "Bear 2022", detail))
        print(f"\n{verdict_line(passed, 'Bear 2022', detail)}")
    else:
        print("  Sin trades en 2022 (filtro IV/VIX demasiado estricto en el bear)")
        verdicts.append((False, "Bear 2022", "sin trades — filtros bloquean el bear"))
        print(f"\n{verdict_line(False, 'Bear 2022', 'sin trades — filtros bloquean el bear')}")

    # ════════════════════════════════════════════════════════════════════════════
    # TEST 2 — Universo no entrenado
    # ════════════════════════════════════════════════════════════════════════════
    print(f"\n[TEST 2]  Activos out-of-universe — Sector ETFs (n={len(UNIVERSE_HOLDOUT)})")
    print("─" * W)
    res_oou, n_oou = run_strategy(UNIVERSE_HOLDOUT, "2023-01-01", "2024-12-31",
                                  OPTIMAL, OPT_FILTERS)
    if res_oou.get("num_trades", 0) > 0:
        ret = res_oou.get("retorno_total_pct", 0)
        pf  = res_oou.get("profit_factor", 0)
        wr  = res_oou.get("win_rate_pct", 0)
        n   = res_oou.get("num_trades", 0)
        print(f"  Sectores 23-24: ret {fmt_pct(ret)}  PF {pf:.2f}  "
              f"WR {wr:.1f}%  N={n}")

        passed = pf >= 1.1 and ret > 0
        detail = (f"PF {pf:.2f} ≥ 1.1 con N={n}" if passed
                  else f"PF {pf:.2f} no replica el edge")
        verdicts.append((passed, "Out-of-universe", detail))
        print(f"\n{verdict_line(passed, 'Out-of-universe', detail)}")
    else:
        verdicts.append((False, "Out-of-universe", "muy pocas señales"))
        print(f"\n{verdict_line(False, 'Out-of-universe', 'muy pocas señales')}")

    # ════════════════════════════════════════════════════════════════════════════
    # TEST 3 — Costos pesimistas
    # ════════════════════════════════════════════════════════════════════════════
    print(f"\n[TEST 3]  Costos pesimistas — spread 3% + comisión $2.00")
    print("─" * W)
    cfg_pess = BacktestConfigV2(
        initial_capital=10_000, risk_per_trade_pct=0.01,
        take_profit_pct=0.50, stop_loss_pct=0.30, max_hold_days=14,
        spread_pct=0.03, commission=2.00,
        theta_daily_pct=0.007, leverage_factor=10.0, max_concurrent=8,
    )
    res_p, _ = run_strategy(UNIVERSE_TRAIN, "2023-01-01", "2024-12-31",
                            cfg_pess, OPT_FILTERS)
    if res_p.get("num_trades", 0) > 0:
        ret = res_p.get("retorno_total_pct", 0)
        pf  = res_p.get("profit_factor", 0)
        n   = res_p.get("num_trades", 0)
        print(f"  Costos altos:   ret {fmt_pct(ret)}  PF {pf:.2f}  N={n}")
        passed = pf >= 1.0 and ret > 0
        detail = (f"sobrevive: PF {pf:.2f}, ret {ret:+.1f}%" if passed
                  else f"no sobrevive: PF {pf:.2f}, ret {ret:+.1f}%")
        verdicts.append((passed, "Costos pesimistas", detail))
        print(f"\n{verdict_line(passed, 'Costos pesimistas', detail)}")
    else:
        verdicts.append((False, "Costos pesimistas", "sin trades"))

    # ════════════════════════════════════════════════════════════════════════════
    # TEST 4 — Atribución del filtro IV Rank
    # ════════════════════════════════════════════════════════════════════════════
    print(f"\n[TEST 4]  Atribución — ¿qué pasa si quito el filtro de IV Rank?")
    print("─" * W)
    filters_no_iv = {**OPT_FILTERS, "use_iv_rank": False}
    res_no_iv, n_no_iv = run_strategy(UNIVERSE_TRAIN, "2023-01-01", "2024-12-31",
                                       OPTIMAL, filters_no_iv)
    if res_no_iv.get("num_trades", 0) > 0:
        ret = res_no_iv.get("retorno_total_pct", 0)
        pf  = res_no_iv.get("profit_factor", 0)
        n   = res_no_iv.get("num_trades", 0)
        print(f"  Sin filtro IV:  ret {fmt_pct(ret)}  PF {pf:.2f}  N={n}")
        print(f"  (referencia con filtro:  +18.84%   PF 1.21   N=141)")
        edge_came_from_iv = pf < 1.10
        detail = ("confirmado: PF colapsa sin IV Rank" if edge_came_from_iv
                  else "el edge sobrevive sin IV Rank — buscar otra fuente")
        verdicts.append((edge_came_from_iv, "Atribución a IV Rank", detail))
        print(f"\n{verdict_line(edge_came_from_iv, 'Atribución a IV Rank', detail)}")

    # ════════════════════════════════════════════════════════════════════════════
    # VEREDICTO FINAL
    # ════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * W)
    print("  RESUMEN DE STRESS TEST")
    print("=" * W)
    for passed, label, detail in verdicts:
        mark = "✓" if passed else "✗"
        print(f"  {mark}  {label:<22}  {detail}")

    passed_count = sum(1 for p, _, _ in verdicts if p)
    total = len(verdicts)
    print(f"\n  Pasó {passed_count}/{total} pruebas")

    print("\n" + "=" * W)
    if   passed_count == total:
        print("  RECOMENDACIÓN:  Listo para PAPER TRADING")
        print("  Próximo paso: obtener datos reales de opciones (OptionsDX, ORATS,")
        print("  CBOE LiveVol). El modelo delta×2.5 puede sobreestimar o subestimar.")
    elif passed_count >= total - 1:
        print("  RECOMENDACIÓN:  Casi listo. Investigar la prueba que falló.")
        print("  Si es Bear 2022 — el sistema solo sirve para mercado alcista.")
        print("  Si es out-of-universe — sobreajustado al universo tech.")
    elif passed_count >= 2:
        print("  RECOMENDACIÓN:  Edge frágil. Más iteración antes de paper.")
        print("  Considerar: ampliar muestra, simplificar filtros, validar IV Rank.")
    else:
        print("  RECOMENDACIÓN:  El edge no se generaliza. NO usar capital real.")
        print("  Pivote sugerido: probar debit spreads (menor theta, costos absorbibles).")
    print("=" * W)


if __name__ == "__main__":
    main()
