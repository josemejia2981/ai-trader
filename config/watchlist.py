"""
watchlist.py  –  Lista dinámica de activos
==========================================
Reemplaza la watchlist estática por categorías configurables.
El scanner ahora elige qué activos analizar según el mercado real.
"""

# ─────────────────────────────────────────────
# CATEGORÍAS POR SECTOR / ESTRATEGIA
# ─────────────────────────────────────────────

MEGA_CAPS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META",
    "AMZN", "TSLA", "BRK-B", "LLY", "V", "JPM", "UNH",
    "XOM", "WMT", "MA", "JNJ", "PG", "AVGO", "HD",
]

HIGH_IV_MOMENTUM = [
    "TSLA", "NVDA", "AMD", "PLTR", "MARA", "RIOT",
    "COIN", "GME", "HOOD", "SOFI", "RIVN", "LCID",
    "SNOW", "NET", "CRWD", "DDOG", "MDB", "ABNB",
    "RBLX", "ROKU", "SQ", "PYPL", "UBER", "DASH",
]

TECH = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA",
    "AMD", "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT",
    "LRCX", "KLAC", "CRM", "ORCL", "ADBE", "SAP", "NOW",
    "SNOW", "DDOG", "NET", "CRWD", "ZS", "PANW", "OKTA",
    "MDB", "SHOP", "MELI", "SE", "BIDU", "JD", "BABA",
]

FINANCIALS = [
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK",
    "AXP", "V", "MA", "COF", "USB", "PNC", "TFC",
    "SCHW", "CME", "ICE", "SPGI", "MCO", "HOOD", "COIN",
]

HEALTHCARE = [
    "UNH", "JNJ", "PFE", "ABBV", "LLY", "MRK", "TMO",
    "ABT", "DHR", "AMGN", "GILD", "BIIB", "REGN", "VRTX",
    "ISRG", "MDT", "BSX", "EW", "ZTS", "MRNA", "BNTX",
]

ENERGY = [
    "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "VLO",
    "MPC", "OXY", "HAL", "DVN", "FANG", "APA", "PXD",
]

CONSUMER = [
    "HD", "WMT", "COST", "TGT", "LOW", "MCD", "SBUX",
    "NKE", "PG", "KO", "PEP", "PM", "MO", "CL",
    "AMZN", "EBAY", "ETSY", "DKNG", "PENN",
]

ETFS_LIQUIDOS = [
    "SPY", "QQQ", "IWM", "DIA",
    "XLF", "XLK", "XLE", "XLV", "XLU", "XLB", "XLC",
    "GLD", "SLV", "GDX", "GDXJ",
    "ARKK", "SOXX", "XBI", "IBB",
    "EEM", "EFA", "FXI",
    "TLT", "HYG", "LQD",
    "VXX", "UVXY",
]

# ─────────────────────────────────────────────
# WATCHLISTS PRECONFIGURADAS
# ─────────────────────────────────────────────

WATCHLISTS = {
    "Mercado Amplio": list(dict.fromkeys(
        MEGA_CAPS + TECH[:15] + FINANCIALS[:10] + ETFS_LIQUIDOS[:15]
    )),
    "Alto Momentum (IV alta)": list(dict.fromkeys(
        HIGH_IV_MOMENTUM + TECH[:10] + ETFS_LIQUIDOS[:5]
    )),
    "Tech": list(dict.fromkeys(TECH + ETFS_LIQUIDOS[:5])),
    "Financials": list(dict.fromkeys(FINANCIALS + ["XLF", "KBE"])),
    "Healthcare": list(dict.fromkeys(HEALTHCARE + ["XLV", "XBI", "IBB"])),
    "Energy": list(dict.fromkeys(ENERGY + ["XLE", "OIH"])),
    "Consumer": list(dict.fromkeys(CONSUMER + ["XLY", "XLP"])),
    "Solo ETFs": ETFS_LIQUIDOS,
    "Mega Caps": MEGA_CAPS,
    "Custom": [],  # el usuario llena esta lista desde la UI
}

# Watchlist que usa el scanner por defecto
DEFAULT_WATCHLIST = "Mercado Amplio"


def get_watchlist(name: str = DEFAULT_WATCHLIST) -> list:
    """Retorna los símbolos de una watchlist por nombre."""
    return WATCHLISTS.get(name, WATCHLISTS[DEFAULT_WATCHLIST])


def get_all_symbols() -> list:
    """Retorna todos los símbolos únicos de todas las watchlists."""
    all_syms = []
    for syms in WATCHLISTS.values():
        all_syms.extend(syms)
    return list(dict.fromkeys(all_syms))


def get_watchlist_names() -> list:
    """Retorna los nombres de todas las watchlists disponibles."""
    return list(WATCHLISTS.keys())
