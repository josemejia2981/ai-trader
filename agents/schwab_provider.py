# agents/schwab_provider.py
# Proveedor de datos en tiempo real via Charles Schwab API
# Modo SOLO LECTURA — no ejecuta ningún trade
#
# SETUP (primera vez):
#   1. Ve a https://developer.schwab.com
#   2. Crea una cuenta y registra una nueva app
#   3. En "Callback URL" pon exactamente: https://127.0.0.1
#   4. Copia App Key y App Secret
#   5. Ponlos en el archivo .env:
#        SCHWAB_APP_KEY=tu_app_key
#        SCHWAB_APP_SECRET=tu_app_secret
#   6. La primera vez que corras el bot, se abrirá un navegador para
#      que apruebes el acceso. Después se guarda token automáticamente.

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SCHWAB_APP_KEY    = os.environ.get("SCHWAB_APP_KEY", "")
SCHWAB_APP_SECRET = os.environ.get("SCHWAB_APP_SECRET", "")
SCHWAB_CALLBACK   = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
SCHWAB_TOKEN_PATH = os.environ.get("SCHWAB_TOKEN_PATH", "schwab_token.json")

_client = None   # singleton


def _get_client():
    """Retorna el cliente Schwab (inicializa si es necesario)."""
    global _client

    if not SCHWAB_APP_KEY or not SCHWAB_APP_SECRET:
        return None

    if _client is not None:
        return _client

    try:
        import schwab
        token_path = Path(SCHWAB_TOKEN_PATH)

        if token_path.exists():
            # Token guardado — reúsalo (refresca automáticamente si expiró)
            _client = schwab.auth.client_from_token_file(
                token_path=str(token_path),
                api_key=SCHWAB_APP_KEY,
                app_secret=SCHWAB_APP_SECRET,
            )
        else:
            # Primera vez — abre el navegador para login OAuth
            print("\n[SCHWAB] Primera autenticación — se abrirá el navegador.")
            print("[SCHWAB] Inicia sesión en Schwab y aprueba el acceso.")
            _client = schwab.auth.easy_client(
                api_key=SCHWAB_APP_KEY,
                app_secret=SCHWAB_APP_SECRET,
                callback_url=SCHWAB_CALLBACK,
                token_path=str(token_path),
            )
            print("[SCHWAB] Token guardado en:", str(token_path))

        return _client

    except ImportError:
        print("[SCHWAB] schwab-py no instalado. Corre: pip install schwab-py")
        return None
    except Exception as e:
        print("[SCHWAB] Error de autenticación: " + str(e))
        return None


def is_available():
    """Devuelve True si Schwab está configurado y disponible."""
    return bool(SCHWAB_APP_KEY and SCHWAB_APP_SECRET)


