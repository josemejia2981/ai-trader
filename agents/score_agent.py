# agents/score_agent.py

def score_agent(state):

    print("STEP 8 🏆 SCORE")
    print("🏆 Calculando score institucional...")

    score = 0
    reasons = []

    trend = state.get("trend")
    rsi = state.get("rsi")
    macd = state.get("macd")
    macd_signal = state.get("macd_signal")
    volume = state.get("volume")
    avg_volume = state.get("avg_volume")
    entry_ready = state.get("entry_ready")
    risk = state.get("risk")

    # Tendencia
    if trend == "UP":
        score += 25
        reasons.append("Tendencia alcista")

    # RSI
    if isinstance(rsi, (int, float)):
        if 50 <= rsi <= 65:
            score += 20
            reasons.append("RSI óptimo")
        elif 65 < rsi <= 70:
            score += 10
            reasons.append("RSI aceptable")
        elif rsi > 80:
            score -= 20
            reasons.append("RSI sobrecomprado")

    # MACD
    if isinstance(macd, (int, float)) and isinstance(macd_signal, (int, float)):
        if macd > macd_signal:
            score += 20
            reasons.append("MACD alcista")

    # Volumen
    if isinstance(volume, (int, float)) and isinstance(avg_volume, (int, float)):
        if volume > avg_volume:
            score += 15
            reasons.append("Volumen superior al promedio")

    # Entrada confirmada
    if entry_ready:
        score += 20
        reasons.append("Entrada confirmada")

    # Riesgo
    if risk == "LOW":
        score += 10
        reasons.append("Riesgo bajo")

    elif risk == "HIGH":
        score -= 15
        reasons.append("Riesgo alto")

    score = max(0, min(score, 100))

    if score >= 85:
        rating = "EXCELENTE"
    elif score >= 70:
        rating = "FUERTE"
    elif score >= 55:
        rating = "INTERESANTE"
    elif score >= 40:
        rating = "OBSERVAR"
    else:
        rating = "DESCARTAR"

    state["score"] = score
    state["rating"] = rating
    state["score_reasons"] = reasons

    print(f"🏆 Score: {score}/100")
    print(f"📊 Rating: {rating}")

    return state