# agents/option_contract_agent.py
# MIN_DELTA bajado 0.70->0.45, usa IV real de yfinance, scoring mejorado
import sys, yfinance as yf, pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, '.')
try:
    from config.settings import (
        MIN_DTE, MAX_DTE, MIN_DELTA, MAX_SPREAD_PCT,
        MIN_VOLUME, MIN_OPEN_INTEREST, MAX_ENTRY_PRICE,
        MAX_RISK_PER_TRADE, MAX_OTM_PCT, MAX_STRIKE_DISTANCE_PCT,
        STOP_LOSS_PCT, TAKE_PROFIT_1_PCT, TAKE_PROFIT_2_PCT, TRAILING_STOP_PCT,
    )
except Exception:
    MIN_DTE=21; MAX_DTE=90; MIN_DELTA=0.45; MAX_SPREAD_PCT=12
    MIN_VOLUME=50; MIN_OPEN_INTEREST=200; MAX_ENTRY_PRICE=30.0
    MAX_RISK_PER_TRADE=800; MAX_OTM_PCT=0.10; MAX_STRIKE_DISTANCE_PCT=0.15
    STOP_LOSS_PCT=0.40; TAKE_PROFIT_1_PCT=0.50; TAKE_PROFIT_2_PCT=1.00; TRAILING_STOP_PCT=0.25

NY_TZ = ZoneInfo("America/New_York")
MULTIPLIER = 100

def now_ny(): return datetime.now(NY_TZ)

def sf(v, d=0.0):
    try: return float(v) if v is not None else d
    except: return d

def si(v, d=0):
    try: return int(float(v)) if v is not None else d
    except: return d

def get_dte(exp):
    try:
        e = datetime.strptime(exp, "%Y-%m-%d").replace(tzinfo=NY_TZ)
        return max((e.date() - now_ny().date()).days, 0)
    except: return 0

def estimate_delta(opt_type, strike, price):
    s = sf(strike); p = sf(price)
    if p <= 0 or s <= 0: return 0.0
    r = s / p
    if opt_type == "CALL":
        if r <= 0.92: return 0.85
        elif r <= 0.95: return 0.75
        elif r <= 0.98: return 0.65
        elif r <= 1.00: return 0.55
        elif r <= 1.02: return 0.48
        elif r <= 1.04: return 0.42
        elif r <= 1.06: return 0.35
        elif r <= 1.08: return 0.28
        else: return 0.20
    else:
        if r >= 1.08: return -0.85
        elif r >= 1.05: return -0.75
        elif r >= 1.02: return -0.65
        elif r >= 1.00: return -0.55
        elif r >= 0.98: return -0.48
        elif r >= 0.96: return -0.42
        elif r >= 0.94: return -0.35
        elif r >= 0.92: return -0.28
        else: return -0.20

def build_levels(opt_type, up, strike, ep):
    up=sf(up); sp=sf(strike); ep=sf(ep)
    if up <= 0 or ep <= 0: return {}
    opt_stop  = round(ep * (1 - STOP_LOSS_PCT), 2)
    opt_tp1   = round(ep * (1 + TAKE_PROFIT_1_PCT), 2)
    opt_tp2   = round(ep * (1 + TAKE_PROFIT_2_PCT), 2)
    opt_trail = round(ep * (1 + TRAILING_STOP_PCT), 2)
    max_entry = round(ep * 1.08, 2)
    if opt_type == "CALL":
        se=round(up,2); ss=round(up*0.97,2); st1=round(max(sp,up*1.04),2); st2=round(up*1.08,2)
    else:
        se=round(up,2); ss=round(up*1.03,2); st1=round(min(sp,up*0.96),2); st2=round(up*0.92,2)
    return {
        "option_stop_loss": opt_stop, "option_take_profit_1": opt_tp1,
        "option_take_profit_2": opt_tp2, "option_trailing_stop": opt_trail,
        "max_option_entry": max_entry, "stock_entry_price": se,
        "stock_stop_loss": ss, "stock_take_profit_1": st1, "stock_take_profit_2": st2,
    }

