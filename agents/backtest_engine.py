"""
backtest_engine.py  –  Motor de Backtest Realista de Opciones
==============================================================
Diseñado para datos de ThetaData (plan gratuito end-of-day).

Estrategia configurada:
  • ENTRADA: compra calls (señal alcista) o puts (señal bajista)
  • SALIDA:  +50% ganancia / -30% pérdida (configurable) o al vencimiento
  • RIESGO:  % del capital por trade (default 5%, configurable)
  • COSTOS:  comisiones + spread bid/ask incluidos (CRÍTICO para realismo)

IMPORTANTE — Honestidad del backtest:
  Un backtest que ignora spread y comisiones MIENTE a tu favor.
  Este motor los incluye. Aun así, "rentable en backtest" NO garantiza
  rentable en vivo (slippage, eventos, cambios de régimen de mercado).
  Úsalo para descartar estrategias malas, no para confiar ciegamente.

REQUISITOS:
  1. Cuenta en thetadata.net (plan Free = end-of-day)
  2. ThetaTerminal corriendo localmente (intermediario)
  3. pip install thetadata pandas numpy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CONFIGURACIÓN DE LA ESTRATEGIA
# ─────────────────────────────────────────────

@dataclass
class BacktestConfig:
    # Capital
    initial_capital: float = 10_000.0
    risk_per_trade_pct: float = 0.05      # 5% del capital por trade (AGRESIVO)

    # Reglas de salida
    take_profit_pct: float = 0.50         # +50% → cerrar ganando
    stop_loss_pct: float = 0.30           # -30% → cerrar perdiendo
    exit_at_dte: int = 5                  # cerrar si quedan ≤ 5 DTE (evitar gamma/decay final)

    # Selección de contrato
    target_delta: float = 0.45            # delta objetivo (ej 0.45 = ligeramente OTM/ATM)
    min_dte_entry: int = 25               # DTE mínimo al entrar
    max_dte_entry: int = 70               # DTE máximo al entrar (margen para expiraciones mensuales)
    min_premium: float = 0.50             # prima mínima (evita contratos "lotería" sin valor)
    max_contracts: int = 50               # tope de contratos por trade (evita over-sizing)

    # COSTOS REALES (lo que hace honesto al backtest)
    commission_per_contract: float = 0.65 # comisión por contrato (típico retail)
    use_bid_ask_spread: bool = True       # comprar al ASK, vender al BID (realista)
    slippage_pct: float = 0.0             # slippage adicional opcional

    # Liquidez mínima para considerar un contrato operable
    min_open_interest: int = 100
    min_volume: int = 10


# ─────────────────────────────────────────────
# REPRESENTACIÓN DE UN TRADE
# ─────────────────────────────────────────────

@dataclass
class Trade:
    symbol: str
    option_type: str          # "call" o "put"
    strike: float
    expiration: str
    entry_date: str
    entry_price: float        # precio pagado (incluye ASK + comisión)
    contracts: int
    capital_used: float

    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    is_open: bool = True


# ─────────────────────────────────────────────
# MOTOR DE BACKTEST
# ─────────────────────────────────────────────

class OptionsBacktest:
    """
    Motor de backtest para estrategias direccionales de opciones.

    Requiere un 'data_provider' que entregue cadenas históricas.
    Por defecto está pensado para ThetaData, pero acepta cualquier
    función que cumpla la interfaz (ver `set_data_provider`).
    """

    def __init__(self, config: BacktestConfig = None):
        self.cfg = config or BacktestConfig()
        self.capital = self.cfg.initial_capital
        self.equity_curve = []      # [(fecha, capital)]
        self.trades = []            # lista de Trade cerrados
        self.open_trades = []       # Trades abiertos
        self._data_provider = None  # función que entrega cadenas

    # ── Conexión de datos ──────────────────────
    def set_data_provider(self, provider: Callable):
        """
        provider(symbol, date) → DataFrame con columnas:
          strike, option_type, expiration, dte, bid, ask, last, delta,
          openInterest, volume, impliedVolatility
        """
        self._data_provider = provider

    # ── Selección de contrato ──────────────────
    def _pick_contract(self, chain: pd.DataFrame, direction: str) -> Optional[pd.Series]:
        """Elige el contrato más cercano al delta objetivo, líquido y con DTE válido."""
        if chain is None or chain.empty:
            return None

        opt_type = "call" if direction == "bullish" else "put"
        df = chain[chain["option_type"] == opt_type].copy()

        # Filtros de DTE y liquidez
        df = df[(df["dte"] >= self.cfg.min_dte_entry) &
                (df["dte"] <= self.cfg.max_dte_entry)]
        df = df[df["openInterest"].fillna(0) >= self.cfg.min_open_interest]
        df = df[df["volume"].fillna(0) >= self.cfg.min_volume]

        if df.empty:
            return None

        # Delta objetivo (puts tienen delta negativo → usar abs)
        df["delta_dist"] = (df["delta"].abs() - self.cfg.target_delta).abs()
        df = df.sort_values("delta_dist")

        return df.iloc[0]

    # ── Precio de compra/venta con costos ──────
    def _entry_price(self, contract: pd.Series) -> float:
        """Precio de ENTRADA = comprar al ASK (peor caso realista) + slippage."""
        if self.cfg.use_bid_ask_spread and not pd.isna(contract.get("ask")):
            px = contract["ask"]
        else:
            px = contract["last"]
        px *= (1 + self.cfg.slippage_pct)
        return px

    def _exit_price(self, contract: pd.Series) -> float:
        """Precio de SALIDA = vender al BID (peor caso realista) - slippage."""
        if self.cfg.use_bid_ask_spread and not pd.isna(contract.get("bid")):
            px = contract["bid"]
        else:
            px = contract["last"]
        px *= (1 - self.cfg.slippage_pct)
        return max(px, 0.0)

    # ── Abrir un trade ─────────────────────────
    def _open_trade(self, symbol: str, direction: str, date: str, chain: pd.DataFrame):
        contract = self._pick_contract(chain, direction)
        if contract is None:
            logger.debug(f"{date} {symbol}: sin contrato válido")
            return

        entry_px = self._entry_price(contract)
        if entry_px < self.cfg.min_premium:
            logger.debug(f"{date} {symbol}: prima ${entry_px:.2f} < mínimo ${self.cfg.min_premium}")
            return

        # Tamaño de posición según riesgo
        risk_capital = self.capital * self.cfg.risk_per_trade_pct
        cost_per_contract = entry_px * 100 + self.cfg.commission_per_contract
        n_contracts = int(risk_capital // cost_per_contract)
        n_contracts = min(n_contracts, self.cfg.max_contracts)  # tope anti over-sizing

        if n_contracts < 1:
            logger.debug(f"{date} {symbol}: capital insuficiente para 1 contrato "
                         f"(necesita ${cost_per_contract:.0f}, disponible ${risk_capital:.0f})")
            return

        total_cost = n_contracts * cost_per_contract
        if total_cost > self.capital:
            return

        self.capital -= total_cost

        trade = Trade(
            symbol=symbol,
            option_type=contract["option_type"],
            strike=float(contract["strike"]),
            expiration=str(contract["expiration"]),
            entry_date=date,
            entry_price=entry_px,
            contracts=n_contracts,
            capital_used=total_cost,
        )
        self.open_trades.append(trade)
        logger.info(f"📈 {date} ABRIR {symbol} {contract['option_type']} "
                    f"strike {contract['strike']} x{n_contracts} @ ${entry_px:.2f}")

    # ── Evaluar salidas ────────────────────────
    def _check_exits(self, date: str, chains_by_symbol: dict):
        still_open = []
        for trade in self.open_trades:
            chain = chains_by_symbol.get(trade.symbol)
            if chain is None or chain.empty:
                still_open.append(trade)
                continue

            # Buscar el contrato exacto en la cadena de hoy
            match = chain[
                (chain["option_type"] == trade.option_type) &
                (np.isclose(chain["strike"], trade.strike)) &
                (chain["expiration"].astype(str) == trade.expiration)
            ]
            if match.empty:
                still_open.append(trade)
                continue

            contract = match.iloc[0]
            cur_price = self._exit_price(contract)
            dte = int(contract.get("dte", 0))

            pnl_pct = (cur_price - trade.entry_price) / trade.entry_price

            exit_reason = None
            if pnl_pct >= self.cfg.take_profit_pct:
                exit_reason = "take_profit"
            elif pnl_pct <= -self.cfg.stop_loss_pct:
                exit_reason = "stop_loss"
            elif dte <= self.cfg.exit_at_dte:
                exit_reason = "dte_exit"

            if exit_reason:
                self._close_trade(trade, date, cur_price, exit_reason)
            else:
                still_open.append(trade)

        self.open_trades = still_open

    def _close_trade(self, trade: Trade, date: str, exit_px: float, reason: str):
        proceeds = exit_px * 100 * trade.contracts - self.cfg.commission_per_contract * trade.contracts
        self.capital += max(proceeds, 0.0)

        trade.exit_date = date
        trade.exit_price = exit_px
        trade.exit_reason = reason
        trade.pnl = proceeds - trade.capital_used
        trade.pnl_pct = trade.pnl / trade.capital_used if trade.capital_used else 0
        trade.is_open = False

        self.trades.append(trade)
        emoji = "✅" if trade.pnl > 0 else "❌"
        logger.info(f"{emoji} {date} CERRAR {trade.symbol} {trade.option_type} "
                    f"({reason}) PnL ${trade.pnl:,.0f} ({trade.pnl_pct:+.1%})")

    # ── Bucle principal ────────────────────────
    def run(self, signals: pd.DataFrame, date_range: list):
        """
        signals: DataFrame con columnas [date, symbol, direction]
                 direction ∈ {"bullish", "bearish"}
        date_range: lista ordenada de fechas (str 'YYYY-MM-DD') a simular
        """
        if self._data_provider is None:
            raise RuntimeError(
                "Falta el data_provider. Llama a set_data_provider() con la función "
                "que conecta a ThetaData. Ver thetadata_provider() abajo."
            )

        signals_by_date = {}
        for _, s in signals.iterrows():
            signals_by_date.setdefault(s["date"], []).append((s["symbol"], s["direction"]))

        for date in date_range:
            # Símbolos que necesitamos hoy (señales nuevas + trades abiertos)
            symbols_today = set(sym for sym, _ in signals_by_date.get(date, []))
            symbols_today |= set(t.symbol for t in self.open_trades)

            # Descargar cadenas de hoy
            chains = {}
            for sym in symbols_today:
                try:
                    chains[sym] = self._data_provider(sym, date)
                except Exception as e:
                    logger.warning(f"{date} {sym}: error de datos: {e}")
                    chains[sym] = pd.DataFrame()

            # 1) Revisar salidas primero
            self._check_exits(date, chains)

            # 2) Abrir nuevas posiciones
            for sym, direction in signals_by_date.get(date, []):
                self._open_trade(sym, direction, date, chains.get(sym, pd.DataFrame()))

            # 3) Registrar equity (capital + valor de posiciones abiertas)
            open_value = self._mark_to_market(chains)
            self.equity_curve.append((date, self.capital + open_value))

        # Cerrar lo que quede abierto al final
        return self.results()

    def _mark_to_market(self, chains: dict) -> float:
        """Valor actual de las posiciones abiertas (para la curva de equity)."""
        total = 0.0
        for trade in self.open_trades:
            chain = chains.get(trade.symbol)
            if chain is None or chain.empty:
                total += trade.capital_used  # sin dato: usar costo
                continue
            match = chain[
                (chain["option_type"] == trade.option_type) &
                (np.isclose(chain["strike"], trade.strike)) &
                (chain["expiration"].astype(str) == trade.expiration)
            ]
            if not match.empty:
                px = self._exit_price(match.iloc[0])
                total += px * 100 * trade.contracts
            else:
                total += trade.capital_used
        return total

    # ── Métricas ───────────────────────────────
    def results(self) -> dict:
        closed = [t for t in self.trades]
        if not closed:
            return {"error": "No se ejecutaron trades. Revisa señales, fechas y datos."}

        pnls = [t.pnl for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        total_pnl = sum(pnls)
        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")

        # Drawdown máximo
        eq = pd.DataFrame(self.equity_curve, columns=["date", "equity"])
        eq["peak"] = eq["equity"].cummax()
        eq["dd"] = (eq["equity"] - eq["peak"]) / eq["peak"]
        max_dd = eq["dd"].min() if not eq.empty else 0

        final_capital = self.capital + self._mark_to_market({})
        total_return = (final_capital - self.cfg.initial_capital) / self.cfg.initial_capital

        return {
            "capital_inicial":   self.cfg.initial_capital,
            "capital_final":     round(final_capital, 2),
            "retorno_total_pct": round(total_return * 100, 2),
            "pnl_total":         round(total_pnl, 2),
            "num_trades":        len(closed),
            "ganadores":         len(wins),
            "perdedores":        len(losses),
            "win_rate_pct":      round(win_rate * 100, 1),
            "ganancia_promedio": round(avg_win, 2),
            "perdida_promedio":  round(avg_loss, 2),
            "profit_factor":     round(profit_factor, 2) if profit_factor != float("inf") else "inf",
            "max_drawdown_pct":  round(max_dd * 100, 1),
            "equity_curve":      eq,
            "trades":            closed,
        }


# ─────────────────────────────────────────────
# PROVEEDOR DE DATOS: ThetaData
# ─────────────────────────────────────────────

def thetadata_provider(host: str = "127.0.0.1", port: int = 25510):
    """
    Devuelve una función provider(symbol, date) que consulta ThetaData
    a través del ThetaTerminal local.

    USO:
        provider = thetadata_provider()
        bt.set_data_provider(provider)

    Requiere ThetaTerminal corriendo. Endpoint REST local por defecto:
        http://127.0.0.1:25510

    NOTA: La API exacta de ThetaData cambia entre versiones. Este provider
    usa el endpoint REST de cadena end-of-day. Ajusta los nombres de campos
    según la versión de tu ThetaTerminal (revisa http://127.0.0.1:25510/v2/...).
    """
    import requests

    base = f"http://{host}:{port}"

    def provider(symbol: str, date: str) -> pd.DataFrame:
        # date 'YYYY-MM-DD' → ThetaData usa formato 'YYYYMMDD'
        d = date.replace("-", "")

        # Endpoint de cadena EOD (ejemplo v2 — verifica tu versión)
        url = f"{base}/v2/bulk_hist/option/eod"
        params = {
            "root": symbol,
            "exp": "0",          # 0 = todas las expiraciones
            "start_date": d,
            "end_date": d,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"ThetaData error {symbol} {date}: {e}")
            return pd.DataFrame()

        # Parsear respuesta de ThetaData a nuestro formato estándar.
        # La estructura exacta depende de la versión; este es el patrón general:
        rows = []
        for item in data.get("response", []):
            try:
                contract = item.get("contract", {})
                ticks = item.get("ticks", [[]])[0]
                rows.append({
                    "symbol":            symbol,
                    "strike":            contract.get("strike", 0) / 1000.0,  # ThetaData da strike ×1000
                    "option_type":       "call" if contract.get("right") == "C" else "put",
                    "expiration":        str(contract.get("expiration", "")),
                    "bid":               ticks[3] if len(ticks) > 3 else np.nan,
                    "ask":               ticks[7] if len(ticks) > 7 else np.nan,
                    "last":              ticks[5] if len(ticks) > 5 else np.nan,
                    "volume":            ticks[8] if len(ticks) > 8 else 0,
                    "openInterest":      ticks[9] if len(ticks) > 9 else 0,
                    "delta":             np.nan,   # pedir aparte si tu plan lo incluye
                    "impliedVolatility": np.nan,
                })
            except Exception:
                continue

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Calcular DTE
        try:
            exp_dates = pd.to_datetime(df["expiration"], format="%Y%m%d", errors="coerce")
            cur = pd.to_datetime(date)
            df["dte"] = (exp_dates - cur).dt.days
        except Exception:
            df["dte"] = np.nan

        return df

    return provider


# ─────────────────────────────────────────────
# DEMO con datos sintéticos (sin ThetaData)
# ─────────────────────────────────────────────

def demo_synthetic_provider(symbol: str, date: str) -> pd.DataFrame:
    """
    Provider de PRUEBA con datos sintéticos para verificar que el motor
    funciona ANTES de conectar ThetaData. NO usar para decisiones reales.

    Genera contratos CONSISTENTES: las mismas expiraciones y strikes cada día,
    con precios que evolucionan (random walk) para que las salidas se disparen.
    """
    cur = pd.to_datetime(date)

    # Strikes y expiraciones FIJAS (no cambian día a día) basadas en un spot ancla
    np.random.seed(hash(symbol) % (2**32))   # semilla por símbolo (no por fecha)
    spot_anchor = 100 + np.random.rand() * 50

    # Expiraciones fijas relativas a un origen
    origin = pd.to_datetime("2025-01-01")
    exp_offsets = [40, 50, 60]  # días desde el origen
    rows = []
    for off in exp_offsets:
        exp_date = origin + timedelta(days=off)
        dte = (exp_date - cur).days
        if dte < 0:
            continue
        exp_str = exp_date.strftime("%Y%m%d")
        for strike in np.arange(round(spot_anchor * 0.85), round(spot_anchor * 1.15), 5):
            for opt in ["call", "put"]:
                # Precio base por contrato, con random walk según los días transcurridos
                key = hash(f"{symbol}{strike}{opt}{exp_str}") % (2**32)
                rng = np.random.default_rng(key)
                base = max(0.5, rng.random() * 6)
                days_elapsed = (cur - origin).days
                # Random walk reproducible: trayectoria fija por contrato
                walk = rng.normal(0, 0.15, size=max(days_elapsed + 1, 1)).cumsum()
                drift = walk[min(days_elapsed, len(walk) - 1)]
                mid = max(0.05, base * (1 + drift))
                # El valor decae al acercarse a 0 DTE
                mid *= max(0.1, dte / 60)

                delta_mag = rng.uniform(0.2, 0.7)
                rows.append({
                    "symbol": symbol, "strike": float(round(strike, 1)),
                    "option_type": opt, "expiration": exp_str, "dte": int(dte),
                    "bid": round(mid * 0.97, 2), "ask": round(mid * 1.03, 2),
                    "last": round(mid, 2),
                    "volume": int(rng.integers(20, 500)),
                    "openInterest": int(rng.integers(200, 2000)),
                    "delta": round(delta_mag * (1 if opt == "call" else -1), 3),
                    "impliedVolatility": round(rng.uniform(0.3, 0.7), 3),
                })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# EJEMPLO DE USO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 1) Configuración (5% riesgo como pediste, +50%/-30% salida)
    cfg = BacktestConfig(
        initial_capital=10_000,
        risk_per_trade_pct=0.05,
        take_profit_pct=0.50,
        stop_loss_pct=0.30,
    )

    # 2) Motor
    bt = OptionsBacktest(cfg)

    # 3) Datos — DEMO sintético (cambiar por thetadata_provider() cuando tengas API key)
    bt.set_data_provider(demo_synthetic_provider)
    # bt.set_data_provider(thetadata_provider())  # ← cuando tengas ThetaTerminal

    # 4) Señales de ejemplo (date, symbol, direction)
    #    En producción vendrían de technical.py / signal.py
    fechas = pd.date_range("2025-01-02", "2025-03-31", freq="B").strftime("%Y-%m-%d").tolist()
    señales = pd.DataFrame([
        {"date": fechas[0],  "symbol": "AAPL", "direction": "bullish"},
        {"date": fechas[5],  "symbol": "MSFT", "direction": "bullish"},
        {"date": fechas[10], "symbol": "NVDA", "direction": "bearish"},
        {"date": fechas[20], "symbol": "TSLA", "direction": "bullish"},
    ])

    # 5) Correr
    resultados = bt.run(señales, fechas)

    # 6) Reporte
    print("\n" + "=" * 50)
    print("RESULTADOS DEL BACKTEST (datos sintéticos de prueba)")
    print("=" * 50)
    for k, v in resultados.items():
        if k not in ("equity_curve", "trades"):
            print(f"  {k:.<25} {v}")
