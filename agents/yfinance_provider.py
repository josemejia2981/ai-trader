"""
yfinance_provider.py  –  Provider de datos para backtest (GRATIS)
==================================================================
Reconstruye cadenas históricas de opciones usando:
  • Precio histórico REAL del subyacente (yfinance, gratis, años de historial)
  • Volatilidad histórica realizada (calculada de los retornos)
  • Precio teórico de cada opción vía Black-Scholes

LIMITACIÓN HONESTA:
  Esto es una APROXIMACIÓN. La dirección del precio es real, pero la IV
  y el spread son estimados. No captura IV crush tras earnings ni saltos
  reales de volatilidad. Tiende a dar resultados algo optimistas.
  Sirve para validar la LÓGICA de tu estrategia, no para cifras exactas.

USO con el motor de backtest:
    from backtest_engine import OptionsBacktest, BacktestConfig
    from yfinance_provider import make_yfinance_provider

    provider = make_yfinance_provider(vol_window=30, spread_pct=0.05)
    bt = OptionsBacktest(BacktestConfig())
    bt.set_data_provider(provider)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from math import log, sqrt, exp, pi
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.045


# ─────────────────────────────────────────────
# BLACK-SCHOLES (precio + greeks)
# ─────────────────────────────────────────────

def _erf(x):
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * exp(-x * x)
    return sign * y

def _norm_cdf(x):
    return 0.5 * (1.0 + _erf(x / sqrt(2.0)))

def _norm_pdf(x):
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def bs_price_and_greeks(S, K, T, sigma, option_type="call", r=RISK_FREE_RATE):
    """Retorna (precio, delta, theta_diario) con Black-Scholes."""
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return (np.nan, np.nan, np.nan)
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    pdf_d1 = _norm_pdf(d1)

    if option_type == "call":
        price = S * _norm_cdf(d1) - K * exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta = (-(S * pdf_d1 * sigma) / (2 * sqrt(T))
                 - r * K * exp(-r * T) * _norm_cdf(d2))
    else:
        price = K * exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
        theta = (-(S * pdf_d1 * sigma) / (2 * sqrt(T))
                 + r * K * exp(-r * T) * _norm_cdf(-d2))

    return (round(max(price, 0.0), 4), round(delta, 4), round(theta / 365.0, 4))


# ─────────────────────────────────────────────
# CACHÉ DE PRECIOS HISTÓRICOS
# ─────────────────────────────────────────────
# Para no descargar el mismo histórico una y otra vez durante el backtest.

_PRICE_CACHE = {}

def _get_price_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Descarga (y cachea) el histórico diario del subyacente."""
    key = (symbol, start, end)
    if key in _PRICE_CACHE:
        return _PRICE_CACHE[key]
    try:
        df = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
        if not df.empty:
            df.index = pd.to_datetime(df.index).tz_localize(None)
        _PRICE_CACHE[key] = df
        return df
    except Exception as e:
        logger.warning(f"Error descargando histórico de {symbol}: {e}")
        return pd.DataFrame()


def preload_history(symbols: list, start: str, end: str):
    """
    Pre-descarga el histórico de todos los símbolos de una vez.
    Llama esto ANTES de correr el backtest para acelerar mucho.
    Añade margen de días al inicio para calcular la volatilidad.
    """
    # Restamos ~90 días al inicio para tener ventana de volatilidad
    start_dt = (pd.to_datetime(start) - timedelta(days=120)).strftime("%Y-%m-%d")
    for sym in symbols:
        _get_price_history(sym, start_dt, end)
        logger.info(f"  ✓ Histórico precargado: {sym}")


# ─────────────────────────────────────────────
# VOLATILIDAD HISTÓRICA REALIZADA
# ─────────────────────────────────────────────

def realized_volatility(prices: pd.Series, window: int = 30) -> float:
    """
    Volatilidad anualizada de los últimos `window` días.
    Es la mejor estimación de IV que podemos hacer sin datos de opciones.
    """
    if len(prices) < window + 1:
        window = max(len(prices) - 1, 2)
    returns = np.log(prices / prices.shift(1)).dropna()
    if len(returns) < 2:
        return 0.30  # fallback razonable
    vol = returns.tail(window).std() * sqrt(252)  # anualizar
    return float(max(vol, 0.05))  # piso mínimo


