# agents/entry_agent.py

def entry_agent(state):
    print("🚪 Analizando condiciones de entrada...")

    price = state.get("price")
    trend = state.get("trend")
    rsi = state.get("rsi")
    ema21 = state.get("ema21")

    entry_ready = False
    trigger = "No hay entrada confirmada."
    entry_type = "NONE"

    if trend == "UP" and price and ema21 and price > ema21 and rsi and 45 <= rsi <= 70:
        entry_ready = True
        trigger = "Entrada CALL tipo pullback confirmada: tendencia UP, precio sobre EMA21 y RSI saludable."
        entry_type = "PULLBACK CALL"

    elif trend == "DOWN" and price and ema21 and price < ema21 and rsi and 30 <= rsi <= 55:
        entry_ready = True
        trigger = "Entrada PUT tipo pullback confirmada: tendencia DOWN, precio bajo EMA21 y RSI válido."
        entry_type = "PULLBACK PUT"

    state["entry_ready"] = entry_ready
    state["entry_trigger"] = trigger
    state["entry_type"] = entry_type

    print(f"🚪 Entrada lista: {entry_ready}")
    print(f"📌 Trigger: {trigger}")
    print(f"🎯 Tipo entrada: {entry_type}")

    return state