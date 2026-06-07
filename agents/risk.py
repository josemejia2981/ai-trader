# agents/risk.py - Evaluacion de riesgo basada en ATR, ADX, RSI y señal
def risk_agent(state):
    print("  Evaluando riesgo...")
    signal = state.get("signal", "HOLD")
    rsi = float(state.get("rsi", 50))
    atr_pct = float(state.get("atr_pct", 2.0))
    adx = float(state.get("adx", 20))
    trend = state.get("trend", "")
    direction = state.get("direction", "NONE")
    vol_ratio = float(state.get("vol_ratio", 1.0))
    bb_position = state.get("bb_position", "MIDDLE")
    macd_momentum = state.get("macd_momentum", "")

    risk_score = 50
    notes = []

    if atr_pct > 4.0:
        risk_score += 25; notes.append("Volatilidad muy alta (ATR " + str(round(atr_pct,1)) + "%)")
    elif atr_pct > 2.5:
        risk_score += 12; notes.append("Volatilidad elevada (ATR " + str(round(atr_pct,1)) + "%)")
    elif atr_pct < 1.0:
        risk_score -= 10; notes.append("Baja volatilidad - bueno para opciones")
    else:
        risk_score -= 5

    if adx >= 30:
        risk_score -= 15; notes.append("Tendencia fuerte (ADX " + str(round(adx,1)) + ")")
    elif adx >= 20:
        risk_score -= 8; notes.append("Tendencia moderada (ADX " + str(round(adx,1)) + ")")
    else:
        risk_score += 15; notes.append("Sin tendencia clara (ADX " + str(round(adx,1)) + ")")

    if rsi > 75:
        risk_score += 20; notes.append("RSI sobrecomprado (" + str(round(rsi,1)) + ")")
    elif rsi < 25:
        risk_score += 20; notes.append("RSI sobrevendido (" + str(round(rsi,1)) + ")")
    elif 40 <= rsi <= 60:
        risk_score -= 10

    if signal == "BUY" and trend == "UP":
        risk_score -= 15; notes.append("Señal alineada con tendencia UP")
    elif signal == "SELL" and trend == "DOWN":
        risk_score -= 15; notes.append("Señal alineada con tendencia DOWN")
    elif signal != "HOLD":
        if (signal == "BUY" and trend == "DOWN") or (signal == "SELL" and trend == "UP"):
            risk_score += 20; notes.append("Señal CONTRA tendencia")

    if bb_position == "NEAR_UPPER" and direction == "CALL":
        risk_score += 12; notes.append("Precio cerca banda superior - menor margen CALL")
    elif bb_position == "NEAR_LOWER" and direction == "PUT":
        risk_score += 12; notes.append("Precio cerca banda inferior - menor margen PUT")

    if direction == "CALL" and macd_momentum == "BULLISH":
        risk_score -= 8
    elif direction == "PUT" and macd_momentum == "BEARISH":
        risk_score -= 8
    else:
        risk_score += 8

    if vol_ratio < 0.5:
        risk_score += 10; notes.append("Volumen muy bajo")

    risk_score = max(0, min(risk_score, 100))
    risk_level = "HIGH" if risk_score >= 70 else "MEDIUM" if risk_score >= 40 else "LOW"

    print("  Riesgo: " + risk_level + " (score:" + str(risk_score) + ")")
    state["risk"] = risk_level
    state["risk_score"] = risk_score
    state["risk_notes"] = notes
    return state
