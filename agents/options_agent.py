# agents/options_agent.py

def options_agent(state):
    price = float(state.get("price", 0))
    trend = state.get("trend", "")
    risk = state.get("risk", "MEDIUM")
    rsi = float(state.get("rsi", 50))
    entry_ready = state.get("entry_ready", False)

    strategy = "NO TRADE"
    strike = None
    dte = None
    confidence = 0
    reason = "No hay condición clara para operar opciones."

    if risk == "HIGH":
        strategy = "NO TRADE"
        confidence = 0
        reason = "Riesgo alto. Mejor no operar."

    elif trend == "UP" and rsi < 70:
        strategy = "WATCHLIST CALL"
        strike = round(price + 5, 2)
        dte = 14
        confidence = 65
        reason = "Tendencia alcista y RSI saludable."

        if entry_ready:
            strategy = "BUY CALL OPTION"
            confidence = 80
            reason = "Entrada CALL confirmada con tendencia alcista y RSI saludable."

    elif trend == "DOWN" and rsi > 30:
        strategy = "WATCHLIST PUT"
        strike = round(price - 5, 2)
        dte = 14
        confidence = 65
        reason = "Tendencia bajista y RSI permite buscar PUT."

        if entry_ready:
            strategy = "BUY PUT OPTION"
            confidence = 80
            reason = "Entrada PUT confirmada con tendencia bajista."

    elif rsi >= 70:
        strategy = "WAIT"
        confidence = 40
        reason = "RSI sobrecomprado. Mejor esperar retroceso."

    elif rsi <= 30:
        strategy = "WAIT"
        confidence = 40
        reason = "RSI sobrevendido. Mejor esperar confirmación."

    state["strategy"] = strategy
    state["option_strategy"] = strategy
    state["strike"] = strike
    state["dte"] = dte
    state["option_confidence"] = confidence
    state["option_reason"] = reason

    return state