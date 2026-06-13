"""
backtest_engine_v2.py  –  Motor de backtest de opciones (versión 2)
════════════════════════════════════════════════════════════════════
Mejoras sobre el engine original:

  COSTOS REALES
    • Spread bid-ask round-trip : 2% del allocation (default)
    • Comisión                  : $1.30 por trade (round-trip)

  MODELO NORMALIZADO DE OPCIÓN ATM
    risk_amount   = capital × risk_pct           →  p.ej. $100
    option_alloc  = risk_amount / stop_loss_pct  →  $100/0.30 = $333
    leverage      ≈ 10× (delta=0.50, prima ≈ 5% del subyacente)
    theta_decay   = 0.7%/día del valor de la opción

  SALIDAS ADAPTATIVAS (día a día, sin look-ahead)
    • Take profit   : +50% en el valor de la opción
    • Stop loss     : −30%
    • Trailing stop : se activa tras +20%; trailing 15% desde el pico
    • Time exit     : máximo 21 días en posición

  LÍMITES DE PORTFOLIO
    • max_concurrent : no más de N posiciones abiertas a la vez
    • sin repetir símbolo mientras la posición anterior esté abierta

  MÉTODOS DE VALIDACIÓN ESTADÍSTICA
    • run_monte_carlo()    1 000 shuffles del orden de trades
    • run_walk_forward()   75% train / 25% test out-of-sample

Compatibilidad con el engine original
    Retorna las mismas claves que el engine v1 + extras:
    sharpe_ratio, avg_hold_days, exit_reasons, trades_df, equity_curve

Requiere: pandas, numpy, yfinance (si yfinance_provider no está disponible)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Proveedor de precios ─────────────────────────────────────────────────────
try:
    from yfinance_provider import _get_price_history as _ext_hist
    def _get_hist(sym: str, start: str, end: str) -> pd.DataFrame:
        return _ext_hist(sym, start, end)
    logger.debug("Usando yfinance_provider para precios")
except ImportError:
    import yfinance as yf
    _PC: dict = {}
    def _get_hist(sym: str, start: str, end: str) -> pd.DataFrame:
        key = (sym, start, end)
        if key not in _PC:
            try:
                df = yf.download(sym, start=start, end=end,
                                 auto_adjust=True, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                _PC[key] = df
            except Exception:
                _PC[key] = pd.DataFrame()
        return _PC[key]
    logger.debug("yfinance_provider no encontrado; usando yfinance directo")


def _strip_tz(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Elimina timezone de un DatetimeIndex de forma segura."""
    if idx.tz is not None:
        return idx.tz_convert(None)
    return pd.to_datetime(idx)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BacktestConfigV2:
    initial_capital:       float = 10_000.0
    risk_per_trade_pct:    float = 0.01     # fracción del capital en riesgo por trade
    take_profit_pct:       float = 0.50     # TP al +50% del valor de la opción
    stop_loss_pct:         float = 0.30     # SL al −30%
    trailing_activate_pct: float = 0.20     # activar trailing tras +20% de ganancia
    trailing_stop_pct:     float = 0.15     # trailing 15% desde el pico de valor
    max_hold_days:         int   = 21       # salida forzada a los 21 días
    theta_daily_pct:       float = 0.007    # 0.7%/día de erosión del valor (theta)
    leverage_factor:       float = 10.0     # ATM: delta≈0.5, prima≈5% → leverage 10×
    spread_pct:            float = 0.02     # bid-ask round-trip (2% del allocation)
    commission:            float = 1.30     # $0.65×2 = $1.30 round-trip
    max_concurrent:        int   = 8        # posiciones abiertas simultáneas


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR
# ══════════════════════════════════════════════════════════════════════════════

