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
TRIGGERS   = ['.', 'actualizar', 'precio', 'cotizacion', 'cotización', 'dolar', 'dólar', '/precio', '/actualizar']
# ─────────────────────────────────────────────────────────

def get_prices():
    r = requests.get(API_URL, timeout=10)
    r.raise_for_status()
    prices = {}
    for item in r.json():
        casa = item.get('casa', '')
        if casa == 'bolsa':   prices['mep']     = item
        elif casa == 'oficial': prices['oficial'] = item
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

def cotizacion_msg(prices, now_str):
    mep     = prices.get('mep', {})
    oficial = prices.get('oficial', {})
    return (
        f"💵 <b>Cotización Dólar</b> — {now_str} UTC\n\n"
        f"📌 MEP/Bolsa (COCOS, brokers)\n"
        f"   Compra: ${mep.get('compra'):,.2f}  |  Venta: ${mep.get('venta'):,.2f}\n\n"
        f"🏦 Oficial (BNA)\n"
        f"   Compra: ${oficial.get('compra'):,.2f}  |  Venta: ${oficial.get('venta'):,.2f}"
    )

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def check_incoming_messages(prices, state, now_str):
    """Revisa si el usuario mandó un mensaje trigger y responde con la cotización."""
    offset = state.get('tg_offset', 0)
    r = requests.get(
        f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
        params={'offset': offset, 'timeout': 0},
        timeout=10
    )
    if r.status_code != 200:
        print(f"Error getUpdates: {r.status_code}"); return

    updates = r.json().get('result', [])
    triggered = False

    for update in updates:
        update_id = update.get('update_id', 0)
        state['tg_offset'] = update_id + 1   # marcar como procesado

        msg   = update.get('message', {})
        text  = msg.get('text', '').strip().lower()
        # Solo responder al chat del dueño
        if str(msg.get('chat', {}).get('id', '')) != str(CHAT_ID):
            continue

        if any(text == t or text.startswith(t) for t in TRIGGERS):
            triggered = True

    if triggered:
        print("Mensaje trigger recibido, enviando cotización.")
        send_telegram(cotizacion_msg(prices, now_str))

def check_alerts(prices, state, now_iso, now_str):
    alerts = []
    for key, label in [('mep', 'MEP/Bolsa (COCOS, brokers)'), ('oficial', 'Oficial (BNA)')]:
        item   = prices.get(key, {})
        precio = item.get('venta')
        if precio is None: continue

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
                notify = True
                reason = f'Bajó otros ${last_price - precio:,.2f} (antes ${last_price:,.2f})'
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

def send_bihourly_update(prices, state, now_iso, now_str):
    last = state.get('last_bihourly_update')
    if last:
        mins = (datetime.fromisoformat(now_iso) - datetime.fromisoformat(last)).total_seconds() / 60
        if mins < 110:
            print(f"Update bihoral: faltan {int(120 - mins)} min."); return
    send_telegram(cotizacion_msg(prices, now_str))
    state['last_bihourly_update'] = now_iso

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

    check_incoming_messages(prices, state, now_str)  # responde si mandaste un trigger
    check_alerts(prices, state, now_iso, now_str)     # alertas de umbral
    send_bihourly_update(prices, state, now_iso, now_str)  # update cada 2hs

    save_state(state)

if __name__ == '__main__':
    main()
