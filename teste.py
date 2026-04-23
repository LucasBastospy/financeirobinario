import pandas as pd
import numpy as np
from curl_cffi import requests
import yfinance as yf
import time
from datetime import datetime, timedelta
from pytz import timezone
import warnings
warnings.filterwarnings('ignore')

# ==================== CONFIGURAÇÕES ====================
TIMEFRAME = "15m"  # Pode mudar para: 1m, 5m, 30m, 1h
PERIODO_ANALISE = "5d"  # Aumentado para melhor análise de tendência
MIN_SINAIS_CONCORDANTES = 3

# Mapeamento de timeframes para minutos
TIMEFRAME_MINUTOS = {
    "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "1d": 1440
}

# Sessão que imita navegador
session = requests.Session(impersonate="chrome120")

PARES = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "NZDUSD=X",
    "USDCAD=X",
    "USDCHF=X",
    "EURJPY=X",
    "GBPJPY=X",
    "AUDJPY=X",
]

# ==================== FUNÇÕES DE ANÁLISE ====================

def analise_engolfo(df, idx):
    if idx < 1:
        return "NEUTRO", "Dados insuficientes"
    
    vela_atual = df.iloc[idx]
    vela_anterior = df.iloc[idx-1]
    
    if (vela_atual['Close'] > vela_atual['Open'] and 
        vela_anterior['Close'] < vela_anterior['Open'] and
        vela_atual['Open'] <= vela_anterior['Close'] and
        vela_atual['Close'] >= vela_anterior['Open']):
        return "CALL", "Engolfo de Alta"
    
    if (vela_atual['Close'] < vela_atual['Open'] and 
        vela_anterior['Close'] > vela_anterior['Open'] and
        vela_atual['Open'] >= vela_anterior['Close'] and
        vela_atual['Close'] <= vela_anterior['Open']):
        return "PUT", "Engolfo de Baixa"
    
    return "NEUTRO", "Sem padrão"

def analise_martelo_estrela(df, idx):
    vela = df.iloc[idx]
    corpo = abs(vela['Close'] - vela['Open'])
    range_total = vela['High'] - vela['Low']
    
    if range_total == 0:
        return "NEUTRO", "Range zero"
    
    sombra_inferior = min(vela['Open'], vela['Close']) - vela['Low']
    sombra_superior = vela['High'] - max(vela['Open'], vela['Close'])
    
    if sombra_inferior >= 2 * corpo and corpo > 0:
        return "CALL", "Martelo (reversão alta)"
    
    if sombra_superior >= 2 * corpo and corpo > 0:
        return "PUT", "Estrela Cadente (reversão baixa)"
    
    return "NEUTRO", "Sem padrão"

def analise_doji_confirmacao(df, idx):
    if idx < 1:
        return "NEUTRO", "Dados insuficientes"
    
    vela_anterior = df.iloc[idx-1]
    vela_atual = df.iloc[idx]
    
    range_anterior = vela_anterior['High'] - vela_anterior['Low']
    if range_anterior == 0:
        return "NEUTRO", "Range zero"
    
    corpo_anterior = abs(vela_anterior['Close'] - vela_anterior['Open'])
    percentual_corpo = (corpo_anterior / range_anterior) * 100
    
    if percentual_corpo <= 10:
        if vela_atual['Close'] > vela_atual['Open'] and vela_atual['Close'] > vela_anterior['High']:
            return "CALL", "Doji + confirmação alta"
        elif vela_atual['Close'] < vela_atual['Open'] and vela_atual['Close'] < vela_anterior['Low']:
            return "PUT", "Doji + confirmação baixa"
    
    return "NEUTRO", "Sem Doji"

def analise_tres_velas(df, idx):
    if idx < 2:
        return "NEUTRO", "Dados insuficientes"
    
    vela1 = df.iloc[idx-2]
    vela2 = df.iloc[idx-1]
    vela3 = df.iloc[idx]
    
    if (vela1['Close'] > vela1['Open'] and
        vela2['Close'] > vela2['Open'] and
        vela3['Close'] > vela3['Open']):
        return "CALL", "3 velas de alta"
    
    if (vela1['Close'] < vela1['Open'] and
        vela2['Close'] < vela2['Open'] and
        vela3['Close'] < vela3['Open']):
        return "PUT", "3 velas de baixa"
    
    return "NEUTRO", "Sem padrão"

