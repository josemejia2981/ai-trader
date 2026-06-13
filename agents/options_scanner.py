"""
options_scanner.py  –  Scanner dinámico de opciones
=====================================================
Reemplaza el scanner original que analizaba activos fijos.
Ahora rastrea el mercado amplio y filtra automáticamente
contratos con:
  • Delta alto  (≥ 0.40 por defecto)
  • Theta bajo  (≤ -0.05 por defecto)
  • Precio asequible (prima ≤ $5.00 por defecto)
  • DTE largo  (≥ 30 días por defecto)
  • Open Interest decente (≥ 100)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)

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
    "max_theta":       -0.05,   # Theta máximo (más negativo = penalizado; -0.05 filtra theta muy agresivo)
    "max_premium":      5.00,   # Prima máxima en $ por contrato unitario (× 100 = costo real)
    "min_dte":           30,    # Días a vencimiento mínimos
    "max_dte":          180,    # Días a vencimiento máximos (largo plazo preferido)
    "min_open_interest": 50,    # OI mínimo para liquidez
    "min_volume":         5,    # Volumen mínimo del día
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

            # Columnas de Greeks (no siempre disponibles en yfinance)
            for col in ["delta", "theta", "gamma", "vega", "impliedVolatility"]:
                if col not in df.columns:
                    df[col] = np.nan

            df["dte"] = dte
            df["expiration"] = exp_str
            df["symbol"] = symbol

            # ── FILTROS ──────────────────────────────────────
            # Delta: si está disponible en la cadena
            if df["delta"].notna().any():
                df = df[df["delta"].abs() >= filters["min_delta"]]
            
            # Theta: si está disponible
            if df["theta"].notna().any():
                df = df[df["theta"] >= filters["max_theta"]]
            
            # Prima asequible
            df = df[df["lastPrice"] <= filters["max_premium"]]
            df = df[df["lastPrice"] > 0]
            
            # Liquidez
            df = df[df["openInterest"] >= filters["min_open_interest"]]
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
