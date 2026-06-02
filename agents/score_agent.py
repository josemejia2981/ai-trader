# agents/score_agent.py

def safe_float(value, default=0.0):
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


def score_agent(state):

    print("STEP 8 SCORE")
    print("Calculando score institucional...")

    score = 0
    reasons = []

    trend = state.get("trend")
    signal = state.get("signal")
    rsi = safe_float(state.get("rsi"))
    macd = safe_float(state.get("macd"))
    macd_signal = safe_float(state.get("macd_signal"))
    volume = safe_float(state.get("volume"))
    avg_volume = safe_float(state.get("avg_volume"))
    entry_ready = state.get("entry_ready")
    risk = state.get("risk")

    option_type = str(state.get("option_type", "")).upper()
    entry_type = str(state.get("entry_type", "")).upper()

    risk_reward = safe_float(state.get("risk_reward"))
    delta = abs(safe_float(state.get("delta")))
    spread_pct = safe_float(state.get("spread_pct"), 100)
    option_volume = safe_float(state.get("volume"))
    option_open_interest = safe_float(state.get("openInterest"))
    contract_quality_score = safe_float(state.get("contract_quality_score"))

    entry_price = safe_float(state.get("entry_price"))
    risk_amount = safe_float(state.get("risk_amount"))
    potential_profit = safe_float(state.get("potential_profit"))
    contracts = safe_int(state.get("contracts"), 1)

    trade_allowed = state.get("trade_allowed", True)

    # ------------------------------
    # TENDENCIA Y DIRECCION
    # ------------------------------
    if trend == "UP" and option_type == "CALL":
        score += 18
        reasons.append("CALL alineado con tendencia alcista")
    elif trend == "DOWN" and option_type == "PUT":
        score += 18
        reasons.append("PUT alineado con tendencia bajista")
    elif trend in ["UP", "DOWN"]:
        score += 6
        reasons.append("Tendencia definida, pero dirección no perfecta")

    # ------------------------------
    # SEÑAL
    # ------------------------------
    if signal == "BUY" and option_type == "CALL":
        score += 12
        reasons.append("Señal BUY compatible con CALL")
    elif signal == "SELL" and option_type == "PUT":
        score += 12
        reasons.append("Señal SELL compatible con PUT")
    elif signal == "HOLD":
        score += 4
        reasons.append("Señal HOLD: oportunidad moderada")

    # ------------------------------
    # RSI
    # ------------------------------
    if option_type == "CALL":
        if 45 <= rsi <= 68:
            score += 12
            reasons.append("RSI saludable para CALL")
        elif 68 < rsi <= 75:
            score += 5
            reasons.append("RSI alto pero todavía operable")
        elif rsi > 75:
            score -= 10
            reasons.append("RSI sobrecomprado para CALL")

    elif option_type == "PUT":
        if 30 <= rsi <= 55:
            score += 12
            reasons.append("RSI saludable para PUT")
        elif 20 <= rsi < 30:
            score += 5
            reasons.append("RSI bajo, posible continuación bajista")
        elif rsi < 20:
            score -= 10
            reasons.append("RSI demasiado sobrevendido")

    # ------------------------------
    # MACD
    # ------------------------------
    if option_type == "CALL" and macd > macd_signal:
        score += 8
        reasons.append("MACD favorece CALL")
    elif option_type == "PUT" and macd < macd_signal:
        score += 8
        reasons.append("MACD favorece PUT")

    # ------------------------------
    # VOLUMEN DE LA ACCION
    # ------------------------------
    if volume > avg_volume:
        score += 8
        reasons.append("Volumen de acción superior al promedio")
    elif volume > avg_volume * 0.80:
        score += 4
        reasons.append("Volumen de acción aceptable")

    # ------------------------------
    # ENTRADA
    # ------------------------------
    if entry_ready:
        score += 15
        reasons.append("Entrada confirmada")
    else:
        score -= 8
        reasons.append("Entrada no confirmada")

    if "PULLBACK" in entry_type:
        score += 6
        reasons.append("Entrada tipo pullback detectada")

    # ------------------------------
    # RIESGO DE MERCADO
    # ------------------------------
    if risk == "LOW":
        score += 8
        reasons.append("Riesgo de mercado bajo")
    elif risk == "MEDIUM":
        score += 4
        reasons.append("Riesgo de mercado medio")
    elif risk == "HIGH":
        score -= 20
        reasons.append("Riesgo de mercado alto")

    # ------------------------------
    # DELTA
    # ------------------------------
    if delta >= 0.75:
        score += 14
        reasons.append("Delta fuerte")
    elif delta >= 0.65:
        score += 10
        reasons.append("Delta aceptable")
    elif delta >= 0.50:
        score += 4
        reasons.append("Delta moderado")
    else:
        score -= 15
        reasons.append("Delta débil")

    # ------------------------------
    # RISK / REWARD
    # ------------------------------
    if risk_reward >= 3:
        score += 15
        reasons.append("Risk Reward excelente")
    elif risk_reward >= 2:
        score += 12
        reasons.append("Risk Reward fuerte")
    elif risk_reward >= 1.5:
        score += 6
        reasons.append("Risk Reward aceptable")
    else:
        score -= 12
        reasons.append("Risk Reward débil")

    # ------------------------------
    # LIQUIDEZ DE OPCION
    # ------------------------------
    if option_open_interest >= 3000:
        score += 10
        reasons.append("Open Interest fuerte")
    elif option_open_interest >= 1000:
        score += 7
        reasons.append("Open Interest bueno")
    elif option_open_interest >= 300:
        score += 4
        reasons.append("Open Interest aceptable")
    else:
        score -= 6
        reasons.append("Open Interest bajo")

    if option_volume >= 1000:
        score += 10
        reasons.append("Volumen de opción fuerte")
    elif option_volume >= 100:
        score += 6
        reasons.append("Volumen de opción aceptable")
    elif option_volume >= 30:
        score += 2
        reasons.append("Volumen de opción bajo pero usable")
    else:
        score -= 8
        reasons.append("Volumen de opción muy bajo")

    # ------------------------------
    # SPREAD
    # ------------------------------
    if spread_pct <= 3:
        score += 10
        reasons.append("Spread excelente")
    elif spread_pct <= 6:
        score += 7
        reasons.append("Spread bueno")
    elif spread_pct <= 12:
        score += 3
        reasons.append("Spread aceptable")
    else:
        score -= 12
        reasons.append("Spread demasiado alto")

    # ------------------------------
    # CALIDAD CONTRATO
    # ------------------------------
    if contract_quality_score >= 90:
        score += 8
        reasons.append("Contrato de alta calidad")
    elif contract_quality_score >= 75:
        score += 5
        reasons.append("Contrato de buena calidad")
    elif contract_quality_score >= 60:
        score += 2
        reasons.append("Contrato aceptable")

    # ------------------------------
    # PREMIUM / RIESGO
    # ------------------------------
    if 2 <= entry_price <= 20:
        score += 5
        reasons.append("Premium dentro de rango operable")
    elif 20 < entry_price <= 25:
        score += 2
        reasons.append("Premium alto pero permitido")
    elif entry_price > 25:
        score -= 10
        reasons.append("Premium demasiado caro")

    if risk_amount > 0 and potential_profit > 0:
        score += 5
        reasons.append("Plan de riesgo calculado")

    if contracts > 0:
        score += 5
        reasons.append("Tamaño de posición calculado")

    if trade_allowed is False:
        score -= 25
        reasons.append("Trade no permitido por control de riesgo")

    # ------------------------------
    # LIMITE FINAL
    # ------------------------------
    score = max(0, min(round(score), 100))

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