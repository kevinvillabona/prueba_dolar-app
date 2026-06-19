import requests
import json
import os
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────
UMBRAL       = 1450          # pesos argentinos
BOT_TOKEN    = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID      = os.environ.get('TELEGRAM_CHAT_ID', '')
STATE_FILE   = 'state.json'
API_URL      = 'https://dolarapi.com/v1/dolares'
# ─────────────────────────────────────────────────────────

def get_prices():
    r = requests.get(API_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    prices = {}
    for item in data:
        casa = item.get('casa', '')
        if casa == 'bolsa':
            prices['mep'] = {'venta': item.get('venta'), 'compra': item.get('compra'), 'label': 'MEP/Bolsa (COCOS, brokers)'}
        elif casa == 'oficial':
            prices['oficial'] = {'venta': item.get('venta'), 'compra': item.get('compra'), 'label': 'Oficial (BNA)'}
    return prices

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  Sin credenciales de Telegram, salteando envío.")
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    r = requests.post(url, json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    if r.status_code == 200:
        print("✅ Mensaje enviado por Telegram")
    else:
        print(f"❌ Error Telegram: {r.status_code} {r.text}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def check_currency(key, info, state, now_iso, now_str):
    precio = info.get('venta')
    label  = info.get('label', key)
    compra = info.get('compra')

    if precio is None:
        return state

    s = state.get(key, {})
    last_price = s.get('last_notified_price')        # último precio con que notificamos
    last_time  = s.get('last_notification_time')     # ISO string del último envío

    notify = False
    reason = ''

    if precio < UMBRAL:
        if last_price is None:
            # Primera vez que baja del umbral
            notify = True
            reason = f'Cruzó el umbral de ${UMBRAL:,} por primera vez 🎯'
        elif precio < last_price:
            # Bajó más todavía
            diff = last_price - precio
            notify = True
            reason = f'Bajó otros ${diff:,.2f} más (antes ${last_price:,.2f})'
        elif last_time:
            # Misma zona: notificar si pasó más de 1 hora
            last_dt = datetime.fromisoformat(last_time)
            mins_elapsed = (datetime.fromisoformat(now_iso) - last_dt).total_seconds() / 60
            if mins_elapsed >= 60:
                notify = True
                reason = f'Actualización horaria (lleva {int(mins_elapsed)} min por debajo del umbral)'
    else:
        # Volvió arriba del umbral → resetear para detectar próxima bajada
        if last_price is not None:
            print(f"[{key.upper()}] Volvió arriba de ${UMBRAL:,} (${precio:,.2f}), reseteando estado.")
        state[key] = {}
        return state

    if notify:
        msg = (
            f"🔔 <b>Alerta Dólar Argentina</b>\n\n"
            f"📌 <b>{label}</b>\n"
            f"💵 Venta: <b>${precio:,.2f}</b>\n"
            f"💰 Compra: ${compra:,.2f}\n"
            f"📉 Por debajo del umbral de <b>${UMBRAL:,}</b>\n\n"
            f"ℹ️ {reason}\n"
            f"🕐 {now_str} (UTC)"
        )
        send_telegram(msg)
        state[key] = {
            'last_notified_price': precio,
            'last_notification_time': now_iso
        }
    else:
        print(f"[{key.upper()}] ${precio:,.2f} — sin notificación necesaria.")

    return state

def main():
    print(f"Iniciando monitor — umbral: ${UMBRAL:,}")

    try:
        prices = get_prices()
    except Exception as e:
        print(f"❌ Error obteniendo precios: {e}")
        return

    print(f"Precios: { {k: v['venta'] for k, v in prices.items()} }")

    state = load_state()
    now   = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_str = now.strftime('%d/%m/%Y %H:%M')

    for key, info in prices.items():
        state = check_currency(key, info, state, now_iso, now_str)

    save_state(state)
    print("Estado guardado.")

if __name__ == '__main__':
    main()
