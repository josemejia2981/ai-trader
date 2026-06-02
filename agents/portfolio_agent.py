# agents/portfolio_agent.py

import pandas as pd
from pathlib import Path
from datetime import datetime

MAX_POSITIONS = 4
MAX_TOTAL_RISK = 1200

MIN_DELTA = 0.65
MIN_SCORE = 70
MIN_RISK_REWARD = 2.00

REPORTS_DIR = Path("reports")


def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def get_contract_symbol(trade):
    if trade.get("contractSymbol"):
        return trade.get("contractSymbol")

    if trade.get("option_contract"):
        return trade.get("option_contract")

    best_contract = trade.get("best_contract")

    if isinstance(best_contract, dict):
        return best_contract.get("contractSymbol")

    return None


def normalize_rating(rating):
    return str(rating or "").upper().strip()


def is_valid_rating(rating):
    allowed_ratings = [
        "EXCELENTE",
        "INTERESANTE",
        "BUY STRONG",
        "STRONG BUY",
        "FUERTE",
        "STRONG",
        "BUENA OPORTUNIDAD",
        "ALTO RENDIMIENTO",
        "🔥 ALTO RENDIMIENTO",
        "✅ BUENA OPORTUNIDAD",
    ]

    rating = normalize_rating(rating)

    for allowed in allowed_ratings:
        if allowed in rating:
            return True

    return False