# ─────────────────────────────────────────────
# EXPIRACIONES Y STRIKES FIJOS (anclados a calendario)
# ─────────────────────────────────────────────

def _third_friday(year: int, month: int):
    """Tercer viernes del mes (día estándar de vencimiento de opciones mensuales)."""
    # Día 1 del mes
    d = datetime(year, month, 1)
    # weekday(): lunes=0 ... viernes=4
    first_friday = 1 + (4 - d.weekday()) % 7
    third = first_friday + 14
    return datetime(year, month, third)


def _monthly_expirations(from_date, lookahead_days: int):
    """Lista de terceros viernes desde from_date hasta lookahead_days adelante."""
    exps = []
    d = pd.to_datetime(from_date)
    year, month = d.year, d.month
    end = d + timedelta(days=lookahead_days)
    for _ in range(12):  # como máximo 12 meses adelante
        tf = _third_friday(year, month)
        if tf > end:
            break
        if tf >= d:
            exps.append(tf)
        # avanzar un mes
        month += 1
        if month > 12:
            month = 1
            year += 1
    return exps


def _round_strike(price: float) -> float:
    """
    Redondea a un strike 'realista' según el nivel de precio.
    Esto evita que el strike cambie cada día (debe ser fijo por contrato).
    """
    if price < 25:
        return round(price * 2) / 2        # pasos de $0.50
    elif price < 200:
        return float(round(price))          # pasos de $1
    else:
        return float(round(price / 5) * 5)  # pasos de $5


# ─────────────────────────────────────────────
# PROVIDER PRINCIPAL
# ─────────────────────────────────────────────

def make_yfinance_provider(
    vol_window: int = 30,
    spread_pct: float = 0.05,
    strikes_around: int = 6,
    strike_step_pct: float = 0.025,
    expirations_dte: list = None,
):
    """
    Crea un provider(symbol, date) que reconstruye una cadena de opciones
    para esa fecha histórica.

    Parámetros
    ----------
    vol_window : int
        Días para calcular la volatilidad histórica realizada (usada como IV).
    spread_pct : float
        Spread bid/ask simulado (0.05 = 5% alrededor del precio teórico).
    strikes_around : int
        Cuántos strikes generar por encima y por debajo del precio actual.
    strike_step_pct : float
        Separación entre strikes como % del precio (0.025 = 2.5%).
    expirations_dte : list
        Lista de DTEs a generar (ej. [35, 45, 60]). Default: [35, 45, 60].
    """
    if expirations_dte is None:
        expirations_dte = [35, 45, 60]

    def provider(symbol: str, date: str) -> pd.DataFrame:
        cur = pd.to_datetime(date)

        # Histórico hasta la fecha (con margen previo para volatilidad)
        start = (cur - timedelta(days=vol_window * 3 + 30)).strftime("%Y-%m-%d")
        end = (cur + timedelta(days=1)).strftime("%Y-%m-%d")
        hist = _get_price_history(symbol, start, end)

        if hist.empty:
            return pd.DataFrame()

        # Precio del subyacente en (o justo antes de) la fecha
        hist_until = hist[hist.index <= cur]
        if hist_until.empty:
            return pd.DataFrame()
        spot = float(hist_until["Close"].iloc[-1])

        # Volatilidad histórica realizada como proxy de IV
        sigma = realized_volatility(hist_until["Close"], window=vol_window)

        # Expiraciones ANCLADAS a fechas fijas (terceros viernes mensuales),
        # igual que las opciones reales. Esto es CLAVE: así un contrato con
        # vencimiento 2024-03-15 es el MISMO contrato cualquier día que se
        # consulte, y su DTE solo baja con el tiempo (permite cerrarlo).
        candidate_exps = _monthly_expirations(cur, max(expirations_dte) + 31)

        rows = []
        for exp_date in candidate_exps:
            dte = (exp_date - cur).days
            # Solo expiraciones dentro del rango de interés
            if dte < min(expirations_dte) - 20 or dte > max(expirations_dte) + 31:
                continue
            if dte <= 0:
                continue
            exp_str = exp_date.strftime("%Y%m%d")
            T = dte / 365.0

            # Strikes alrededor del precio actual, en pasos FIJOS de calendario
            # (anclados a múltiplos para que el strike no varíe día a día)
            for i in range(-strikes_around, strikes_around + 1):
                raw = spot * (1 + i * strike_step_pct)
                strike = _round_strike(raw)
                if strike <= 0:
                    continue

                for opt in ["call", "put"]:
                    price, delta, theta = bs_price_and_greeks(spot, strike, T, sigma, opt)
                    if pd.isna(price) or price <= 0:
                        continue

                    bid = round(price * (1 - spread_pct), 2)
                    ask = round(price * (1 + spread_pct), 2)

                    rows.append({
                        "symbol":            symbol,
                        "strike":            strike,
                        "option_type":       opt,
                        "expiration":        exp_str,
                        "dte":               dte,
                        "bid":               max(bid, 0.01),
                        "ask":               max(ask, 0.02),
                        "last":              price,
                        "volume":            500,    # sintético: asumimos líquido
                        "openInterest":      1000,   # sintético: asumimos líquido
                        "delta":             delta,
                        "theta":             theta,
                        "impliedVolatility": round(sigma, 4),
                        "spot":              round(spot, 2),
                    })

        return pd.DataFrame(rows)

    return provider


