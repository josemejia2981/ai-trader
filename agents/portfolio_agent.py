# agents/portfolio_agent.py

MAX_POSITIONS = 4
MAX_TOTAL_RISK = 600


def portfolio_agent(results):
    print("\nSTEP 9 PORTFOLIO")
    print("Construyendo cartera diaria...")

    valid_trades = []

    for trade in results:
        if trade.get("trade_allowed") is True and int(trade.get("contracts") or 0) > 0:
            valid_trades.append(trade)

    valid_trades = sorted(
        valid_trades,
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    portfolio = []
    total_risk = 0
    total_profit = 0
    call_count = 0
    put_count = 0

    for trade in valid_trades:
        if len(portfolio) >= MAX_POSITIONS:
            break

        risk_amount = float(trade.get("risk_amount") or 0)
        potential_profit = float(trade.get("potential_profit") or 0)
        option_type = trade.get("option_type")

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

    print("\nTOP PORTFOLIO DEL DIA")

    if not portfolio:
        print("No hay trades ejecutables para cartera.")
    else:
        for i, trade in enumerate(portfolio, start=1):
            print("--------------------------------")
            print(f"#{i} {trade.get('symbol')}")
            print(f"Contrato: {trade.get('option_contract')}")
            print(f"Tipo: {trade.get('option_type')}")
            print(f"Contratos: {trade.get('contracts')}")
            print(f"Riesgo: ${trade.get('risk_amount')}")
            print(f"Ganancia potencial: ${trade.get('potential_profit')}")
            print(f"Score: {trade.get('score')}")

    print("--------------------------------")
    print(f"Total posiciones: {portfolio_summary['positions']}")
    print(f"Riesgo total cartera: ${portfolio_summary['total_risk']}")
    print(f"Ganancia potencial total: ${portfolio_summary['total_potential_profit']}")
    print(f"CALLS: {portfolio_summary['call_count']}")
    print(f"PUTS: {portfolio_summary['put_count']}")

    return portfolio, portfolio_summary