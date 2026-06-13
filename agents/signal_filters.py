"""
signal_filters.py  –  Filtros de calidad para señales de opciones
══════════════════════════════════════════════════════════════════
Filtros implementados (vectorizados, sin loop por fila):

  1. Régimen de mercado  VIX ≤ vix_max  AND  SPY ≥ SMA(n)
  2. HV Rank             percentil 252d de la HV-20 < umbral   (proxy de IV Rank)
  3. Earnings window     sin señal ±N días alrededor de reportes
  4. Volumen mínimo      volumen diario ≥ vol_mult × media-20d

Uso típico
----------
    from signal_filters import apply_all_filters
    sig_filtered, stats = apply_all_filters(signals_df, "2023-01-01", "2024-12-31")

Requiere: pandas, numpy, yfinance
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import yfinance as yf
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# ─── Caché de datos (compartido por módulo) ───────────────────────────────────
_CACHE: dict = {}
_EARNINGS_CACHE: dict = {}


def _fetch(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Descarga OHLCV con caché en memoria."""
    key = (symbol, start, end)
    if key not in _CACHE:
        try:
            df = yf.download(symbol, start=start, end=end,
                             auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            _CACHE[key] = df
        except Exception as exc:
            logger.debug("_fetch %s: %s", symbol, exc)
            _CACHE[key] = pd.DataFrame()
    return _CACHE[key]


def _dk(dt) -> str:
    """Convierte cualquier fecha a string 'YYYY-MM-DD' para lookup rápido."""
    return str(pd.Timestamp(dt).date())


# ══════════════════════════════════════════════════════════════════════════════
# FILTRO 1: Régimen de mercado
# ══════════════════════════════════════════════════════════════════════════════

def _build_regime_series(
    start: str, end: str,
    vix_max: float = 25.0,
    sma_days: int = 50,
) -> dict:
    """
    Retorna {date_str: bool} — True = régimen OK para comprar opciones.
    Condición: VIX ≤ vix_max  Y  SPY ≥ SMA(sma_days)
    """
    ext = (pd.to_datetime(start) - timedelta(days=sma_days * 3)).strftime("%Y-%m-%d")
    spy   = _fetch("SPY", ext, end)
    vix_d = _fetch("^VIX", ext, end)

    idx = pd.date_range(start, end, freq="B")
    combined = pd.Series(True, index=idx)

    if not spy.empty:
        sma = spy["Close"].rolling(sma_days).mean()
        spy_ok = (spy["Close"] >= sma).reindex(idx, method="ffill").fillna(False)
        combined &= spy_ok

    if not vix_d.empty:
        vix_ok = (vix_d["Close"] <= vix_max).reindex(idx, method="ffill").fillna(True)
        combined &= vix_ok

    return {_dk(d): bool(v) for d, v in combined.items()}


# ══════════════════════════════════════════════════════════════════════════════
# FILTRO 2: HV Rank  (proxy de IV Rank)
# ══════════════════════════════════════════════════════════════════════════════

def _build_hv_rank_series(
    symbol: str, start: str, end: str,
    hv_window: int = 20,
    lookback: int = 252,
) -> dict:
    """
    Retorna {date_str: float} — percentil de la HV-20 en los últimos 252 días.
    Valor bajo  = volatilidad implícita barata  → buen momento para comprar opciones.
    Valor alto  = opciones caras, riesgo de IV-crush.
    """
    ext = (pd.to_datetime(start) - timedelta(days=lookback + hv_window + 30)).strftime("%Y-%m-%d")
    h = _fetch(symbol, ext, end)
    if h.empty or len(h) < hv_window + 30:
        return {}

    log_ret = np.log(h["Close"] / h["Close"].shift(1))
    hv = log_ret.rolling(hv_window).std() * np.sqrt(252) * 100

    def pct_rank(arr: np.ndarray) -> float:
        if len(arr) < 2 or np.isnan(arr[-1]):
            return 50.0
        return float(100.0 * np.mean(arr[-1] > arr[:-1]))

    rank_s = hv.rolling(lookback).apply(pct_rank, raw=True)
    idx = pd.date_range(start, end, freq="B")
    r = rank_s.reindex(idx, method="ffill").fillna(50.0)
    return {_dk(d): float(v) for d, v in r.items()}


# ══════════════════════════════════════════════════════════════════════════════
# FILTRO 3: Earnings window
# ══════════════════════════════════════════════════════════════════════════════

def _get_earnings_dates(symbol: str) -> list:
    """Fechas de earnings conocidas vía yfinance (puede estar vacío)."""
    if symbol in _EARNINGS_CACHE:
        return _EARNINGS_CACHE[symbol]
    dates = []
    try:
        cal = yf.Ticker(symbol).calendar
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            for v in cal.values.flatten():
                try:
                    dates.append(pd.Timestamp(v).normalize())
                except Exception:
                    pass
        elif isinstance(cal, dict):
            for v in cal.get("Earnings Date", []):
                try:
                    dates.append(pd.Timestamp(v).normalize())
                except Exception:
                    pass
    except Exception as exc:
        logger.debug("earnings %s: %s", symbol, exc)
    _EARNINGS_CACHE[symbol] = dates
    return dates


# ══════════════════════════════════════════════════════════════════════════════
# FILTRO 4: Volumen mínimo
# ══════════════════════════════════════════════════════════════════════════════

def _build_vol_ok_series(
    symbol: str, start: str, end: str,
    vol_mult: float = 1.2,
    avg_window: int = 20,
) -> dict:
    """Retorna {date_str: bool} — True si volumen del día ≥ vol_mult × media-20d."""
    ext = (pd.to_datetime(start) - timedelta(days=avg_window + 5)).strftime("%Y-%m-%d")
    h = _fetch(symbol, ext, end)
    if h.empty:
        return {}
    avg_vol = h["Volume"].rolling(avg_window).mean().shift(1)
    ok = (h["Volume"] >= avg_vol * vol_mult)
    idx = pd.date_range(start, end, freq="B")
    r = ok.reindex(idx, method="ffill").fillna(True)
    return {_dk(d): bool(v) for d, v in r.items()}


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def apply_all_filters(
    signals: pd.DataFrame,
    start: str,
    end: str,
    *,
    use_regime:   bool  = True,
    use_iv_rank:  bool  = True,
    use_earnings: bool  = True,
    use_volume:   bool  = True,
    vix_max:      float = 25.0,
    sma_regime:   int   = 50,
    iv_rank_max:  float = 50.0,
    earnings_window: int = 5,
    vol_mult:     float = 1.2,
    verbose:      bool  = True,
) -> tuple[pd.DataFrame, dict]:
    """
    Aplica los filtros de calidad en secuencia.

    Parámetros
    ----------
    signals : DataFrame con columnas ['date', 'symbol', 'direction']
    start, end : rango del backtest (para pre-calcular las series temporales)

    Retorna
    -------
    (df_filtrado, dict_con_estadísticas)
    """
    if signals is None or (hasattr(signals, "empty") and signals.empty):
        return pd.DataFrame(), {"original": 0, "final": 0}

    df = signals.copy()
    df["_dt"] = pd.to_datetime(df["date"])
    stats: dict = {"original": len(df)}

    # ── 1. Régimen ─────────────────────────────────────────────────────────
    if use_regime:
        if verbose:
            print(f"  [filter] Régimen (VIX≤{vix_max}, SPY≥SMA{sma_regime})...",
                  end=" ", flush=True)
        reg = _build_regime_series(start, end, vix_max=vix_max, sma_days=sma_regime)
        mask = df["_dt"].apply(lambda d: reg.get(_dk(d), True))
        df = df[mask].reset_index(drop=True)
        stats["after_regime"] = len(df)
        if verbose:
            print(f"{stats['original']} → {len(df)}")

    # ── 2. HV Rank ────────────────────────────────────────────────────────
    if use_iv_rank and not df.empty:
        if verbose:
            print(f"  [filter] HV Rank < {iv_rank_max} por símbolo...",
                  end=" ", flush=True)
        hv_maps: dict = {}
        for sym in df["symbol"].unique():
            hv_maps[sym] = _build_hv_rank_series(sym, start, end)
        ranks = [hv_maps.get(r.symbol, {}).get(_dk(r._dt), 50.0)
                 for _, r in df.iterrows()]
        df = df[[r < iv_rank_max for r in ranks]].reset_index(drop=True)
        stats["after_iv_rank"] = len(df)
        if verbose:
            prev = stats.get("after_regime", stats["original"])
            print(f"{prev} → {len(df)}")

    # ── 3. Earnings ───────────────────────────────────────────────────────
    if use_earnings and not df.empty:
        if verbose:
            print(f"  [filter] Earnings ±{earnings_window}d...",
                  end=" ", flush=True)
        e_map: dict = {s: _get_earnings_dates(s) for s in df["symbol"].unique()}
        keep = []
        for _, r in df.iterrows():
            ed = e_map.get(r.symbol, [])
            near = any(abs((r._dt - d).days) <= earnings_window for d in ed)
            keep.append(not near)
        df = df[keep].reset_index(drop=True)
        stats["after_earnings"] = len(df)
        if verbose:
            prev = stats.get("after_iv_rank", stats.get("after_regime", stats["original"]))
            print(f"{prev} → {len(df)}")

    # ── 4. Volumen ────────────────────────────────────────────────────────
    if use_volume and not df.empty:
        if verbose:
            print(f"  [filter] Volumen ≥ {vol_mult}× media-20d...",
                  end=" ", flush=True)
        vol_maps: dict = {s: _build_vol_ok_series(s, start, end, vol_mult=vol_mult)
                          for s in df["symbol"].unique()}
        keep = [bool(vol_maps.get(r.symbol, {}).get(_dk(r._dt), True))
                for _, r in df.iterrows()]
        df = df[keep].reset_index(drop=True)
        stats["after_volume"] = len(df)
        if verbose:
            prev = stats.get("after_earnings",
                   stats.get("after_iv_rank",
                   stats.get("after_regime", stats["original"])))
            print(f"{prev} → {len(df)}")

    df = df.drop(columns=["_dt"], errors="ignore").reset_index(drop=True)
    stats["final"] = len(df)
    return df, stats
