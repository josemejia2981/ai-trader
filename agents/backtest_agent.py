# agents/backtest_agent.py

import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

NY_TIMEZONE = ZoneInfo("America/New_York")

BACKTEST_FILE = REPORTS_DIR / "backtest_results.csv"
BACKTEST_EQUITY_FILE = REPORTS_DIR / "backtest_equity_curve.csv"

STARTING_CAPITAL = 10000
OPTION_MULTIPLIER = 100


def now_new_york():
    return datetime.now(NY_TIMEZONE)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def detect_direction(row):
    text = f"{row.get('option_type', '')} {row.get('strategy', '')} {row.get('entry_type', '')}".upper()

    if "PUT" in text or "BEARISH" in text or "DOWN" in text:
        return "PUT"

    return "CALL"


def simulate_trade_result(row, holding_days=5):
    symbol = row.get("symbol", row.get("ticker", None))

    if not symbol:
        return None

    entry_price = safe_float(row.get("underlying_price", row.get("current_price", row.get("price", 0))))
    option_entry = safe_float(row.get("entry_price", row.get("lastPrice", 0)))
    risk_amount = safe_float(row.get("risk_amount", 0))
    potential_profit = safe_float(row.get("potential_profit", 0))
    score = safe_float(row.get("score", row.get("contract_quality_score", 0)))
    delta = safe_float(row.get("delta_estimate", row.get("delta", 0)))
    contracts = int(safe_float(row.get("contracts", 1), 1))

    direction = detect_direction(row)

    end_date = now_new_york()
    start_date = end_date - timedelta(days=30)

    try:
        data = yf.download(
            symbol,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if data.empty or len(data) < holding_days + 1:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        start_close = safe_float(data["Close"].iloc[-holding_days - 1])
        end_close = safe_float(data["Close"].iloc[-1])

        if start_close <= 0:
            return None

        stock_move_pct = ((end_close - start_close) / start_close) * 100

        if direction == "CALL":
            win = end_close > start_close
            option_move_pct = stock_move_pct * abs(delta) * 2.5
        else:
            win = end_close < start_close
            option_move_pct = -stock_move_pct * abs(delta) * 2.5

        simulated_option_exit = option_entry * (1 + option_move_pct / 100)

        if simulated_option_exit < 0:
            simulated_option_exit = 0

        pnl = (simulated_option_exit - option_entry) * OPTION_MULTIPLIER * contracts

        if risk_amount > 0:
            pnl = max(pnl, -risk_amount)

        if potential_profit > 0:
            pnl = min(pnl, potential_profit)

        result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"

        return {
            "date_ny": now_new_york().strftime("%Y-%m-%d"),
            "timestamp_ny": now_new_york().strftime("%Y-%m-%d %I:%M:%S %p New York"),
            "symbol": symbol,
            "contractSymbol": row.get("contractSymbol", row.get("option_contract", "N/A")),
            "direction": direction,
            "contracts": contracts,
            "holding_days": holding_days,
            "start_close": round(start_close, 2),
            "end_close": round(end_close, 2),
            "stock_move_pct": round(stock_move_pct, 2),
            "option_entry": round(option_entry, 2),
            "simulated_option_exit": round(simulated_option_exit, 2),
            "risk_amount": round(risk_amount, 2),
            "potential_profit": round(potential_profit, 2),
            "pnl": round(pnl, 2),
            "result": result,
            "score": round(score, 2),
            "delta": round(delta, 2),
        }

    except Exception:
        return None


def run_backtest(portfolio_df, holding_days=5):
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()

    results = []

    for _, row in portfolio_df.iterrows():
        result = simulate_trade_result(row, holding_days=holding_days)
        if result:
            results.append(result)

    if not results:
        return pd.DataFrame()

    results_df = pd.DataFrame(results)
    results_df.to_csv(BACKTEST_FILE, index=False)

    return results_df


def calculate_backtest_equity(results_df):
    if results_df is None or results_df.empty:
        equity_df = pd.DataFrame([{
            "date_ny": now_new_york().strftime("%Y-%m-%d"),
            "daily_pnl": 0,
            "equity": STARTING_CAPITAL,
            "return_pct": 0,
            "drawdown": 0,
            "drawdown_pct": 0,
        }])
        equity_df.to_csv(BACKTEST_EQUITY_FILE, index=False)
        return equity_df

    df = results_df.copy()
    df["pnl"] = df["pnl"].apply(safe_float)

    daily = df.groupby("date_ny", as_index=False)["pnl"].sum()
    daily = daily.rename(columns={"pnl": "daily_pnl"})

    daily["equity"] = STARTING_CAPITAL + daily["daily_pnl"].cumsum()
    daily["return_pct"] = ((daily["equity"] - STARTING_CAPITAL) / STARTING_CAPITAL) * 100
    daily["peak"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] - daily["peak"]
    daily["drawdown_pct"] = (daily["drawdown"] / daily["peak"]) * 100

    daily.to_csv(BACKTEST_EQUITY_FILE, index=False)

    return daily


def calculate_backtest_metrics(results_df, equity_df):
    if results_df is None or results_df.empty:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "total_return_pct": 0,
        }

    pnl = results_df["pnl"].apply(safe_float)

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    total_trades = len(pnl)
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = losses.mean() if len(losses) > 0 else 0

    max_drawdown = 0
    total_return_pct = 0

    if equity_df is not None and not equity_df.empty:
        max_drawdown = safe_float(equity_df["drawdown"].min()) if "drawdown" in equity_df.columns else 0
        total_return_pct = safe_float(equity_df["return_pct"].iloc[-1]) if "return_pct" in equity_df.columns else 0

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(pnl.sum(), 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
        "total_return_pct": round(total_return_pct, 2),
    }


def backtest_agent(portfolio_df, holding_days=5):
    results_df = run_backtest(portfolio_df, holding_days=holding_days)
    equity_df = calculate_backtest_equity(results_df)
    metrics = calculate_backtest_metrics(results_df, equity_df)

    return {
        "results": results_df,
        "equity_curve": equity_df,
        "metrics": metrics,
        "backtest_file": str(BACKTEST_FILE),
        "backtest_equity_file": str(BACKTEST_EQUITY_FILE),
    }