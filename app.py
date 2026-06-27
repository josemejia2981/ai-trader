import os
import sys
import glob
import subprocess
import time
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="AI TRADER — Schwab",
    page_icon="📈",
    layout="wide"
)

REPORTS_DIR = "reports"


def ny_time():
    return datetime.now(ZoneInfo("America/New_York"))


def find_latest_csv():
    for pattern in ["portfolio_*.csv", "options_scanner_*.csv", "trades_*.csv"]:
        files = glob.glob(os.path.join(REPORTS_DIR, pattern))
        if files:
            return max(files, key=os.path.getmtime)
    return None


def remove_dup_cols(df):
    return df.loc[:, ~df.columns.duplicated()]


def normalize_columns(df):
    rename_map = {
        "contract": "contractSymbol", "contract_symbol": "contractSymbol",
        "type": "option_type", "optionType": "option_type",
        "Strike": "strike", "option_strike": "strike",
        "Delta": "delta", "option_delta": "delta", "delta_estimate": "delta",
        "open_interest": "openInterest", "OpenInterest": "openInterest",
        "option_open_interest": "openInterest", "oi": "openInterest",
        "option_volume": "volume", "Volume": "volume",
        "last_price": "lastPrice", "option_last_price": "lastPrice",
        "Bid": "bid", "option_bid": "bid",
        "Ask": "ask", "option_ask": "ask",
        "risk": "risk_amount", "riskAmount": "risk_amount",
        "potentialProfit": "potential_profit",
        "option_contract": "contractSymbol",
    }
    df = df.rename(columns=rename_map)
    return remove_dup_cols(df)


def safe_val(v):
    try:
        if pd.isna(v):
            return "N/A"
    except Exception:
        pass
    return v if v is not None else "N/A"


def fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "N/A"


def fmt_pct(v):
    try:
        return f"{float(v):.1f}%"
    except Exception:
        return "N/A"


def fmt_num(v, decimals=2):
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return "N/A"


def score_color(score):
    try:
        s = float(score)
        if s >= 80:
            return "🟢", "#1a7a1a", "EXCELENTE"
        elif s >= 70:
            return "🟡", "#7a6a00", "FUERTE"
        elif s >= 60:
            return "🟠", "#7a3d00", "INTERESANTE"
        else:
            return "🔴", "#7a0000", "OBSERVAR"
    except Exception:
        return "⚪", "#555", "N/A"


def run_analysis():
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    proc = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    lines = []
    for line in proc.stdout:
        lines.append(line.rstrip())
    proc.wait()
    return proc.returncode, lines


# ══════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════

now = ny_time()
open_mkt = (
    now.weekday() < 5
    and now.replace(hour=9, minute=30, second=0, microsecond=0)
    <= now
    <= now.replace(hour=16, minute=0, second=0, microsecond=0)
)

col_title, col_status = st.columns([4, 1])
with col_title:
    st.title("📈 AI TRADER — Panel de Recomendaciones")
    st.caption("Análisis de opciones swing trading • Solo lectura — no ejecuta trades")

with col_status:
    st.metric("Hora NY", now.strftime("%H:%M:%S"))
    if open_mkt:
        st.success("🟢 Mercado ABIERTO")
    else:
        st.warning("🔴 Mercado CERRADO")

st.divider()

# ══════════════════════════════════════════
# BOTÓN EJECUTAR ANÁLISIS
# ══════════════════════════════════════════

col_btn, col_info = st.columns([2, 5])
with col_btn:
    ejecutar = st.button("🚀 Ejecutar Análisis", type="primary", use_container_width=True)

with col_info:
    st.info("El análisis toma 1-3 minutos. Descarga datos de mercado y evalúa cada símbolo.")

if ejecutar:
    with st.status("⏳ Analizando mercado...", expanded=True) as status:
        st.write("Descargando datos y evaluando señales...")
        returncode, output_lines = run_analysis()
        for line in output_lines[-25:]:
            if line.strip():
                st.text(line)
        if returncode == 0:
            status.update(label="✅ Análisis completado.", state="complete")
            st.session_state["analysis_done"] = True
            time.sleep(1)
            st.rerun()
        else:
            status.update(label="❌ Error en el análisis.", state="error")

# ══════════════════════════════════════════
# CARGAR DATOS
# ══════════════════════════════════════════