def analise_media_moveis(df, idx):
    if idx < 21:
        return "NEUTRO", "Dados insuficientes"
    
    mm7 = df['Close'].rolling(window=7).mean()
    mm21 = df['Close'].rolling(window=21).mean()
    mm50 = df['Close'].rolling(window=50).mean()
    
    preco = df.iloc[idx]['Close']
    mm7_val = mm7.iloc[idx]
    mm21_val = mm21.iloc[idx]
    mm50_val = mm50.iloc[idx]
    
    mm7_ant = mm7.iloc[idx-1]
    mm21_ant = mm21.iloc[idx-1]
    
    if mm7_ant <= mm21_ant and mm7_val > mm21_val:
        return "CALL", "Golden Cross (forte)"
    
    if mm7_ant >= mm21_ant and mm7_val < mm21_val:
        return "PUT", "Death Cross (forte)"
    
    if preco > mm7_val and preco > mm21_val and preco > mm50_val:
        return "CALL", "Preço acima de todas médias"
    elif preco < mm7_val and preco < mm21_val and preco < mm50_val:
        return "PUT", "Preço abaixo de todas médias"
    
    return "NEUTRO", "Preço entre médias"

def analise_rsi(df, idx):
    if idx < 14:
        return "NEUTRO", "Dados insuficientes"
    
    fechamentos = df['Close'].iloc[idx-14:idx+1]
    diferencas = fechamentos.diff()
    
    ganhos = diferencas[diferencas > 0].sum()
    perdas = abs(diferencas[diferencas < 0].sum())
    
    if perdas == 0:
        rsi = 100
    else:
        rs = ganhos / perdas
        rsi = 100 - (100 / (1 + rs))
    
    if rsi > 70:
        return "PUT", f"RSI={rsi:.1f} (sobrecomprado)"
    elif rsi < 30:
        return "CALL", f"RSI={rsi:.1f} (sobrevendido)"
    
    return "NEUTRO", f"RSI={rsi:.1f} (neutro)"

def analise_tendencia_forca(df, idx):
    """Analisa força da tendência e momento ideal para entrada"""
    if idx < 20:
        return "NEUTRO", "Dados insuficientes"
    
    # Calcula inclinação das médias
    mm7 = df['Close'].rolling(window=7).mean()
    mm21 = df['Close'].rolling(window=21).mean()
    
    inclinacao_mm7 = (mm7.iloc[idx] - mm7.iloc[idx-5]) / 5 if idx >= 5 else 0
    inclinacao_mm21 = (mm21.iloc[idx] - mm21.iloc[idx-5]) / 5 if idx >= 5 else 0
    
    # Força da tendência (0-100)
    forca = 0
    if inclinacao_mm7 > 0 and inclinacao_mm21 > 0:
        forca = min(100, (inclinacao_mm7 / 0.0005) * 100)
        if forca > 60:
            return "CALL", f"Tendência de ALTA forte ({forca:.0f}%) - Momento ideal para CALL"
        elif forca > 30:
            return "CALL", f"Tendência de ALTA moderada ({forca:.0f}%)"
    elif inclinacao_mm7 < 0 and inclinacao_mm21 < 0:
        forca = min(100, abs(inclinacao_mm7 / 0.0005) * 100)
        if forca > 60:
            return "PUT", f"Tendência de BAIXA forte ({forca:.0f}%) - Momento ideal para PUT"
        elif forca > 30:
            return "PUT", f"Tendência de BAIXA moderada ({forca:.0f}%)"
    
    return "NEUTRO", f"Tendência fraca ou lateral ({forca:.0f}%)"

# ==================== FUNÇÃO DE PREVISÃO DE TEMPO ====================

