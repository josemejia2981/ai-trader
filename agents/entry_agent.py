# agents/entry_agent.py - Confirmacion de entrada con multiples indicadores
# DEBE correr ANTES de options_agent en el pipeline
import sys
sys.path.insert(0, '.')
try:
    from config.settings import RSI_CALL_MIN, RSI_CALL_MAX, RSI_PUT_MIN, RSI_PUT_MAX
except Exception:
    RSI_CALL_MIN, RSI_CALL_MAX = 40, 70
    RSI_PUT_MIN, RSI_PUT_MAX = 30, 60


def entry_agent(state):
    print("  Analizando entrada...")
    price = float(state.get("price", 0))
    trend = state.get("trend", "")
    signal = state.get("signal", "HOLD")
    direction = state.get("direction", "NONE")
    rsi = float(state.get("rsi", 50))
    ema21 = float(state.get("ema21", 0))
    ema50 = float(state.get("ema50", 0))
    macd = float(state.get("macd", 0))
    macd_signal_val = float(state.get("macd_signal", 0))
    macd_momentum = state.get("macd_momentum", "")
    adx = float(state.get("adx", 20))
    plus_di = float(state.get("plus_di", 20))
    minus_di = float(state.get("minus_di", 20))
    stoch_k = float(state.get("stoch_k", 50))
    stoch_d = float(state.get("stoch_d", 50))
    bb_pct_b = float(state.get("bb_pct_b", 0.5))
    bb_position = state.get("bb_position", "MIDDLE")
    vol_ratio = float(state.get("vol_ratio", 1.0))
    support = float(state.get("support", 0))
    resistance = float(state.get("resistance", 0))
    risk = state.get("risk", "MEDIUM")

    # Bloqueadores
    if risk == "HIGH":
        state.update({"entry_ready": False, "entry_type": "NONE",
                      "entry_trigger": "Bloqueado: riesgo alto.", "entry_score": 0, "entry_reasons": []})
        return state
    if signal == "HOLD" or direction == "NONE":
        state.update({"entry_ready": False, "entry_type": "NONE",
                      "entry_trigger": "Sin señal activa.", "entry_score": 0, "entry_reasons": []})
        return state

    entry_ready = False
    entry_type = "NONE"
    entry_trigger = "Sin entrada confirmada."
    entry_score = 0
    reasons = []

    if direction == "CALL":
        sc = 0
        if trend == "UP": sc += 25; reasons.append("Tendencia UP")
        if macd > macd_signal_val: sc += 20; reasons.append("MACD sobre signal")
        if macd_momentum == "BULLISH": sc += 10; reasons.append("Momentum MACD bullish")
        if RSI_CALL_MIN <= rsi <= RSI_CALL_MAX: sc += 15; reasons.append("RSI saludable " + str(round(rsi,1)))
        elif rsi > RSI_CALL_MAX: sc -= 10
        if adx >= 20 and plus_di > minus_di: sc += 12; reasons.append("ADX/DI alcista")
        if stoch_k > stoch_d and stoch_k < 80: sc += 10; reasons.append("Stoch alcista")
        if price > ema21: sc += 8; reasons.append("Precio > EMA21")
        if ema21 > ema50: sc += 5; reasons.append("EMA21 > EMA50 (bull)")
        if bb_position == "NEAR_LOWER": sc += 12; reasons.append("Pullback BB inferior")
        if support > 0 and abs(price - support) / price < 0.02: sc += 10; reasons.append("En soporte")
        if vol_ratio >= 1.2: sc += 8; reasons.append("Vol " + str(round(vol_ratio,1)) + "x")
        elif vol_ratio >= 0.9: sc += 4
        sc = max(0, min(sc, 100))
        entry_score = sc
        if sc >= 50:
            entry_ready = True
            entry_type = "PULLBACK CALL" if bb_position == "NEAR_LOWER" else "MOMENTUM CALL"
            entry_trigger = "CALL confirmada (score " + str(sc) + "): " + ", ".join(reasons[:3])

    elif direction == "PUT":
        sc = 0
        if trend == "DOWN": sc += 25; reasons.append("Tendencia DOWN")
        if macd < macd_signal_val: sc += 20; reasons.append("MACD bajo signal")
        if macd_momentum == "BEARISH": sc += 10; reasons.append("Momentum MACD bearish")
        if RSI_PUT_MIN <= rsi <= RSI_PUT_MAX: sc += 15; reasons.append("RSI valido " + str(round(rsi,1)))
        elif rsi < RSI_PUT_MIN: sc -= 10
        if adx >= 20 and minus_di > plus_di: sc += 12; reasons.append("ADX/DI bajista")
        if stoch_k < stoch_d and stoch_k > 20: sc += 10; reasons.append("Stoch bajista")
        if price < ema21: sc += 8; reasons.append("Precio < EMA21")
        if ema21 < ema50: sc += 5; reasons.append("EMA21 < EMA50 (bear)")
        if bb_position == "NEAR_UPPER": sc += 12; reasons.append("Rechazo BB superior")
        if resistance > 0 and abs(price - resistance) / price < 0.02: sc += 10; reasons.append("En resistencia")
        if vol_ratio >= 1.2: sc += 8; reasons.append("Vol " + str(round(vol_ratio,1)) + "x")
        elif vol_ratio >= 0.9: sc += 4
        sc = max(0, min(sc, 100))
        entry_score = sc
        if sc >= 50:
            entry_ready = True
            entry_type = "PULLBACK PUT" if bb_position == "NEAR_UPPER" else "MOMENTUM PUT"
            entry_trigger = "PUT confirmada (score " + str(sc) + "): " + ", ".join(reasons[:3])

    print("  Entrada lista: " + str(entry_ready) + " | Tipo: " + entry_type + " | Score: " + str(entry_score))
    state["entry_ready"] = entry_ready
    state["entry_type"] = entry_type
    state["entry_trigger"] = entry_trigger
    state["entry_score"] = entry_score
    state["entry_reasons"] = reasons
    return state
