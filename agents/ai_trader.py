# agents/ai_trader.py

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

# Modelo rápido recomendado
OLLAMA_MODEL = "llama3.2:1b"

# Si quieres probar DeepSeek después:
# OLLAMA_MODEL = "deepseek-r1:latest"


def ai_trader(data):
    """
    Analiza una operación usando Ollama local.
    Siempre devuelve el diccionario data actualizado.
    """

    try:
        symbol = data.get("symbol", "N/A")
        price = data.get("price", "N/A")
        rsi = data.get("rsi", "N/A")
        trend = data.get("trend", "N/A")
        signal = data.get("signal", "N/A")
        risk = data.get("risk", "N/A")
        strategy = data.get("options_strategy", "N/A")
        entry_ready = data.get("entry_ready", False)
        entry_type = data.get("entry_type", "N/A")
        entry_price = data.get("entry_price", "N/A")
        stop_loss = data.get("stop_loss", "N/A")
        take_profit = data.get("take_profit", "N/A")
        risk_reward = data.get("risk_reward", "N/A")

        if not entry_ready:
            data["ai_analysis"] = "IA omitida: no hay entrada confirmada."
            return data

        print(f"🤖 Consultando IA para {symbol}...")

        prompt = f"""
Eres un trader profesional de opciones.

IMPORTANTE:
- No contradigas la estrategia del sistema.
- Si la estrategia del sistema es CALL, evalúa CALL solamente.
- Si la estrategia del sistema es PUT, evalúa PUT solamente.
- No recomiendes CALL y PUT al mismo tiempo.
- RSI entre 45 y 70 es saludable para CALL.
- RSI mayor de 80 es sobrecomprado.
- Responde muy corto.

DATOS DEL TRADE:
Símbolo: {symbol}
Precio actual: {price}
Tendencia: {trend}
RSI: {rsi}
Señal técnica general: {signal}
Riesgo: {risk}
Estrategia confirmada: {strategy}
Tipo de entrada: {entry_type}
Entrada: {entry_price}
Stop Loss: {stop_loss}
Take Profit: {take_profit}
Risk/Reward: {risk_reward}

Formato obligatorio:

RECOMENDACIÓN: {strategy}
CONFIANZA: BAJA, MEDIA o ALTA
RAZÓN: máximo 1 línea
RIESGO PRINCIPAL: máximo 1 línea
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 60
                }
            },
            timeout=45
        )

        response.raise_for_status()
        result = response.json()

        ai_response = result.get("response", "").strip()

        if not ai_response:
            ai_response = "IA sin respuesta útil."

        print(f"✅ IA respondió para {symbol}")

        data["ai_analysis"] = ai_response
        return data

    except requests.exceptions.ConnectionError:
        data["ai_analysis"] = "IA no disponible: Ollama no está abierto."
        return data

    except requests.exceptions.Timeout:
        strategy = data.get("options_strategy", "TRADE")
        data["ai_analysis"] = (
            f"IA omitida por tiempo: operación {strategy} válida según reglas técnicas."
        )
        return data

    except Exception as e:
        data["ai_analysis"] = f"Error IA Ollama: {e}"
        return data