def prever_proximo_sinal(df, ultimo_idx):
    """Previsão de quando pode ocorrer o próximo sinal baseado na volatilidade"""
    
    if len(df) < 20:
        return "Dados insuficientes para previsão"
    
    # Calcula tempo médio entre padrões de vela
    padroes_encontrados = []
    
    for i in range(max(5, ultimo_idx-50), ultimo_idx):
        # Verifica se houve padrão de engolfo ou martelo
        sinal_eng, _ = analise_engolfo(df, i)
        sinal_mar, _ = analise_martelo_estrela(df, i)
        
        if sinal_eng != "NEUTRO" or sinal_mar != "NEUTRO":
            padroes_encontrados.append(i)
    
    if len(padroes_encontrados) < 2:
        return "Padrões pouco frequentes - aguarde confirmação"
    
    # Calcula intervalo médio entre padrões
    intervalos = []
    for j in range(1, len(padroes_encontrados)):
        intervalos.append(padroes_encontrados[j] - padroes_encontrados[j-1])
    
    intervalo_medio = int(np.mean(intervalos)) if intervalos else 0
    minutos_por_vela = TIMEFRAME_MINUTOS.get(TIMEFRAME, 15)
    minutos_espera = intervalo_medio * minutos_por_vela
    
    # Verifica volatilidade recente
    ultimos_ranges = []
    for k in range(max(0, ultimo_idx-10), ultimo_idx):
        range_vela = df.iloc[k]['High'] - df.iloc[k]['Low']
        ultimos_ranges.append(range_vela)
    
    volatilidade = np.mean(ultimos_ranges) if ultimos_ranges else 0
    volatilidade_status = "ALTA" if volatilidade > 0.0005 else "MODERADA" if volatilidade > 0.0002 else "BAIXA"
    
    return {
        "minutos_espera": minutos_espera,
        "tempo_estimado": f"~{minutos_espera} minutos",
        "volatilidade": volatilidade_status,
        "padroes_ultimos": len(padroes_encontrados),
        "intervalo_medio": intervalo_medio
    }

# ==================== FUNÇÃO DE COLETA ====================

def coletar_dados_par(par, periodo=PERIODO_ANALISE, intervalo=TIMEFRAME):
    try:
        ticker = yf.Ticker(par, session=session)
        df = ticker.history(period=periodo, interval=intervalo)
        if df.empty:
            return None
        df = df.reset_index()
        return df
    except Exception as e:
        return None

# ==================== EXECUÇÃO PRINCIPAL ====================

