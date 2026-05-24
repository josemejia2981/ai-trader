# agents/report_agent.py

import os
import pandas as pd
from datetime import datetime


def report_agent(results):
    print("\nSTEP 9 💾 REPORTE")
    print("💾 Guardando reportes CSV y HTML...")

    os.makedirs("reports", exist_ok=True)

    now = datetime.now().strftime("%Y_%m_%d_%H_%M")
    csv_file = f"reports/trades_{now}.csv"
    html_file = f"reports/trades_{now}.html"

    rows = []

    for r in results:
        rows.append({
            "symbol": r.get("symbol"),
            "price": r.get("price"),
            "trend": r.get("trend"),
            "signal": r.get("signal"),
            "risk": r.get("risk"),
            "score": r.get("score"),
            "rating": r.get("rating"),

            "entry_ready": r.get("entry_ready"),
            "entry_type": r.get("entry_type"),
            "entry_price": r.get("entry_price"),
            "stop_loss": r.get("stop_loss"),
            "take_profit": r.get("take_profit"),

            "contracts": r.get("contracts"),
            "risk_amount": r.get("risk_amount"),
            "potential_profit": r.get("potential_profit"),
            "risk_reward": r.get("risk_reward"),

            "account_size": r.get("account_size"),
            "risk_percent": r.get("risk_percent"),
            "max_risk_allowed": r.get("max_risk_allowed"),
            "risk_per_share": r.get("risk_per_share"),
            "risk_per_contract": r.get("risk_per_contract"),

            "trade_plan": r.get("trade_plan"),
            "ai_analysis": r.get("ai_analysis"),
            "score_reasons": ", ".join(r.get("score_reasons", [])),
        })

    df = pd.DataFrame(rows)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    cards_html = ""

    for i, r in enumerate(results, start=1):
        score = r.get("score", 0)
        rating = r.get("rating", "N/A")

        if score >= 85:
            badge_class = "excellent"
        elif score >= 70:
            badge_class = "strong"
        elif score >= 55:
            badge_class = "interesting"
        elif score >= 40:
            badge_class = "watch"
        else:
            badge_class = "discard"

        reasons = ", ".join(r.get("score_reasons", []))

        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <div>
                    <h2>#{i} {r.get("symbol")}</h2>
                    <p class="price">${round(r.get("price", 0), 2)}</p>
                </div>
                <div class="badge {badge_class}">
                    {score}/100<br>{rating}
                </div>
            </div>

            <div class="grid">
                <div><span>Tendencia</span><strong>{r.get("trend")}</strong></div>
                <div><span>Señal</span><strong>{r.get("signal")}</strong></div>
                <div><span>Riesgo</span><strong>{r.get("risk")}</strong></div>
                <div><span>Entrada Lista</span><strong>{r.get("entry_ready")}</strong></div>

                <div><span>Tipo Entrada</span><strong>{r.get("entry_type")}</strong></div>
                <div><span>Entrada Precio</span><strong>{r.get("entry_price")}</strong></div>
                <div><span>Stop Loss</span><strong>{r.get("stop_loss")}</strong></div>
                <div><span>Take Profit</span><strong>{r.get("take_profit")}</strong></div>

                <div><span>Contratos</span><strong>{r.get("contracts")}</strong></div>
                <div><span>Riesgo Real</span><strong>${r.get("risk_amount")}</strong></div>
                <div><span>Ganancia Potencial</span><strong>${r.get("potential_profit")}</strong></div>
                <div><span>R/R</span><strong>{r.get("risk_reward")}</strong></div>
            </div>

            <div class="section">
                <h3>📋 Plan de Trade</h3>
                <p>{r.get("trade_plan")}</p>
            </div>

            <div class="section">
                <h3>🏆 Razones del Score</h3>
                <p>{reasons}</p>
            </div>

            <div class="section ai">
                <h3>🤖 Análisis IA</h3>
                <p>{r.get("ai_analysis")}</p>
            </div>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AI Trader Report</title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #e5e7eb;
            padding: 30px;
        }}

        h1 {{
            text-align: center;
            color: #38bdf8;
        }}

        .subtitle {{
            text-align: center;
            color: #94a3b8;
            margin-bottom: 30px;
        }}

        .card {{
            background: #111827;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.35);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}

        h2 {{
            margin: 0;
            color: #f8fafc;
        }}

        .price {{
            font-size: 24px;
            color: #22c55e;
            margin: 8px 0 0;
        }}

        .badge {{
            padding: 14px 20px;
            border-radius: 14px;
            text-align: center;
            font-weight: bold;
            color: white;
        }}

        .excellent {{ background: #16a34a; }}
        .strong {{ background: #2563eb; }}
        .interesting {{ background: #ca8a04; }}
        .watch {{ background: #9333ea; }}
        .discard {{ background: #dc2626; }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 20px;
        }}

        .grid div {{
            background: #1e293b;
            padding: 14px;
            border-radius: 12px;
        }}

        .grid span {{
            display: block;
            color: #94a3b8;
            font-size: 13px;
            margin-bottom: 6px;
        }}

        .grid strong {{
            color: #f8fafc;
        }}

        .section {{
            background: #020617;
            border-left: 4px solid #38bdf8;
            padding: 14px 18px;
            border-radius: 10px;
            margin-top: 14px;
        }}

        .section h3 {{
            margin-top: 0;
            color: #38bdf8;
        }}

        .ai {{
            border-left-color: #a855f7;
        }}
    </style>
</head>

<body>
    <h1>🚀 AI Trader Report</h1>
    <p class="subtitle">Reporte generado: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

    {cards_html}
</body>
</html>
"""

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ CSV guardado en: {csv_file}")
    print(f"✅ HTML guardado en: {html_file}")

    return html_file