# agents/trade_plan_agent.py

def trade_plan_agent(state):
    print("📋 Creando plan de trade...")

    entry_ready = state.get("entry_ready", False)
    price = state.get("price")
    atr = state.get("atr")
    entry_type = state.get("entry_type", "NONE")

    if not entry_ready or price is None or atr is None:
        state["trade_plan"] = "No hay plan activo."
        print("📋 Plan: No hay plan activo.")
        return state

    if "CALL" in entry_type:
        stop_loss = round(price - atr, 2)
        take_profit = round(price + (atr * 2), 2)
    elif "PUT" in entry_type:
        stop_loss = round(price + atr, 2)
        take_profit = round(price - (atr * 2), 2)
    else:
        stop_loss = None
        take_profit = None

    contracts = 2
    risk_amount = 200.0

    plan = (
        f"{entry_type} confirmado. Entrada: {round(price, 2)}, "
        f"Stop Loss: {stop_loss}, Take Profit: {take_profit}, "
        f"Contratos: {contracts}, Riesgo estimado: ${risk_amount}"
    )

    state["entry_price"] = round(price, 2)
    state["stop_loss"] = stop_loss
    state["take_profit"] = take_profit
    state["contracts"] = contracts
    state["risk_amount"] = risk_amount
    state["trade_plan"] = plan

    print(f"📋 Plan: {plan}")

    return state