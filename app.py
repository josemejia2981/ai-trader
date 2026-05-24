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

REPORTS_FOLDER = "reports"
os.makedirs(REPORTS_FOLDER, exist_ok=True)


def show_df(df):
    st.dataframe(df, use_container_width=True)


def available_columns(df, columns):
    return [col for col in columns if col in df.columns]


def latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_csv(file_path):
    if not file_path:
        return pd.DataFrame()

    try:
        return pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame()


def clean_value(value, default="N/A"):
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return value


st.title("AI Trader Pro Dashboard")
st.caption("Sistema de analisis, scanner de opciones y gestion de riesgo")


st.subheader("Control del Bot")

if st.button("Ejecutar analisis ahora"):
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
        st.success("Analisis ejecutado correctamente")
        st.code(result.stdout[-6000:], language="text")
    else:
        st.error("Error ejecutando el bot")
        st.code(result.stderr, language="text")

st.divider()


latest_trade_csv = latest_file(os.path.join(REPORTS_FOLDER, "trades_*.csv"))
latest_options_csv = latest_file(os.path.join(REPORTS_FOLDER, "options_scanner_*.csv"))
latest_html = latest_file(os.path.join(REPORTS_FOLDER, "trades_*.html"))

trades_df = load_csv(latest_trade_csv)
options_df = load_csv(latest_options_csv)

if not trades_df.empty and "score" in trades_df.columns:
    trades_df = trades_df.sort_values("score", ascending=False)

if not options_df.empty and "score" in options_df.columns:
    options_df = options_df.sort_values("score", ascending=False)


st.subheader("Panel Principal")

if trades_df.empty:
    st.warning("No hay reporte principal todavia. Presiona 'Ejecutar analisis ahora'.")
else:
    best_stock = trades_df.iloc[0]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Mejor Accion", clean_value(best_stock.get("symbol")))

    with c2:
        st.metric("Score Accion", clean_value(best_stock.get("score")))

    with c3:
        st.metric("Tendencia", clean_value(best_stock.get("trend")))

    with c4:
        st.metric("Riesgo", clean_value(best_stock.get("risk")))

    risk_cols = st.columns(4)

    with risk_cols[0]:
        entrada = best_stock.get("option_entry", best_stock.get("entry_price", "N/A"))
        st.metric("Entrada Opcion", clean_value(entrada))

    with risk_cols[1]:
        stop = best_stock.get("option_stop_loss", best_stock.get("stop_loss", "N/A"))
        st.metric("Stop Loss", clean_value(stop))

    with risk_cols[2]:
        tp = best_stock.get("option_take_profit", best_stock.get("take_profit", "N/A"))
        st.metric("Take Profit", clean_value(tp))

    with risk_cols[3]:
        st.metric("R/R", clean_value(best_stock.get("risk_reward")))

    extra_cols = st.columns(4)

    with extra_cols[0]:
        st.metric("Contratos", clean_value(best_stock.get("contracts", 0)))

    with extra_cols[1]:
        st.metric("Riesgo Real", f"${clean_value(best_stock.get('risk_amount', 0), 0)}")

    with extra_cols[2]:
        st.metric("Ganancia Potencial", f"${clean_value(best_stock.get('potential_profit', 0), 0)}")

    with extra_cols[3]:
        st.metric("Trade Permitido", clean_value(best_stock.get("trade_allowed", False)))

    if not options_df.empty:
        best_contract = options_df.iloc[0]

        st.subheader("Mejor Contrato Automatico")

        o1, o2, o3, o4 = st.columns(4)

        with o1:
            st.metric("Contrato", clean_value(best_contract.get("contractSymbol")))

        with o2:
            st.metric("Tipo", clean_value(best_contract.get("type")))

        with o3:
            st.metric("Strike", clean_value(best_contract.get("strike")))

        with o4:
            st.metric("Score Contrato", clean_value(best_contract.get("score")))

        o5, o6, o7, o8 = st.columns(4)

        with o5:
            entry_value = best_contract.get("entry", best_contract.get("premium", "N/A"))
            st.metric("Entrada", clean_value(entry_value))

        with o6:
            st.metric("Take Profit", clean_value(best_contract.get("take_profit")))

        with o7:
            st.metric("Stop Loss", clean_value(best_contract.get("stop_loss")))

        with o8:
            st.metric("DTE", clean_value(best_contract.get("dte")))

    st.divider()


