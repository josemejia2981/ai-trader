# agents/options_agent.py - Estrategia de opciones (corre DESPUES de entry_agent)
import sys
sys.path.insert(0, '.')
try:
    from config.settings import ACCOUNT_SIZE, RISK_PERCENT, MAX_CONTRACTS
except Exception:
    ACCOUNT_SIZE = 10000; RISK_PERCENT = 0.02; MAX_CONTRACTS = 10


def options_agent(state):
    print("  Determinando estrategia...")
    signal = state.get("signal", "HOLD")
    direction = state.get("direction", "NONE")
    risk = state.get("risk", "MEDIUM")
    entry_ready = state.get("entry_ready", False)
    entry_score = float(state.get("entry_score", 0))
    bull_score = float(state.get("bull_score", 0))
    bear_score = float(state.get("bear_score", 0))

    max_risk = round(ACCOUNT_SIZE * RISK_PERCENT, 2)

    if risk == "HIGH":
        state.update({"option_strategy": "NO TRADE", "option_reason": "Riesgo alto.",
                      "option_confidence": 0, "trade_allowed": False})
        print("  Estrategia: NO TRADE (riesgo alto)")
        return state

    if signal == "HOLD" or direction == "NONE":
        state.update({"option_strategy": "HOLD", "option_reason": "Sin señal activa.",
                      "option_confidence": 0, "trade_allowed": False})
        print("  Estrategia: HOLD")
        return state

    if direction == "CALL":
        opt_type = "CALL"
        if entry_ready:
            strategy = "BUY CALL OPTION"
            confidence = min(95, int(60 + entry_score * 0.35))
            reason = "CALL confirmada. Entry score:" + str(int(entry_score)) + " Bull:" + str(int(bull_score))
            trade_allowed = True
        else:
            strategy = "WATCHLIST CALL"
            confidence = max(40, int(bull_score * 0.6))
            reason = "Tendencia CALL sin confirmacion de entrada (score " + str(int(entry_score)) + ")"
            trade_allowed = False
    else:
        opt_type = "PUT"
        if entry_ready:
            strategy = "BUY PUT OPTION"
            confidence = min(95, int(60 + entry_score * 0.35))
            reason = "PUT confirmada. Entry score:" + str(int(entry_score)) + " Bear:" + str(int(bear_score))
            trade_allowed = True
        else:
            strategy = "WATCHLIST PUT"
            confidence = max(40, int(bear_score * 0.6))
            reason = "Tendencia PUT sin confirmacion de entrada (score " + str(int(entry_score)) + ")"
            trade_allowed = False

    print("  Estrategia: " + strategy + " | Confianza: " + str(confidence) + "% | Trade: " + str(trade_allowed))
    state["option_strategy"] = strategy
    state["option_reason"] = reason
    state["option_confidence"] = confidence
    state["option_type"] = opt_type
    state["trade_allowed"] = trade_allowed
    state["max_risk_allowed"] = max_risk
    state["account_size"] = ACCOUNT_SIZE
    state["risk_percent"] = RISK_PERCENT
    return state
