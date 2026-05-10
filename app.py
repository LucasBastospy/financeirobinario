import streamlit as st
import pandas as pd
import teste
from teste import executar_analise, PARES

st.set_page_config(
    page_title="Análise Interativa ",
    page_icon="📈",
    layout="wide",
)

st.title("📊 Front-end Interativo`")
st.markdown(
    "Este painel usa a lógica desenvolvida por Lucas Bastos para exibir sinalizações de mercado com clareza"
)

with st.sidebar:
    st.header("Configuração rápida")
    pares_input = st.text_area(
        "Pares para análise",
        value=", ".join(PARES),
        help="Digite os pares separados por vírgula. Ex: EURUSD=X, GBPUSD=X",
        height=120,
    )

    timeframe = st.selectbox(
        "Timeframe",
        options=["1m", "2m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"],
        index=3,
    )

    periodo = st.selectbox(
        "Período de análise",
        options=["1d", "5d", "7d", "15d", "30d", "60d", "90d"],
        index=1,
    )

    min_sinais = st.slider("Mínimo de sinais concordantes", 1, 7, 3)
    rodar = st.button("🔄 Executar análise")

if not rodar:
    st.info("Clique em **Executar análise** na barra lateral para iniciar a análise em tempo real.")
    st.write("A configuração padrão usa os pares definidos em `teste.py` e exibe os resultados de maneira clara.")
    st.stop()

pares = [item.strip() for item in pares_input.split(",") if item.strip()]
if not pares:
    st.error("Digite pelo menos um par válido para análise.")
    st.stop()

# Atualiza as configurações do módulo teste.py para a execução interativa
teste.PARES = pares
teste.TIMEFRAME = timeframe
teste.PERIODO_ANALISE = periodo
teste.MIN_SINAIS_CONCORDANTES = min_sinais

with st.spinner("Coletando dados e executando as análises..."):
    resultados = executar_analise(verbose=False)

if not resultados:
    st.warning("Não foi possível obter resultados. Verifique sua conexão e se os pares informados são válidos.")
    st.stop()

st.success("✅ Análise concluída com sucesso")

# ==================== ÁREA DE RESUMO EXECUTIVO ====================
st.header("🎯 RESUMO EXECUTIVO - AÇÕES RECOMENDADAS")

# Filtrar apenas pares com ação recomendada (não aguardar)
acoes_recomendadas = [r for r in resultados if r["acao"] != "AGUARDAR"]

# Métricas rápidas no topo
total_pares = len(resultados)
pares_com_acao = len(acoes_recomendadas)
pares_aguardando = total_pares - pares_com_acao

col1, col2, col3 = st.columns(3)
col1.metric("Total de Pares Analisados", total_pares)
col2.metric("Pares com Sinal Forte", pares_com_acao)
col3.metric("Pares em Aguardo", pares_aguardando)

if acoes_recomendadas:
    # Ordenar por confiança (maior porcentagem primeiro)
    for r in acoes_recomendadas:
        total_analises = len(r["analises"])
        if "COMPRAR" in r["acao"]:
            r["porcentagem"] = (r["call"] / total_analises) * 100
            r["tipo_acao"] = "COMPRA (CALL)"
            r["icone_resumo"] = "🟢"
        elif "VENDER" in r["acao"]:
            r["porcentagem"] = (r["put"] / total_analises) * 100
            r["tipo_acao"] = "VENDA (PUT)"
            r["icone_resumo"] = "🔴"

    acoes_recomendadas.sort(key=lambda x: x["porcentagem"], reverse=True)

    # Exibir resumo em formato de lista clara
    with st.container():
        st.markdown(
            """
            <div style="background-color: #f0f8ff; padding: 20px; border-radius: 10px; border-left: 5px solid #1f77b4;">
            <h4 style="color: #1f77b4; margin-top: 0;">📋 AÇÕES PRIORITÁRIAS (Ordenadas por confiança)</h4>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        for r in acoes_recomendadas:
            previsao_texto = ""
            if r.get("previsao"):
                previsao_texto = f"nos próximos {r['previsao']['tempo_estimado']}"

            st.markdown(
                f"**{r['icone_resumo']} {r['par']}**: {r['porcentagem']:.0f}% das análises indicando **{r['tipo_acao']}** {previsao_texto}",
                help=f"Preço atual: {r['preco']:.5f} | Motivo: {r['motivo']}"
            )

    st.markdown("---")
else:
    st.info("⏳ Nenhum sinal forte detectado no momento. Todas as análises indicam aguardar melhor oportunidade.")

# ==================== ANÁLISES DETALHADAS ====================
with st.expander("📊 Ver Análises Detalhadas por Par", expanded=False):
    for resultado in resultados:
        par = resultado["par"]
        preco = resultado["preco"]
        acao = resultado["acao"]
        motivo = resultado["motivo"]
        previsao = resultado.get("previsao")
        timestamp = resultado["timestamp"]

        if "COMPRAR" in acao:
            cor = "#0f9d58"
            icone = "🟢"
        elif "VENDER" in acao:
            cor = "#d23f31"
            icone = "🔴"
        else:
            cor = "#444444"
            icone = "⚪"

        with st.container():
            st.markdown(f"### {icone} {par}")
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            col1.metric("Preço atual", f"{preco:.5f}")
            col2.metric("Ação recomendada", acao)
            col3.metric("Sinais CALL", resultado["call"])
            col4.metric("Sinais PUT", resultado["put"])

            st.markdown(f"**Motivo:** {motivo}")
            st.markdown(f"**Atualizado em:** {timestamp.strftime('%d/%m/%Y %H:%M:%S')}")

            if previsao:
                st.markdown(
                    f"**Previsão próximo sinal:** {previsao['tempo_estimado']} — volatilidade {previsao['volatilidade']}"
                )

            analises = []
            for nome, (sinal, detalhe) in resultado["analises"].items():
                if sinal == "CALL":
                    ic = "🟢 CALL"
                elif sinal == "PUT":
                    ic = "🔴 PUT"
                else:
                    ic = "⚪ NEUTRO"
                analises.append({"Análise": nome, "Sinal": ic, "Detalhe": detalhe})

            df_analises = pd.DataFrame(analises)
            st.dataframe(df_analises, use_container_width=True)
            st.markdown("---")

st.markdown(
    "<small>Sem `.env` necessário. Execute localmente com `streamlit run app.py`.</small>",
    unsafe_allow_html=True,
)