if not trades_df.empty:
    st.subheader("Top Oportunidades")

    top_cols = available_columns(
        trades_df,
        [
            "symbol",
            "price",
            "trend",
            "signal",
            "risk",
            "score",
            "rating",
            "entry_ready",
            "entry_type",
            "option_contract",
            "option_type",
            "option_strike",
            "option_expiration",
            "option_entry",
            "option_stop_loss",
            "option_take_profit",
            "contracts",
            "risk_amount",
            "potential_profit",
            "risk_reward",
            "trade_allowed",
            "ai_analysis",
        ]
    )

    show_df(trades_df[top_cols].head(10))

    if "score" in trades_df.columns and "symbol" in trades_df.columns:
        fig = px.bar(
            trades_df.head(10),
            x="symbol",
            y="score",
            text="score",
            title="Ranking de acciones por score"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()


if not options_df.empty:
    st.subheader("Top Contratos Automaticos")

    option_cols = available_columns(
        options_df,
        [
            "contractSymbol",
            "symbol",
            "type",
            "strike",
            "expiration",
            "dte",
            "current_price",
            "premium",
            "entry",
            "bid",
            "ask",
            "spread_percent",
            "moneyness_percent",
            "volume",
            "openInterest",
            "score",
            "rating",
            "take_profit",
            "stop_loss",
        ]
    )

    show_df(options_df[option_cols].head(15))

    if "score" in options_df.columns and "contractSymbol" in options_df.columns:
        fig2 = px.bar(
            options_df.head(15),
            x="contractSymbol",
            y="score",
            text="score",
            color="type" if "type" in options_df.columns else None,
            title="Ranking de contratos por score"
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()


st.subheader("Scanner Manual de Opciones")

m1, m2, m3 = st.columns(3)

with m1:
    scanner_symbol = st.text_input("Ticker", value="NVDA").upper()

with m2:
    min_dte = st.selectbox("DTE minimo", [30, 60, 120], index=0)

with m3:
    max_rows = st.slider("Cantidad de contratos", 5, 50, 20)

if st.button("Buscar mejores contratos"):
    with st.spinner("Buscando contratos..."):
        try:
            manual_df = scan_options(
                symbol=scanner_symbol,
                max_rows=max_rows,
                min_dte=min_dte
            )

            if manual_df.empty:
                st.warning("No se encontraron contratos.")
            else:
                manual_df = manual_df.sort_values("score", ascending=False)
                best_manual = manual_df.iloc[0]

                st.success(f"Mejores contratos encontrados para {scanner_symbol}")

                a1, a2, a3, a4 = st.columns(4)

                with a1:
                    st.metric("Mejor contrato", clean_value(best_manual.get("contractSymbol")))

                with a2:
                    st.metric("Tipo", clean_value(best_manual.get("type")))

                with a3:
                    st.metric("Strike", clean_value(best_manual.get("strike")))

                with a4:
                    st.metric("Score", clean_value(best_manual.get("score")))

                manual_cols = available_columns(
                    manual_df,
                    [
                        "contractSymbol",
                        "symbol",
                        "type",
                        "strike",
                        "expiration",
                        "dte",
                        "current_price",
                        "premium",
                        "entry",
                        "bid",
                        "ask",
                        "spread_percent",
                        "moneyness_percent",
                        "volume",
                        "openInterest",
                        "score",
                        "rating",
                        "take_profit",
                        "stop_loss",
                    ]
                )

                show_df(manual_df[manual_cols])

                fig3 = px.bar(
                    manual_df.head(15),
                    x="contractSymbol",
                    y="score",
                    text="score",
                    color="type" if "type" in manual_df.columns else None,
                    title=f"Top contratos por score - {scanner_symbol}"
                )
                st.plotly_chart(fig3, use_container_width=True)

        except Exception as e:
            st.error("Error buscando opciones.")
            st.code(str(e), language="text")

st.divider()


st.subheader("Reportes")

r1, r2 = st.columns(2)

with r1:
    if latest_trade_csv:
        st.info(f"Reporte principal: {latest_trade_csv}")
    else:
        st.warning("No hay reporte principal.")

with r2:
    if latest_options_csv:
        st.info(f"Reporte opciones: {latest_options_csv}")
    else:
        st.warning("No hay reporte automatico de opciones.")

if latest_html:
    with open(latest_html, "r", encoding="utf-8", errors="replace") as file:
        html_content = file.read()

    st.download_button(
        label="Descargar ultimo reporte HTML",
        data=html_content,
        file_name=os.path.basename(latest_html),
        mime="text/html"
    )