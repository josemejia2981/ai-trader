print("INICIANDO BOT...")

from agents.market_data import get_market_data
from agents.signal import signal_agent
from agents.risk import risk_agent
from agents.options_agent import options_agent
from agents.entry_agent import entry_agent
from agents.option_contract_agent import option_contract_agent
from agents.trade_plan_agent import trade_plan_agent
from agents.score_agent import score_agent
from agents.report_agent import report_agent

try:
    from agents.options_scanner import options_scanner
except Exception:
    options_scanner = None

try:
    from agents.portfolio_agent import portfolio_agent
except Exception:
    portfolio_agent = None


SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META",
    "AMZN", "GOOGL", "AMD", "NFLX", "PLTR",
    "AVGO", "CRM", "UBER", "SNOW", "SHOP",
    "COIN", "QQQ", "SPY"
]


def show_contract_info(state):
    contract = state.get("best_contract")

    if not contract:
        print("No se encontro contrato valido.")
        print("Estado contrato:", state.get("contract_status", "N/A"))
        return

    print("")
    print("CONTRATO SELECCIONADO")
    print("------------------------------")
    print("Contrato:", contract.get("contractSymbol"))
    print("Tipo:", contract.get("option_type"))
    print("Expiracion:", contract.get("expiration"))
    print("DTE:", contract.get("dte"))
    print("Strike:", contract.get("strike"))
    print("Precio accion:", contract.get("underlying_price"))
    print("Last Price:", contract.get("lastPrice"))
    print("Bid:", contract.get("bid"))
    print("Ask:", contract.get("ask"))
    print("Mid Price:", contract.get("mid_price"))
    print("Spread:", contract.get("spread"))
    print("Spread %:", contract.get("spread_pct"))
    print("Volumen:", contract.get("volume"))
    print("Open Interest:", contract.get("openInterest"))
    print("Delta estimado:", contract.get("delta_estimate"))
    print("Score contrato:", contract.get("contract_quality_score"))
    print("")
    print("PLAN DEL CONTRATO")
    print("------------------------------")
    print("Entrada recomendada:", contract.get("entry_price"))
    print("Stop Loss:", contract.get("stop_loss"))
    print("Take Profit:", contract.get("take_profit"))
    print("Riesgo estimado:", contract.get("risk_amount"))
    print("Ganancia potencial:", contract.get("potential_profit"))
    print("Risk / Reward:", contract.get("risk_reward"))
    print("------------------------------")


def normalize_contract_state(state):
    contract = state.get("best_contract")

    if not isinstance(contract, dict):
        return state

    state["contractSymbol"] = contract.get("contractSymbol")
    state["option_contract"] = contract.get("contractSymbol")
    state["option_type"] = contract.get("option_type")
    state["expiration"] = contract.get("expiration")
    state["dte"] = contract.get("dte")
    state["strike"] = contract.get("strike")
    state["underlying_price"] = contract.get("underlying_price")
    state["lastPrice"] = contract.get("lastPrice")
    state["bid"] = contract.get("bid")
    state["ask"] = contract.get("ask")
    state["mid_price"] = contract.get("mid_price")
    state["spread"] = contract.get("spread")
    state["spread_pct"] = contract.get("spread_pct")
    state["volume"] = contract.get("volume")
    state["openInterest"] = contract.get("openInterest")
    state["delta_estimate"] = contract.get("delta_estimate")
    state["contract_quality_score"] = contract.get("contract_quality_score")

    state["entry_price"] = contract.get("entry_price")
    state["stop_loss"] = contract.get("stop_loss")
    state["take_profit"] = contract.get("take_profit")
    state["risk_amount"] = contract.get("risk_amount")
    state["potential_profit"] = contract.get("potential_profit")
    state["risk_reward"] = contract.get("risk_reward")

    if not state.get("contracts"):
        state["contracts"] = 1

    return state


def print_portfolio_result(portfolio_result):
    if not isinstance(portfolio_result, dict):
        print("Portfolio no devolvio formato valido.")
        return

    portfolio = portfolio_result.get("portfolio", [])
    summary = portfolio_result.get("summary", {})

    if not portfolio:
        print("No hay portfolio recomendado hoy.")
        return

    for i, item in enumerate(portfolio, start=1):
        print("")
        print(f"#{i}")
        print("Symbol:", item.get("symbol"))
        print("Contrato:", item.get("contractSymbol"))
        print("Tipo:", item.get("option_type"))
        print("Contratos:", item.get("contracts"))
        print("Entrada:", item.get("entry_price"))
        print("Stop:", item.get("stop_loss"))
        print("Take Profit:", item.get("take_profit"))
        print("Riesgo:", item.get("risk_amount"))
        print("Ganancia:", item.get("potential_profit"))
        print("Risk/Reward:", item.get("risk_reward"))
        print("Score:", item.get("score"))
        print("Rating:", item.get("rating"))

    print("")
    print("RESUMEN PORTFOLIO")
    print("------------------------------")
    print("Total posiciones:", summary.get("positions"))
    print("Riesgo total:", summary.get("total_risk"))
    print("Ganancia potencial total:", summary.get("total_potential_profit"))
    print("CALLS:", summary.get("call_count"))
    print("PUTS:", summary.get("put_count"))


def main():
    results = []

    for symbol in SYMBOLS:
        print("")
        print("==============================")
        print(f"ANALIZANDO {symbol}")
        print("==============================")

        try:
            print("STEP 1 DATA")
            state = get_market_data(symbol)
            state["symbol"] = symbol

            print("STEP 2 SIGNAL")
            state = signal_agent(state)

            print("STEP 3 RISK")
            state = risk_agent(state)

            print("STEP 4 OPTIONS")
            state = options_agent(state)

            print("STEP 5 ENTRY")
            state = entry_agent(state)

            print("STEP 6 OPTION CONTRACT")
            state = option_contract_agent(state)
            state = normalize_contract_state(state)
            show_contract_info(state)

            print("STEP 7 TRADE PLAN")
            state = trade_plan_agent(state)

            state = normalize_contract_state(state)

            print("STEP 8 SCORE")
            state = score_agent(state)

            results.append(state)

        except Exception as e:
            print(f"ERROR analizando {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "error": str(e),
                "score": 0,
                "rating": "ERROR"
            })

    print("")
    print("==============================")
    print("GENERANDO REPORTE")
    print("==============================")

    try:
        report_agent(results)
    except Exception as e:
        print("Error generando reporte:", e)

    if options_scanner:
        print("")
        print("==============================")
        print("SCANNER AUTOMATICO")
        print("==============================")

        try:
            scanner_results = options_scanner(SYMBOLS)
            print("Scanner completado.")
        except Exception as e:
            print("Error en scanner:", e)

    if portfolio_agent:
        print("")
        print("==============================")
        print("PORTFOLIO DEL DIA")
        print("==============================")

        try:
            portfolio_result = portfolio_agent(results)
            print("Portfolio generado.")
            print_portfolio_result(portfolio_result)

        except Exception as e:
            print("Error generando portfolio:", e)

    print("")
    print("==============================")
    print("BOT FINALIZADO")
    print("==============================")


if __name__ == "__main__":
    main()