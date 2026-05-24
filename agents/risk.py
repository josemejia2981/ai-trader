def risk_agent(state):
    print("⚠️ Evaluando riesgo PRO...")

    signal = state["signal"]
    rsi = state["rsi"]

    if signal == "BUY" and rsi < 55:
        risk = "LOW"
    elif signal == "SELL" and rsi > 70:
        risk = "HIGH"
    else:
        risk = "MEDIUM"

    print(f"⚠️ Riesgo: {risk}")

    state["risk"] = risk
    return state
