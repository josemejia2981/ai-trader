# app.py

import os
import glob
import subprocess
import sys

import pandas as pd
import streamlit as st
import plotly.express as px

from agents.options_scanner import scan_options


st.set_page_config(
    page_title="AI Trader Pro",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 AI Trader Pro Dashboard")
st.caption("Dashboard visual de AI Trader")

REPORTS_FOLDER = "reports"
os.makedirs(REPORTS_FOLDER, exist_ok=True)


def show_clean_dataframe(df):
    st.dataframe(df, use_container_width=True)


def find_available_columns(df, columns):
    return [col for col in columns if col in df.columns]


# ====================================================
# CONTROL DEL BOT
# ====================================================

st.subheader("⚙️ Control del Bot")

if st.button("🚀 Ejecutar análisis ahora"):
    with st.spinner("Ejecutando AI Trader..."):
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8"
            }
        )

    if result.returncode == 0:
        st.success("✅ Análisis ejecutado correctamente")
        st.subheader("📋 Salida del Bot")
        st.code(result.stdout[-4000:], language="text")
    else:
        st.error("❌ Error ejecutando el bot")
        st.subheader("Detalle del error")
        st.code(result.stderr, language="text")


st.divider()


# ====================================================
# SCANNER DE OPCIONES SWING TRADING
# ====================================================

st.subheader("📊 Scanner de Opciones - Swing Trading")

col1, col2, col3 = st.columns(3)

with col1:
    scanner_symbol = st.text_input(
        "Ticker para escanear",
        value="NVDA"
    ).upper()

with col2:
    min_dte = st.selectbox(
        "DTE mínimo para Swing Trading",
        [30, 60, 120],
        index=1
    )

with col3:
    max_rows = st.slider(
        "Cantidad de contratos",
        min_value=5,
        max_value=50,
        value=20
    )

if st.button("🔎 Buscar mejores contratos"):
    with st.spinner("Buscando mejores contratos por volumen, open interest y score..."):
        try:
            options_df = scan_options(
                scanner_symbol,
                max_rows=max_rows,
                min_dte=min_dte
            )

            if options_df.empty:
                st.warning("No se encontraron contratos para ese ticker y DTE seleccionado.")
            else:
                st.success(
                    f"🏆 Mejores contratos encontrados para {scanner_symbol} con DTE mínimo {min_dte} días"
                )

                if "score" in options_df.columns:
                    options_df = options_df.sort_values("score", ascending=False)
                elif "volume" in options_df.columns:
                    options_df = options_df.sort_values("volume", ascending=False)

                top_contract = options_df.iloc[0]

                st.subheader("🥇 Mejor contrato encontrado")

                m1, m2, m3, m4 = st.columns(4)

                with m1:
                    st.metric("Tipo", str(top_contract.get("type", "N/A")))

                with m2:
                    st.metric("Strike", top_contract.get("strike", "N/A"))

                with m3:
                    st.metric("DTE", top_contract.get("dte", "N/A"))

                with m4:
                    st.metric("Score", round(top_contract.get("score", 0), 2) if "score" in options_df.columns else "N/A")

                st.write("### 📌 Detalle del mejor contrato")

                detail_columns = find_available_columns(
                    options_df,
                    [
                        "contractSymbol",
                        "symbol",
                        "expiration",
                        "dte",
                        "type",
                        "strike",
                        "lastPrice",
                        "bid",
                        "ask",
                        "premium",
                        "volume",
                        "openInterest",
                        "impliedVolatility",
                        "score",
                        "recommendation",
                        "entry",
                        "take_profit",
                        "stop_loss",
                    ]
                )

                show_clean_dataframe(options_df[detail_columns].head(10))

                st.subheader("🏆 Ranking de mejores contratos")

                ranking_columns = find_available_columns(
                    options_df,
                    [
                        "contractSymbol",
                        "type",
                        "strike",
                        "expiration",
                        "dte",
                        "lastPrice",
                        "bid",
                        "ask",
                        "volume",
                        "openInterest",
                        "score",
                        "entry",
                        "take_profit",
                        "stop_loss",
                        "recommendation",
                    ]
                )

                show_clean_dataframe(options_df[ranking_columns])

                if "score" in options_df.columns and "contractSymbol" in options_df.columns:
                    fig_score = px.bar(
                        options_df.head(15),
                        x="contractSymbol",
                        y="score",
                        color="type" if "type" in options_df.columns else None,
                        title=f"Top contratos por Score - {scanner_symbol}"
                    )
                    st.plotly_chart(fig_score, use_container_width=True)

                if "volume" in options_df.columns and "openInterest" in options_df.columns:
                    fig_volume = px.bar(
                        options_df.head(15),
                        x="strike",
                        y=["volume", "openInterest"],
                        color="type" if "type" in options_df.columns else None,
                        barmode="group",
                        title=f"Volumen y Open Interest - {scanner_symbol}"
                    )
                    st.plotly_chart(fig_volume, use_container_width=True)

        except Exception as e:
            st.error("Error buscando opciones.")
            st.code(str(e), language="text")


st.divider()


# ====================================================
# REPORTES DEL BOT
# ====================================================

csv_files = glob.glob(os.path.join(REPORTS_FOLDER, "*.csv"))

if not csv_files:
    st.warning("No hay reportes CSV todavía. Presiona el botón para ejecutar el análisis.")
    st.stop()

latest_csv = max(csv_files, key=os.path.getmtime)

st.subheader("📊 Último reporte")
st.caption(f"Archivo cargado: {latest_csv}")

try:
    df = pd.read_csv(latest_csv)
except Exception as e:
    st.error("No se pudo leer el archivo CSV.")
    st.code(str(e), language="text")
    st.stop()

if "score" in df.columns:
    df = df.sort_values("score", ascending=False)

st.subheader("📋 Datos completos del último reporte")
show_clean_dataframe(df)

if "score" in df.columns:
    st.subheader("🏆 Ranking por Score")

    chart_df = df.sort_values("score", ascending=False)

    x_column = "contractSymbol" if "contractSymbol" in chart_df.columns else "symbol"

    fig = px.bar(
        chart_df.head(20),
        x=x_column,
        y="score",
        text="score",
        color="type" if "type" in chart_df.columns else None,
        title="Mejores oportunidades por Score"
    )

    st.plotly_chart(fig, use_container_width=True)

summary_columns = find_available_columns(
    df,
    [
        "contractSymbol",
        "symbol",
        "expiration",
        "dte",
        "type",
        "strike",
        "lastPrice",
        "bid",
        "ask",
        "premium",
        "volume",
        "openInterest",
        "impliedVolatility",
        "score",
        "recommendation",
        "entry",
        "take_profit",
        "stop_loss",
        "price",
        "trend",
        "signal",
        "risk",
        "rating",
    ]
)

st.subheader("📌 Resumen de oportunidades")
show_clean_dataframe(df[summary_columns])

st.divider()

html_files = glob.glob(os.path.join(REPORTS_FOLDER, "*.html"))

if html_files:
    latest_html = max(html_files, key=os.path.getmtime)

    st.subheader("📄 Reporte HTML")

    with open(latest_html, "r", encoding="utf-8", errors="replace") as file:
        html_content = file.read()

    st.download_button(
        label="⬇️ Descargar último reporte HTML",
        data=html_content,
        file_name=os.path.basename(latest_html),
        mime="text/html"
    )