class OptionsBacktestV2:
    """
    Uso rápido
    ----------
        cfg = BacktestConfigV2(initial_capital=10_000, risk_per_trade_pct=0.01)
        bt  = OptionsBacktestV2(cfg)
        res = bt.run(signals_df)
    """

    def __init__(self, cfg: Optional[BacktestConfigV2] = None):
        self.cfg = cfg or BacktestConfigV2()
        self._hist: dict = {}   # caché de DataFrames históricos

    # ── Compatibilidad con engine v1 ──────────────────────────────────────────
    def set_data_provider(self, provider) -> None:
        """No-op — mantiene compatibilidad con la interfaz original."""
        pass

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _load(self, sym: str, start: str, end: str) -> pd.DataFrame:
        """Carga y normaliza histórico (caché por instancia)."""
        key = (sym, start, end)
        if key not in self._hist:
            ext = (pd.to_datetime(start) - timedelta(days=5)).strftime("%Y-%m-%d")
            df = _get_hist(sym, ext, end)
            if not df.empty:
                df = df.copy()
                df.index = _strip_tz(df.index)
            self._hist[key] = df
        return self._hist[key]

    # ── Simulación de un trade ────────────────────────────────────────────────

    def _simulate(
        self,
        sig_date: str,
        symbol: str,
        direction: str,
        hist: pd.DataFrame,
    ) -> Optional[dict]:
        """
        Simula un trade día a día desde sig_date hasta la condición de salida.
        Retorna None si no hay datos o la señal es rechazada.
        """
        cfg = self.cfg
        sig_dt = pd.Timestamp(sig_date)

        # Entrada = primer día hábil DESPUÉS de la señal (evita look-ahead)
        future = hist.index[hist.index > sig_dt]
        if future.empty:
            return None

        entry_dt  = future[0]
        entry_idx = hist.index.get_loc(entry_dt)
        entry_px  = float(hist["Close"].iloc[entry_idx])
        if entry_px <= 0:
            return None

        # ── Modelo normalizado ────────────────────────────────────────────────
        # risk_amount  : cuánto estamos dispuestos a perder (= SL en $)
        # option_alloc : "capital de opción" que controlamos
        risk_amount  = cfg.initial_capital * cfg.risk_per_trade_pct
        option_alloc = risk_amount / max(cfg.stop_loss_pct, 0.01)
        dir_sign     = 1.0 if direction == "bullish" else -1.0

        opt_val  = 1.0   # normalizado → 1.0 = precio de entrada
        peak_val = 1.0
        trail_on = False

        for day in range(1, cfg.max_hold_days + 1):
            idx = entry_idx + day
            if idx >= len(hist):
                break

            curr = float(hist["Close"].iloc[idx])
            prev = float(hist["Close"].iloc[idx - 1])
            if prev <= 0 or np.isnan(curr) or np.isnan(prev):
                continue

            # Movimiento diario del subyacente → impacto amplificado en la opción
            stock_move = (curr - prev) / prev
            opt_move   = stock_move * dir_sign * cfg.leverage_factor
            theta      = cfg.theta_daily_pct

            # Actualizar valor de la opción (leverage + theta decay)
            opt_val = opt_val * (1.0 + opt_move) - opt_val * theta
            opt_val = max(0.01, opt_val)   # la opción no puede ser negativa

            # Trailing stop
            if opt_val > peak_val:
                peak_val = opt_val
            if not trail_on and (peak_val - 1.0) >= cfg.trailing_activate_pct:
                trail_on = True
            trail_dd = (peak_val - opt_val) / peak_val if peak_val > 0 else 0.0

            # ── Condiciones de salida ─────────────────────────────────────────
            gain = opt_val - 1.0  # fracción de ganancia/pérdida desde la entrada

            if   gain >= cfg.take_profit_pct:                           reason = "take_profit"
            elif gain <= -cfg.stop_loss_pct:                            reason = "stop_loss"
            elif trail_on and trail_dd >= cfg.trailing_stop_pct:        reason = "trailing_stop"
            elif day >= cfg.max_hold_days:                              reason = "time_exit"
            else:                                                        continue

            exit_dt = hist.index[idx]

            # ── P&L con costos reales ──────────────────────────────────────
            # Costos fijos sobre el allocation inicial (spread round-trip + comisión)
            pnl_gross = option_alloc * gain
            cost      = option_alloc * cfg.spread_pct + cfg.commission
            pnl_net   = pnl_gross - cost

            return {
                "signal_date": sig_date,
                "entry_date":  entry_dt.strftime("%Y-%m-%d"),
                "exit_date":   exit_dt.strftime("%Y-%m-%d"),
                "symbol":      symbol,
                "direction":   direction,
                "hold_days":   day,
                "entry_close": round(entry_px, 2),
                "exit_close":  round(curr, 2),
                "opt_val":     round(opt_val, 4),
                "gain_pct":    round(gain * 100, 2),
                "pnl_gross":   round(pnl_gross, 2),
                "cost":        round(cost, 2),
                "pnl":         round(pnl_net, 2),
                "exit_reason": reason,
                "result":      "WIN" if pnl_net > 0 else "LOSS",
            }

        return None  # no se llegó a ninguna condición de salida

    # ── Backtest principal ────────────────────────────────────────────────────

    def run(
        self,
        signals_df: pd.DataFrame,
        fechas: Optional[list] = None,   # ignorado, compatibilidad v1
    ) -> dict:
        """
        Ejecuta el backtest sobre signals_df.

        signals_df debe tener: ['date', 'symbol', 'direction']
        Retorna dict compatible con el engine original + métricas extra.
        """
        if signals_df is None or (hasattr(signals_df, "empty") and signals_df.empty):
            return {"error": "Sin señales", "num_trades": 0}

        df = signals_df.sort_values("date").reset_index(drop=True)

        # Rango de datos necesario
        start_s = df["date"].min()
        end_s   = (pd.to_datetime(df["date"].max()) + timedelta(days=45)).strftime("%Y-%m-%d")

        # Pre-cargar todos los históricos
        for sym in df["symbol"].unique():
            self._load(sym, start_s, end_s)

        # ── Tracking de posiciones abiertas ──────────────────────────────────
        # active[sym] = fecha de exit del trade abierto en ese símbolo
        active: dict = {}
        trades: list = []

        for _, sig in df.iterrows():
            sym      = str(sig["symbol"])
            sig_date = str(sig["date"])
            sig_dt   = pd.Timestamp(sig_date)
            direction = str(sig.get("direction", "bullish"))

            # Limpiar posiciones que ya cerraron
            active = {s: x for s, x in active.items() if x > sig_dt}

            # Límites de portfolio
            if len(active) >= self.cfg.max_concurrent:
                continue
            if sym in active:
                continue

            hist_key = (sym, start_s, end_s)
            hist = self._hist.get(hist_key, pd.DataFrame())
            if hist.empty:
                continue

            trade = self._simulate(sig_date, sym, direction, hist)
            if trade is None:
                continue

            active[sym] = pd.Timestamp(trade["exit_date"])
            trades.append(trade)

        if not trades:
            return {"error": "Sin trades ejecutados", "num_trades": 0}

        return self._metrics(trades)

    # ── Métricas ──────────────────────────────────────────────────────────────

    def _metrics(self, trades: list) -> dict:
        df  = pd.DataFrame(trades)
        pnl = df["pnl"].values.astype(float)

        wins   = pnl[pnl > 0]
        losses = pnl[pnl < 0]

        capital_final = self.cfg.initial_capital + pnl.sum()
        retorno_pct   = pnl.sum() / self.cfg.initial_capital * 100
        win_rate      = len(wins) / len(pnl) * 100 if len(pnl) > 0 else 0.0
        gp = wins.sum()  if len(wins)   > 0 else 0.0
        gl = abs(losses.sum()) if len(losses) > 0 else 0.0
        pf = round(gp / gl, 2) if gl > 0 else round(gp, 2)

        # Curva de equity y drawdown
        equity = self.cfg.initial_capital + np.cumsum(pnl)
        peak   = np.maximum.accumulate(equity)
        dd_pct = (equity - peak) / np.where(peak > 0, peak, 1) * 100
        max_dd = float(dd_pct.min()) if len(dd_pct) > 0 else 0.0

        # Sharpe anualizado (por trade, no diario)
        sharpe = 0.0
        if len(pnl) > 1:
            r = pnl / self.cfg.initial_capital
            avg_hold = float(df["hold_days"].mean()) if "hold_days" in df.columns else float(self.cfg.max_hold_days)
            ann = np.sqrt(252 / max(avg_hold, 1))
            if r.std() > 0:
                sharpe = float(r.mean() / r.std() * ann)

        exit_reasons = (df["exit_reason"].value_counts().to_dict()
                        if "exit_reason" in df.columns else {})
        avg_hold = round(float(df["hold_days"].mean()), 1) if "hold_days" in df.columns else 0.0

        return {
            # ── Claves compatibles con engine v1 ──────────────────────────
            "capital_final":     round(capital_final, 2),
            "retorno_total_pct": round(retorno_pct, 2),
            "num_trades":        len(pnl),
            "win_rate_pct":      round(win_rate, 2),
            "ganancia_promedio": round(wins.mean(), 2)   if len(wins)   > 0 else 0.0,
            "perdida_promedio":  round(losses.mean(), 2) if len(losses) > 0 else 0.0,
            "profit_factor":     pf,
            "max_drawdown_pct":  round(max_dd, 2),
            # ── Extras v2 ─────────────────────────────────────────────────
            "sharpe_ratio":      round(sharpe, 2),
            "avg_hold_days":     avg_hold,
            "exit_reasons":      exit_reasons,
            "trades_df":         df,
            "equity_curve":      pd.Series(equity, name="equity"),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDACIÓN ESTADÍSTICA
    # ══════════════════════════════════════════════════════════════════════════

    def run_monte_carlo(
        self,
        result: dict,
        n_runs: int = 1_000,
        seed: int = 42,
    ) -> dict:
        """
        Aleatoriza el orden de trades N veces.

        Si el sistema es robusto, la distribución de retornos debería ser
        consistentemente positiva independientemente del orden.
        Un sistema que depende de la suerte del orden → señal de fragilidad.
        """
        if "trades_df" not in result or result["trades_df"].empty:
            return {}

        pnl_arr = result["trades_df"]["pnl"].values.astype(float).copy()
        cap     = self.cfg.initial_capital
        rng     = np.random.default_rng(seed)
        rets    = np.empty(n_runs)

        for i in range(n_runs):
            shuffled = pnl_arr.copy()
            rng.shuffle(shuffled)
            rets[i] = shuffled.sum() / cap * 100

        return {
            "n_runs":      n_runs,
            "mean_pct":    round(float(rets.mean()), 2),
            "median_pct":  round(float(np.median(rets)), 2),
            "p5_pct":      round(float(np.percentile(rets, 5)), 2),
            "p95_pct":     round(float(np.percentile(rets, 95)), 2),
            "prob_pos_pct":round(float((rets > 0).mean() * 100), 1),
            "best_pct":    round(float(rets.max()), 2),
            "worst_pct":   round(float(rets.min()), 2),
        }

    def run_walk_forward(
        self,
        signals_df: pd.DataFrame,
        train_pct: float = 0.75,
    ) -> dict:
        """
        Divide las señales cronológicamente en train/test.

        Si el edge desaparece en test → overfitting.
        Si se mantiene → el sistema es robusto.
        """
        if signals_df is None or signals_df.empty or len(signals_df) < 10:
            return {}

        df    = signals_df.sort_values("date").reset_index(drop=True)
        split = int(len(df) * train_pct)
        train = df.iloc[:split].reset_index(drop=True)
        test  = df.iloc[split:].reset_index(drop=True)

        r_train = self.run(train)
        r_test  = self.run(test)

        degrad = (r_test.get("retorno_total_pct", 0)
                  - r_train.get("retorno_total_pct", 0))

        return {
            "train_n":         len(train),
            "test_n":          len(test),
            "train_return":    r_train.get("retorno_total_pct", 0),
            "test_return":     r_test.get("retorno_total_pct", 0),
            "train_pf":        r_train.get("profit_factor", 0),
            "test_pf":         r_test.get("profit_factor", 0),
            "train_wr":        r_train.get("win_rate_pct", 0),
            "test_wr":         r_test.get("win_rate_pct", 0),
            "degradation_pct": round(degrad, 2),
        }
