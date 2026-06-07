# main.py - AI TRADER (Pipeline corregido)
# PIPELINE: market_data -> signal -> risk -> entry -> options -> contract -> trade_plan -> score
import sys
sys.path.insert(0, '.')
from datetime import datetime
from zoneinfo import ZoneInfo

from agents.market_data import get_market_data
from agents.signal import signal_agent
from agents.risk import risk_agent
from agents.entry_agent import entry_agent        # PASO 4: ANTES de options_agent
from agents.options_agent import options_agent    # PASO 5: lee entry_ready correctamente
from agents.option_contract_agent import option_contract_agent
from agents.trade_plan_agent import trade_plan_agent
from agents.score_agent import score_agent
from agents.report_agent import report_agent

try:
    from config.settings import DEFAULT_SYMBOLS
except Exception:
    DEFAULT_SYMBOLS = ["AAPL","MSFT","NVDA","TSLA","META","AMZN","GOOGL","AMD","NFLX","QQQ","SPY"]

try:
    from agents.options_scanner import options_scanner
except Exception:
    options_scanner = None

try:
    from agents.portfolio_agent import portfolio_agent
except Exception:
    portfolio_agent = None


def is_market_hours():
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False, "Mercado cerrado (fin de semana)"
    mo = now.replace(hour=9, minute=30, second=0, microsecond=0)
    mc = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if mo <= now <= mc:
        return True, "Mercado ABIERTO - " + now.strftime("%H:%M ET")
    return False, "Mercado cerrado - " + now.strftime("%H:%M ET") + " (horario: 9:30-16:00 ET)"


def normalize_contract_state(state):
    contract = state.get("best_contract")
    if not isinstance(contract, dict):
        return state
    for f in ["contractSymbol","option_type","expiration","dte","strike","underlying_price",
              "lastPrice","bid","ask","mid_price","spread","spread_pct","volume","openInterest",
              "delta_estimate","delta","entry_price","stop_loss","take_profit",
              "option_stop_loss","option_take_profit","risk_amount","potential_profit",
              "risk_reward","contract_quality_score","score","recommendation"]:
        if not state.get(f):
            state[f] = contract.get(f)
    if not state.get("contracts"):
        state["contracts"] = 1
    return state


def show_contract(state):
    c = state.get("best_contract")
    if not c:
        print("  Sin contrato: " + str(state.get("contract_status","N/A")))
        return
    print("  Contrato: " + str(c.get("contractSymbol")))
    print("  Tipo:" + str(c.get("option_type")) + " Strike:$" + str(c.get("strike")) + " DTE:" + str(c.get("dte")))
    print("  Entrada:$" + str(c.get("entry_price")) + " Stop:$" + str(c.get("stop_loss")) + " TP:$" + str(c.get("take_profit_2")))
    print("  Delta:" + str(c.get("delta")) + " IV:" + str(c.get("impliedVolatility")) + "% Spread:" + str(c.get("spread_pct")) + "%")
    print("  OI:" + str(c.get("openInterest")) + " Vol:" + str(c.get("volume")) + " Score:" + str(c.get("contract_quality_score")) + "/100")


def print_portfolio(result):
    if not isinstance(result, dict): return
    portfolio = result.get("portfolio", [])
    summary = result.get("summary", {})
    if not portfolio:
        print("  No hay portfolio institucional hoy.")
        return
    for i, item in enumerate(portfolio, 1):
        print("  #" + str(i) + " " + str(item.get("symbol")) + " " + str(item.get("option_type")))
        print("    Contrato:" + str(item.get("contractSymbol")))
        print("    Entrada:$" + str(item.get("entry_price")) + " Stop:$" + str(item.get("stop_loss")) + " TP:$" + str(item.get("take_profit_2")))
        print("    Riesgo:$" + str(item.get("risk_amount")) + " Ganancia:$" + str(item.get("potential_profit")) + " R/R:" + str(item.get("risk_reward")))
        print("    Score:" + str(item.get("score")) + " Rating:" + str(item.get("rating")))
    print("  RESUMEN: " + str(summary.get("positions")) + " posiciones | Riesgo total:$" +
          str(summary.get("total_risk")) + " | Ganancia potencial:$" + str(summary.get("total_potential_profit")) +
          " | CALLS:" + str(summary.get("call_count")) + " PUTS:" + str(summary.get("put_count")))


def main():
    print("=" * 60)
    print("AI TRADER - SWING OPTIONS BOT")
    print("=" * 60)
    open_mkt, msg = is_market_hours()
    print("\nMercado: " + msg)
    if not open_mkt:
        print("AVISO: Corriendo fuera de horario. Precios pueden no ser en tiempo real.\n")

    results = []

    for symbol in DEFAULT_SYMBOLS:
        print("\n" + "=" * 60)
        print("  ANALIZANDO: " + symbol)
        print("=" * 60)
        try:
            print("\n[1/8] Datos de mercado...")
            state = get_market_data(symbol)
            state["symbol"] = symbol

            print("\n[2/8] Señal...")
            state = signal_agent(state)

            print("\n[3/8] Riesgo...")
            state = risk_agent(state)

            print("\n[4/8] Entrada...")       # BUG FIX: entry ANTES de options
            state = entry_agent(state)

            print("\n[5/8] Estrategia...")    # Ahora lee entry_ready=True si aplica
            state = options_agent(state)

            print("\n[6/8] Contrato...")
            state = option_contract_agent(state)
            state = normalize_contract_state(state)
            show_contract(state)

            print("\n[7/8] Plan de trade...")
            state = trade_plan_agent(state)
            state = normalize_contract_state(state)

            print("\n[8/8] Score final...")
            state = score_agent(state)

            print("\n  Score: " + str(state.get("score")) + "/100 | Rating: " + str(state.get("rating")))
            results.append(state)

        except Exception as e:
            print("  ERROR en " + symbol + ": " + str(e))
            results.append({"symbol": symbol, "error": str(e), "score": 0, "rating": "ERROR"})

    print("\n" + "=" * 60)
    print("  GENERANDO REPORTE")
    print("=" * 60)
    try:
        report_agent(results)
    except Exception as e:
        print("Error reporte: " + str(e))

    if options_scanner:
        print("\n" + "=" * 60)
        print("  SCANNER AUTOMATICO")
        print("=" * 60)
        try:
            options_scanner(DEFAULT_SYMBOLS)
        except Exception as e:
            print("Error scanner: " + str(e))

    if portfolio_agent:
        print("\n" + "=" * 60)
        print("  PORTFOLIO DEL DIA")
        print("=" * 60)
        try:
            res = portfolio_agent(results)
            print_portfolio(res)
        except Exception as e:
            print("Error portfolio: " + str(e))

    valid = [r for r in results if r.get("score",0) >= 65 and not r.get("error")]
    print("\n" + "=" * 60)
    print("  FINALIZADO - " + str(len(valid)) + "/" + str(len(DEFAULT_SYMBOLS)) + " simbolos con oportunidad")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