def portfolio_agent(results):
    print("\nSTEP 9 PORTFOLIO")
    print("Construyendo cartera institucional...")

    REPORTS_DIR.mkdir(exist_ok=True)

    valid_trades = []

    for trade in results:
        if not isinstance(trade, dict):
            continue

        score = safe_float(trade.get("score"))
        contract_quality_score = safe_float(trade.get("contract_quality_score"))

        final_score = max(score, contract_quality_score)

        delta = abs(safe_float(trade.get("delta")))
        risk_amount = safe_float(trade.get("risk_amount"))
        potential_profit = safe_float(trade.get("potential_profit"))
        risk_reward = safe_float(trade.get("risk_reward"))

        contracts = safe_int(trade.get("contracts"), 1)

        trade_allowed = trade.get("trade_allowed")
        entry_ready = trade.get("entry_ready")

        rating = normalize_rating(trade.get("rating"))
        recommendation = normalize_rating(trade.get("recommendation"))

        contract_symbol = get_contract_symbol(trade)

        if final_score < MIN_SCORE:
            continue

        if delta < MIN_DELTA:
            continue

        if risk_reward < MIN_RISK_REWARD:
            continue

        if not is_valid_rating(rating) and not is_valid_rating(recommendation):
            continue

        if risk_amount <= 0:
            continue

        if potential_profit <= 0:
            continue

        if not contract_symbol:
            continue

        if contracts <= 0:
            contracts = 1

        if trade_allowed is False:
            continue

        if entry_ready is False:
            continue

        trade["contracts"] = contracts
        trade["contractSymbol"] = contract_symbol
        trade["portfolio_score"] = final_score

        valid_trades.append(trade)

    valid_trades = sorted(
        valid_trades,
        key=lambda x: (
            safe_float(x.get("portfolio_score")),
            abs(safe_float(x.get("delta"))),
            safe_float(x.get("risk_reward")),
            safe_float(x.get("potential_profit")),
            safe_float(x.get("openInterest")),
            safe_float(x.get("volume")),
        ),
        reverse=True,
    )

    portfolio = []

    total_risk = 0
    total_profit = 0

    call_count = 0
    put_count = 0

    for trade in valid_trades:
        if len(portfolio) >= MAX_POSITIONS:
            break

        risk_amount = safe_float(trade.get("risk_amount"))
        potential_profit = safe_float(trade.get("potential_profit"))

        option_type = str(trade.get("option_type", "")).upper()

        if total_risk + risk_amount > MAX_TOTAL_RISK:
            continue

        portfolio.append(trade)

        total_risk += risk_amount
        total_profit += potential_profit

        if option_type == "CALL":
            call_count += 1
        elif option_type == "PUT":
            put_count += 1

    portfolio_summary = {
        "positions": len(portfolio),
        "total_risk": round(total_risk, 2),
        "total_potential_profit": round(total_profit, 2),
        "call_count": call_count,
        "put_count": put_count,
        "max_total_risk": MAX_TOTAL_RISK,
        "symbols": [p.get("symbol") for p in portfolio],
    }

    print("\nTOP PORTFOLIO INSTITUCIONAL")

    if not portfolio:
        print("No hay trades institucionales válidos.")
    else:
        for i, trade in enumerate(portfolio, start=1):
            print("--------------------------------")
            print(f"#{i} {trade.get('symbol')}")
            print(f"Contrato: {trade.get('contractSymbol')}")
            print(f"Tipo: {trade.get('option_type')}")
            print(f"Delta: {trade.get('delta')}")
            print(f"Contratos: {trade.get('contracts')}")
            print(f"Entrada opción: {trade.get('entry_price')}")
            print(f"Entrada acción: {trade.get('stock_entry_price')}")
            print(f"Stop Loss: {trade.get('stop_loss')}")
            print(f"Take Profit 1: {trade.get('take_profit_1')}")
            print(f"Take Profit 2: {trade.get('take_profit_2')}")
            print(f"Riesgo: ${trade.get('risk_amount')}")
            print(f"Ganancia potencial: ${trade.get('potential_profit')}")
            print(f"Risk/Reward: {trade.get('risk_reward')}")
            print(f"Score institucional: {trade.get('score')}")
            print(f"Score contrato: {trade.get('contract_quality_score')}")
            print(f"Score portfolio: {trade.get('portfolio_score')}")
            print(f"Rating: {trade.get('rating')}")
            print(f"Recomendación: {trade.get('recommendation')}")

    print("--------------------------------")
    print(f"Total posiciones: {portfolio_summary['positions']}")
    print(f"Riesgo total cartera: ${portfolio_summary['total_risk']}")
    print(f"Ganancia potencial total: ${portfolio_summary['total_potential_profit']}")
    print(f"CALLS: {portfolio_summary['call_count']}")
    print(f"PUTS: {portfolio_summary['put_count']}")

    if portfolio:
        portfolio_rows = []

        for trade in portfolio:
            portfolio_rows.append({
                "symbol": trade.get("symbol"),
                "contractSymbol": trade.get("contractSymbol"),
                "option_type": trade.get("option_type"),
                "delta": trade.get("delta"),
                "contracts": trade.get("contracts"),
                "entry_price": trade.get("entry_price"),
                "max_option_entry": trade.get("max_option_entry"),
                "stop_loss": trade.get("stop_loss"),
                "take_profit": trade.get("take_profit"),
                "take_profit_1": trade.get("take_profit_1"),
                "take_profit_2": trade.get("take_profit_2"),
                "trailing_stop": trade.get("trailing_stop"),
                "stock_entry_price": trade.get("stock_entry_price"),
                "stock_stop_loss": trade.get("stock_stop_loss"),
                "stock_take_profit_1": trade.get("stock_take_profit_1"),
                "stock_take_profit_2": trade.get("stock_take_profit_2"),
                "risk_amount": trade.get("risk_amount"),
                "potential_profit": trade.get("potential_profit"),
                "risk_reward": trade.get("risk_reward"),
                "score": trade.get("score"),
                "rating": trade.get("rating"),
                "recommendation": trade.get("recommendation"),
                "recommendation_reason": trade.get("recommendation_reason"),
                "portfolio_score": trade.get("portfolio_score"),
                "dte": trade.get("dte"),
                "strike": trade.get("strike"),
                "expiration": trade.get("expiration"),
                "bid": trade.get("bid"),
                "ask": trade.get("ask"),
                "mid_price": trade.get("mid_price"),
                "spread": trade.get("spread"),
                "spread_pct": trade.get("spread_pct"),
                "volume": trade.get("volume"),
                "openInterest": trade.get("openInterest"),
                "underlying_price": trade.get("underlying_price"),
                "contract_quality_score": trade.get("contract_quality_score"),
                "liquidity_score": trade.get("liquidity_score"),
                "spread_score": trade.get("spread_score"),
                "dte_score": trade.get("dte_score"),
                "moneyness_score": trade.get("moneyness_score"),
                "delta_score": trade.get("delta_score"),
                "price_score": trade.get("price_score"),
                "risk_score": trade.get("risk_score"),
                "rr_score": trade.get("rr_score"),
            })

        df = pd.DataFrame(portfolio_rows)

        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
        file_path = REPORTS_DIR / f"portfolio_{timestamp}.csv"

        df.to_csv(file_path, index=False)

        print(f"Portfolio CSV guardado en: {file_path}")

    return {
        "portfolio": portfolio,
        "summary": portfolio_summary
    }