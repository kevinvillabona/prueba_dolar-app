import requests
import json
import os
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────
UMBRAL     = 1450
BOT_TOKEN  = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID    = os.environ.get('TELEGRAM_CHAT_ID', '')
STATE_FILE = 'state.json'
API_URL    = 'https://dolarapi.com/v1/dolares'
# ─────────────────────────────────────────────────────────

def get_prices():
    r = requests.get(API_URL, timeout=10)
    r.raise_for_status()
    prices = {}
    for item in r.json():
        casa = item.get('casa', '')
        if casa == 'bolsa':
            prices['mep'] = item
        elif casa == 'oficial':
            prices['oficial'] = item
    return prices

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Sin credenciales Telegram"); return
    r = requests.post(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'},
        timeout=10
    )
    print("✅ Enviado" if r.status_code == 200 else f"❌ {r.status_code}: {r.text}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def check_alerts(prices, state, now_iso, now_str):
    """Lógica de alerta: notifica si baja del umbral, nueva baja, o cada hora si sigue abajo."""
    alerts = []

    for key, label in [('mep', 'MEP/Bolsa (COCOS, brokers)'), ('oficial', 'Oficial (BNA)')]:
        item  = prices.get(key, {})
        precio = item.get('venta')
        if precio is None:
            continue

        s          = state.get(key, {})
        last_price = s.get('last_notified_price')
        last_time  = s.get('last_notification_time')

        if precio < UMBRAL:
            notify = False
            reason = ''

            if last_price is None:
                notify = True
                reason = f'Cruzó el umbral de ${UMBRAL:,} 🎯'
            elif precio < last_price:
                diff   = last_price - precio
                notify = True
                reason = f'Bajó otros ${diff:,.2f} (antes ${last_price:,.2f})'
            elif last_time:
                mins = (datetime.fromisoformat(now_iso) - datetime.fromisoformat(last_time)).total_seconds() / 60
                if mins >= 60:
                    notify = True
                    reason = f'Actualización horaria ({int(mins)} min por debajo del umbral)'

            if notify:
                alerts.append(
                    f"🔔 <b>Alerta — {label}</b>\n"
                    f"💵 Venta: <b>${precio:,.2f}</b>  |  Compra: ${item.get('compra'):,.2f}\n"
                    f"📉 Por debajo de ${UMBRAL:,}\n"
                    f"ℹ️ {reason}"
                )
                state[key] = {'last_notified_price': precio, 'last_notification_time': now_iso}
        else:
            if last_price is not None:
                print(f"[{key.upper()}] Volvió arriba de ${UMBRAL:,}, reseteando.")
            state[key] = {}

    if alerts:
        send_telegram(f"🕐 {now_str} UTC\n\n" + "\n\n".join(alerts))

def send_biohourly_update(prices, state, now_iso, now_str):
    """Cada 2 horas manda la cotización actual sin importar el precio."""
    last_update = state.get('last_biohourly_update')
    if last_update:
        mins = (datetime.fromisoformat(now_iso) - datetime.fromisoformat(last_update)).total_seconds() / 60
        if mins < 110:   # margen de 10 min por si el cron se corre un poco
            print(f"Update bihoral: faltan {int(120 - mins)} min, salteando.")
            return

    mep     = prices.get('mep', {})
    oficial = prices.get('oficial', {})

    msg = (
        f"💵 <b>Cotización Dólar</b> — {now_str} UTC\n\n"
        f"📌 MEP/Bolsa (COCOS, brokers)\n"
        f"   Compra: ${mep.get('compra'):,.2f}  |  Venta: ${mep.get('venta'):,.2f}\n\n"
        f"🏦 Oficial (BNA)\n"
        f"   Compra: ${oficial.get('compra'):,.2f}  |  Venta: ${oficial.get('venta'):,.2f}"
    )
    send_telegram(msg)
    state['last_biohourly_update'] = now_iso

def main():
    try:
        prices = get_prices()
    except Exception as e:
        print(f"Error obteniendo precios: {e}"); return

    state   = load_state()
    now     = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_str = now.strftime('%d/%m/%Y %H:%M')

    print(f"MEP: {prices.get('mep',{}).get('venta')}  |  Oficial: {prices.get('oficial',{}).get('venta')}")

    check_alerts(prices, state, now_iso, now_str)
    send_biohourly_update(prices, state, now_iso, now_str)

    save_state(state)

if __name__ == '__main__':
    main()