def executar_analise(verbose=True):
    minutos_frame = TIMEFRAME_MINUTOS.get(TIMEFRAME, 15)
    
    if verbose:
        print("=" * 100)
        print("🤖 SISTEMA DE ANÁLISE DE MERCADO BINÁRIO")
        print(f"⏱️ Timeframe: {TIMEFRAME} ({minutos_frame} minutos por vela)")
        print(f"🎯 Regra: Mínimo de {MIN_SINAIS_CONCORDANTES} análises no mesmo sentido")
        print("=" * 100)
        print(f"📅 Análise executada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 100)
    
    todos_resultados = []
    
    for i, par in enumerate(PARES):
        if verbose:
            print(f"\n{'='*100}")
            print(f"📊 ANALISANDO: {par}")
            print(f"{'='*100}")
        
        df = coletar_dados_par(par)
        
        if df is None or len(df) < 30:
            if verbose:
                print(f"❌ Não foi possível coletar dados suficientes")
            continue
        
        ultimo_idx = len(df) - 1
        preco_atual = df.iloc[-1]['Close']
        ultimo_timestamp = datetime.now().astimezone(timezone('America/Sao_Paulo'))
        
        if verbose:
            print(f"✅ {len(df)} velas coletadas")
            print(f"💰 Preço atual: {preco_atual:.5f}")
            print(f"🕐 Último update: {ultimo_timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Executa as 7 análises (incluindo força da tendência)
        analises = {
            "ENGOLFO": analise_engolfo(df, ultimo_idx),
            "MARTELO": analise_martelo_estrela(df, ultimo_idx),
            "DOJI": analise_doji_confirmacao(df, ultimo_idx),
            "3 VELAS": analise_tres_velas(df, ultimo_idx),
            "MÉDIAS": analise_media_moveis(df, ultimo_idx),
            "RSI": analise_rsi(df, ultimo_idx),
            "TENDÊNCIA": analise_tendencia_forca(df, ultimo_idx),
        }
        
        # Previsão de próximo sinal
        previsao = prever_proximo_sinal(df, ultimo_idx)
        
        if verbose:
            # Tabela de resultados
            print(f"\n{'─'*100}")
            print(f"{'ANÁLISE':<15} │ {'SINAL':<10} │ {'DETALHE'}")
            print(f"{'─'*100}")
            
            sinais = []
            for nome, (sinal, detalhe) in analises.items():
                if sinal == "CALL":
                    icone_sinal = "🟢 CALL"
                    sinais.append("CALL")
                elif sinal == "PUT":
                    icone_sinal = "🔴 PUT"
                    sinais.append("PUT")
                else:
                    icone_sinal = "⚪ NEUTRO"
                    sinais.append("NEUTRO")
                
                print(f"{nome:<15} │ {icone_sinal:<10} │ {detalhe}")
            
            print(f"{'─'*100}")
            
            # Contagem
            total_call = sinais.count("CALL")
            total_put = sinais.count("PUT")
            total_neutro = sinais.count("NEUTRO")
            
            print(f"\n📊 CONTAGEM DE SINAIS:")
            print(f"   🟢 CALL:  {total_call}")
            print(f"   🔴 PUT:   {total_put}")
            print(f"   ⚪ NEUTRO: {total_neutro}")
            
            # INFORMAÇÃO DE MOMENTO E PREVISÃO
            print(f"\n{'─'*100}")
            print(f"⏰ INFORMAÇÕES DE MOMENTO E PREVISÃO:")
            print(f"{'─'*100}")
            
            if isinstance(previsao, dict):
                print(f"   📊 Volatilidade atual: {previsao['volatilidade']}")
                print(f"   📈 Padrões identificados (últimas 50 velas): {previsao['padroes_ultimos']}")
                print(f"   ⏱️ Intervalo médio entre sinais: {previsao['intervalo_medio']} velas (~{previsao['minutos_espera']} minutos)")
                print(f"   🔮 Próximo sinal estimado: {previsao['tempo_estimado']}")
                
                # Momento ideal baseado na tendência
                forca_tendencia = analise_tendencia_forca(df, ultimo_idx)
                if "forte" in forca_tendencia[1].lower() and "ALTA" in forca_tendencia[1]:
                    print(f"   ✅ MOMENTO IDEAL: Tendência forte de ALTA - Considere entrada agora")
                elif "forte" in forca_tendencia[1].lower() and "BAIXA" in forca_tendencia[1]:
                    print(f"   ✅ MOMENTO IDEAL: Tendência forte de BAIXA - Considere entrada agora")
                else:
                    print(f"   ⏳ AGUARDE: Tendência ainda fraca - Melhor esperar confirmação")
            else:
                print(f"   ⚠️ {previsao}")
            
            # Decisão final
            acao = "AGUARDAR"
            motivo = ""
            cor_acao = "⚪"
            
            if total_call >= MIN_SINAIS_CONCORDANTES:
                acao = "COMPRAR (CALL)"
                motivo = f"{total_call} de {len(analises)} análises indicam ALTA"
                cor_acao = "🟢"
            elif total_put >= MIN_SINAIS_CONCORDANTES:
                acao = "VENDER (PUT)"
                motivo = f"{total_put} de {len(analises)} análises indicam BAIXA"
                cor_acao = "🔴"
            else:
                if isinstance(previsao, dict):
                    motivo = f"Apenas {max(total_call, total_put)} análise(s) concordante(s). Próximo sinal estimado em ~{previsao['minutos_espera']} minutos"
                else:
                    motivo = f"Apenas {max(total_call, total_put)} análise(s) concordante(s) - Mínimo: {MIN_SINAIS_CONCORDANTES}"
            
            print(f"\n{'─'*100}")
            print(f"🎯 DECISÃO FINAL: {cor_acao} {acao}")
            print(f"📝 MOTIVO: {motivo}")
            print(f"{'─'*100}")
        
        # Collect data for return
        sinais = [sinal for sinal, _ in analises.values()]
        total_call = sinais.count("CALL")
        total_put = sinais.count("PUT")
        total_neutro = sinais.count("NEUTRO")
        
        acao = "AGUARDAR"
        motivo = ""
        if total_call >= MIN_SINAIS_CONCORDANTES:
            acao = "COMPRAR (CALL)"
            motivo = f"{total_call} de {len(analises)} análises indicam ALTA"
        elif total_put >= MIN_SINAIS_CONCORDANTES:
            acao = "VENDER (PUT)"
            motivo = f"{total_put} de {len(analises)} análises indicam BAIXA"
        else:
            if isinstance(previsao, dict):
                motivo = f"Apenas {max(total_call, total_put)} análise(s) concordante(s). Próximo sinal estimado em ~{previsao['minutos_espera']} minutos"
            else:
                motivo = f"Apenas {max(total_call, total_put)} análise(s) concordante(s) - Mínimo: {MIN_SINAIS_CONCORDANTES}"
        
        todos_resultados.append({
            "par": par,
            "preco": preco_atual,
            "acao": acao,
            "call": total_call,
            "put": total_put,
            "neutro": total_neutro,
            "motivo": motivo,
            "previsao": previsao if isinstance(previsao, dict) else None,
            "analises": analises,
            "timestamp": ultimo_timestamp
        })
        
        if i < len(PARES) - 1 and verbose:
            print(f"\n⏳ Aguardando 1 segundo...")
            time.sleep(1)
    
    if verbose:
        # Resumo Geral
        print(f"\n{'='*100}")
        print("📋 RESUMO GERAL - TODOS OS PARES")
        print(f"{'='*100}")
        
        if todos_resultados:
            print(f"\n{'PAR':<12} │ {'PREÇO':<12} │ {'CALL':<6} │ {'PUT':<6} │ {'PREVISÃO PRÓXIMO SINAL'}")
            print(f"{'─'*100}")
            
            for r in todos_resultados:
                if "COMPRAR" in r['acao']:
                    icone = "🟢"
                elif "VENDER" in r['acao']:
                    icone = "🔴"
                else:
                    icone = "⚪"
                
                previsao_texto = r['previsao']['tempo_estimado'] if r['previsao'] else "N/D"
                print(f"{r['par']:<12} │ {r['preco']:<12.5f} │ {r['call']:<6} │ {r['put']:<6} │ {previsao_texto}")
            
            print(f"{'─'*100}")
            
            acoes_recomendadas = [r for r in todos_resultados if r['acao'] != "AGUARDAR"]
            
            if acoes_recomendadas:
                print(f"\n✅ PARES COM SINAL FORTE (ENTRAGAR AGORA):")
                for r in acoes_recomendadas:
                    if "COMPRAR" in r['acao']:
                        print(f"   🟢 {r['par']}: {r['acao']} (Confiança: {r['call']}/{len(analises)} análises)")
                    else:
                        print(f"   🔴 {r['par']}: {r['acao']} (Confiança: {r['put']}/{len(analises)} análises)")
            else:
                print(f"\n⏳ NENHUM SINAL FORTE NO MOMENTO")
                print(f"   📊 Previsão de próximo sinal para cada par:")
                for r in todos_resultados:
                    if r['previsao']:
                        print(f"   • {r['par']}: ~{r['previsao']['minutos_espera']} minutos")
        
        print(f"\n{'='*100}")
        print("✅ ANÁLISE CONCLUÍDA")
        print(f"{'='*100}")
    
    return todos_resultados

if __name__ == "__main__":
    try:
        executar_analise()
    except KeyboardInterrupt:
        print("\n\n⚠️ Análise interrompida pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()