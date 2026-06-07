# agents/trade_plan_agent.py
# BUG CORREGIDO: leia option_stop_loss/option_take_profit (nunca seteados)
# Ahora lee stop_loss/take_profit (campos correctos de option_contract_agent)
import sys
sys.path.insert(0, '.')
try:
    from config.settings import ACCOUNT_SIZE, RISK_PERCENT, MAX_CONTRACTS, RISK_TOLERANCE_PERCENT
except Exception:
    ACCOUNT_SIZE=10000; RISK_PERCENT=0.02; MAX_CONTRACTS=10; RISK_TOLERANCE_PERCENT=0.15

def sf(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d

def si(v, d=0):
    try: return int(v) if v is not None else d
    except: return d

def trade_plan_agent(state):
    print("  Calculando plan de trade...")
    entry_ready = state.get("entry_ready", False)
    strategy = state.get("option_strategy", "NO TRADE")

    # Precio real del contrato - usa option_entry (seteado por option_contract_agent)
    entry_price = sf(state.get("option_entry") or state.get("entry_price") or state.get("option_price"))

    max_risk = round(ACCOUNT_SIZE * RISK_PERCENT, 2)
    max_risk_tol = round(max_risk * (1 + RISK_TOLERANCE_PERCENT), 2)

    state["account_size"] = ACCOUNT_SIZE
    state["risk_percent"] = RISK_PERCENT
    state["max_risk_allowed"] = max_risk
    state["max_risk_with_tolerance"] = max_risk_tol

    def block(msg, warn=""):
        state.update({"trade_plan": msg, "contracts": 0, "risk_amount": 0,
                      "potential_profit": 0, "risk_reward": 0,
                      "trade_allowed": False, "risk_warning": warn})
        return state

    if not entry_ready:
        return block("Sin plan: entrada no confirmada.")
    if entry_price <= 0:
        return block("Sin plan: precio de opcion no disponible.")

    # BUG FIX: leer los campos correctos que setea option_contract_agent
    stop_loss = sf(state.get("stop_loss") or state.get("option_stop_loss"))
    take_profit = sf(state.get("take_profit") or state.get("option_take_profit"))

    if stop_loss <= 0:
        stop_loss = round(entry_price * 0.60, 2)
    if take_profit <= 0:
        take_profit = round(entry_price * 2.0, 2)

    cost_per_contract = round(entry_price * 100, 2)
    risk_per_contract = round((entry_price - stop_loss) * 100, 2)

    if risk_per_contract <= 0:
        return block("Trade bloqueado: stop loss invalido.", "Stop >= entrada")

    contracts = int(max_risk // risk_per_contract)
    risk_warning = ""

    if contracts <= 0:
        if risk_per_contract <= max_risk_tol:
            contracts = 1
            risk_warning = "Riesgo sobre limite normal, permitido con tolerancia. $" + str(risk_per_contract) + "/contrato"
        else:
            return block(
                "Trade bloqueado: riesgo/contrato $" + str(risk_per_contract) + " > limite $" + str(max_risk_tol),
                "Riesgo excesivo: $" + str(risk_per_contract)
            )

    contracts = min(contracts, MAX_CONTRACTS)
    risk_amount = round(risk_per_contract * contracts, 2)
    potential_profit = round((take_profit - entry_price) * 100 * contracts, 2)
    risk_reward = round(potential_profit / risk_amount, 2) if risk_amount > 0 else 0

    plan = (strategy + " | Contratos:" + str(contracts) +
            " | Entrada:$" + str(entry_price) +
            " | Stop:$" + str(stop_loss) + " | TP:$" + str(take_profit) +
            " | Riesgo:$" + str(risk_amount) + " | Ganancia:$" + str(potential_profit) +
            " | R/R:" + str(risk_reward))
    if risk_warning: plan += " | " + risk_warning

    print("  Contratos:" + str(contracts) + " Riesgo:$" + str(risk_amount) +
          " Ganancia:$" + str(potential_profit) + " R/R:" + str(risk_reward))

    state["trade_plan"] = plan
    state["contracts"] = contracts
    state["risk_amount"] = risk_amount
    state["potential_profit"] = potential_profit
    state["risk_reward"] = risk_reward
    state["stop_loss"] = stop_loss
    state["take_profit"] = take_profit
    state["option_price_used"] = entry_price
    state["cost_per_contract"] = cost_per_contract
    state["risk_per_contract"] = risk_per_contract
    state["risk_warning"] = risk_warning
    state["trade_allowed"] = True
    return state
