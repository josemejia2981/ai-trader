# ============================================================
# AI TRADER — Configuración Central
# ============================================================
# Modifica aquí para cambiar el comportamiento global del bot.
# No hardcodees constantes en los agentes individuales.
# ============================================================

# --- CUENTA ---
ACCOUNT_SIZE = 10_000        # Tamaño de la cuenta en USD
RISK_PERCENT = 0.02          # Riesgo por trade (2% de la cuenta)
MAX_CONTRACTS = 10           # Máximo de contratos por trade
RISK_TOLERANCE_PERCENT = 0.15  # Tolerancia adicional al riesgo (15%)

# --- PORTFOLIO ---
MAX_POSITIONS = 4            # Máximo de posiciones simultáneas
MAX_TOTAL_RISK = 1_200       # Riesgo total máximo del portfolio en USD

# --- OPCIONES: FILTROS DE CONTRATO ---
MIN_DTE = 21                 # Días mínimos a expiración (evitar decay extremo)
MAX_DTE = 90                 # Días máximos a expiración
MIN_DELTA = 0.45             # Delta mínimo (0.45 = balance leverage/costo ideal)
MAX_SPREAD_PCT = 12          # Spread bid/ask máximo como % del mid price
MIN_VOLUME = 50              # Volumen mínimo del contrato
MIN_OPEN_INTEREST = 200      # Open interest mínimo
MAX_ENTRY_PRICE = 30.00      # Precio máximo de la prima por contrato
MAX_RISK_PER_TRADE = 800     # Riesgo máximo por trade en USD

# --- OPCIONES: STRIKES ---
MAX_OTM_PCT = 0.10           # Máximo % fuera del dinero para CALLs y PUTs
MAX_STRIKE_DISTANCE_PCT = 0.15  # Máxima distancia strike/precio

# --- GESTIÓN DE RIESGO ---
STOP_LOSS_PCT = 0.40         # Stop loss como % de la prima pagada (perder 40%)
TAKE_PROFIT_1_PCT = 0.50     # Take profit 1 como % de ganancia (50%)
TAKE_PROFIT_2_PCT = 1.00     # Take profit 2 como % de ganancia (100%)
TRAILING_STOP_PCT = 0.25     # Trailing stop (25% desde el máximo)

# --- SEÑALES TÉCNICAS ---
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_CALL_MIN = 40            # RSI mínimo para señal CALL
RSI_CALL_MAX = 70            # RSI máximo para señal CALL
RSI_PUT_MIN = 30             # RSI mínimo para señal PUT
RSI_PUT_MAX = 60             # RSI máximo para señal PUT

# --- SCORING ---
MIN_SCORE_FOR_TRADE = 65     # Score mínimo para considerar un trade
MIN_SCORE_PORTFOLIO = 70     # Score mínimo para entrar al portfolio
MIN_RISK_REWARD = 1.8        # Risk/Reward mínimo

# --- DATOS DE MERCADO ---
DATA_PERIOD = "6mo"          # Período de datos históricos
DATA_INTERVAL = "1d"         # Intervalo (daily para swing trading)

# --- REPORTES ---
REPORTS_DIR = "reports"

# --- WATCHLIST POR DEFECTO ---
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META",
    "AMZN", "GOOGL", "AMD", "NFLX", "PLTR",
    "AVGO", "CRM", "UBER", "SNOW", "SHOP",
    "COIN", "QQQ", "SPY"
]