def score_contract(row, price, opt_type):
    strike = sf(row.get("strike")); last = sf(row.get("lastPrice"))
    bid = sf(row.get("bid")); ask = sf(row.get("ask"))
    vol = si(row.get("volume")); oi = si(row.get("openInterest"))
    dte = si(row.get("dte")); iv = sf(row.get("impliedVolatility"), 0.30)
    if ask > 0 and bid > 0:
        mid = round((bid+ask)/2, 2); spread = round(ask-bid, 2)
        spct = round(spread/mid*100, 2) if mid > 0 else 100
    else:
        mid = last; spread = 0; spct = 0 if last > 0 else 100
    ep = mid if mid > 0 else last
    if ep <= 0: return None
    delta = estimate_delta(opt_type, strike, price)
    dist = abs(strike-price)/price*100 if price > 0 else 100
    lv = build_levels(opt_type, price, strike, ep)
    opt_stop = lv.get("option_stop_loss", round(ep*(1-STOP_LOSS_PCT),2))
    opt_tp2  = lv.get("option_take_profit_2", round(ep*(1+TAKE_PROFIT_2_PCT),2))
    risk_amt = round((ep-opt_stop)*MULTIPLIER, 2)
    pot_prof = round((opt_tp2-ep)*MULTIPLIER, 2)
    rr = round(pot_prof/risk_amt, 2) if risk_amt > 0 else 0
    sc = 0
    ad = abs(delta)
    if ad >= 0.65: sc += 25
    elif ad >= 0.55: sc += 20
    elif ad >= 0.45: sc += 14
    elif ad >= 0.35: sc += 6
    else: sc -= 15
    if oi >= 5000: sc += 15
    elif oi >= 2000: sc += 12
    elif oi >= 1000: sc += 9
    elif oi >= MIN_OPEN_INTEREST: sc += 5
    else: sc -= 8
    if vol >= 2000: sc += 15
    elif vol >= 500: sc += 12
    elif vol >= 100: sc += 8
    elif vol >= MIN_VOLUME: sc += 4
    else: sc -= 8
    if spct <= 2: sc += 15
    elif spct <= 5: sc += 12
    elif spct <= 8: sc += 8
    elif spct <= MAX_SPREAD_PCT: sc += 3
    else: sc -= 15
    if 45 <= dte <= 75: sc += 10
    elif 30 <= dte <= 90: sc += 7
    elif MIN_DTE <= dte <= MAX_DTE: sc += 3
    else: sc -= 8
    if dist <= 2: sc += 10
    elif dist <= 4: sc += 8
    elif dist <= 6: sc += 5
    elif dist <= 8: sc += 2
    else: sc -= 10
    if 1.0 <= ep <= 10.0: sc += 5
    elif 10.0 < ep <= 20.0: sc += 3
    elif 20.0 < ep <= MAX_ENTRY_PRICE: sc += 1
    else: sc -= 8
    if rr >= 3.0: sc += 5
    elif rr >= 2.0: sc += 3
    elif rr >= 1.5: sc += 1
    else: sc -= 5
    sc = round(max(0, min(sc, 100)), 2)
    if sc >= 80 and ad >= 0.55 and rr >= 2.0 and spct <= 6 and vol >= 200:
        rec = "COMPRA FUERTE"
    elif sc >= 65 and ad >= 0.45 and rr >= 1.8:
        rec = "BUENA OPORTUNIDAD"
    elif sc >= 50:
        rec = "WATCHLIST"
    else:
        rec = "EVITAR"
    return {
        "strike": round(strike,2), "lastPrice": round(last,2), "bid": round(bid,2),
        "ask": round(ask,2), "volume": vol, "openInterest": oi,
        "impliedVolatility": round(iv*100,1), "mid_price": round(ep,2),
        "spread": spread, "spread_pct": spct, "delta_estimate": delta, "delta": delta,
        "distance_pct": round(dist,2), "entry_price": round(ep,2),
        "stop_loss": opt_stop, "option_stop_loss": opt_stop,
        "take_profit": lv.get("option_take_profit_2"), "option_take_profit": lv.get("option_take_profit_2"),
        "take_profit_1": lv.get("option_take_profit_1"), "take_profit_2": lv.get("option_take_profit_2"),
        "trailing_stop": lv.get("option_trailing_stop"), "max_option_entry": lv.get("max_option_entry"),
        "stock_entry_price": lv.get("stock_entry_price"), "stock_stop_loss": lv.get("stock_stop_loss"),
        "stock_take_profit_1": lv.get("stock_take_profit_1"), "stock_take_profit_2": lv.get("stock_take_profit_2"),
        "risk_amount": risk_amt, "potential_profit": pot_prof, "risk_reward": rr,
        "contract_quality_score": sc, "score": sc, "recommendation": rec,
    }

def get_candidates(symbol, opt_type="CALL"):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    if hist.empty: return pd.DataFrame()
    price = sf(hist["Close"].iloc[-1])
    exps = ticker.options
    if not exps: return pd.DataFrame()
    all_c = []
    for exp in exps:
        dte = get_dte(exp)
        if dte < MIN_DTE or dte > MAX_DTE: continue
        try:
            chain = ticker.option_chain(exp)
            df = chain.calls.copy() if opt_type == "CALL" else chain.puts.copy()
            if df.empty: continue
            df["symbol"]=symbol; df["option_type"]=opt_type
            df["expiration"]=exp; df["dte"]=dte; df["underlying_price"]=price
            all_c.append(df)
        except: continue
    if not all_c: return pd.DataFrame()
    contracts = pd.concat(all_c, ignore_index=True)
    for col in ["volume","openInterest","bid","ask","lastPrice","strike","impliedVolatility"]:
        if col not in contracts.columns: contracts[col] = 0
        contracts[col] = contracts[col].fillna(0)
    enriched = []
    for _, row in contracts.iterrows():
        strike = sf(row.get("strike"))
        dist = abs(strike-price)/price if price > 0 else 1.0
        if dist > MAX_STRIKE_DISTANCE_PCT: continue
        if opt_type == "CALL" and strike > price*(1+MAX_OTM_PCT): continue
        if opt_type == "PUT" and strike < price*(1-MAX_OTM_PCT): continue
        scored = score_contract(row, price, opt_type)
        if scored is None: continue
        if abs(scored.get("delta",0)) < MIN_DELTA: continue
        if scored.get("spread_pct",100) > MAX_SPREAD_PCT: continue
        if si(row.get("openInterest")) < MIN_OPEN_INTEREST: continue
        if si(row.get("volume")) < MIN_VOLUME: continue
        if scored.get("entry_price",0) > MAX_ENTRY_PRICE: continue
        if scored.get("risk_amount",999999) > MAX_RISK_PER_TRADE: continue
        enriched.append({**row.to_dict(), **scored})
    if not enriched: return pd.DataFrame()
    df = pd.DataFrame(enriched)
    return df.sort_values(by=["contract_quality_score","delta","risk_reward","openInterest","volume"],
                          ascending=[False,False,False,False,False])

