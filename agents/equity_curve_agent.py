# agents/equity_curve_agent.py

import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

NY_TIMEZONE = ZoneInfo("America/New_York")

STARTING_CAPITAL = 10000
HISTORY_FILE = REPORTS_DIR / "trade_history.csv"
EQUITY_FILE = REPORTS_DIR / "equity_curve.csv"


def now_new_york():
    return datetime.now(NY_TIMEZONE)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def load_history():
    if HISTORY_FILE.exists():
        try:
            return pd.read_csv(HISTORY_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def save_trade_snapshot(portfolio_df):
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()

    history = load_history()
    today = now_new_york().strftime("%Y-%m-%d")
    timestamp = now_new_york().strftime("%Y-%m-%d %I:%M:%S %p New York")

    rows = []

    for _, row in portfolio_df.iterrows():
        symbol = row.get("symbol", "N/A")
        contract = row.get("contractSymbol", row.get("option_contract", "N/A"))

        trade_id = f"{today}_{symbol}_{contract}"

        if not history.empty and "trade_id" in history.columns:
            if trade_id in history["trade_id"].astype(str).values:
                continue

        potential_profit = safe_float(row.get("potential_profit", 0))
        risk_amount = safe_float(row.get("risk_amount", 0))

        simulated_result = potential_profit * 0.35

        rows.append({
            "trade_id": trade_id,
            "date": today,
            "timestamp_ny": timestamp,
            "symbol": symbol,
            "contractSymbol": contract,
            "option_type": row.get("option_type", "N/A"),
            "entry_price": safe_float(row.get("entry_price", row.get("lastPrice", 0))),
            "stop_loss": safe_float(row.get("stop_loss", 0)),
            "take_profit": safe_float(row.get("take_profit", 0)),
            "risk_amount": risk_amount,
            "potential_profit": potential_profit,
            "simulated_pnl": round(simulated_result, 2),
            "delta_estimate": safe_float(row.get("delta_estimate", 0)),
            "score": safe_float(row.get("score", row.get("contract_quality_score", 0))),
            "status": "OPEN_SIMULATED"
        })

    if not rows:
        return history

    new_rows = pd.DataFrame(rows)
    updated_history = pd.concat([history, new_rows], ignore_index=True)

    updated_history.to_csv(HISTORY_FILE, index=False)
    return updated_history


def calculate_equity_curve(history_df):
    if history_df is None or history_df.empty:
        equity_df = pd.DataFrame([{
            "date": now_new_york().strftime("%Y-%m-%d"),
            "daily_pnl": 0,
            "equity": STARTING_CAPITAL,
            "return_pct": 0,
            "drawdown": 0
        }])
        equity_df.to_csv(EQUITY_FILE, index=False)
        return equity_df

    df = history_df.copy()

    if "date" not in df.columns:
        return pd.DataFrame()

    if "simulated_pnl" not in df.columns:
        df["simulated_pnl"] = 0

    df["simulated_pnl"] = df["simulated_pnl"].apply(safe_float)

    daily = df.groupby("date", as_index=False)["simulated_pnl"].sum()
    daily = daily.rename(columns={"simulated_pnl": "daily_pnl"})

    daily["equity"] = STARTING_CAPITAL + daily["daily_pnl"].cumsum()
    daily["return_pct"] = ((daily["equity"] - STARTING_CAPITAL) / STARTING_CAPITAL) * 100
    daily["peak"] = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] - daily["peak"]
    daily["drawdown_pct"] = (daily["drawdown"] / daily["peak"]) * 100

    daily.to_csv(EQUITY_FILE, index=False)
    return daily


def calculate_performance_metrics(history_df, equity_df):
    if history_df is None or history_df.empty:
        return {
            "total_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "total_return_pct": 0
        }

    pnl = history_df["simulated_pnl"].apply(safe_float) if "simulated_pnl" in history_df.columns else pd.Series([])

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    total_pnl = pnl.sum()
    total_trades = len(pnl)
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

    max_drawdown = 0
    total_return_pct = 0

    if equity_df is not None and not equity_df.empty:
        if "drawdown" in equity_df.columns:
            max_drawdown = equity_df["drawdown"].min()
        if "return_pct" in equity_df.columns:
            total_return_pct = equity_df["return_pct"].iloc[-1]

    return {
        "total_trades": round(total_trades, 2),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
        "total_return_pct": round(total_return_pct, 2)
    }


def equity_curve_agent(portfolio_df):
    history_df = save_trade_snapshot(portfolio_df)
    equity_df = calculate_equity_curve(history_df)
    metrics = calculate_performance_metrics(history_df, equity_df)

    return {
        "history": history_df,
        "equity_curve": equity_df,
        "metrics": metrics,
        "history_file": str(HISTORY_FILE),
        "equity_file": str(EQUITY_FILE)
    }