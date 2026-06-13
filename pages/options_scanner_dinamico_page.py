"""
pages/options_scanner_dinamico.py
==================================
Página Streamlit para el scanner dinámico de opciones.
Agregar en tu carpeta `pages/` de la app Streamlit.
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

# Ajusta estos imports según tu estructura de carpetas
try:
    from agents.options_scanner import (
        scan_market,
        DEFAULT_FILTERS,
        UNIVERSE,
        get_top_by_symbol,
    )
    from config.watchlist import (
        WATCHLISTS,
        get_watchlist,
        get_watchlist_names,
    )
except ImportError:
    # Si el archivo está en la raíz del proyecto
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from options_scanner import scan_market, DEFAULT_FILTERS, get_top_by_symbol
    from watchlist import WATCHLISTS, get_watchlist, get_watchlist_names


# ─────────────────────────────────────────────
# CONFIG DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="📡 Scanner Dinámico de Opciones",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Scanner Dinámico de Opciones")
st.caption(
    "Escanea el mercado completo buscando contratos con "
    "**delta alto · theta bajo · precio asequible · DTE largo**"
)

# ─────────────────────────────────────────────
# SIDEBAR: FILTROS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurar Filtros")

    # Watchlist
    st.subheader("🗂️ Universo de activos")
    watchlist_name = st.selectbox(
        "Selecciona el universo",
        options=get_watchlist_names(),
        index=0,
        help="El scanner analiza todos estos activos en busca de contratos óptimos.",
    )

    if watchlist_name == "Custom":
        custom_input = st.text_area(
            "Tickers personalizados (uno por línea o separados por coma)",
            placeholder="AAPL\nMSFT\nNVDA",
            height=120,
        )
        custom_syms = [
            s.strip().upper()
            for s in custom_input.replace(",", "\n").splitlines()
            if s.strip()
        ]
        symbols_to_scan = custom_syms if custom_syms else UNIVERSE[:20]
    else:
        symbols_to_scan = get_watchlist(watchlist_name)

    st.caption(f"📊 {len(symbols_to_scan)} activos en este universo")
    max_symbols = st.slider(
        "Máx. activos a escanear",
        min_value=10, max_value=len(symbols_to_scan),
        value=min(60, len(symbols_to_scan)),
        step=10,
        help="Más activos = scan más completo pero más lento (~1.5s por activo)",
    )

    st.divider()
    st.subheader("🎯 Tipo de contrato")
    option_type = st.radio(
        "Tipo de opción",
        options=["call", "put", "both"],
        index=0,
        horizontal=True,
    )

    st.divider()
    st.subheader("📐 Greeks")

    min_delta = st.slider(
        "Delta mínimo (abs)",
        min_value=0.10, max_value=0.90,
        value=DEFAULT_FILTERS["min_delta"],
        step=0.05,
        help="Delta ≥ este valor. 0.40+ = opciones con buen momentum, cerca del dinero.",
    )

    max_theta = st.slider(
        "Theta máximo (decay diario $)",
        min_value=-0.50, max_value=-0.01,
        value=DEFAULT_FILTERS["max_theta"],
        step=0.01,
        help="Theta ≤ este valor. Ej: -0.05 = pierde máx $5/día por contrato.",
    )

    st.divider()
    st.subheader("💰 Precio y plazo")

    max_premium = st.slider(
        "Prima máxima por contrato ($)",
        min_value=0.50, max_value=20.00,
        value=DEFAULT_FILTERS["max_premium"],
        step=0.25,
        help="Precio unitario de la opción. Costo real = prima × 100.",
    )
    st.caption(f"💵 Costo máximo real por contrato: **${max_premium * 100:,.0f}**")

    col1, col2 = st.columns(2)
    with col1:
        min_dte = st.number_input(
            "DTE mínimo (días)",
            min_value=7, max_value=365,
            value=DEFAULT_FILTERS["min_dte"],
            step=7,
        )
    with col2:
        max_dte = st.number_input(
            "DTE máximo (días)",
            min_value=30, max_value=730,
            value=DEFAULT_FILTERS["max_dte"],
            step=30,
        )

    st.divider()
    st.subheader("📈 Liquidez")

    min_oi = st.number_input(
        "Open Interest mínimo",
        min_value=1, max_value=10000,
        value=DEFAULT_FILTERS["min_open_interest"],
        step=10,
    )
    min_vol = st.number_input(
        "Volumen diario mínimo",
        min_value=0, max_value=1000,
        value=DEFAULT_FILTERS["min_volume"],
        step=1,
    )

    st.divider()
    n_results = st.slider(
        "Mostrar top N contratos",
        min_value=5, max_value=100,
        value=25, step=5,
    )
    group_by_symbol = st.checkbox(
        "Agrupar: máx 2 contratos por símbolo",
        value=False,
        help="Evita que un solo activo domine los resultados.",
    )

# ─────────────────────────────────────────────
# BOTÓN DE SCAN
# ─────────────────────────────────────────────
filters = {
    "min_delta":         min_delta,
    "max_theta":         max_theta,
    "max_premium":       max_premium,
    "min_dte":           min_dte,
    "max_dte":           max_dte,
    "min_open_interest": min_oi,
    "min_volume":        min_vol,
    "option_type":       option_type,
    "max_symbols":       max_symbols,
}

col_btn, col_info = st.columns([1, 3])
with col_btn:
    run_scan = st.button("🚀 Escanear Mercado", type="primary", width="stretch")
with col_info:
    est_time = max_symbols * 1.5
    st.info(
        f"⏱️ Tiempo estimado: ~{est_time:.0f}s  |  "
        f"Activos: {max_symbols}  |  "
        f"Delta≥{min_delta} · Theta≥{max_theta} · Prima≤${max_premium} · "
        f"DTE {min_dte}-{max_dte}d"
    )

# ─────────────────────────────────────────────
# EJECUCIÓN DEL SCAN
# ─────────────────────────────────────────────
if run_scan:
    start_time = time.time()

    progress_bar = st.progress(0, text="Iniciando scan…")
    status_text = st.empty()
    found_text = st.empty()

    found_count = 0
    scanned_count = 0

    def update_progress(symbol, idx, total):
        global scanned_count
        scanned_count = idx
        pct = idx / total
        progress_bar.progress(pct, text=f"Analizando {symbol}… ({idx}/{total})")
        status_text.caption(f"⏳ {symbol} | Encontrados hasta ahora: {found_count} contratos")

    # Capturar resultados en tiempo real no es directo en Streamlit,
    # así que mostramos el progreso por símbolo y acumulamos al final.
    with st.spinner("Escaneando el mercado…"):
        results_df = scan_market(
            filters=filters,
            custom_symbols=symbols_to_scan[:max_symbols],
            progress_callback=update_progress,
        )

    progress_bar.empty()
    status_text.empty()
    found_text.empty()

    elapsed = time.time() - start_time

    # ─────────────────────────────────────────
    # MOSTRAR RESULTADOS
    # ─────────────────────────────────────────
    if results_df.empty:
        st.warning(
            "⚠️ No se encontraron contratos que pasen los filtros actuales.\n\n"
            "Intenta:\n"
            "- Bajar el Delta mínimo (ej: 0.30)\n"
            "- Subir la Prima máxima (ej: $10)\n"
            "- Ampliar el rango de DTE\n"
            "- Bajar el Open Interest mínimo\n"
            "- Usar una watchlist más grande"
        )
    else:
        # Aplicar agrupación si se solicita
        display_df = get_top_by_symbol(results_df, 2) if group_by_symbol else results_df.head(n_results)

        # Métricas resumen
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("✅ Contratos", f"{len(results_df):,}")
        col2.metric("📊 Activos únicos", f"{results_df['symbol'].nunique()}")
        col3.metric("⏱️ Tiempo", f"{elapsed:.0f}s")
        col4.metric("💰 Prima prom.", f"${results_df['prima'].mean():.2f}")
        col5.metric("📅 DTE prom.", f"{results_df['dte'].mean():.0f}d")

        st.success(f"🎯 **{len(results_df)} contratos encontrados** en {results_df['symbol'].nunique()} activos · Mostrando top {len(display_df)}")

        # ── TABLA PRINCIPAL ──────────────────────
        st.subheader("🏆 Mejores Contratos")

        # Formatear tabla
        fmt_df = display_df.copy()
        
        # Columnas que mostrar y su formato
        show_cols = []
        col_formats = {}

        if "symbol" in fmt_df.columns:
            show_cols.append("symbol")
        if "option_type" in fmt_df.columns:
            show_cols.append("option_type")
        if "expiration" in fmt_df.columns:
            show_cols.append("expiration")
        if "dte" in fmt_df.columns:
            show_cols.append("dte")
            col_formats["dte"] = "{:.0f}d"
        if "strike" in fmt_df.columns:
            show_cols.append("strike")
            col_formats["strike"] = "${:.2f}"
        if "prima" in fmt_df.columns:
            show_cols.append("prima")
            col_formats["prima"] = "${:.2f}"
        if "delta" in fmt_df.columns:
            show_cols.append("delta")
            col_formats["delta"] = "{:.3f}"
        if "theta" in fmt_df.columns:
            show_cols.append("theta")
            col_formats["theta"] = "{:.3f}"
        if "gamma" in fmt_df.columns:
            show_cols.append("gamma")
            col_formats["gamma"] = "{:.4f}"
        if "IV" in fmt_df.columns:
            show_cols.append("IV")
            col_formats["IV"] = "{:.1%}"
        if "OI" in fmt_df.columns:
            show_cols.append("OI")
            col_formats["OI"] = "{:,.0f}"
        if "volume" in fmt_df.columns:
            show_cols.append("volume")
            col_formats["volume"] = "{:,.0f}"
        if "score" in fmt_df.columns:
            show_cols.append("score")
            col_formats["score"] = "{:.3f}"

        fmt_df = fmt_df[show_cols]

        # ── Calcular max del score de forma SEGURA (evita NaN -> crash JSON) ──
        score_max = 10.0
        if "score" in fmt_df.columns:
            s = pd.to_numeric(fmt_df["score"], errors="coerce")
            if s.notna().any() and s.max() > 0:
                score_max = float(s.max())

        # ── Construir column_config solo con las columnas presentes ──
        column_config = {
            "symbol":      st.column_config.TextColumn("Activo", width="small"),
            "option_type": st.column_config.TextColumn("Tipo", width="small"),
            "expiration":  st.column_config.TextColumn("Vencimiento"),
            "dte":         st.column_config.NumberColumn("DTE", format="%d d"),
            "strike":      st.column_config.NumberColumn("Strike", format="$%.2f"),
            "prima":       st.column_config.NumberColumn("Prima", format="$%.2f"),
            "delta":       st.column_config.NumberColumn("Δ Delta", format="%.3f"),
            "theta":       st.column_config.NumberColumn("Θ Theta", format="%.3f"),
            "gamma":       st.column_config.NumberColumn("Γ Gamma", format="%.4f"),
            "IV":          st.column_config.NumberColumn("IV", format="%.1f%%"),
            "OI":          st.column_config.NumberColumn("Open Int.", format="%d"),
            "volume":      st.column_config.NumberColumn("Volumen", format="%d"),
            "score":       st.column_config.ProgressColumn("Score", min_value=0, max_value=score_max),
        }
        # Filtrar solo las columnas que realmente existen
        column_config = {k: v for k, v in column_config.items() if k in fmt_df.columns}

        st.dataframe(
            fmt_df,
            width="stretch",
            height=min(600, 50 + len(fmt_df) * 35),
            column_config=column_config,
        )

        # ── DISTRIBUCIÓN POR ACTIVO ───────────────
        if "symbol" in results_df.columns:
            st.subheader("📊 Distribución por Activo")
            symbol_counts = results_df.groupby("symbol").size().sort_values(ascending=False).head(20)
            st.bar_chart(symbol_counts)

        # ── DESCARGA ─────────────────────────────
        st.divider()
        csv = results_df.to_csv(index=False).encode("utf-8")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            "⬇️ Descargar todos los resultados (CSV)",
            data=csv,
            file_name=f"options_scan_{timestamp}.csv",
            mime="text/csv",
        )

        # ── NOTA SOBRE GREEKS ─────────────────────
        if results_df[["delta", "theta"]].isna().all().all():
            st.info(
                "ℹ️ **No se pudieron calcular los Greeks** porque faltó la Implied Volatility "
                "en estos contratos. El filtrado se basó en Prima, DTE y Open Interest. "
                "Los Greeks se calculan con Black-Scholes a partir de la IV de yfinance."
            )
        else:
            st.caption(
                "📐 Delta, Theta, Gamma y Vega calculados con **Black-Scholes** "
                "(yfinance no los entrega directamente). Son estimaciones; "
                "para precisión institucional usa Tradier o TD Ameritrade."
            )

# ─────────────────────────────────────────────
# INSTRUCCIONES SI NO SE HA HECHO SCAN
# ─────────────────────────────────────────────
else:
    st.divider()
    st.markdown("""
    ### 📖 Cómo usar este scanner

    1. **Selecciona el universo** – "Mercado Amplio" analiza más de 100 activos
    2. **Ajusta los filtros** en el panel izquierdo según tu estrategia:
       - **Delta alto (≥0.40)** → opciones con más probabilidad de mover en tu dirección
       - **Theta bajo (≥-0.05)** → contratos con decay lento (pagas poco por el tiempo)
       - **Prima baja** → contratos asequibles para entrar con poco capital
       - **DTE largo (≥30d)** → más tiempo para que el trade funcione
    3. **Pulsa "Escanear Mercado"** y espera los resultados
    4. **Ordena la tabla** por Score, Delta o cualquier columna
    5. **Descarga el CSV** para analizar en Excel u otras herramientas

    ---
    #### 🎯 Estrategias sugeridas

    | Estrategia | Delta | Theta | Prima | DTE |
    |---|---|---|---|---|
    | Compra agresiva | ≥0.50 | cualquiera | ≤$3 | 30-60d |
    | Swing moderado | ≥0.35 | ≥-0.05 | ≤$5 | 45-90d |
    | Posición larga | ≥0.30 | ≥-0.03 | ≤$8 | 90-180d |
    | LEAPS conservador | ≥0.25 | ≥-0.02 | ≤$15 | 180-365d |
    """)
