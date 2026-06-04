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


def remove_duplicate_columns(df):
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def normalize_columns(df):
    rename_map = {
        "contract": "contractSymbol",
        "contract_symbol": "contractSymbol",
        "option_contract": "contractSymbol",

        "type": "option_type",
        "optionType": "option_type",

        "Strike": "strike",
        "option_strike": "strike",
        "recommended_strike": "strike",

        "Delta": "delta",
        "option_delta": "delta",
        "delta_estimate": "delta",

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
        "option_last_price": "lastPrice",
        "option_price": "lastPrice",

        "Bid": "bid",
        "option_bid": "bid",

        "Ask": "ask",
        "option_ask": "ask",

        "risk": "risk_amount",
        "riskAmount": "risk_amount",

        "potentialProfit": "potential_profit",
        "profit_target": "potential_profit",
    }

    df = df.rename(columns=rename_map)
    df = remove_duplicate_columns(df)
    return df


def ensure_column(df, column, default="N/A"):
    if column not in df.columns:
        df[column] = default
    return df


def safe_series(df, column, default="N/A"):
    if column not in df.columns:
        return pd.Series([default] * len(df))

    data = df[column]

    if isinstance(data, pd.DataFrame):
        data = data.iloc[:, 0]

    return data


def safe_numeric_series(df, column):
    data = safe_series(df, column, 0)
    return pd.to_numeric(data, errors="coerce").fillna(0)


def safe_value(value):
    try:
        if pd.isna(value):
            return "N/A"
        return value
    except Exception:
        return "N/A"


def format_money(value):
    try:
        value = float(value)
        return f"${value:,.2f}"
    except Exception:
        return "N/A"


def format_number(value):
    try:
        value = float(value)
        return f"{value:,.2f}"
    except Exception:
        return "N/A"


def fix_last_price(df):
    if "lastPrice" not in df.columns:
        df["lastPrice"] = "N/A"

    bid = safe_numeric_series(df, "bid")
    ask = safe_numeric_series(df, "ask")
    last_price = pd.to_numeric(df["lastPrice"], errors="coerce")

    mid = ((bid + ask) / 2).round(2)

    df["lastPrice"] = last_price.fillna(mid)
    df["lastPrice"] = df["lastPrice"].fillna("N/A")

    return df


# =========================
# HEADER
# =========================

now = ny_time()

st.title("📊 Panel ejecutivo de AI TRADER")
st.caption("Dashboard profesional para opciones, Delta, Strike, Open Interest, riesgo y portfolio.")

st.success("Sistema activo")

c1, c2 = st.columns(2)

with c1:
    st.metric("Fecha NY", now.strftime("%d-%m-%Y"))

with c2:
    st.metric("Hora NY", now.strftime("%H:%M:%S"))


# =========================
# CARGAR ARCHIVO
# =========================

latest_csv = find_latest_trade_csv()

if latest_csv is None:
    st.error("No encontré archivos portfolio_*.csv, options_scanner_*.csv ni trades_*.csv dentro de reports.")
    st.stop()

try:
    df = pd.read_csv(latest_csv)
except Exception as e:
    st.error(f"No se pudo leer el CSV: {e}")
    st.stop()

df = normalize_columns(df)

st.subheader("📄 Último reporte cargado")
st.info(f"Archivo cargado: {latest_csv}")


# =========================
# COLUMNAS NECESARIAS
# =========================

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
    "risk_reward",
    "dte",
    "trade_allowed",
]

for col in columns:
    df = ensure_column(df, col, "N/A")

df = fix_last_price(df)

df["score_numeric"] = safe_numeric_series(df, "score")
df = df.sort_values("score_numeric", ascending=False)


# =========================
# METRICAS
# =========================

risk_total = safe_numeric_series(df, "risk_amount").sum()
profit_total = safe_numeric_series(df, "potential_profit").sum()
avg_score = safe_numeric_series(df, "score").mean()
avg_rr = safe_numeric_series(df, "risk_reward").mean()

best_trade = "N/A"
if "symbol" in df.columns and len(df) > 0:
    best_trade = safe_value(df.iloc[0].get("symbol", "N/A"))

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric("Contratos", len(df))

with m2:
    st.metric("Riesgo Total", format_money(risk_total))

with m3:
    st.metric("Ganancia Potencial", format_money(profit_total))

with m4:
    st.metric("Score Promedio", f"{avg_score:.2f}")

with m5:
    st.metric("Mejor Trade", best_trade)


# =========================
# TABLA PRINCIPAL
# =========================

st.subheader("🏆 Portfolio / Contratos encontrados")

show_df = df[columns].copy()

st.dataframe(
    show_df,
    width="stretch",
    hide_index=True
)


# =========================
# RESUMEN DE CONTRATOS
# =========================

st.subheader("📌 Resumen de mejores contratos")

for _, row in df.head(5).iterrows():
    symbol = safe_value(row.get("symbol"))
    option_type = safe_value(row.get("option_type"))
    contract = safe_value(row.get("contractSymbol"))
    strike = safe_value(row.get("strike"))
    delta = safe_value(row.get("delta"))
    open_interest = safe_value(row.get("openInterest"))
    volume = safe_value(row.get("volume"))
    last_price = safe_value(row.get("lastPrice"))
    bid = safe_value(row.get("bid"))
    ask = safe_value(row.get("ask"))
    score = safe_value(row.get("score"))
    risk_amount = safe_value(row.get("risk_amount"))
    potential_profit = safe_value(row.get("potential_profit"))
    risk_reward = safe_value(row.get("risk_reward"))
    dte = safe_value(row.get("dte"))
    trade_allowed = safe_value(row.get("trade_allowed"))

    with st.container(border=True):
        st.markdown(f"### {symbol} — {option_type}")

        a, b, c = st.columns(3)

        with a:
            st.write(f"**Contrato:** {contract}")
            st.write(f"**Strike recomendado:** {strike}")
            st.write(f"**Delta:** {delta}")
            st.write(f"**DTE:** {dte}")

        with b:
            st.write(f"**Open Interest:** {open_interest}")
            st.write(f"**Volumen:** {volume}")
            st.write(f"**Último precio:** {last_price}")
            st.write(f"**Risk / Reward:** {risk_reward}")

        with c:
            st.write(f"**Bid:** {bid}")
            st.write(f"**Ask:** {ask}")
            st.write(f"**Score:** {score}")
            st.write(f"**Trade permitido:** {trade_allowed}")

        st.write(f"**Riesgo:** {format_money(risk_amount)}")
        st.write(f"**Ganancia potencial:** {format_money(potential_profit)}")


# =========================
# DEBUG
# =========================

with st.expander("🔍 Ver columnas reales del CSV"):
    st.write(df.columns.tolist())

st.caption("AI TRADER actualizado: carga contratos reales, evita equity_curve.csv y corrige columnas duplicadas.")