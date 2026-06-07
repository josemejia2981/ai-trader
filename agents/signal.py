# agents/signal.py - Sistema de señal ponderado
import sys
sys.path.insert(0, '.')
try:
    from config.settings import RSI_CALL_MIN, RSI_CALL_MAX, RSI_PUT_MIN, RSI_PUT_MAX
except Exception:
    RSI_CALL_MIN, RSI_CALL_MAX = 40, 70
    RSI_PUT_MIN, RSI_PUT_MAX = 30, 60


def signal_agent(state):
    print("  Calculando señal...")
    rsi = float(state.get("rsi", 50))
    trend = state.get("trend", "")
    short_trend = state.get("short_trend", "")
    medium_trend = state.get("medium_trend", "")
    macd = float(state.get("macd", 0))
    macd_signal = float(state.get("macd_signal", 0))
    macd_hist = float(state.get("macd_hist", 0))
    macd_momentum = state.get("macd_momentum", "")
    vol_ratio = float(state.get("vol_ratio", 1.0))
    stoch_k = float(state.get("stoch_k", 50))
    stoch_d = float(state.get("stoch_d", 50))
    adx = float(state.get("adx", 20))
    plus_di = float(state.get("plus_di", 20))
    minus_di = float(state.get("minus_di", 20))
    bb_pct_b = float(state.get("bb_pct_b", 0.5))
    bb_position = state.get("bb_position", "MIDDLE")
    support = float(state.get("support", 0))
    resistance = float(state.get("resistance", 0))
    ema21 = float(state.get("ema21", 0))
    price = float(state.get("price", 0))

    # ALCISTA
    bull = 0
    if trend == "UP": bull += 20
    if short_trend == "UP": bull += 10
    if medium_trend == "UP": bull += 10
    if macd > macd_signal: bull += 15
    if macd_hist > 0 and macd_momentum == "BULLISH": bull += 10
    if RSI_CALL_MIN <= rsi <= RSI_CALL_MAX: bull += 15
    elif rsi > RSI_CALL_MAX: bull -= 10
    if stoch_k > stoch_d and stoch_k < 80: bull += 8
    if stoch_k < 30 and stoch_k > stoch_d: bull += 12
    if adx >= 25: bull += 10
    if plus_di > minus_di: bull += 8
    if bb_position == "NEAR_LOWER" and trend == "UP": bull += 10
    elif bb_position == "NEAR_UPPER": bull -= 5
    if vol_ratio >= 1.2: bull += 10
    elif vol_ratio >= 0.9: bull += 5
    if support > 0 and price > support: bull += 5
    if ema21 > 0 and price > ema21: bull += 5

    # BAJISTA
    bear = 0
    if trend == "DOWN": bear += 20
    if short_trend == "DOWN": bear += 10
    if medium_trend == "DOWN": bear += 10
    if macd < macd_signal: bear += 15
    if macd_hist < 0 and macd_momentum == "BEARISH": bear += 10
    if RSI_PUT_MIN <= rsi <= RSI_PUT_MAX: bear += 15
    elif rsi < RSI_PUT_MIN: bear -= 10
    if stoch_k < stoch_d and stoch_k > 20: bear += 8
    if stoch_k > 70 and stoch_k < stoch_d: bear += 12
    if adx >= 25: bear += 10
    if minus_di > plus_di: bear += 8
    if bb_position == "NEAR_UPPER" and trend == "DOWN": bear += 10
    elif bb_position == "NEAR_LOWER": bear -= 5
    if vol_ratio >= 1.2: bear += 10
    elif vol_ratio >= 0.9: bear += 5
    if resistance > 0 and price < resistance: bear += 5
    if ema21 > 0 and price < ema21: bear += 5

    bull = max(0, min(bull, 100))
    bear = max(0, min(bear, 100))

    if bull >= 55 and bull > bear:
        signal, direction, confidence = "BUY", "CALL", bull
    elif bear >= 55 and bear > bull:
        signal, direction, confidence = "SELL", "PUT", bear
    else:
        signal, direction, confidence = "HOLD", "NONE", max(bull, bear)

    print("  Bull:" + str(bull) + " Bear:" + str(bear) + " => " + signal + "/" + direction)
    state["signal"] = signal
    state["direction"] = direction
    state["signal_confidence"] = confidence
    state["bull_score"] = bull
    state["bear_score"] = bear
    return state
