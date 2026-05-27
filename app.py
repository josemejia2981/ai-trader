import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="AI TRADER | Executive Dashboard",
    page_icon="📊",
    layout="wide"
)

REPORTS_DIR = Path("reports")
OPTION_MULTIPLIER = 100

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #020617 0%, #0f172a 45%, #111827 100%);
    color: #e5e7eb;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
[data-testid="stMetricValue"] {
    color: white;
}
[data-testid="stMetricLabel"] {
    color: #cbd5e1;
}
</style>
""", unsafe_allow_html=True)


def get_latest_file(pattern):
    files = list(REPORTS_DIR.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def load_csv(file_path):
    if file_path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame()


def find_column(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def to_float(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def number(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "0.00"


def recommendation_from_score(score):
    score = to_float(score)
    if score >= 90:
        return "🟢 COMPRA FUERTE"
    elif score >= 75:
        return "🟡 RELOJ"
    else:
        return "🔴 EVITAR"


def prepare_portfolio(df):
    if df.empty:
        return df

    df = df.copy()

    contracts_col = find_column(df, ["contracts", "quantity", "qty"])
    price_col = find_column(df, ["price", "lastPrice", "last_price", "underlying_price", "option_price"])
    current_price_col = find_column(df, ["current_price", "market_price", "price", "underlying_price", "last_price"])

    entry_col = find_column(df, [
        "entry", "entry_price", "recommended_entry", "buy_price",
        "option_entry", "entry_option_price", "lastPrice"
    ])

    stop_col = find_column(df, [
        "stop_loss", "stop", "sl", "recommended_stop", "option_stop"
    ])

    take_profit_col = find_column(df, [
        "take_profit", "target", "tp", "recommended_exit",
        "exit_price", "sell_target", "option_take_profit"
    ])

    risk_col = find_column(df, ["risk_amount", "risk", "max_risk"])
    profit_col = find_column(df, ["potential_profit", "profit", "expected_profit"])
    score_col = find_column(df, ["score", "final_score", "institutional_score"])
    confidence_col = find_column(df, ["confidence", "ai_confidence", "option_confidence"])

    if contracts_col is None:
        df["contracts"] = 1
        contracts_col = "contracts"

    if entry_col is None and price_col:
        df["entry_price"] = df[price_col]
        entry_col = "entry_price"

    if current_price_col is None and price_col:
        df["current_price"] = df[price_col]
        current_price_col = "current_price"

    if risk_col is None:
        df["risk_amount"] = df.apply(
            lambda row: max(
                (to_float(row.get(entry_col)) - to_float(row.get(stop_col))) *
                to_float(row.get(contracts_col), 1) *
                OPTION_MULTIPLIER,
                0
            ) if entry_col and stop_col else 0,
            axis=1
        )

    if profit_col is None:
        df["potential_profit"] = df.apply(
            lambda row: max(
                (to_float(row.get(take_profit_col)) - to_float(row.get(entry_col))) *
                to_float(row.get(contracts_col), 1) *
                OPTION_MULTIPLIER,
                0
            ) if entry_col and take_profit_col else 0,
            axis=1
        )

    risk_col = find_column(df, ["risk_amount", "risk", "max_risk"])
    profit_col = find_column(df, ["potential_profit", "profit", "expected_profit"])

    if "risk_reward" not in df.columns:
        df["risk_reward"] = df.apply(
            lambda row: round(
                to_float(row.get(profit_col)) / to_float(row.get(risk_col)),
                2
            ) if risk_col and profit_col and to_float(row.get(risk_col)) > 0 else 0,
            axis=1
        )

    if "distance_to_entry_pct" not in df.columns:
        df["distance_to_entry_pct"] = df.apply(
            lambda row: round(
                ((to_float(row.get(current_price_col)) - to_float(row.get(entry_col))) /
                 to_float(row.get(entry_col))) * 100,
                2
            ) if current_price_col and entry_col and to_float(row.get(entry_col)) > 0 else 0,
            axis=1
        )

    if "entry_status" not in df.columns:
        df["entry_status"] = df["distance_to_entry_pct"].apply(
            lambda x: "✅ CERCA DE ENTRADA" if abs(to_float(x)) <= 2 else "⏳ ESPERAR"
        )

    if score_col:
        df["recommendation"] = df[score_col].apply(recommendation_from_score)
    else:
        df["recommendation"] = "N/A"

    if confidence_col is None:
        df["confidence"] = df[score_col] if score_col else 0

    return df


latest_trades_file = get_latest_file("trades_*.csv")
latest_scanner_file = get_latest_file("options_scanner_*.csv")
latest_portfolio_file = get_latest_file("portfolio_*.csv")
latest_html_file = get_latest_file("*.html")

trades_df = load_csv(latest_trades_file)
scanner_df = load_csv(latest_scanner_file)
portfolio_df = load_csv(latest_portfolio_file)

if portfolio_df.empty:
    portfolio_df = scanner_df.copy()

if portfolio_df.empty:
    portfolio_df = trades_df.copy()

portfolio_df = prepare_portfolio(portfolio_df)

st.title("📊 AI TRADER Executive Dashboard")
st.caption("Panel profesional para entradas, salidas, riesgo, ganancia potencial, precio actual y Portfolio del Día.")

h1, h2, h3 = st.columns([2, 1, 1])

with h1:
    st.success("Sistema activo")

with h2:
    st.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d')}")

with h3:
    st.write(f"**Hora:** {datetime.now().strftime('%H:%M:%S')}")

st.divider()

if portfolio_df.empty:
    st.warning("No hay reportes disponibles. Ejecuta primero main.py.")
    st.stop()


symbol_col = find_column(portfolio_df, ["symbol", "Symbol", "ticker", "Ticker"])
contract_col = find_column(portfolio_df, ["contractSymbol", "contract", "option_contract", "contract_symbol"])
type_col = find_column(portfolio_df, ["option_type", "type", "strategy", "entry_type"])
score_col = find_column(portfolio_df, ["score", "final_score", "institutional_score"])
contracts_col = find_column(portfolio_df, ["contracts", "quantity", "qty"])
price_col = find_column(portfolio_df, ["price", "lastPrice", "last_price", "underlying_price", "option_price"])
current_price_col = find_column(portfolio_df, ["current_price", "market_price", "price", "underlying_price", "last_price"])
entry_col = find_column(portfolio_df, ["entry", "entry_price", "recommended_entry", "buy_price", "option_entry", "entry_option_price", "lastPrice"])
stop_col = find_column(portfolio_df, ["stop_loss", "stop", "sl", "recommended_stop", "option_stop"])
take_profit_col = find_column(portfolio_df, ["take_profit", "target", "tp", "recommended_exit", "exit_price", "sell_target", "option_take_profit"])
dte_col = find_column(portfolio_df, ["dte", "DTE", "days_to_expiration"])
confidence_col = find_column(portfolio_df, ["confidence", "ai_confidence", "option_confidence"])
risk_col = find_column(portfolio_df, ["risk_amount", "risk", "max_risk"])
profit_col = find_column(portfolio_df, ["potential_profit", "profit", "expected_profit"])
rr_col = find_column(portfolio_df, ["risk_reward"])
recommendation_col = find_column(portfolio_df, ["recommendation"])
distance_col = find_column(portfolio_df, ["distance_to_entry_pct"])
entry_status_col = find_column(portfolio_df, ["entry_status"])


st.sidebar.title("AI TRADER")
st.sidebar.caption("Panel de Control Ejecutivo")

filtered_df = portfolio_df.copy()

if symbol_col:
    symbols = sorted(filtered_df[symbol_col].dropna().unique().tolist())
    selected_symbols = st.sidebar.multiselect("Filtrar símbolos", symbols, default=symbols)
    filtered_df = filtered_df[filtered_df[symbol_col].isin(selected_symbols)]

if type_col:
    types = sorted(filtered_df[type_col].dropna().unique().tolist())
    selected_types = st.sidebar.multiselect("Filtrar estrategia", types, default=types)
    filtered_df = filtered_df[filtered_df[type_col].isin(selected_types)]

if score_col:
    min_score = st.sidebar.slider("Puntuación mínima", 0, 100, 0)
    filtered_df = filtered_df[filtered_df[score_col] >= min_score]

if recommendation_col:
    recs = sorted(filtered_df[recommendation_col].dropna().unique().tolist())
    selected_recs = st.sidebar.multiselect("Filtrar recomendación", recs, default=recs)
    filtered_df = filtered_df[filtered_df[recommendation_col].isin(selected_recs)]

st.sidebar.divider()
st.sidebar.caption("Prioridad: score alto + Risk/Reward fuerte + entrada cercana.")


total_positions = len(filtered_df)
total_risk = filtered_df[risk_col].sum() if risk_col else 0
total_profit = filtered_df[profit_col].sum() if profit_col else 0
avg_score = filtered_df[score_col].mean() if score_col and not filtered_df.empty else 0
avg_rr = filtered_df[rr_col].mean() if rr_col and not filtered_df.empty else 0

best_symbol = "N/A"
if score_col and symbol_col and not filtered_df.empty:
    best_row = filtered_df.sort_values(by=score_col, ascending=False).iloc[0]
    best_symbol = best_row.get(symbol_col, "N/A")

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Posiciones", total_positions)
m2.metric("Riesgo Total", money(total_risk))
m3.metric("Ganancia Potencial", money(total_profit))
m4.metric("Score Promedio", number(avg_score))
m5.metric("Risk / Reward", number(avg_rr))
m6.metric("Mejor Trade", best_symbol)


st.subheader("🏆 Portfolio del Día")

portfolio_day_df = filtered_df.copy()

if score_col:
    portfolio_day_df = portfolio_day_df.sort_values(by=score_col, ascending=False)

portfolio_day_df = portfolio_day_df.head(3)

if not portfolio_day_df.empty:
    p1, p2, p3 = st.columns(3)

    cols = [p1, p2, p3]

    for i, (_, row) in enumerate(portfolio_day_df.iterrows()):
        with cols[i]:
            symbol = row.get(symbol_col, "N/A") if symbol_col else "N/A"
            trade_type = row.get(type_col, "N/A") if type_col else "N/A"
            score = row.get(score_col, 0) if score_col else 0
            risk = row.get(risk_col, 0) if risk_col else 0
            profit = row.get(profit_col, 0) if profit_col else 0
            rr = row.get(rr_col, 0) if rr_col else 0
            recommendation = row.get(recommendation_col, "N/A") if recommendation_col else "N/A"

            with st.container(border=True):
                st.markdown(f"### #{i + 1} {symbol}")
                st.caption(str(trade_type))
                st.write(str(recommendation))
                st.metric("Score", number(score))
                st.metric("Riesgo", money(risk))
                st.metric("Ganancia Potencial", money(profit))
                st.metric("Risk / Reward", number(rr))


st.subheader("🏆 Trade del Día")

if not filtered_df.empty:
    if score_col:
        trade_day = filtered_df.sort_values(by=score_col, ascending=False).iloc[0]
    else:
        trade_day = filtered_df.iloc[0]

    symbol = trade_day.get(symbol_col, "N/A") if symbol_col else "N/A"
    contract = trade_day.get(contract_col, "N/A") if contract_col else "N/A"
    trade_type = trade_day.get(type_col, "N/A") if type_col else "N/A"
    current_price = trade_day.get(current_price_col, 0) if current_price_col else 0
    entry = trade_day.get(entry_col, 0) if entry_col else 0
    stop = trade_day.get(stop_col, 0) if stop_col else 0
    target = trade_day.get(take_profit_col, 0) if take_profit_col else 0
    risk = trade_day.get(risk_col, 0) if risk_col else 0
    profit = trade_day.get(profit_col, 0) if profit_col else 0
    rr = trade_day.get(rr_col, 0) if rr_col else 0
    score = trade_day.get(score_col, 0) if score_col else 0
    dte = trade_day.get(dte_col, "N/A") if dte_col else "N/A"
    confidence = trade_day.get(confidence_col, 0) if confidence_col else 0
    recommendation = trade_day.get(recommendation_col, "N/A") if recommendation_col else "N/A"
    distance = trade_day.get(distance_col, 0) if distance_col else 0
    entry_status = trade_day.get(entry_status_col, "N/A") if entry_status_col else "N/A"

    with st.container(border=True):
        t1, t2 = st.columns([3, 1])

        with t1:
            st.markdown(f"### {symbol} — {trade_type}")
            st.caption(str(contract))

        with t2:
            st.success(str(recommendation))

        a, b, c, d = st.columns(4)
        a.metric("Precio Actual", money(current_price))
        b.metric("Entrada Recomendada", money(entry))
        c.metric("Distancia a Entrada", f"{number(distance)}%")
        d.metric("Estado Entrada", entry_status)

        e, f, g, h = st.columns(4)
        e.metric("Stop Loss", money(stop))
        f.metric("Salida / Take Profit", money(target))
        g.metric("Riesgo Estimado", money(risk))
        h.metric("Ganancia Potencial", money(profit))

        i, j, k, l = st.columns(4)
        i.metric("Risk / Reward", number(rr))
        j.metric("Score Institucional", number(score))
        k.metric("DTE", dte)
        l.metric("Confianza", f"{number(confidence)}%")

        conf_value = max(0, min(to_float(confidence), 100))
        st.progress(conf_value / 100)
else:
    st.warning("No hay trades disponibles con los filtros actuales.")


st.subheader("Top Operaciones Recomendadas")

top_df = filtered_df.copy()

if score_col:
    top_df = top_df.sort_values(by=score_col, ascending=False)

top_df = top_df.head(5)

for _, row in top_df.iterrows():
    symbol = row.get(symbol_col, "N/A") if symbol_col else "N/A"
    contract = row.get(contract_col, "N/A") if contract_col else "N/A"
    trade_type = row.get(type_col, "N/A") if type_col else "N/A"
    current_price = row.get(current_price_col, 0) if current_price_col else 0
    entry = row.get(entry_col, 0) if entry_col else 0
    stop = row.get(stop_col, 0) if stop_col else 0
    target = row.get(take_profit_col, 0) if take_profit_col else 0
    risk = row.get(risk_col, 0) if risk_col else 0
    profit = row.get(profit_col, 0) if profit_col else 0
    rr = row.get(rr_col, 0) if rr_col else 0
    score = row.get(score_col, 0) if score_col else 0
    dte = row.get(dte_col, "N/A") if dte_col else "N/A"
    recommendation = row.get(recommendation_col, "N/A") if recommendation_col else "N/A"
    distance = row.get(distance_col, 0) if distance_col else 0
    entry_status = row.get(entry_status_col, "N/A") if entry_status_col else "N/A"

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])

        with c1:
            st.markdown(f"### {symbol} — {trade_type}")
            st.caption(str(contract))

        with c2:
            st.write(str(recommendation))

        x1, x2, x3, x4 = st.columns(4)
        x1.metric("Precio Actual", money(current_price))
        x2.metric("Entrada", money(entry))
        x3.metric("Distancia", f"{number(distance)}%")
        x4.metric("Estado", entry_status)

        y1, y2, y3, y4, y5, y6 = st.columns(6)
        y1.metric("Stop", money(stop))
        y2.metric("Salida", money(target))
        y3.metric("Riesgo", money(risk))
        y4.metric("Ganancia", money(profit))
        y5.metric("R/R", number(rr))
        y6.metric("Score / DTE", f"{number(score)} / {dte}")


st.subheader("Tabla Ejecutiva")

display_cols = []

for col in [
    symbol_col,
    contract_col,
    type_col,
    recommendation_col,
    contracts_col,
    current_price_col,
    entry_col,
    distance_col,
    entry_status_col,
    stop_col,
    take_profit_col,
    risk_col,
    profit_col,
    rr_col,
    dte_col,
    confidence_col,
    score_col
]:
    if col and col not in display_cols:
        display_cols.append(col)

table_df = filtered_df[display_cols].copy() if display_cols else filtered_df.copy()

if score_col and score_col in table_df.columns:
    table_df = table_df.sort_values(by=score_col, ascending=False)

st.dataframe(table_df, width="stretch", hide_index=True)


st.subheader("Análisis Visual del Portfolio")

c1, c2 = st.columns(2)

with c1:
    if symbol_col and risk_col and not filtered_df.empty:
        risk_chart = filtered_df.groupby(symbol_col, as_index=False)[risk_col].sum()
        fig = px.bar(risk_chart, x=symbol_col, y=risk_col, title="Riesgo Total por Símbolo", text_auto=True)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, width="stretch")

with c2:
    if symbol_col and profit_col and not filtered_df.empty:
        profit_chart = filtered_df.groupby(symbol_col, as_index=False)[profit_col].sum()
        fig = px.bar(profit_chart, x=symbol_col, y=profit_col, title="Ganancia Potencial por Símbolo", text_auto=True)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, width="stretch")


c3, c4 = st.columns(2)

with c3:
    if recommendation_col and not filtered_df.empty:
        rec_chart = filtered_df[recommendation_col].value_counts().reset_index()
        rec_chart.columns = ["Recomendación", "Cantidad"]
        fig = px.pie(rec_chart, values="Cantidad", names="Recomendación", title="Distribución por Recomendación")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, width="stretch")

with c4:
    if symbol_col and score_col and not filtered_df.empty:
        score_chart = filtered_df[[symbol_col, score_col]].copy()
        score_chart = score_chart.sort_values(by=score_col, ascending=False)
        fig = px.bar(score_chart, x=symbol_col, y=score_col, title="Ranking por Score Institucional", text_auto=True)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, width="stretch")


st.subheader("Resumen Ejecutivo del Trader")

if not filtered_df.empty:
    strong_count = len(filtered_df[filtered_df["recommendation"].astype(str).str.contains("COMPRA FUERTE", na=False)])
    watch_count = len(filtered_df[filtered_df["recommendation"].astype(str).str.contains("RELOJ", na=False)])
    avoid_count = len(filtered_df[filtered_df["recommendation"].astype(str).str.contains("EVITAR", na=False)])
    near_entry_count = len(filtered_df[filtered_df["entry_status"].astype(str).str.contains("CERCA", na=False)])

    st.info(
        f"""
        **Lectura rápida del sistema:**

        - Operaciones COMPRA FUERTE: {strong_count}
        - Operaciones RELOJ: {watch_count}
        - Operaciones EVITAR: {avoid_count}
        - Operaciones cerca de entrada: {near_entry_count}
        - Riesgo total estimado: {money(total_risk)}
        - Ganancia potencial estimada: {money(total_profit)}
        - Risk/Reward promedio: {number(avg_rr)}

        **Regla sugerida:** priorizar COMPRA FUERTE, entrada cercana, Risk/Reward mayor de 2.00 y riesgo controlado.
        """
    )


st.subheader("Reportes y Descargas")

r1, r2, r3 = st.columns(3)

with r1:
    if latest_trades_file:
        st.success("Trades CSV encontrado")
        st.caption(str(latest_trades_file))
        with open(latest_trades_file, "rb") as file:
            st.download_button("Descargar Trades CSV", file, file_name=latest_trades_file.name, mime="text/csv")
    else:
        st.warning("No hay trades CSV.")

with r2:
    if latest_scanner_file:
        st.success("Scanner CSV encontrado")
        st.caption(str(latest_scanner_file))
        with open(latest_scanner_file, "rb") as file:
            st.download_button("Descargar Scanner CSV", file, file_name=latest_scanner_file.name, mime="text/csv")
    else:
        st.warning("No hay scanner CSV.")

with r3:
    if latest_html_file:
        st.success("Reporte HTML encontrado")
        st.caption(str(latest_html_file))
        with open(latest_html_file, "rb") as file:
            st.download_button("Descargar Reporte HTML", file, file_name=latest_html_file.name, mime="text/html")
    else:
        st.warning("No hay HTML.")

st.divider()
st.caption("AI TRADER | Executive Options Intelligence Dashboard")