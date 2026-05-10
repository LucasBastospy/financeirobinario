from telethon import TelegramClient, events
import asyncio
from iqoptionapi.stable_api import IQ_Option
from iqoptionapi.constants import ACTIVES
import time
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Credenciais da IQ Option
IQ_OPTION_EMAIL = "Bebastos1234@gmail.com"
IQ_OPTION_PASSWORD = "8483537Be!"
IQ_OPTION_DEMO = True

api_id = 32501572
api_hash = '2cf8c6998c935bc8afc515017f8fd774'
phone = '+5511932287126'

client = TelegramClient('session_name', api_id, api_hash)
iq_api = None

def connect_iqoption():
    I_want_money = IQ_Option(IQ_OPTION_EMAIL, IQ_OPTION_PASSWORD)
    I_want_money.connect()
    if I_want_money.check_connect():
        mode = "DEMO" if IQ_OPTION_DEMO else "REAL"
        print(f"Conectado à IQ Option ({mode}) com sucesso!")
        return I_want_money
    else:
        print("Falha na conexão com a IQ Option.")
        return None

def parse_signal(signal_text):
    """
    Parseia sinais no formato:
    📊 Pair: USD-RUB (OTC)
    ⏰ Expiration: 5 Minutos
    🟢 COMPRA ou 🔴 VENDA
    """
    
    # Mapeamento completo baseado nos seus sinais
    signal_mapping = {
        # Criptos (novos sinais)
        "XRP (OTC)": "XRPUSD-OTC",
        "Bitcoin (OTC)": "BTCUSD-OTC",
        "Ethereum (OTC)": "ETHUSD-OTC",
        "TRON (OTC)": "TRON-OTC",
        "Solana (OTC)": "SOLUSD-OTC",
        "Dogecoin (OTC)": "DOGECOIN-OTC",
        "Cardano (OTC)": "CARDANO-OTC",
        
        # Forex OTC
        
        "GBP-AUD (OTC)": "GBPAUD-OTC",
        "EUR-JPY (OTC)": "EURJPY-OTC",
        "AUD-NZD (OTC)": "AUDNZD-OTC",
        "AUD-USD (OTC)": "AUDUSD-OTC",
        "AUD-CAD (OTC)": "AUDCAD-OTC",
        "GBP-NZD (OTC)": "GBPNZD-OTC",
        "USD-CAD (OTC)": "USDCAD-OTC",
        "USD-BRL (OTC)": "USDBRL-OTC",
        "EUR-USD (OTC)": "EURUSD-OTC",
        "NZD-JPY (OTC)": "NZDJPY-OTC",
        "NZD-USD (OTC)": "NZDUSD-OTC",
        "EUR-GBP (OTC)": "EURGBP-OTC",
        "GBP-JPY (OTC)": "GBPJPY-OTC",
        "EUR-AUD (OTC)": "EURAUD-OTC",
        "AUD-JPY (OTC)": "AUDJPY-OTC",
        "USD-CNY (OTC)": "USDCNH-OTC",
        
        # Ações OTC
        "Nike (OTC)": "NIKE",
        
        
    }
    
    # 1. Extrair o par
    par_match = re.search(r'📊 Pair:\s*(.+)', signal_text)
    if not par_match:
        par_match = re.search(r'Pair:\s*(.+)', signal_text)
        if not par_match:
            print("❌ Não foi possível extrair o Pair do sinal")
            return None
    
    telegram_pair = par_match.group(1).strip()
    print(f"📊 Par detectado: '{telegram_pair}'")
    
    # 2. Converter para o código da IQ Option
    iq_pair = signal_mapping.get(telegram_pair)
    
    if not iq_pair:
        # Tenta busca automática
        search_term = telegram_pair.replace(" (OTC)", "").replace("-", "").upper()
        
        for key in ACTIVES.keys():
            if search_term in key.upper() or key.upper() in search_term:
                # Verifica se é forex (prefere sem -OTC)
                if key in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY"]:
                    iq_pair = key
                    break
                elif "OTC" not in key and len(key) < 10:  # Prefere os principais
                    iq_pair = key
                    break
        
        if not iq_pair:
            print(f"❌ Mapeamento não encontrado para: '{telegram_pair}'")
            print(f"   Opções disponíveis similares:")
            for key in list(ACTIVES.keys())[:20]:
                if search_term[:4] in key:
                    print(f"     - {key}")
            return None
    
    # 3. Verificar se existe no ACTIVES
    if iq_pair not in ACTIVES:
        print(f"❌ '{iq_pair}' não encontrado no constants.py")
        print(f"   ID disponível: {ACTIVES.get(iq_pair, 'N/A')}")
        return None
    
    asset_id = ACTIVES[iq_pair]
    print(f"✅ Mapeado: {telegram_pair} -> {iq_pair} (ID: {asset_id})")
    
    # 4. Extrair ação (COMPRA/VENDA)
    action = None
    if '🟢 COMPRA' in signal_text or 'CALL' in signal_text.upper():
        action = 'call'
    elif '🔴 VENDA' in signal_text or 'PUT' in signal_text.upper():
        action = 'put'
    
    if not action:
        print("❌ Ação não reconhecida (COMPRA/VENDA)")
        return None
    
    # 5. Extrair tempo de expiração
    exp_match = re.search(r'⏰ Expiration:\s*(\d+)\s*Minutos?', signal_text)
    if not exp_match:
        exp_match = re.search(r'Expiration:\s*(\d+)\s*Min', signal_text)
        if not exp_match:
            print("❌ Tempo de expiração não encontrado")
            return None
    
    time_frame = int(exp_match.group(1))
    
    print(f"🎯 Sinal: {action.upper()} {iq_pair} por {time_frame} minutos")
    
    return {
        'pair': iq_pair,
        'action': action,
        'time_frame': time_frame,
        'asset_id': asset_id
    }

