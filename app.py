# app.py

import os
import glob
import subprocess
import pandas as pd
import streamlit as st
import plotly.express as px


st.set_page_config(
    page_title="AI Trader Pro",
    page_icon="🚀",
    layout="wide"
)


st.title("🚀 AI Trader Pro Dashboard")
st.caption("Dashboard visual de AI Trader")


st.subheader("⚙️ Control del Bot")

if st.button("🚀 Ejecutar análisis ahora"):
    with st.spinner("Ejecutando AI Trader..."):
        result = subprocess.run(
            ["python", "main.py"],
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


REPORTS_FOLDER = "reports"

if not os.path.exists(REPORTS_FOLDER):
    st.warning("No existe la carpeta reports. Ejecuta primero el análisis.")
    st.stop()


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


st.dataframe(df, width="stretch")


if "score" in df.columns:
    st.subheader("🏆 Ranking por Score")

    if "symbol" in df.columns:
        chart_df = df.sort_values("score", ascending=False)

        fig = px.bar(
            chart_df,
            x="symbol",
            y="score",
            text="score",
            title="Score por símbolo"
        )

        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("El reporte tiene score, pero no tiene columna symbol.")


required_columns = [
    "symbol",
    "price",
    "trend",
    "signal",
    "risk",
    "score",
    "rating"
]

if all(col in df.columns for col in required_columns):
    st.subheader("📌 Resumen de oportunidades")

    st.dataframe(
        df[required_columns],
        width="stretch"
    )
else:
    st.subheader("📌 Datos disponibles")
    st.info("El CSV no tiene todas las columnas esperadas, pero se muestra completo arriba.")


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