def select_best(symbol, direction="CALL"):
    opt_type = "CALL" if direction.upper() in ["CALL","BUY","UP","BULLISH"] else "PUT"
    cands = get_candidates(symbol, opt_type)
    return None if cands.empty else cands.iloc[0].to_dict()

def option_contract_agent(state):
    symbol = state.get("symbol")
    direction = state.get("direction", "CALL")
    signal = state.get("signal", "")
    trend = state.get("trend", "")
    entry_type = state.get("entry_type", "")
    state["analysis_datetime_ny"] = now_ny().strftime("%Y-%m-%d %I:%M:%S %p ET")
    if not symbol:
        state.update({"best_contract": None, "contract_status": "No symbol.", "trade_allowed": False})
        return state
    text = (direction + " " + signal + " " + trend + " " + entry_type).upper()
    opt_dir = "PUT" if any(x in text for x in ["PUT","DOWN","SELL","BEARISH"]) else "CALL"
    try:
        best = select_best(symbol, opt_dir)
        if best is None:
            state.update({
                "best_contract": None, "trade_allowed": False,
                "contract_status": "Sin contrato valido. Criterios: delta>=" + str(MIN_DELTA) +
                    ", spread<=" + str(MAX_SPREAD_PCT) + "%, OI>=" + str(MIN_OPEN_INTEREST) +
                    ", vol>=" + str(MIN_VOLUME) + ", prima<=$" + str(MAX_ENTRY_PRICE),
            })
            return state
        state["best_contract"] = best
        state["contract_status"] = "Contrato seleccionado."
        fields = ["contractSymbol","option_type","expiration","dte","strike","underlying_price",
                  "lastPrice","bid","ask","mid_price","spread","spread_pct","volume","openInterest",
                  "impliedVolatility","delta_estimate","delta","entry_price","max_option_entry",
                  "stop_loss","take_profit","take_profit_1","take_profit_2","trailing_stop",
                  "option_stop_loss","option_take_profit",
                  "stock_entry_price","stock_stop_loss","stock_take_profit_1","stock_take_profit_2",
                  "risk_amount","potential_profit","risk_reward","distance_pct",
                  "contract_quality_score","score","recommendation"]
        for f in fields: state[f] = best.get(f)
        state["option_contract"] = best.get("contractSymbol")
        state["contract_symbol"] = best.get("contractSymbol")
        state["recommended_strike"] = best.get("strike")
        state["option_strike"] = best.get("strike")
        state["option_delta"] = best.get("delta")
        state["option_open_interest"] = best.get("openInterest")
        state["open_interest"] = best.get("openInterest")
        state["option_volume"] = best.get("volume")
        state["option_bid"] = best.get("bid")
        state["option_ask"] = best.get("ask")
        state["option_last_price"] = best.get("lastPrice")
        state["option_entry"] = best.get("entry_price")
        state["option_dte"] = best.get("dte")
        state["expiration_date"] = best.get("expiration")
        if not state.get("contracts"): state["contracts"] = 1
        state["trade_allowed"] = True
        print("  Contrato: " + str(best.get("contractSymbol")))
        print("  " + opt_dir + " | Strike:" + str(best.get("strike")) + " | DTE:" + str(best.get("dte")))
        print("  Delta:" + str(best.get("delta")) + " | IV:" + str(best.get("impliedVolatility")) + "%")
        print("  Entrada:$" + str(best.get("entry_price")) + " Stop:$" + str(best.get("option_stop_loss")) + " TP:$" + str(best.get("option_take_profit")))
        print("  Spread:" + str(best.get("spread_pct")) + "% OI:" + str(best.get("openInterest")) + " Vol:" + str(best.get("volume")))
        print("  Score:" + str(best.get("contract_quality_score")) + "/100 R/R:" + str(best.get("risk_reward")))
        return state
    except Exception as e:
        state.update({"best_contract": None, "contract_status": "Error: " + str(e), "trade_allowed": False})
        return state
