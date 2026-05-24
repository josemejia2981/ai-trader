from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def news_analysis(state):

    technical = state["technical"]

    prompt = f"""
You are a financial sentiment analyst.

Technical signal: {technical}

Classify market sentiment as ONLY ONE:
- bullish
- bearish
- neutral

Respond with only one word.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    sentiment = response.choices[0].message.content.strip().lower()

    state["news"] = sentiment

    return state
