import os
import glob
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="AI TRADER",
    page_icon="📊",
    layout="wide"
)

REPORTS_DIR = "reports"

def ny_time():
    return datetime.now(ZoneInfo("America/New_York"))

def find_latest_trade_csv():
    patterns = [
        "portfolio_*.csv",
        "options_scanner_*.csv",
        "trades_*.csv",
    ]

    files = []

    for pattern in patterns:
        files.extend(glob.glob(os.path.join(REPORTS_DIR, pattern)))

    files = [
        f for f in files
        if "equity_curve" not in os.path.basename(f).lower()
    ]

    if not files:
        return None

    return max(files, key=os.path.getmtime)

def normalize_columns(df):
    rename_map = {
        "contract": "contractSymbol",
        "contract_symbol": "contractSymbol",
        "option_contract": "contractSymbol",

        "type": "option_type",
        "optionType": "option_type",

        "Strike": "strike",
        "option_strike": "strike",

        "Delta": "delta",
        "option_delta": "delta",

        "open_interest": "openInterest",
        "open interest": "openInterest",
        "Open Interest": "openInterest",
        "OpenInterest": "openInterest",
        "option_open_interest": "openInterest",
        "oi": "openInterest",

        "option_volume": "volume",
        "Volume": "volume",
        "vol": "volume",

        "last_price": "lastPrice",
        "option_price": "lastPrice",

        "Bid": "bid",
        "Ask": "ask",

        "risk": "risk_amount",
        "riskAmount": "risk_amount",

        "potentialProfit": "potential_profit",
        "profit_target": "potential_profit",
    }

    return df.rename(columns=rename_map)

def safe(value):
    try:
        if pd.isna(value):
            return "N/A"
        return value
    except Exception:
        return "N/A"

# ================= HEADER =================

now = ny_time()

st.title("📊 Panel ejecutivo de AI TRADER")
st.caption("Dashboard profesional para opciones, contratos, Delta, Strike y Open Interest.")

st.success("Sistema activo")

c1, c2 = st.columns(2)

with c1:
    st.metric("Fecha NY", now.strftime("%d-%m-%Y"))

with c2:
    st.metric("Hora NY", now.strftime("%H:%M:%S"))

# ================= LOAD FILE =================

latest_csv = find_latest_trade_csv()

if latest_csv is None:
    st.error("No encontré portfolio_*.csv, options_scanner_*.csv ni trades_*.csv dentro de reports.")
    st.stop()

df = pd.read_csv(latest_csv)
df = normalize_columns(df)

st.subheader("📄 Último reporte cargado")
st.info(f"Archivo cargado: {latest_csv}")

# ================= COLUMNS =================

columns = [
    "symbol",
    "contractSymbol",
    "option_type",
    "strike",
    "delta",
    "openInterest",
    "volume",
    "lastPrice",
    "bid",
    "ask",
    "score",
    "risk_amount",
    "potential_profit",
    "trade_allowed",
]

for col in columns:
    if col not in df.columns:
        df[col] = "N/A"

df["score_numeric"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
df = df.sort_values("score_numeric", ascending=False)

# ================= METRICS =================

risk_total = pd.to_numeric(df["risk_amount"], errors="coerce").fillna(0).sum()
profit_total = pd.to_numeric(df["potential_profit"], errors="coerce").fillna(0).sum()
avg_score = pd.to_numeric(df["score"], errors="coerce").fillna(0).mean()

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Contratos", len(df))

with m2:
    st.metric("Riesgo Total", f"${risk_total:,.2f}")

with m3:
    st.metric("Ganancia Potencial", f"${profit_total:,.2f}")

with m4:
    st.metric("Score Promedio", f"{avg_score:.2f}")

# ================= TABLE =================

st.subheader("🏆 Portfolio / Contratos encontrados")

st.dataframe(
    df[columns],
    width="stretch",
    hide_index=True
)

# ================= CARDS =================

st.subheader("📌 Resumen de mejores contratos")

for _, row in df.head(5).iterrows():
    with st.container(border=True):
        st.markdown(f"### {safe(row['symbol'])} — {safe(row['option_type'])}")

        a, b, c = st.columns(3)

        with a:
            st.write(f"**Contrato:** {safe(row['contractSymbol'])}")
            st.write(f"**Strike:** {safe(row['strike'])}")
            st.write(f"**Delta:** {safe(row['delta'])}")

        with b:
            st.write(f"**Open Interest:** {safe(row['openInterest'])}")
            st.write(f"**Volumen:** {safe(row['volume'])}")
            st.write(f"**Último precio:** {safe(row['lastPrice'])}")

        with c:
            st.write(f"**Bid:** {safe(row['bid'])}")
            st.write(f"**Ask:** {safe(row['ask'])}")
            st.write(f"**Score:** {safe(row['score'])}")

        st.write(f"**Riesgo:** ${safe(row['risk_amount'])}")
        st.write(f"**Ganancia potencial:** ${safe(row['potential_profit'])}")
        st.write(f"**Trade permitido:** {safe(row['trade_allowed'])}")

with st.expander("🔍 Ver columnas reales del CSV"):
    st.write(df.columns.tolist())

st.caption("AI TRADER corregido: ignora equity_curve.csv y carga archivos reales de contratos.")