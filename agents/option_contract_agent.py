# agents/option_contract_agent.py

import pandas as pd
import yfinance as yf
from datetime import datetime


MIN_DTE = 30
MAX_DTE = 60

MIN_PREMIUM = 1.00
MAX_PREMIUM = 5.00

MIN_VOLUME = 1
MIN_OPEN_INTEREST = 10


def get_dte(expiration):
    today = datetime.now().date()
    exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    return (exp_date - today).days


def option_contract_agent(state):
    print("Buscando contrato de opcion para el trade plan...")

    symbol = state.get("symbol")
    entry_ready = state.get("entry_ready", False)
    entry_type = state.get("entry_type", "")

    if not entry_ready or not symbol:
        return state

    option_side = "CALL" if "CALL" in entry_type else "PUT" if "PUT" in entry_type else None

    if option_side is None:
        return state

    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options

        if not expirations:
            print(f"No hay expiraciones disponibles para {symbol}")
            return state

        valid_expirations = []

        for expiration in expirations:
            dte = get_dte(expiration)

            if MIN_DTE <= dte <= MAX_DTE:
                valid_expirations.append((expiration, dte))

        if not valid_expirations:
            print(f"No hay expiraciones entre {MIN_DTE} y {MAX_DTE} dias para {symbol}")
            return state

        price = float(state.get("price", 0))
        all_candidates = []

        for expiration, dte in valid_expirations:
            try:
                chain = ticker.option_chain(expiration)

                if option_side == "CALL":
                    options = chain.calls.copy()
                else:
                    options = chain.puts.copy()

                if options.empty:
                    continue

                options["dte"] = dte
                options["expiration"] = expiration
                options["distance"] = abs(options["strike"] - price)

                for col in ["bid", "ask", "lastPrice", "volume", "openInterest", "strike"]:
                    if col in options.columns:
                        options[col] = pd.to_numeric(options[col], errors="coerce").fillna(0)

                options["entry"] = 0.0

                valid_mid = (options["bid"] > 0) & (options["ask"] > 0)

                options.loc[valid_mid, "entry"] = (
                    (options["bid"] + options["ask"]) / 2
                ).round(2)

                options.loc[options["entry"] <= 0, "entry"] = options["lastPrice"]

                options = options[
                    (options["entry"] >= MIN_PREMIUM) &
                    (options["entry"] <= MAX_PREMIUM) &
                    (options["volume"] >= MIN_VOLUME) &
                    (options["openInterest"] >= MIN_OPEN_INTEREST)
                ]

                if options.empty:
                    continue

                options["score"] = 0

                options.loc[options["openInterest"] >= 50, "score"] += 10
                options.loc[options["openInterest"] >= 100, "score"] += 10
                options.loc[options["openInterest"] >= 300, "score"] += 10

                options.loc[options["volume"] >= 5, "score"] += 10
                options.loc[options["volume"] >= 20, "score"] += 10
                options.loc[options["volume"] >= 50, "score"] += 10

                options.loc[options["distance"] <= price * 0.05, "score"] += 20
                options.loc[options["distance"] <= price * 0.10, "score"] += 10

                options.loc[(options["dte"] >= 30) & (options["dte"] <= 45), "score"] += 10
                options.loc[(options["entry"] >= 1.50) & (options["entry"] <= 4.00), "score"] += 10

                all_candidates.append(options)

            except Exception as e:
                print(f"Error leyendo expiracion {expiration} para {symbol}: {e}")
                continue

        if not all_candidates:
            print(
                f"No hay contratos compatibles para {symbol} "
                f"con premium entre ${MIN_PREMIUM} y ${MAX_PREMIUM}"
            )
            return state

        final_options = pd.concat(all_candidates, ignore_index=True)

        best = final_options.sort_values(
            by=["score", "openInterest", "volume"],
            ascending=False
        ).iloc[0]

        entry = round(float(best.get("entry", 0) or 0), 2)

        if entry <= 0:
            print(f"Contrato sin precio valido para {symbol}")
            return state

        stop_loss = round(entry * 0.70, 2)
        take_profit = round(entry * 1.50, 2)

        state["option_contract"] = best.get("contractSymbol")
        state["option_type"] = option_side
        state["option_strike"] = float(best.get("strike"))
        state["option_expiration"] = best.get("expiration")
        state["option_dte"] = int(best.get("dte"))
        state["option_entry"] = entry
        state["option_stop_loss"] = stop_loss
        state["option_take_profit"] = take_profit
        state["option_bid"] = float(best.get("bid", 0) or 0)
        state["option_ask"] = float(best.get("ask", 0) or 0)
        state["option_last_price"] = float(best.get("lastPrice", 0) or 0)
        state["option_volume"] = int(best.get("volume", 0) or 0)
        state["option_open_interest"] = int(best.get("openInterest", 0) or 0)
        state["option_contract_score"] = int(best.get("score", 0) or 0)

        print("Contrato agregado al state:")
        print(f"Contrato: {state['option_contract']}")
        print(f"Tipo: {state['option_type']}")
        print(f"Strike: {state['option_strike']}")
        print(f"Expiracion: {state['option_expiration']}")
        print(f"DTE: {state['option_dte']}")
        print(f"Entrada opcion: {state['option_entry']}")
        print(f"Stop opcion: {state['option_stop_loss']}")
        print(f"Take Profit opcion: {state['option_take_profit']}")
        print(f"Volumen: {state['option_volume']}")
        print(f"Open Interest: {state['option_open_interest']}")
        print(f"Score contrato: {state['option_contract_score']}")

        return state

    except Exception as e:
        print(f"Error buscando contrato para {symbol}: {e}")
        return state