# ─────────────────────────────────────────────
# GENERADOR DE SEÑALES SIMPLE (para probar)
# ─────────────────────────────────────────────

def generate_sma_crossover_signals(
    symbols: list,
    start: str,
    end: str,
    fast: int = 20,
    slow: int = 50,
) -> pd.DataFrame:
    """
    Genera señales de dirección con cruce de medias móviles:
      • Cruce alcista (rápida cruza por encima de lenta) → "bullish"
      • Cruce bajista (rápida cruza por debajo de lenta) → "bearish"

    Esto es solo para PROBAR el motor. Más adelante se reemplaza por
    tus señales reales de technical.py / signal.py.

    Retorna DataFrame con columnas [date, symbol, direction].
    """
    all_signals = []
    start_dt = (pd.to_datetime(start) - timedelta(days=slow * 2)).strftime("%Y-%m-%d")

    for sym in symbols:
        hist = _get_price_history(sym, start_dt, end)
        if hist.empty or len(hist) < slow + 5:
            continue

        close = hist["Close"]
        sma_fast = close.rolling(fast).mean()
        sma_slow = close.rolling(slow).mean()

        # Detectar cruces
        diff = sma_fast - sma_slow
        sign = np.sign(diff)
        cross = sign.diff()  # +2 = cruce alcista, -2 = cruce bajista

        for date, val in cross.items():
            d = pd.to_datetime(date)
            if d < pd.to_datetime(start):
                continue
            if val > 0:
                all_signals.append({"date": d.strftime("%Y-%m-%d"),
                                    "symbol": sym, "direction": "bullish"})
            elif val < 0:
                all_signals.append({"date": d.strftime("%Y-%m-%d"),
                                    "symbol": sym, "direction": "bearish"})

    df = pd.DataFrame(all_signals)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ─────────────────────────────────────────────
# EJEMPLO DE USO COMPLETO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from backtest_engine import OptionsBacktest, BacktestConfig

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMD", "TSLA"]
    START = "2024-01-01"
    END = "2024-12-31"

    print("📥 Precargando históricos…")
    preload_history(SYMBOLS, START, END)

    print("\n📊 Generando señales (cruce SMA 20/50)…")
    signals = generate_sma_crossover_signals(SYMBOLS, START, END, fast=20, slow=50)
    print(f"   → {len(signals)} señales generadas")
    if not signals.empty:
        print(signals.head(10).to_string(index=False))

    print("\n⚙️  Configurando backtest (5% riesgo, +50%/-30%)…")
    cfg = BacktestConfig(
        initial_capital=10_000,
        risk_per_trade_pct=0.05,
        take_profit_pct=0.50,
        stop_loss_pct=0.30,
    )
    bt = OptionsBacktest(cfg)
    bt.set_data_provider(make_yfinance_provider(vol_window=30, spread_pct=0.05))

    # Rango de fechas hábiles
    fechas = pd.date_range(START, END, freq="B").strftime("%Y-%m-%d").tolist()

    print("\n🚀 Corriendo backtest…\n")
    resultados = bt.run(signals, fechas)

    print("\n" + "=" * 55)
    print("RESULTADOS (yfinance + Black-Scholes, APROXIMADO)")
    print("=" * 55)
    for k, v in resultados.items():
        if k not in ("equity_curve", "trades"):
            print(f"  {k:.<28} {v}")
    print("\n⚠️  Recuerda: precios de opciones reconstruidos, no reales.")
