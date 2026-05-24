# agents/score_agent.py

def score_agent(state):

    print("STEP 8 SCORE")
    print("Calculando score institucional...")

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

    trade_allowed = state.get("trade_allowed", False)
    risk_reward = float(state.get("risk_reward") or 0)
    option_volume = int(state.get("option_volume") or 0)
    option_open_interest = int(state.get("option_open_interest") or 0)
    option_contract_score = int(state.get("option_contract_score") or 0)
    option_entry = float(state.get("option_entry") or 0)
    contracts = int(state.get("contracts") or 0)

    # Tendencia
    if trend == "UP":
        score += 20
        reasons.append("Tendencia alcista")
    elif trend == "DOWN":
        score += 10
        reasons.append("Tendencia bajista")

    # RSI
    if isinstance(rsi, (int, float)):
        if 50 <= rsi <= 65:
            score += 15
            reasons.append("RSI optimo")
        elif 65 < rsi <= 70:
            score += 8
            reasons.append("RSI aceptable")
        elif rsi > 80:
            score -= 20
            reasons.append("RSI sobrecomprado")

    # MACD
    if isinstance(macd, (int, float)) and isinstance(macd_signal, (int, float)):
        if macd > macd_signal:
            score += 12
            reasons.append("MACD alcista")

    # Volumen de la accion
    if isinstance(volume, (int, float)) and isinstance(avg_volume, (int, float)):
        if volume > avg_volume:
            score += 10
            reasons.append("Volumen accion superior al promedio")

    # Entrada confirmada
    if entry_ready:
        score += 15
        reasons.append("Entrada confirmada")

    # Riesgo de mercado
    if risk == "LOW":
        score += 8
        reasons.append("Riesgo de mercado bajo")
    elif risk == "HIGH":
        score -= 15
        reasons.append("Riesgo de mercado alto")

    # Trade permitido por control de riesgo
    if trade_allowed:
        score += 15
        reasons.append("Trade permitido por gestion de riesgo")
    else:
        score -= 10
        reasons.append("Trade no permitido por gestion de riesgo")

    # Risk Reward
    if risk_reward >= 2:
        score += 12
        reasons.append("Risk Reward excelente")
    elif risk_reward >= 1.5:
        score += 8
        reasons.append("Risk Reward saludable")
    elif 0 < risk_reward < 1.5:
        score -= 5
        reasons.append("Risk Reward bajo")

    # Liquidez del contrato
    if option_open_interest >= 1000:
        score += 10
        reasons.append("Open Interest fuerte")
    elif option_open_interest >= 300:
        score += 6
        reasons.append("Open Interest aceptable")

    if option_volume >= 500:
        score += 10
        reasons.append("Volumen de opcion fuerte")
    elif option_volume >= 100:
        score += 6
        reasons.append("Volumen de opcion aceptable")

    # Score del contrato
    if option_contract_score >= 90:
        score += 10
        reasons.append("Contrato con score excelente")
    elif option_contract_score >= 80:
        score += 7
        reasons.append("Contrato con score fuerte")
    elif option_contract_score >= 60:
        score += 4
        reasons.append("Contrato con score aceptable")

    # Premium razonable
    if 1 <= option_entry <= 5:
        score += 5
        reasons.append("Premium dentro del rango ideal")

    # Contratos calculados
    if contracts > 0:
        score += 5
        reasons.append("Tamano de posicion calculado")

    score = max(0, min(score, 100))

    if score >= 90:
        rating = "EXCELENTE"
    elif score >= 75:
        rating = "FUERTE"
    elif score >= 60:
        rating = "INTERESANTE"
    elif score >= 40:
        rating = "OBSERVAR"
    else:
        rating = "DESCARTAR"

    state["score"] = score
    state["rating"] = rating
    state["score_reasons"] = reasons

    print(f"Score: {score}/100")
    print(f"Rating: {rating}")

    return state