# agents/options_agent.py

def options_agent(state):

    technical = state.get("technical", "")
    news = state.get("news", "neutral")
    risk = state.get("risk", "LOW RISK")

    strategy = "NO TRADE"

    if risk == "HIGH RISK":
        strategy = "NO TRADE"

    elif "OVERBOUGHT PUT" in technical and news == "bearish":
        strategy = "BUY PUT OPTION"

    elif "OVERSOLD CALL" in technical and news == "bullish":
        strategy = "BUY CALL OPTION"

    elif risk == "LOW RISK":
        strategy = "WAIT"

    state["strategy"] = strategy

    return state