# Solo mostramos datos si el usuario corrió un análisis en ESTA sesión.
# Así nunca se carga automáticamente un reporte viejo de la carpeta reports/.
if not st.session_state.get("analysis_done"):
    st.warning(
        "👋 No hay análisis cargado en esta sesión. "
        "Haz clic en **🚀 Ejecutar Análisis** para generar un reporte nuevo con datos de hoy."
    )
    st.stop()

latest_csv = find_latest_csv()

if latest_csv is None:
    st.error(
        "El análisis corrió pero no se encontró ningún CSV en la carpeta `reports/`. "
        "Revisa que `main.py` esté guardando el reporte correctamente."
    )
    st.stop()

try:
    df = pd.read_csv(latest_csv)
except Exception as e:
    st.error(f"No se pudo leer el reporte: {e}")
    st.stop()

df = normalize_columns(df)
df["_score_num"] = pd.to_numeric(df.get("score", pd.Series([0]*len(df))), errors="coerce").fillna(0)
df = df.sort_values("_score_num", ascending=False).reset_index(drop=True)

ts = datetime.fromtimestamp(os.path.getmtime(latest_csv)).strftime("%d/%m/%Y %H:%M")
st.caption(f"📄 Reporte: `{os.path.basename(latest_csv)}` — generado {ts}")

# ══════════════════════════════════════════
# MÉTRICAS RESUMEN
# ══════════════════════════════════════════

def safe_sum(col):
    return pd.to_numeric(df.get(col, pd.Series([0]*len(df))), errors="coerce").fillna(0).sum()

def safe_mean(col):
    return pd.to_numeric(df.get(col, pd.Series([0]*len(df))), errors="coerce").fillna(0).mean()

df_opp = df[df["_score_num"] >= 70]

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("Símbolos analizados", len(df))
with m2:
    st.metric("Oportunidades (≥70)", len(df_opp))
with m3:
    st.metric("Riesgo total", fmt_money(safe_sum("risk_amount")))
with m4:
    st.metric("Ganancia potencial", fmt_money(safe_sum("potential_profit")))
with m5:
    avg = safe_mean("_score_num")
    st.metric("Score promedio", f"{avg:.0f}/100")

st.divider()

# ══════════════════════════════════════════
# RECOMENDACIONES PRINCIPALES
# ══════════════════════════════════════════

st.subheader("🎯 Recomendaciones de Hoy")

if df_opp.empty:
    st.info("Ningún símbolo alcanzó score ≥ 70 hoy. El mercado no presenta condiciones óptimas para entrar.")
