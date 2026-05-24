print("🚀 INICIANDO BOT...")

from agents.market_data import get_market_data
from agents.signal import signal_agent
from agents.risk import risk_agent
from agents.options_agent import options_agent
from agents.entry_agent import entry_agent
from agents.trade_plan_agent import trade_plan_agent
from agents.ai_trader import ai_trader
from agents.score_agent import score_agent
from agents.report_agent import report_agent


SYMBOLS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "MSFT"
]


def main():

    results = []

    for symbol in SYMBOLS:

        print("\n==============================")
        print(f"🚀 ANALIZANDO {symbol}")
        print("==============================")

        try:

            print("STEP 1 📈 DATA")
            state = get_market_data(symbol)

            print("STEP 2 📊 SIGNAL")
            state = signal_agent(state)

            print("STEP 3 🛡️ RISK")
            state = risk_agent(state)

            print("STEP 4 🧠 OPTIONS")
            state = options_agent(state)

            print("STEP 5 🚪 ENTRY")
            state = entry_agent(state)

            print("STEP 6 📋 TRADE PLAN")
            state = trade_plan_agent(state)

            print("STEP 7 🤖 IA")
            state = ai_trader(state)

            state = score_agent(state)

            results.append(state)

        except Exception as e:
            print(f"❌ Error analizando {symbol}: {e}")

    results.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    print("\n==============================")
    print("🏆 TOP OPORTUNIDADES")
    print("==============================")

    for i, r in enumerate(results, start=1):

        print("\n--------------------------------")
        print(f"#{i}")
        print(f"📌 Símbolo: {r.get('symbol')}")
        print(f"💰 Precio: {r.get('price')}")
        print(f"📈 Tendencia: {r.get('trend')}")
        print(f"📊 Señal: {r.get('signal')}")
        print(f"⚠️ Riesgo: {r.get('risk')}")
        print(f"🏆 Score: {r.get('score', 0)}/100")
        print(f"📊 Rating: {r.get('rating', 'N/A')}")

        reasons = r.get("score_reasons", [])
        if reasons:
            print(f"📝 Razones: {', '.join(reasons)}")

        print(f"🤖 IA: {r.get('ai_analysis')}")

    report_file = report_agent(results)

    print("\n✅ Análisis finalizado.")
    print(f"📁 Reporte CSV: {report_file}")


if __name__ == "__main__":
    main()