# main.py

import sys

sys.stdout.reconfigure(encoding="utf-8")

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
from agents.options_scanner import run_auto_options_scanner


SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT"]


def main():
    results = []

    for symbol in SYMBOLS:
        print("\n==============================")
        print(f"ANALIZANDO {symbol}")
        print("==============================")

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

        print("STEP 7 TRADE PLAN")
        state = trade_plan_agent(state)

        print("STEP 8 SCORE")
        state = score_agent(state)

        results.append(state)

    results = sorted(
        results,
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    print("\n==============================")
    print("IA SOLO PARA TOP 1")
    print("==============================")

    for i, state in enumerate(results):
        if i == 0:
            state["ai_analysis"] = (
                f"Evaluacion tecnica automatica: {state.get('symbol')} tiene "
                f"score {state.get('score')}, rating {state.get('rating')}, "
                f"tendencia {state.get('trend')}, riesgo {state.get('risk')}, "
                f"entrada {state.get('entry_type')}."
            )
        else:
            state["ai_analysis"] = "IA pendiente: solo se analiza la mejor oportunidad."

    print("\n==============================")
    print("TOP OPORTUNIDADES")
    print("==============================")

    for i, state in enumerate(results, start=1):
        print("\n--------------------------------")
        print(f"#{i}")
        print(f"Simbolo: {state.get('symbol')}")
        print(f"Precio accion: {state.get('price')}")
        print(f"Tendencia: {state.get('trend')}")
        print(f"Senal: {state.get('signal')}")
        print(f"Riesgo mercado: {state.get('risk')}")
        print(f"Score: {state.get('score')}/100")
        print(f"Rating: {state.get('rating')}")
        print(f"Razones: {', '.join(state.get('score_reasons', []))}")
        print(f"IA: {state.get('ai_analysis')}")

        print("\nOPCIONES")
        print(f"Estrategia: {state.get('option_strategy')}")
        print(f"Motivo: {state.get('option_reason')}")
        print(f"Confianza: {state.get('option_confidence')}%")
        print(f"Strike sugerido: {state.get('strike')}")
        print(f"DTE sugerido: {state.get('dte')}")
        print(f"Precio opcion estimado: ${state.get('option_price')}")

        if state.get("option_contract"):
            print("\nCONTRATO SELECCIONADO")
            print(f"Contrato: {state.get('option_contract')}")
            print(f"Tipo: {state.get('option_type')}")
            print(f"Strike real: {state.get('option_strike')}")
            print(f"Expiracion: {state.get('option_expiration')}")
            print(f"Entrada opcion real: ${state.get('option_entry')}")
            print(f"Stop opcion real: ${state.get('option_stop_loss')}")
            print(f"Take Profit opcion real: ${state.get('option_take_profit')}")

        print("\nPLAN DE TRADE")
        print(f"Plan: {state.get('trade_plan')}")
        print(f"Contratos recomendados: {state.get('contracts')}")
        print(f"Riesgo real: ${state.get('risk_amount')}")
        print(f"Ganancia potencial: ${state.get('potential_profit')}")
        print(f"Risk/Reward: {state.get('risk_reward')}")
        print(f"Stop Loss: ${state.get('stop_loss')}")
        print(f"Take Profit: ${state.get('take_profit')}")
        print(f"Trade permitido: {state.get('trade_allowed')}")

    print("\nSTEP 9 SCANNER AUTOMATICO")
    auto_options_report = run_auto_options_scanner(results)

    print("\nSTEP 10 REPORTE")
    report_files = report_agent(results)

    print("\nAnalisis finalizado.")
    print(f"Reporte principal: {report_files}")

    if auto_options_report:
        print(f"Reporte opciones automatico: {auto_options_report}")


if __name__ == "__main__":
    main()