def get_realtime_quote(symbol):
    """
    Obtiene cotización en tiempo real de Schwab.
    Retorna dict con price, volume, bid, ask, change_pct
    o None si Schwab no está disponible.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        r = client.get_quote(symbol)
        if not r.ok:
            return None

        data = r.json()
        q = data.get(symbol, {}).get("quote", {})

        price = float(q.get("lastPrice") or q.get("mark") or 0)
        if price <= 0:
            return None

        return {
            "price":      price,
            "bid":        float(q.get("bidPrice", 0)),
            "ask":        float(q.get("askPrice", 0)),
            "volume":     float(q.get("totalVolume", 0)),
            "change_pct": float(q.get("netPercentChangeInDouble", 0)),
            "open":       float(q.get("openPrice", 0)),
            "high":       float(q.get("highPrice", 0)),
            "low":        float(q.get("lowPrice", 0)),
            "close_prev": float(q.get("closePrice", 0)),
            "source":     "schwab_realtime",
        }

    except Exception as e:
        print("[SCHWAB] Error quote " + symbol + ": " + str(e))
        return None


def get_options_chain(symbol, option_type="CALL", min_dte=25, max_dte=60):
    """
    Obtiene cadena de opciones con greeks REALES de Schwab.
    option_type: "CALL" o "PUT"
    Retorna lista de dicts con todos los campos del contrato,
    o [] si Schwab no está disponible.

    Cada contrato incluye:
      contractSymbol, strike, expiration, dte,
      bid, ask, lastPrice, volume, openInterest,
      delta, gamma, theta, vega, impliedVolatility,
      inTheMoney, spread, spread_pct, mid_price
    """
    client = _get_client()
    if client is None:
        return []

    try:
        from schwab.client import Client

        from_date = date.today() + timedelta(days=min_dte)
        to_date   = date.today() + timedelta(days=max_dte)

        contract_type = (
            Client.Options.ContractType.CALL
            if option_type.upper() == "CALL"
            else Client.Options.ContractType.PUT
        )

        r = client.get_option_chain(
            symbol,
            contract_type=contract_type,
            include_underlying_quote=True,
            from_date=from_date,
            to_date=to_date,
        )

        if not r.ok:
            print("[SCHWAB] Error opciones " + symbol + ": HTTP " + str(r.status_code))
            return []

        data    = r.json()
        exp_map = data.get("callExpDateMap" if option_type.upper() == "CALL" else "putExpDateMap", {})

        contracts = []

        for exp_key, strikes_dict in exp_map.items():
            # exp_key formato: "2025-07-18:35" (fecha:dte)
            parts = exp_key.split(":")
            exp_str = parts[0]
            dte_val = int(parts[1]) if len(parts) > 1 else 0

            if dte_val < min_dte or dte_val > max_dte:
                continue

            for strike_str, contract_list in strikes_dict.items():
                for c in contract_list:
                    bid  = float(c.get("bid", 0) or 0)
                    ask  = float(c.get("ask", 0) or 0)
                    last = float(c.get("last", 0) or 0)
                    mid  = round((bid + ask) / 2, 2) if bid > 0 and ask > 0 else last
                    spread     = round(ask - bid, 2) if ask > bid else 0
                    spread_pct = round(spread / mid * 100, 2) if mid > 0 else 100

                    delta = float(c.get("delta", 0) or 0)
                    # Schwab da delta negativo para PUTs — normalizamos al valor absoluto
                    # pero conservamos el signo para saber si es PUT
                    gamma = float(c.get("gamma", 0) or 0)
                    theta = float(c.get("theta", 0) or 0)
                    vega  = float(c.get("vega", 0) or 0)
                    iv    = float(c.get("volatility", 0) or 0) / 100  # viene como porcentaje

                    contracts.append({
                        "contractSymbol":    c.get("symbol", ""),
                        "strike":            float(strike_str),
                        "expiration":        exp_str,
                        "dte":               dte_val,
                        "bid":               bid,
                        "ask":               ask,
                        "lastPrice":         last,
                        "mid_price":         mid,
                        "spread":            spread,
                        "spread_pct":        spread_pct,
                        "volume":            int(c.get("totalVolume", 0) or 0),
                        "openInterest":      int(c.get("openInterest", 0) or 0),
                        "delta":             delta,
                        "delta_estimate":    delta,   # mismo campo — es real
                        "gamma":             gamma,
                        "theta":             theta,
                        "vega":              vega,
                        "impliedVolatility": round(iv * 100, 2),  # en % para consistencia
                        "inTheMoney":        bool(c.get("inTheMoney", False)),
                        "option_type":       option_type.upper(),
                        "entry_price":       mid if mid > 0 else last,
                        "data_source":       "schwab_realtime",
                    })

        print("[SCHWAB] " + symbol + " " + option_type + ": " + str(len(contracts)) + " contratos obtenidos")
        return contracts

    except Exception as e:
        print("[SCHWAB] Error cadena de opciones " + symbol + ": " + str(e))
        return []
