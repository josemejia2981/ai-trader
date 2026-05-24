# agents/ai_trader.py

def ai_trader(data):
    """
    IA desactivada temporalmente.
    El sistema usa reglas técnicas para evitar lentitud de Ollama.
    """

    if not data.get("entry_ready", False):
        data["ai_analysis"] = "IA omitida: no hay entrada confirmada."
        return data

    symbol = data.get("symbol", "N/A")
    score = data.get("score", 0)
    rating = data.get("rating", "N/A")
    trend = data.get("trend", "N/A")
    risk = data.get("risk", "N/A")
    entry_type = data.get("entry_type", "N/A")

    data["ai_analysis"] = (
        f"Evaluación técnica automática: {symbol} tiene score {score}, "
        f"rating {rating}, tendencia {trend}, riesgo {risk}, entrada {entry_type}."
    )

    return data