# ============================================================
# AI TRADER — Configuración Central (OPTIMIZADA)
# Swing Trading de Opciones — Versión Profesional
# ============================================================
# REGLA DE ORO: Solo trades con alta probabilidad, buena
# liquidez, y riesgo controlado. Calidad sobre cantidad.
# ============================================================

# --- CUENTA ---
ACCOUNT_SIZE       = 10_000   # Tamaño de cuenta en USD (ajusta si cambia)
RISK_PERCENT       = 0.015    # 1.5% por trade — más conservador protege capital
MAX_CONTRACTS      = 5        # Máximo 5 contratos — evita concentración
RISK_TOLERANCE_PERCENT = 0.10 # 10% tolerancia extra sobre el límite normal

# --- PORTFOLIO ---
MAX_POSITIONS      = 3        # Máximo 3 posiciones abiertas — enfoque, no dispersión
MAX_TOTAL_RISK     = 900      # Riesgo total del portfolio en USD (9% de cuenta)

# --- OPCIONES: FILTROS DE CONTRATO ---
# DTE óptimo: 30-60 días. Más tiempo = menos theta decay inmediato.
# Menos tiempo = demasiado riesgo de decay acelerado.
MIN_DTE            = 25       # Mínimo 25 días (antes 21)
MAX_DTE            = 60       # Máximo 60 días (antes 90) — sweet spot swing trading

# Delta 0.50+ = opciones cerca o dentro del dinero.
# Se mueven más con el subyacente = mayor rentabilidad por movimiento.
MIN_DELTA          = 0.50     # Subido de 0.45 → más ITM/ATM, más confiable

# Spread ajustado = mejor precio de entrada y salida.
MAX_SPREAD_PCT     = 8        # Bajado de 12% → spreads más ajustados

# Liquidez mínima: asegura poder entrar y salir sin deslizamiento.
MIN_VOLUME         = 100      # Subido de 50 → más liquidez real
MIN_OPEN_INTEREST  = 500      # Subido de 200 → más contratos activos

# Control de prima máxima y riesgo absoluto por trade.
MAX_ENTRY_PRICE    = 20.00    # Bajado de 30 → primas más baratas, más contratos
MAX_RISK_PER_TRADE = 600      # Bajado de 800 → riesgo máximo más conservador

# --- OPCIONES: STRIKES ---
# Solo opciones cerca del dinero (no demasiado OTM).
# OTM extremas son baratas pero raramente llegan a ser rentables.
MAX_OTM_PCT           = 0.05  # Bajado de 10% → máximo 5% fuera del dinero
MAX_STRIKE_DISTANCE_PCT = 0.10 # Bajado de 15% → strikes más cercanos al precio

# --- GESTIÓN DE RIESGO (sobre precio de la prima) ---
STOP_LOSS_PCT      = 0.35    # Stop loss al 35% — cortar pérdidas antes
TAKE_PROFIT_1_PCT  = 0.50    # TP1 al 50% — asegurar ganancia parcial
TAKE_PROFIT_2_PCT  = 0.80    # TP2 al 80% — no esperar el 100%, tomar ganancias
TRAILING_STOP_PCT  = 0.20    # Trailing 20% desde el máximo — proteger ganancias

# --- SEÑALES TÉCNICAS RSI ---
# CALL: RSI entre 45-65 = momentum alcista sin estar sobrecomprado
# PUT: RSI entre 35-55 = momentum bajista sin estar sobrevendido extremo
RSI_OVERSOLD       = 30
RSI_OVERBOUGHT     = 70
RSI_CALL_MIN       = 45      # Subido de 40 → requiere más momentum alcista
RSI_CALL_MAX       = 65      # Bajado de 70 → evita zonas sobrecompradas
RSI_PUT_MIN        = 35      # Subido de 30 → más selectivo en bajistas
RSI_PUT_MAX        = 55      # Bajado de 60 → evita poner en rebote

# --- SCORING (qué tan bueno debe ser el setup) ---
# Subir el mínimo filtra trades mediocres y solo deja los de alta calidad.
MIN_SCORE_FOR_TRADE  = 70    # Subido de 65 → solo trades buenos
MIN_SCORE_PORTFOLIO  = 75    # Subido de 70 → portfolio solo con los mejores
MIN_RISK_REWARD      = 2.0   # Subido de 1.8 → mínimo 2:1 para entrar

# --- DATOS DE MERCADO ---
DATA_PERIOD   = "6mo"        # 6 meses de histórico para indicadores sólidos
DATA_INTERVAL = "1d"         # Daily — swing trading, no intraday

# --- REPORTES ---
REPORTS_DIR = "reports"

# --- WATCHLIST POR DEFECTO ---
# Símbolos con alta liquidez de opciones y movimiento suficiente para swing.
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META",
    "AMZN", "GOOGL", "AMD", "NFLX", "PLTR",
    "AVGO", "CRM", "UBER", "SNOW", "SHOP",
    "COIN", "QQQ", "SPY"
]