def execute_trade(iq_api, pair, action, amount, time_frame):
    if not iq_api or not iq_api.check_connect():
        print("Tentando reconectar...")
        iq_api = connect_iqoption()
        if not iq_api:
            return None
    
    if pair not in ACTIVES:
        print(f"ERRO: Par '{pair}' não encontrado no ACTIVES")
        return None
    
    print(f"Executando: {pair} {action} {time_frame}m ${amount}")
    
    try:
        check, order_id = iq_api.buy(amount, pair, action, time_frame)
        if check:
            print(f"✅ Ordem executada! ID: {order_id}")
            return order_id
        else:
            print(f"❌ Falha: {order_id}")
            return None
    except Exception as e:
        print(f"Erro: {e}")
        return None

def process_signal(signal_text):
    print(f"\n📊 Processando sinal...")
    global iq_api
    
    signal_data = parse_signal(signal_text)
    if not signal_data:
        print("❌ Sinal inválido")
        return
    
    # CÓDIGO CORRIGIDO AQUI
    pair = signal_data['pair']
    asset_id = ACTIVES.get(pair, 'N/A')
    
    print(f"Par: {pair} (ID: {asset_id})")
    print(f"Ação: {signal_data['action']}")
    print(f"Expiração: {signal_data['time_frame']} min")
    
    amount = 5 if 'USD-L' in pair or 'BTC' in pair else 10
    execute_trade(iq_api, pair, signal_data['action'], amount, signal_data['time_frame'])

async def my_event_handler(event):
    chat = await event.get_chat()
    chat_name = getattr(chat, 'title', None) or str(event.chat_id)
    print(f"\n📨 Sinal recebido de {chat_name}")
    process_signal(event.raw_text)

async def main():
    global iq_api
    
    print(f"📚 Carregados {len(ACTIVES)} ativos do constants.py")
    
    iq_api = connect_iqoption()
    if not iq_api:
        return
    
    await client.start(phone=phone)
    print("✅ Bot iniciado. Aguardando sinais...")
    
    chat_ids = [3272112505, 2936763017]
    client.add_event_handler(my_event_handler, events.NewMessage(chats=chat_ids))
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())