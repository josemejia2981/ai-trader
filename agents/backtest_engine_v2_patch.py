"""
backtest_engine_v2_patch.py  –  Parches sobre backtest_engine_v2
═══════════════════════════════════════════════════════════════════
APLICA dos mejoras críticas al motor v2:

  1. FIX  run_monte_carlo:
         El método anterior solo barajaba el orden, lo que NO cambia
         la suma total. Resultado: P5 == P95 == media (bug visible
         en la corrida del usuario).
         La versión corregida hace BOOTSTRAP con reemplazo: muestrea
         N trades con repetición. Eso sí mide si el edge depende
         de unos pocos trades excepcionales o si es robusto.

  2. NEW  run_regime_filtered:
         Corre el backtest solo en días donde SPY está sobre SMA50
         Y VIX ≤ vix_max. Útil para sistemas de momentum que
         solo funcionan en tendencia (validado por el walk-forward
         del usuario: PF 0.90 train 2023 → PF 1.23 test 2024).

USO
───
    from backtest_engine_v2 import OptionsBacktestV2, BacktestConfigV2
    from backtest_engine_v2_patch import patch_engine
    patch_engine()                              # aplica los dos fixes
    bt  = OptionsBacktestV2(BacktestConfigV2())
    res = bt.run(signals)
    mc  = bt.run_monte_carlo(res, n_runs=1000)  # ahora con bootstrap real
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import timedelta

from backtest_engine_v2 import OptionsBacktestV2


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1 — Monte Carlo correcto (bootstrap)
# ══════════════════════════════════════════════════════════════════════════════

def run_monte_carlo_bootstrap(
    self,
    result: dict,
    n_runs: int = 1_000,
    seed:   int = 42,
) -> dict:
    """
    Bootstrap con reemplazo: muestrea N trades con repetición.

    Si el resultado depende de unos pocos trades grandes, la varianza
    será enorme y la probabilidad de positivo bajará.
    Si el edge es robusto, la mayoría de muestreos serán positivos.
    """
    if "trades_df" not in result or result["trades_df"].empty:
        return {}

    pnl_arr = result["trades_df"]["pnl"].values.astype(float)
    n       = len(pnl_arr)
    cap     = self.cfg.initial_capital
    rng     = np.random.default_rng(seed)

    rets   = np.empty(n_runs)
    sharps = np.empty(n_runs)
    dds    = np.empty(n_runs)

    for i in range(n_runs):
        # ── Bootstrap: N trades con reemplazo
        sample = rng.choice(pnl_arr, size=n, replace=True)
        rets[i] = sample.sum() / cap * 100

        # ── Path-dependent: max drawdown del orden bootstrap
        eq    = cap + np.cumsum(sample)
        peak  = np.maximum.accumulate(eq)
        dd    = ((eq - peak) / np.where(peak > 0, peak, 1) * 100).min()
        dds[i] = dd

        # ── Sharpe del sample
        r = sample / cap
        sharps[i] = (r.mean() / r.std() * np.sqrt(252 / max(self.cfg.max_hold_days, 1))
                     if r.std() > 0 else 0.0)

    return {
        "n_runs":         n_runs,
        "method":         "bootstrap_with_replacement",
        "mean_pct":       round(float(rets.mean()),  2),
        "median_pct":     round(float(np.median(rets)), 2),
        "std_pct":        round(float(rets.std()),  2),
        "p5_pct":         round(float(np.percentile(rets,  5)), 2),
        "p25_pct":        round(float(np.percentile(rets, 25)), 2),
        "p75_pct":        round(float(np.percentile(rets, 75)), 2),
        "p95_pct":        round(float(np.percentile(rets, 95)), 2),
        "prob_pos_pct":   round(float((rets > 0).mean() * 100), 1),
        "best_pct":       round(float(rets.max()),   2),
        "worst_pct":      round(float(rets.min()),   2),
        "median_sharpe":  round(float(np.median(sharps)), 2),
        "median_dd_pct":  round(float(np.median(dds)),    2),
        "worst_dd_pct":   round(float(dds.min()),         2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 — Backtest condicionado a régimen
# ══════════════════════════════════════════════════════════════════════════════

def run_regime_filtered(
    self,
    signals_df: pd.DataFrame,
    *,
    vix_max:    float = 25.0,
    sma_days:   int   = 50,
    use_vix:    bool  = True,
    use_spy:    bool  = True,
) -> dict:
    """
    Variante del run() estándar que descarta señales fuera de régimen.

    Régimen "trending":
        SPY ≥ SMA(sma_days)  AND  VIX ≤ vix_max

    Útil para sistemas de momentum: el walk-forward del usuario mostró
    que momentum funciona en 2024 (tendencia) y falla en 2023 (lateral).
    """
    if signals_df is None or signals_df.empty:
        return {"error": "Sin señales", "num_trades": 0}

    import yfinance as yf

    start = pd.to_datetime(signals_df["date"].min())
    end   = pd.to_datetime(signals_df["date"].max()) + timedelta(days=10)
    ext   = (start - timedelta(days=sma_days * 3)).strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")

    # ── Descargar SPY y VIX una vez ───────────────────────────────────────
    spy = yf.download("SPY", start=ext, end=end_s,
                      auto_adjust=True, progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)

    vix = yf.download("^VIX", start=ext, end=end_s,
                      auto_adjust=True, progress=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)

    idx     = pd.date_range(start, end, freq="B")
    regime  = pd.Series(True, index=idx)

    if use_spy and not spy.empty:
        sma = spy["Close"].rolling(sma_days).mean()
        spy_ok = (spy["Close"] >= sma).reindex(idx, method="ffill").fillna(False)
        regime &= spy_ok
    if use_vix and not vix.empty:
        vix_ok = (vix["Close"] <= vix_max).reindex(idx, method="ffill").fillna(True)
        regime &= vix_ok

    reg_map = {str(d.date()): bool(v) for d, v in regime.items()}

    # ── Filtrar señales según régimen del día ─────────────────────────────
    df = signals_df.copy()
    df["_in_regime"] = df["date"].apply(
        lambda d: reg_map.get(str(pd.Timestamp(d).date()), True))
    df_in = df[df["_in_regime"]].drop(columns=["_in_regime"]).reset_index(drop=True)

    days_in    = int(regime.sum())
    days_total = len(regime)
    days_pct   = days_in / days_total * 100 if days_total > 0 else 0.0

    print(f"  [regime] {days_in}/{days_total} días en régimen "
          f"({days_pct:.1f}%) → {len(df_in)}/{len(signals_df)} señales válidas")

    if df_in.empty:
        return {"error": "Sin señales en régimen", "num_trades": 0}

    result = self.run(df_in)
    result["regime_days_in_pct"]  = round(days_pct, 1)
    result["regime_signals_kept"] = len(df_in)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Aplicación de los parches
# ══════════════════════════════════════════════════════════════════════════════

def patch_engine() -> None:
    """Aplica monkey-patches a OptionsBacktestV2."""
    OptionsBacktestV2.run_monte_carlo    = run_monte_carlo_bootstrap
    OptionsBacktestV2.run_regime_filtered = run_regime_filtered
    print("  [patch] Monte Carlo arreglado (bootstrap)")
    print("  [patch] Añadido run_regime_filtered()")


if __name__ == "__main__":
    patch_engine()
    print("\nLos parches están aplicados. Usa OptionsBacktestV2 normalmente.")
