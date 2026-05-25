# agents/trade_plan_agent.py

ACCOUNT_SIZE = 10000
RISK_PERCENT = 0.02
MAX_CONTRACTS = 10

RISK_TOLERANCE_PERCENT = 0.15


def trade_plan_agent(state):
    print("Creando plan de trade...")

    entry_ready = state.get("entry_ready", False)
    strategy = state.get("option_strategy", "NO TRADE")

    option_entry = float(state.get("option_entry") or 0)
    option_price = float(state.get("option_price") or 0)

    real_option_price = option_entry if option_entry > 0 else option_price

    max_risk_allowed = round(ACCOUNT_SIZE * RISK_PERCENT, 2)
    max_risk_with_tolerance = round(
        max_risk_allowed * (1 + RISK_TOLERANCE_PERCENT),
        2
    )

    state["account_size"] = ACCOUNT_SIZE
    state["risk_percent"] = RISK_PERCENT
    state["max_risk_allowed"] = max_risk_allowed
    state["max_risk_with_tolerance"] = max_risk_with_tolerance

    if not entry_ready:
        state["trade_plan"] = "No hay plan activo: entrada no confirmada."
        state["contracts"] = 0
        state["risk_amount"] = 0
        state["potential_profit"] = 0
        state["risk_reward"] = 0
        state["trade_allowed"] = False
        state["risk_warning"] = ""
        return state

    if real_option_price <= 0:
        state["trade_plan"] = "No hay plan activo: no hay precio real de opcion."
        state["contracts"] = 0
        state["risk_amount"] = 0
        state["potential_profit"] = 0
        state["risk_reward"] = 0
        state["trade_allowed"] = False
        state["risk_warning"] = ""
        return state

    option_stop_loss = float(state.get("option_stop_loss") or 0)
    option_take_profit = float(state.get("option_take_profit") or 0)

    if option_stop_loss <= 0:
        option_stop_loss = round(real_option_price * 0.70, 2)

    if option_take_profit <= 0:
        option_take_profit = round(real_option_price * 1.50, 2)

    cost_per_contract = round(real_option_price * 100, 2)
    risk_per_contract = round((real_option_price - option_stop_loss) * 100, 2)

    if risk_per_contract <= 0:
        state["trade_plan"] = "Trade bloqueado: stop loss invalido."
        state["contracts"] = 0
        state["risk_amount"] = 0
        state["potential_profit"] = 0
        state["risk_reward"] = 0
        state["trade_allowed"] = False
        state["risk_warning"] = "Stop loss invalido."
        state["option_price_used"] = real_option_price
        state["cost_per_contract"] = cost_per_contract
        state["risk_per_contract"] = risk_per_contract
        return state

    contracts = int(max_risk_allowed // risk_per_contract)
    risk_warning = ""

    if contracts <= 0:
        if risk_per_contract <= max_risk_with_tolerance:
            contracts = 1
            risk_warning = (
                f"Advertencia: riesgo ligeramente superior al limite. "
                f"Permitido con tolerancia. Riesgo contrato ${risk_per_contract}, "
                f"limite normal ${max_risk_allowed}."
            )
        else:
            state["trade_plan"] = (
                f"Trade bloqueado: riesgo por contrato ${risk_per_contract} "
                f"mayor al limite con tolerancia ${max_risk_with_tolerance}."
            )
            state["contracts"] = 0
            state["risk_amount"] = 0
            state["potential_profit"] = 0
            state["risk_reward"] = 0
            state["trade_allowed"] = False
            state["risk_warning"] = (
                f"Riesgo demasiado alto. Riesgo contrato ${risk_per_contract}, "
                f"limite con tolerancia ${max_risk_with_tolerance}."
            )
            state["option_price_used"] = real_option_price
            state["cost_per_contract"] = cost_per_contract
            state["risk_per_contract"] = risk_per_contract
            return state

    contracts = min(contracts, MAX_CONTRACTS)

    risk_amount = round(risk_per_contract * contracts, 2)
    potential_profit = round(
        (option_take_profit - real_option_price) * 100 * contracts,
        2
    )

    risk_reward = round(potential_profit / risk_amount, 2) if risk_amount > 0 else 0

    state["trade_plan"] = (
        f"Estrategia: {strategy} | "
        f"Contratos: {contracts} | "
        f"Entrada opcion: ${real_option_price} | "
        f"Costo por contrato: ${cost_per_contract} | "
        f"Stop loss: ${option_stop_loss} | "
        f"Take profit: ${option_take_profit} | "
        f"Riesgo por contrato: ${risk_per_contract} | "
        f"Riesgo total: ${risk_amount} | "
        f"Ganancia potencial: ${potential_profit}"
    )

    if risk_warning:
        state["trade_plan"] += f" | {risk_warning}"

    state["contracts"] = contracts
    state["risk_amount"] = risk_amount
    state["potential_profit"] = potential_profit
    state["risk_reward"] = risk_reward
    state["stop_loss"] = option_stop_loss
    state["take_profit"] = option_take_profit
    state["option_price_used"] = real_option_price
    state["cost_per_contract"] = cost_per_contract
    state["risk_per_contract"] = risk_per_contract
    state["risk_warning"] = risk_warning
    state["trade_allowed"] = True

    return state