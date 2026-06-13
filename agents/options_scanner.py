"""
options_scanner.py  –  Scanner dinámico de opciones
=====================================================
Reemplaza el scanner original que analizaba activos fijos.
Ahora rastrea el mercado amplio y filtra automáticamente
contratos con:
  • Delta alto  (≥ 0.35 por defecto)
  • Theta bajo  (≥ -0.10 por defecto, decay lento)
  • Precio asequible (prima ≤ $8.00 por defecto)
  • DTE largo  (30-180 días por defecto)
  • Open Interest decente (≥ 10)

NOTA: yfinance NO entrega Delta ni Theta en su cadena de opciones.
Este scanner los CALCULA con Black-Scholes a partir del precio del
subyacente, strike, implied volatility y tiempo a vencimiento.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from math import log, sqrt, exp, pi
import time
import logging

logger = logging.getLogger(__name__)

# Tasa libre de riesgo aproximada (T-bill). Ajustable.
RISK_FREE_RATE = 0.045


# ─────────────────────────────────────────────
# BLACK-SCHOLES: calcular Greeks que yfinance NO da
# ─────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """CDF de la normal estándar (sin scipy)."""
    return 0.5 * (1.0 + _erf(x / sqrt(2.0)))


def _erf(x: float) -> float:
    """Aproximación de la función error (Abramowitz & Stegun 7.1.26)."""
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * exp(-x * x)
    return sign * y


def _norm_pdf(x: float) -> float:
    """PDF de la normal estándar."""
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def black_scholes_greeks(S, K, T, sigma, option_type="call", r=RISK_FREE_RATE):
    """
    Calcula delta y theta (diario) con Black-Scholes.
    
    S     = precio del subyacente
    K     = strike
    T     = tiempo a vencimiento en AÑOS (dte/365)
    sigma = implied volatility (ej. 0.45 = 45%)
    
    Retorna (delta, theta_diario, gamma, vega) o (nan,...) si no se puede calcular.
    """
    try:
        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return (np.nan, np.nan, np.nan, np.nan)

        d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)

        pdf_d1 = _norm_pdf(d1)

        if option_type == "call":
            delta = _norm_cdf(d1)
            theta = (-(S * pdf_d1 * sigma) / (2 * sqrt(T))
                     - r * K * exp(-r * T) * _norm_cdf(d2))
        else:  # put
            delta = _norm_cdf(d1) - 1.0
            theta = (-(S * pdf_d1 * sigma) / (2 * sqrt(T))
                     + r * K * exp(-r * T) * _norm_cdf(-d2))

        theta_daily = theta / 365.0
        gamma = pdf_d1 / (S * sigma * sqrt(T))
        vega = (S * pdf_d1 * sqrt(T)) / 100.0

        return (round(delta, 4), round(theta_daily, 4),
                round(gamma, 5), round(vega, 4))
    except Exception:
        return (np.nan, np.nan, np.nan, np.nan)

# ─────────────────────────────────────────────
# UNIVERSO DE ACTIVOS  (ampliable fácilmente)
# ─────────────────────────────────────────────

# S&P 500 muestra representativa por sector
SP500_SAMPLE = [
    # Tech
    "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","INTC","CRM",
    "ORCL","ADBE","QCOM","TXN","AVGO","MU","AMAT","LRCX","KLAC","SNPS",
    # Financials
    "JPM","BAC","WFC","GS","MS","C","BLK","AXP","V","MA",
    "COF","USB","PNC","TFC","SCHW","CME","ICE","SPGI","MCO",
    # Healthcare
    "UNH","JNJ","PFE","ABBV","LLY","MRK","TMO","ABT","DHR","AMGN",
    "GILD","BIIB","REGN","VRTX","ISRG","MDT","BSX","EW","ZTS",
    # Consumer
    "HD","WMT","COST","TGT","LOW","MCD","SBUX","NKE","PG","KO",
    "PEP","PM","MO","CL","EL","ULTA","LULU","YUM","DPZ",
    # Energy
    "XOM","CVX","COP","EOG","SLB","PSX","VLO","MPC","OXY","HAL",
    # Industrials
    "HON","CAT","DE","MMM","GE","LMT","RTX","NOC","BA","UPS","FDX",
    # ETFs con alta liquidez de opciones
    "SPY","QQQ","IWM","DIA","XLF","XLK","XLE","XLV","GLD","SLV",
    "ARKK","SOXX","XBI","IBB","EEM","EFA","TLT","HYG","VXX",
    # Populares en opciones (alta liquidez)
    "PLTR","SOFI","RIVN","LCID","MARA","RIOT","COIN","HOOD",
    "SNOW","DDOG","NET","CRWD","ZS","PANW","OKTA","MDB","SHOP",
    "SQ","PYPL","ROKU","UBER","LYFT","ABNB","DASH","RBLX",
    "GME","AMC","BBBY","BB","NOK","SNDL","CLOV","WISH",
]

# Elimina duplicados manteniendo orden
UNIVERSE = list(dict.fromkeys(SP500_SAMPLE))


# ─────────────────────────────────────────────
# FILTROS POR DEFECTO
# ─────────────────────────────────────────────
DEFAULT_FILTERS = {
    "min_delta":        0.35,   # Delta mínimo absoluto (calls: positivo, puts: se usa abs)
    "max_theta":       -0.10,   # Theta máximo (más negativo permite contratos; -0.10 = pierde hasta $10/día)
    "max_premium":      8.00,   # Prima máxima en $ por contrato unitario (× 100 = costo real)
    "min_dte":           30,    # Días a vencimiento mínimos
    "max_dte":          180,    # Días a vencimiento máximos (largo plazo preferido)
    "min_open_interest": 10,    # OI mínimo para liquidez
    "min_volume":         0,    # Volumen mínimo del día (0 = no filtrar; opciones largas suelen tener vol bajo)
    "option_type":     "call",  # "call", "put" o "both"
    "max_symbols":       80,    # Cuántos símbolos escanear por corrida
}


# ─────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────

def get_liquid_symbols(universe: list, limit: int = 80) -> list:
    """
    Filtra el universo buscando activos con precio > $5
    y volumen promedio razonable para que tengan opciones líquidas.
    Devuelve hasta `limit` símbolos.
    """
    liquid = []
    logger.info(f"Filtrando {len(universe)} símbolos para encontrar los más líquidos…")
    
    for sym in universe:
        if len(liquid) >= limit:
            break
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            price = getattr(info, 'last_price', None) or getattr(info, 'regularMarketPrice', None)
            if price and price >= 5:
                liquid.append(sym)
        except Exception:
            pass
        time.sleep(0.05)  # pequeño throttle
    
    logger.info(f"  → {len(liquid)} símbolos líquidos encontrados")
    return liquid


def score_contract(row: pd.Series) -> float:
    """
    Puntaje compuesto para ordenar los mejores contratos.
    Mayor puntaje = mejor contrato.
    
    Criterios:
      + Delta alto (más gamma potential)
      + Theta bajo en valor absoluto (decay lento)
      + Premium bajo (asequible)
      + DTE largo (más tiempo)
      + OI alto (liquidez)
    """
    delta = abs(row.get("delta", 0) or 0)
    theta = abs(row.get("theta", 0) or 0)
    premium = row.get("lastPrice", 0) or 0
    dte = row.get("dte", 0) or 0
    oi = row.get("openInterest", 0) or 0

    if premium <= 0:
        return 0

    # Relación delta/theta (queremos delta alto y theta bajo)
    dt_ratio = delta / (theta + 0.001)
    
    # Normalizar: puntaje base
    score = (
        delta * 3.0          # Peso alto para delta
        + dt_ratio * 0.5     # Buen ratio delta/theta
        + (dte / 30) * 0.3   # Más DTE = mejor
        - premium * 0.2      # Penalizar prima alta
        + np.log1p(oi) * 0.1 # Premio por liquidez
    )
    return round(score, 4)


def fetch_options_for_symbol(
    symbol: str,
    filters: dict,
    option_type: str = "call"
) -> pd.DataFrame:
    """
    Obtiene cadena de opciones de un símbolo y aplica filtros.
    Retorna DataFrame con los contratos que pasan los filtros.
    """
    results = []
    today = datetime.now().date()
    
    try:
        ticker = yf.Ticker(symbol)
        exps = ticker.options
        if not exps:
            return pd.DataFrame()

        # Precio del subyacente (necesario para Black-Scholes)
        try:
            fi = ticker.fast_info
            spot = getattr(fi, "last_price", None) or getattr(fi, "regularMarketPrice", None)
        except Exception:
            spot = None
        if not spot or spot <= 0:
            try:
                spot = ticker.history(period="1d")["Close"].iloc[-1]
            except Exception:
                spot = None

        for exp_str in exps:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days

            # Filtro de DTE
            if dte < filters["min_dte"] or dte > filters["max_dte"]:
                continue

            try:
                chain = ticker.option_chain(exp_str)
            except Exception:
                continue

            # Seleccionar calls, puts o ambos
            frames = []
            if option_type in ("call", "both"):
                df_c = chain.calls.copy()
                df_c["option_type"] = "call"
                frames.append(df_c)
            if option_type in ("put", "both"):
                df_p = chain.puts.copy()
                df_p["option_type"] = "put"
                frames.append(df_p)

            if not frames:
                continue

            df = pd.concat(frames, ignore_index=True)

            df["dte"] = dte
            df["expiration"] = exp_str
            df["symbol"] = symbol

            # Asegurar que existe impliedVolatility
            if "impliedVolatility" not in df.columns:
                df["impliedVolatility"] = np.nan

            # ── CALCULAR GREEKS con Black-Scholes ────────────
            # yfinance NO entrega delta/theta, así que los calculamos
            T = dte / 365.0
            deltas, thetas, gammas, vegas = [], [], [], []
            for _, r in df.iterrows():
                K = r.get("strike", np.nan)
                sigma = r.get("impliedVolatility", np.nan)
                opt = r.get("option_type", "call")
                if spot and K and sigma and not pd.isna(sigma) and sigma > 0:
                    d, th, g, v = black_scholes_greeks(spot, K, T, sigma, opt)
                else:
                    d, th, g, v = (np.nan, np.nan, np.nan, np.nan)
                deltas.append(d); thetas.append(th); gammas.append(g); vegas.append(v)

            df["delta"] = deltas
            df["theta"] = thetas
            df["gamma"] = gammas
            df["vega"]  = vegas
            df["spot"]  = spot

            # ── FILTROS ──────────────────────────────────────
            # Delta (ahora SÍ existe gracias a Black-Scholes)
            if df["delta"].notna().any():
                df = df[df["delta"].abs() >= filters["min_delta"]]

            # Theta: queremos decay lento → theta >= max_theta (ej. >= -0.10)
            if df["theta"].notna().any():
                df = df[df["theta"] >= filters["max_theta"]]

            # Prima asequible
            df = df[df["lastPrice"] <= filters["max_premium"]]
            df = df[df["lastPrice"] > 0]

            # Liquidez
            df = df[df["openInterest"].fillna(0) >= filters["min_open_interest"]]
            if filters.get("min_volume", 0) > 0:
                df = df[df["volume"].fillna(0) >= filters["min_volume"]]

            if not df.empty:
                results.append(df)

            time.sleep(0.1)  # throttle entre expirations

    except Exception as e:
        logger.warning(f"Error procesando {symbol}: {e}")
        return pd.DataFrame()

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    return combined


# ─────────────────────────────────────────────
# SCANNER PRINCIPAL
# ─────────────────────────────────────────────

def scan_market(
    filters: dict = None,
    custom_symbols: list = None,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Escanea el mercado completo buscando los mejores contratos de opciones.
    
    Parámetros
    ----------
    filters : dict
        Diccionario de filtros. Si None, usa DEFAULT_FILTERS.
    custom_symbols : list
        Lista custom de símbolos. Si None, usa UNIVERSE.
    progress_callback : callable(symbol, idx, total)
        Función llamada en cada paso para actualizar UI (ej. Streamlit progress bar).
    
    Retorna
    -------
    pd.DataFrame con todos los contratos que pasan los filtros,
    ordenados por score descendente.
    """
    if filters is None:
        filters = DEFAULT_FILTERS.copy()

    # Símbolos a escanear
    symbols = custom_symbols if custom_symbols else UNIVERSE
    limit = filters.get("max_symbols", 80)
    symbols = symbols[:limit]

    logger.info(f"🔍 Iniciando scan de {len(symbols)} símbolos…")
    logger.info(f"   Filtros: delta≥{filters['min_delta']} | theta≥{filters['max_theta']} | "
                f"prima≤${filters['max_premium']} | DTE {filters['min_dte']}-{filters['max_dte']}d")

    all_results = []
    option_type = filters.get("option_type", "call")
    total = len(symbols)

    for idx, sym in enumerate(symbols, 1):
        if progress_callback:
            progress_callback(sym, idx, total)

        df = fetch_options_for_symbol(sym, filters, option_type)
        if not df.empty:
            all_results.append(df)
            logger.info(f"  ✅ {sym}: {len(df)} contratos encontrados")
        else:
            logger.debug(f"  ⬜ {sym}: sin contratos que pasen los filtros")

        time.sleep(0.15)  # throttle general

    if not all_results:
        logger.warning("⚠️  Ningún contrato pasó los filtros. Considera relajar los parámetros.")
        return pd.DataFrame()

    final = pd.concat(all_results, ignore_index=True)

    # ── SCORE y ORDENAMIENTO ─────────────────
    final["score"] = final.apply(score_contract, axis=1)
    final = final.sort_values("score", ascending=False).reset_index(drop=True)

    # ── COLUMNAS FINALES ─────────────────────
    cols_order = [
        "symbol", "option_type", "expiration", "dte",
        "strike", "lastPrice", "delta", "theta", "gamma", "vega",
        "impliedVolatility", "openInterest", "volume",
        "bid", "ask", "contractSymbol", "score"
    ]
    cols_present = [c for c in cols_order if c in final.columns]
    final = final[cols_present]

    # Renombrar para claridad
    final = final.rename(columns={
        "lastPrice":         "prima",
        "impliedVolatility": "IV",
        "openInterest":      "OI",
        "contractSymbol":    "contrato",
    })

    logger.info(f"✨ Scan completo: {len(final)} contratos encontrados en {final['symbol'].nunique()} activos")
    return final


# ─────────────────────────────────────────────
# FUNCIÓN DE CONVENIENCIA PARA STREAMLIT
# ─────────────────────────────────────────────

def get_top_contracts(n: int = 20, filters: dict = None, custom_symbols: list = None) -> pd.DataFrame:
    """Retorna los N mejores contratos del scan."""
    df = scan_market(filters=filters, custom_symbols=custom_symbols)
    if df.empty:
        return df
    return df.head(n)


def get_top_by_symbol(df: pd.DataFrame, n_per_symbol: int = 2) -> pd.DataFrame:
    """Del resultado del scan, devuelve los N mejores contratos por símbolo."""
    if df.empty:
        return df
    return (
        df.groupby("symbol")
          .head(n_per_symbol)
          .sort_values("score", ascending=False)
          .reset_index(drop=True)
    )