else:
    for _, row in df_opp.head(5).iterrows():
        symbol   = safe_val(row.get("symbol", ""))
        opt_type = str(safe_val(row.get("option_type", ""))).upper()
        score    = row.get("_score_num", 0)
        trend    = safe_val(row.get("trend", ""))
        emoji, color, label = score_color(score)

        contract   = safe_val(row.get("contractSymbol", row.get("option_contract", "")))
        strike     = safe_val(row.get("strike", row.get("option_strike", "")))
        expiration = safe_val(row.get("expiration", row.get("option_expiration", row.get("expiration_date", ""))))
        dte        = safe_val(row.get("dte", row.get("option_dte", "")))
        delta      = safe_val(row.get("delta", row.get("option_delta", "")))
        iv         = safe_val(row.get("impliedVolatility", ""))

        entry_price = safe_val(row.get("entry_price", row.get("option_entry", row.get("option_last_price", ""))))
        stop_loss   = safe_val(row.get("stop_loss", row.get("option_stop_loss", "")))
        tp1         = safe_val(row.get("take_profit_1", row.get("option_take_profit_1", "")))
        tp2         = safe_val(row.get("take_profit_2", row.get("option_take_profit", row.get("take_profit", ""))))

        stock_price = safe_val(row.get("price", row.get("underlying_price", "")))
        stock_sl    = safe_val(row.get("stock_stop_loss", ""))
        stock_tp1   = safe_val(row.get("stock_take_profit_1", ""))
        stock_tp2   = safe_val(row.get("stock_take_profit_2", ""))

        contracts   = safe_val(row.get("contracts", 1))
        risk_amount = safe_val(row.get("risk_amount", ""))
        potential   = safe_val(row.get("potential_profit", ""))
        rr          = safe_val(row.get("risk_reward", ""))
        bid         = safe_val(row.get("bid", row.get("option_bid", "")))
        ask         = safe_val(row.get("ask", row.get("option_ask", "")))
        oi          = safe_val(row.get("openInterest", row.get("option_open_interest", "")))
        volume      = safe_val(row.get("volume", row.get("option_volume", "")))
        reasons     = safe_val(row.get("signal_reasons", row.get("entry_trigger", row.get("score_reasons", ""))))

        opt_icon = "📈" if opt_type == "CALL" else "📉"

        with st.container(border=True):
            # Encabezado
            h1, h2 = st.columns([3, 1])
            with h1:
                st.markdown(f"### {opt_icon} {symbol} — {opt_type}")
                st.markdown(f"Tendencia: **{trend}** &nbsp;|&nbsp; Contrato: `{contract}`")
            with h2:
                st.markdown(
                    f"<div style='text-align:center; padding:8px; background:{color}20; "
                    f"border:2px solid {color}; border-radius:10px;'>"
                    f"<span style='font-size:2em'>{emoji}</span><br>"
                    f"<b style='color:{color}; font-size:1.3em'>{score:.0f}/100</b><br>"
                    f"<small style='color:{color}'>{label}</small></div>",
                    unsafe_allow_html=True
                )

            st.write("")

            # Entrada / Salida — Opción
            st.markdown("#### 📌 Opción — Puntos de Entrada y Salida")
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                ep_fmt = fmt_money(entry_price)
                try:
                    cost_total = fmt_money(float(entry_price) * 100 * float(contracts))
                except Exception:
                    cost_total = "N/A"
                st.markdown(
                    f"<div style='background:#0a3d0a; padding:12px; border-radius:8px; text-align:center'>"
                    f"<div style='color:#aaa; font-size:0.85em'>💰 PRECIO DE ENTRADA</div>"
                    f"<div style='color:#4cff4c; font-size:1.6em; font-weight:bold'>{ep_fmt}</div>"
                    f"<div style='color:#888; font-size:0.75em'>{contracts} contrato(s) = {cost_total}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col_b:
                sl_fmt = fmt_money(stop_loss)
                try:
                    sl_pct = f"-{((float(entry_price) - float(stop_loss)) / float(entry_price) * 100):.0f}%"
                except Exception:
                    sl_pct = "-35%"
                st.markdown(
                    f"<div style='background:#3d0a0a; padding:12px; border-radius:8px; text-align:center'>"
                    f"<div style='color:#aaa; font-size:0.85em'>🛑 STOP LOSS</div>"
                    f"<div style='color:#ff5555; font-size:1.6em; font-weight:bold'>{sl_fmt}</div>"
                    f"<div style='color:#888; font-size:0.75em'>Pérdida máxima: {sl_pct}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col_c:
                tp2_fmt = fmt_money(tp2)
                try:
                    tp_pct = f"+{((float(tp2) - float(entry_price)) / float(entry_price) * 100):.0f}%"
                except Exception:
                    tp_pct = "+80%"
                st.markdown(
                    f"<div style='background:#0a2d3d; padding:12px; border-radius:8px; text-align:center'>"
                    f"<div style='color:#aaa; font-size:0.85em'>🎯 TAKE PROFIT</div>"
                    f"<div style='color:#55aaff; font-size:1.6em; font-weight:bold'>{tp2_fmt}</div>"
                    f"<div style='color:#888; font-size:0.75em'>Objetivo: {tp_pct}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.write("")

            if str(tp1) not in ["N/A", "", "nan", "None"]:
                try:
                    tp1_pct = f"+{((float(tp1) - float(entry_price)) / float(entry_price) * 100):.0f}%"
                except Exception:
                    tp1_pct = "+50%"
                st.info(f"💡 **Take Profit parcial:** {fmt_money(tp1)} ({tp1_pct}) — cierra la mitad de la posición aquí para asegurar ganancia")

            st.divider()

            # Acción subyacente
            if str(stock_sl) not in ["N/A", "", "nan", "None"]:
                st.markdown("#### 🏷️ Acción Subyacente — Niveles de Referencia")
                s1, s2, s3, s4 = st.columns(4)
                with s1:
                    st.metric("Precio actual", fmt_money(stock_price))
                with s2:
                    st.metric("Stop (acción)", fmt_money(stock_sl))
                with s3:
                    st.metric("TP1 (acción)", fmt_money(stock_tp1))
                with s4:
                    st.metric("TP2 (acción)", fmt_money(stock_tp2))
                st.divider()

            # Detalles del contrato
            st.markdown("#### 🔍 Detalles del Contrato")
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            with d1:
                st.metric("Strike", fmt_money(strike))
            with d2:
                st.metric("Vencimiento", str(expiration)[:10] if expiration != "N/A" else "N/A")
            with d3:
                st.metric("DTE", f"{dte} días" if dte != "N/A" else "N/A")
            with d4:
                st.metric("Delta", fmt_num(delta))
            with d5:
                st.metric("IV", fmt_pct(iv) if str(iv) not in ["N/A", "0", "0.0"] else "N/A")
            with d6:
                st.metric("Bid / Ask", f"{fmt_money(bid)} / {fmt_money(ask)}")

            st.divider()

            # Riesgo
            st.markdown("#### 💼 Gestión de Riesgo")
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                st.metric("Contratos", str(contracts))
            with r2:
                st.metric("🔴 Riesgo máximo", fmt_money(risk_amount))
            with r3:
                st.metric("🟢 Ganancia potencial", fmt_money(potential))
            with r4:
                rr_val = fmt_num(rr)
                st.metric("R/R", f"{rr_val}:1" if rr_val != "N/A" else "N/A")

            # Liquidez
            l1, l2, l3 = st.columns(3)
            with l1:
                try:
                    st.metric("Open Interest", f"{int(float(oi)):,}")
                except Exception:
                    st.metric("Open Interest", "N/A")
            with l2:
                try:
                    st.metric("Volumen opciones", f"{int(float(volume)):,}")
                except Exception:
                    st.metric("Volumen opciones", "N/A")
            with l3:
                try:
                    spread_val = float(ask) - float(bid)
                    mid_val = (float(bid) + float(ask)) / 2
                    spct = f"{spread_val / mid_val * 100:.1f}%"
                except Exception:
                    spct = "N/A"
                st.metric("Spread bid/ask", spct)

            # Razones
            if str(reasons) not in ["N/A", "", "[]", "nan"]:
                st.write("")
                if isinstance(reasons, list):
                    reasons_str = " • ".join(str(r) for r in reasons[:5])
                else:
                    reasons_str = str(reasons)[:300]
                st.success(f"**¿Por qué este trade?** {reasons_str}")

st.divider()

# ══════════════════════════════════════════
# TABLA COMPLETA
# ══════════════════════════════════════════

with st.expander("📋 Ver todos los símbolos analizados"):
    cols_show = ["symbol", "price", "trend", "signal", "risk", "option_type",
                 "score", "rating", "entry_price", "stop_loss", "take_profit_2",
                 "risk_amount", "potential_profit", "risk_reward", "dte", "expiration"]
    show_df = df[[c for c in cols_show if c in df.columns]].copy()
    st.dataframe(show_df, hide_index=True, use_container_width=True)

# ══════════════════════════════════════════
# INSTRUCCIONES SCHWAB
# ══════════════════════════════════════════

with st.expander("🔌 Conectar Schwab API (datos en tiempo real)"):
    st.markdown("""
### Pasos para conectar tu cuenta Schwab

1. Ve a **[developer.schwab.com](https://developer.schwab.com)** e inicia sesión con tu cuenta Schwab
2. Crea una nueva aplicación → **Individual Developer App**
3. En **Callback URL** escribe exactamente: `https://127.0.0.1`
4. Espera aprobación (1-2 días hábiles)
5. Copia tu **App Key** y **App Secret**
6. Abre el archivo **`.env`** en la carpeta del proyecto y agrega:

```
SCHWAB_APP_KEY=tu_app_key_aqui
SCHWAB_APP_SECRET=tu_app_secret_aqui
SCHWAB_CALLBACK_URL=https://127.0.0.1
```

7. Instala la librería: `pip install schwab-py`
8. La primera vez que ejecutes el análisis se abrirá el navegador para aprobar el acceso

> **Sin Schwab:** funciona con yfinance (datos retrasados 15-20 min, delta estimado)
> **Con Schwab:** datos en tiempo real + greeks reales (delta, IV, theta, vega)
    """)

with st.expander("🔍 Debug — columnas del CSV"):
    st.write(df.columns.tolist())

st.caption("AI TRADER • Solo lectura — no ejecuta trades • Schwab API + yfinance fallback")