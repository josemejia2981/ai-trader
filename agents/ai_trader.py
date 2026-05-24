# agents/ai_trader.py

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

# Modelo rápido recomendado
OLLAMA_MODEL = "llama3.2:1b"


def ai_trader(data):
    """
    Analiza una operación usando Ollama local.
    Nunca debe detener el bot si Ollama falla o tarda demasiado.
    """

    symbol = data.get("symbol", "N/A")
    strategy = data.get("options_strategy", "TRADE")

    try:
        if not data.get("entry_ready", False):
            data["ai_analysis"] = "IA omitida: no hay entrada confirmada."
            return data

        print(f"🤖 Consultando IA para {symbol}...")

        prompt = f"""
Eres un trader profesional de opciones.

Responde corto y directo.

DATOS:
Símbolo: {symbol}
Precio: {data.get("price", "N/A")}
Tendencia: {data.get("trend", "N/A")}
RSI: {data.get("rsi", "N/A")}
Señal: {data.get("signal", "N/A")}
Riesgo: {data.get("risk", "N/A")}
Estrategia: {strategy}
Entrada: {data.get("entry_price", "N/A")}
Stop Loss: {data.get("stop_loss", "N/A")}
Take Profit: {data.get("take_profit", "N/A")}

Formato:
RECOMENDACIÓN:
CONFIANZA:
RAZÓN:
RIESGO:
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 40
                }
            },
            timeout=12
        )

        response.raise_for_status()
        result = response.json()

        ai_response = result.get("response", "").strip()

        if not ai_response:
            ai_response = f"IA sin respuesta útil. Operación {strategy} válida según reglas técnicas."

        print(f"✅ IA respondió para {symbol}")

        data["ai_analysis"] = ai_response
        return data

    except requests.exceptions.ConnectionError:
        print(f"⚠️ IA no disponible para {symbol}. Continuando...")
        data["ai_analysis"] = "IA no disponible: Ollama no está abierto. Trade evaluado por reglas técnicas."
        return data

    except requests.exceptions.Timeout:
        print(f"⚠️ IA tardó demasiado para {symbol}. Continuando...")
        data["ai_analysis"] = f"IA omitida por tiempo. Operación {strategy} válida según reglas técnicas."
        return data

    except Exception as e:
        print(f"⚠️ Error IA para {symbol}: {e}")
        data["ai_analysis"] = f"Error IA Ollama: {e}. Trade evaluado por reglas técnicas."
        return data