import requests, os
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')

r = requests.get('https://dolarapi.com/v1/dolares', timeout=10)
data = r.json()

mep = oficial = None
for item in data:
    if item['casa'] == 'bolsa':   mep     = item
    if item['casa'] == 'oficial': oficial = item

now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')

msg = (
    f"💵 <b>Cotización Dólar</b> — {now} UTC\n\n"
    f"📌 MEP/Bolsa (COCOS, brokers)\n"
    f"   Compra: ${mep['compra']:,.2f}  |  Venta: ${mep['venta']:,.2f}\n\n"
    f"🏦 Oficial (BNA)\n"
    f"   Compra: ${oficial['compra']:,.2f}  |  Venta: ${oficial['venta']:,.2f}"
)

r = requests.post(
    f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
    json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'},
    timeout=10
)
print("✅ Enviado!" if r.status_code == 200 else f"❌ {r.status_code}: {r.text}")
