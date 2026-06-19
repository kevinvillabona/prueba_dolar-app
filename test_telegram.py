import requests, os

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')

# Obtener precios reales para mostrar en el test
r = requests.get('https://dolarapi.com/v1/dolares', timeout=10)
data = r.json()
mep = oficial = None
for item in data:
    if item['casa'] == 'bolsa':   mep     = item['venta']
    if item['casa'] == 'oficial': oficial = item['venta']

msg = (
    "✅ <b>Test exitoso — Monitor Dólar activo</b>\n\n"
    "Este bot te va a notificar cuando el dólar baje de <b>$1.450</b>\n\n"
    f"💵 Cotización actual:\n"
    f"  • MEP/Bolsa (COCOS): <b>${mep:,.2f}</b>\n"
    f"  • Oficial (BNA): <b>${oficial:,.2f}</b>\n\n"
    "⏱ Revisión automática cada 10 minutos."
)

r = requests.post(
    f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
    json={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'},
    timeout=10
)
print("✅ Enviado!" if r.status_code == 200 else f"❌ {r.status_code}: {r.text}")
