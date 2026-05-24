def signal_agent(state):

    print("📡 Generando señal PRO++...")

    rsi = state["rsi"]
    trend = state["trend"]
    macd = state["macd"]
    macd_signal = state["macd_signal"]

    price = state["price"]
    support = state["support"]
    resistance = state["resistance"]

    volume = state["volume"]
    avg_volume = state["avg_volume"]

    signal = "HOLD"

    # BUY fuerte
    if (
        trend == "UP"
        and macd > macd_signal
        and rsi > 50
        and volume > avg_volume
        and price > support
    ):
        signal = "BUY"

    # SELL fuerte
    elif (
        trend == "DOWN"
        and macd < macd_signal
        and rsi < 50
        and volume > avg_volume
        and price < resistance
    ):
        signal = "SELL"

    print(f"📡 Señal: {signal}")

    state["signal"] = signal

    return state