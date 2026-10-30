"""Tratamento e análise do funil de crédito.

Este arquivo concentra a Parte 1 do projeto: leitura e validação do CSV,
limpeza dos dados e análises do funil. As funções recebem e devolvem
DataFrames ou dicionários simples para que possam ser testadas isoladamente.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

LIMITE_LTV = 0.60
ETAPAS = {
    1: "Simulação",
    2: "Lead",
    3: "Análise de Crédito",
    4: "Avaliação do Imóvel",
    5: "Formalização",
    6: "Contratação",
}

SCHEMA_ESPERADO = {
    "id_proposta": "str",
    "data_entrada": "str",
    "canal_origem": "str",
    "cidade": "str",
    "uf": "str",
    "tipo_imovel": "str",
    "valor_imovel": "numeric",
    "valor_solicitado": "numeric",
    "prazo_meses": "numeric",
    "score_credito": "numeric",
    "idade_cliente": "numeric",
    "renda_mensal_declarada": "numeric",
    "flag_cliente_recorrente": "numeric",
    "consultor_id": "str",
    "etapa_max_funil": "numeric",
    "status_final": "str",
    "tempo_analise_dias": "numeric",
    "data_assinatura_contrato": "str",
    "taxa_juros_aa": "numeric",
}
COLUNAS_OBRIGATORIAS = list(SCHEMA_ESPERADO)


def carregar_dados(caminho_csv: str | Path) -> pd.DataFrame:
    """Lê o CSV de entrada sem alterar o arquivo bruto."""
    caminho = Path(caminho_csv)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    try:
        dados = pd.read_csv(caminho, encoding="utf-8")
    except Exception as erro:
        raise RuntimeError(f"Erro ao ler o CSV: {erro}") from erro
    logger.info("Arquivo carregado: %s (%s registros)", caminho, len(dados))
    return dados


def validar_dados(df: pd.DataFrame) -> list[str]:
    """Valida colunas, arquivo vazio e conversão básica de campos numéricos."""
    ausentes = set(COLUNAS_OBRIGATORIAS) - set(df.columns)
    if ausentes:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(ausentes)}")
    if df.empty:
        raise ValueError("CSV carregado está vazio (0 linhas)")

    extras = set(df.columns) - set(COLUNAS_OBRIGATORIAS)
    if extras:
        logger.warning("Colunas inesperadas (ignoradas): %s", sorted(extras))

    erros = []
    for coluna, tipo in SCHEMA_ESPERADO.items():
        if tipo != "numeric":
            continue
        convertido = pd.to_numeric(df[coluna], errors="coerce")
        falhas = max(convertido.isna().sum() - df[coluna].isna().sum(), 0)
        percentual = falhas / len(df) * 100
        # Acima de 10%, a conversão automática deixaria de ser confiável.
        if percentual > 10:
            erros.append(
                f"Coluna '{coluna}': {falhas} valores não convertíveis para numérico "
                f"({percentual:.1f}% dos registros)."
            )
        elif falhas:
            logger.warning(
                "Coluna '%s': %s valor(es) não numérico(s) serão tratados na limpeza",
                coluna,
                falhas,
            )
    if erros:
        logger.error("Validação encontrou erro(s): %s", " | ".join(erros))
    else:
        logger.info("Validação básica: OK")
    return erros


def limpar_dados(df_bruto: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Aplica todos os tratamentos documentados e retorna a base limpa."""
    df = df_bruto.copy()
    relatorio: list[dict] = []
    # A ordem é importante: o LTV depende de valor_imovel já numérico.
    for tratamento in (
        tratar_valor_imovel,
        calcular_ltv,
        normalizar_canal_origem,
        converter_datas,
        verificar_idades,
        verificar_etapa_funil,
        verificar_ltv_politica,
        remover_terrenos,
        verificar_nulos_criticos,
    ):
        df, relatorio = tratamento(df, relatorio)
    logger.info("Limpeza concluída. Registros finais: %s", len(df))
    return df, relatorio


def tratar_valor_imovel(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Remove o prefixo recuperável ``R$`` e converte valor_imovel para número."""
    problema = df["valor_imovel"].astype(str).str.startswith("R$")
    quantidade = int(problema.sum())
    if quantidade:
        logger.warning(
            "valor_imovel: %s registro(s) com prefixo 'R$ '. IDs: %s",
            quantidade,
            df.loc[problema, "id_proposta"].tolist(),
        )
    df["valor_imovel"] = pd.to_numeric(
        df["valor_imovel"].astype(str).str.replace("R$", "", regex=False).str.strip(),
        errors="coerce",
    )
    nulos = int(df["valor_imovel"].isna().sum())
    if nulos:
        logger.error("valor_imovel: %s valor(es) não convertíveis", nulos)
    relatorio.append({
        "problema": "valor_imovel armazenado como texto com prefixo 'R$ '",
        "registros_afetados": quantidade,
        "tratamento": "Removido prefixo 'R$ ' e convertido para float",
        "justificativa": "Erro de digitação recuperável; valor numérico estava correto",
        "impacto": "Sem impacto na análise após correção",
    })
    return df, relatorio


def calcular_ltv(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Reconstrói LTV como valor solicitado dividido pelo valor do imóvel."""
    df["ltv"] = df["valor_solicitado"] / df["valor_imovel"]
    negativos = int((df["ltv"] < 0).sum())
    acima_200 = int((df["ltv"] > 2).sum())
    nulos = int(df["ltv"].isna().sum())
    if negativos:
        logger.error("LTV: %s valor(es) negativos", negativos)
    if acima_200:
        logger.warning("LTV: %s valor(es) acima de 200%%", acima_200)
    if nulos:
        logger.warning("LTV: %s valor(es) nulos", nulos)
    relatorio.append({
        "problema": "Coluna 'ltv' ausente no CSV (previsto no dicionário)",
        "registros_afetados": len(df),
        "tratamento": "LTV reconstruído como valor_solicitado / valor_imovel",
        "justificativa": "Definição padrão de LTV; coluna ausente documentada no projeto",
        "impacto": f"LTV calculado para todos os registros. Nulos: {nulos}, negativos: {negativos}, acima de 200%: {acima_200}",
    })
    return df, relatorio


def normalizar_canal_origem(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Remove espaços laterais e padroniza capitalização dos canais."""
    antes = df["canal_origem"].copy()
    df["canal_origem"] = df["canal_origem"].str.strip().str.title()
    alterados = int((antes != df["canal_origem"]).sum())
    if alterados:
        logger.info("canal_origem: %s registro(s) normalizados", alterados)
    relatorio.append({
        "problema": "canal_origem com capitalização inconsistente",
        "registros_afetados": alterados,
        "tratamento": "str.strip().str.title() aplicado em toda a coluna",
        "justificativa": "Evita separar um mesmo canal em grupos diferentes",
        "impacto": "Mínimo: apenas padronização de texto",
    })
    return df, relatorio


def converter_datas(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Converte datas inválidas para NaT, preservando a base para outras análises."""
    # Datas inválidas não removem a proposta; afetam somente a análise temporal.
    invalidas = pd.to_datetime(df["data_entrada"], errors="coerce").isna()
    quantidade = int(invalidas.sum())
    df["data_entrada"] = pd.to_datetime(df["data_entrada"], errors="coerce")
    df["data_assinatura_contrato"] = pd.to_datetime(
        df["data_assinatura_contrato"], errors="coerce"
    )
    if quantidade:
        logger.warning(
            "data_entrada: %s data(s) inválida(s) -> NaT. IDs: %s",
            quantidade,
            df.loc[invalidas, "id_proposta"].tolist(),
        )
    relatorio.append({
        "problema": "Datas inválidas em data_entrada",
        "registros_afetados": quantidade,
        "tratamento": "Convertidas para NaT com pd.to_datetime(errors='coerce')",
        "justificativa": "Valores irrecuperáveis sem dado original",
        "impacto": f"{quantidade} registro(s) excluídos da análise temporal",
    })
    return df, relatorio


def verificar_idades(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    menores = int((df["idade_cliente"] < 18).sum())
    if menores:
        logger.warning("idade_cliente: %s registro(s) com idade < 18 anos. Não removidos.", menores)
    relatorio.append({
        "problema": "idade_cliente < 18 anos (improvável para este produto)",
        "registros_afetados": menores,
        "tratamento": "Nenhuma remoção: registros sinalizados no log",
        "justificativa": "Não há evidência suficiente para corrigir automaticamente",
        "impacto": f"{menores} registro(s) podem afetar análise por faixa etária",
    })
    return df, relatorio


def verificar_etapa_funil(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    invalidas = ~df["etapa_max_funil"].isin(ETAPAS)
    quantidade = int(invalidas.sum())
    if quantidade:
        logger.warning(
            "etapa_max_funil: %s registro(s) fora de 1–6. IDs: %s, etapas: %s. Mantidos na base geral.",
            quantidade,
            df.loc[invalidas, "id_proposta"].tolist(),
            df.loc[invalidas, "etapa_max_funil"].tolist(),
        )
    relatorio.append({
        "problema": "etapa_max_funil com valor fora do intervalo 1–6",
        "registros_afetados": quantidade,
        "tratamento": "Mantidos na base; análises de funil filtram etapas 1–6",
        "justificativa": "Sem evidência para corrigir automaticamente",
        "impacto": f"{quantidade} registro(s) excluído(s) do funil",
    })
    return df, relatorio


def verificar_ltv_politica(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    acima = df["ltv"] > LIMITE_LTV
    quantidade = int(acima.sum())
    contratos = int((acima & (df["status_final"] == "Contratada")).sum())
    percentual = quantidade / len(df) * 100
    if contratos:
        logger.warning("POLÍTICA DE LTV: %s contrato(s) com LTV > 60%%. Mantidos para análise.", contratos)
    relatorio.append({
        "problema": "LTV acima do limite de 60% da política interna",
        "registros_afetados": quantidade,
        "tratamento": "Não removidos: analisados como informação de negócio",
        "justificativa": "Há contratos acima da política declarada",
        "impacto": f"{percentual:.1f}% das propostas acima da política; {contratos} contratos assinados",
    })
    return df, relatorio


def remover_terrenos(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Remove Terreno conforme regra obrigatória da análise."""
    antes = len(df)
    terrenos = df["tipo_imovel"].str.strip().str.title() == "Terreno"
    quantidade = int(terrenos.sum())
    # A exclusão é aplicada antes de qualquer métrica final do funil.
    df = df.loc[~terrenos].copy()
    logger.info("Terrenos removidos: %s registros (%.1f%%)", quantidade, quantidade / antes * 100)
    relatorio.append({
        "problema": "Registros com tipo_imovel = 'Terreno'",
        "registros_afetados": quantidade,
        "tratamento": "Removidos conforme regra obrigatória do dicionário",
        "justificativa": "Regra explícita da análise",
        "impacto": f"{quantidade} registros removidos; base reduzida para {len(df)}",
    })
    return df, relatorio


def verificar_nulos_criticos(df: pd.DataFrame, relatorio: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    ignorar = {"data_assinatura_contrato", "taxa_juros_aa"}
    for coluna in COLUNAS_OBRIGATORIAS:
        if coluna in ignorar:
            continue
        quantidade = int(df[coluna].isna().sum())
        if quantidade:
            logger.warning("Nulos inesperados em '%s': %s registro(s)", coluna, quantidade)
            relatorio.append({
                "problema": f"Nulos inesperados em '{coluna}'",
                "registros_afetados": quantidade,
                "tratamento": "Apenas registro: não removidos automaticamente",
                "justificativa": "Remoção sem investigação pode ocultar um padrão",
                "impacto": "Pode afetar análises que usam essa coluna",
            })
    return df, relatorio


def analisar_funil(df: pd.DataFrame) -> dict:
    # etapa_max_funil representa a última etapa alcançada por cada proposta.
    df_funil = df[df["etapa_max_funil"].isin(ETAPAS)].copy()
    excluidos = len(df) - len(df_funil)
    if excluidos:
        logger.warning("Funil: %s registro(s) com etapa inválida excluídos", excluidos)
    volume = (
        df_funil.groupby("etapa_max_funil").size().reset_index(name="n_propostas")
        .sort_values("etapa_max_funil").reset_index(drop=True)
    )
    volume["etapa_nome"] = volume["etapa_max_funil"].map(ETAPAS)
    volume["pct_do_total"] = volume["n_propostas"] / volume["n_propostas"].sum() * 100
    valor = (
        df_funil.groupby("etapa_max_funil")["valor_solicitado"].agg(["sum", "mean", "count"])
        .reset_index().rename(columns={"sum": "valor_total", "mean": "ticket_medio", "count": "n_propostas"})
        .sort_values("etapa_max_funil").reset_index(drop=True)
    )
    valor["etapa_nome"] = valor["etapa_max_funil"].map(ETAPAS)
    valor["pct_valor_total"] = valor["valor_total"] / valor["valor_total"].sum() * 100
    abandono = volume[["etapa_max_funil", "etapa_nome", "n_propostas", "pct_do_total"]].merge(
        valor[["etapa_max_funil", "valor_total", "ticket_medio"]], on="etapa_max_funil", how="left"
    )
    abandono["tipo"] = abandono["etapa_max_funil"].apply(lambda etapa: "Contratado" if etapa == 6 else "Abandonou")
    contratos = df_funil["etapa_max_funil"] == 6
    return {
        "volume_por_etapa": volume,
        "valor_por_etapa": valor,
        "abandono_por_etapa": abandono,
        "ltv_policy": analisar_politica_ltv(df),
        "total_propostas": len(df_funil),
        "total_contratadas": int(contratos.sum()),
        "taxa_conversao_geral": float(contratos.mean()),
    }


def analisar_politica_ltv(df: pd.DataFrame) -> dict:
    acima = df[df["ltv"] > LIMITE_LTV]
    contratos_acima = acima[acima["status_final"] == "Contratada"]
    dentro = df[df["ltv"] <= LIMITE_LTV]
    return {
        "n_propostas_acima_60": len(acima),
        "pct_propostas_acima_60": len(acima) / len(df) * 100,
        "valor_solicitado_acima_60": acima["valor_solicitado"].sum(),
        "n_contratos_acima_60": len(contratos_acima),
        "valor_contratado_acima_60": contratos_acima["valor_solicitado"].sum(),
        "taxa_conversao_acima_60": len(contratos_acima) / len(acima) if len(acima) else 0,
        "taxa_conversao_dentro_politica": (dentro["status_final"] == "Contratada").mean() if len(dentro) else 0,
    }


def calcular_perda_financeira_total(df: pd.DataFrame) -> dict:
    # É uma oportunidade máxima: propostas perdidas não seriam todas contratadas.
    perdidos = df[df["etapa_max_funil"].isin([1, 2, 3, 4, 5])]["valor_solicitado"].sum()
    contratados = df[df["etapa_max_funil"] == 6]["valor_solicitado"].sum()
    total = df["valor_solicitado"].sum()
    return {
        "valor_perdido_funil": perdidos,
        "valor_contratado": contratados,
        "valor_total_proposto": total,
        "pct_valor_perdido": perdidos / total * 100,
        "pct_valor_contratado": contratados / total * 100,
        "nota_metodologica": "Valor perdido é a soma do valor solicitado de propostas que não chegaram à etapa 6. Representa o teto superior da perda potencial.",
    }


def analisar_canais(df: pd.DataFrame) -> dict:
    conversao = (
        df.groupby("canal_origem").agg(
            n_propostas=("id_proposta", "count"),
            n_contratadas=("status_final", lambda valores: (valores == "Contratada").sum()),
            valor_total_solicitado=("valor_solicitado", "sum"),
            ticket_medio=("valor_solicitado", "mean"),
            ltv_medio=("ltv", "mean"),
            score_medio=("score_credito", "mean"),
        ).reset_index()
    )
    conversao["taxa_conversao"] = conversao["n_contratadas"] / conversao["n_propostas"]
    conversao["pct_volume_total"] = conversao["n_propostas"] / conversao["n_propostas"].sum() * 100
    conversao = conversao.sort_values("taxa_conversao", ascending=False).reset_index(drop=True)
    composicao = df.groupby("canal_origem").agg(
        ltv_medio=("ltv", "mean"),
        ltv_acima_60_pct=("ltv", lambda valores: (valores > LIMITE_LTV).mean() * 100),
        score_medio=("score_credito", "mean"),
        pct_apartamento=("tipo_imovel", lambda valores: (valores == "Apartamento").mean() * 100),
        pct_casa=("tipo_imovel", lambda valores: (valores == "Casa").mean() * 100),
        pct_comercial=("tipo_imovel", lambda valores: (valores == "Sala Comercial").mean() * 100),
        pct_imovel_rural=("tipo_imovel", lambda valores: (valores == "Imóvel Rural").mean() * 100),
        prazo_medio=("prazo_meses", "mean"),
        pct_recorrente=("flag_cliente_recorrente", "mean"),
        renda_media=("renda_mensal_declarada", "mean"),
    ).reset_index()
    return {
        "conversao_por_canal": conversao,
        "composicao_por_canal": composicao,
        "teste_estatistico": teste_qui_quadrado(df),
        "detalhes_correspondentes": detalhar_correspondentes(df),
    }


def teste_qui_quadrado(df: pd.DataFrame) -> dict:
    # Compara a distribuição de contratação entre os canais, sem indicar causa.
    tabela = pd.crosstab(df["canal_origem"], df["status_final"] == "Contratada")
    chi2, p_valor, graus_liberdade, _ = stats.chi2_contingency(tabela)
    significativo = p_valor < 0.05
    return {
        "chi2": round(chi2, 4),
        "p_valor": round(p_valor, 6),
        "graus_liberdade": graus_liberdade,
        "conclusao": "Diferença de conversão entre canais é estatisticamente significativa (p < 0.05)." if significativo else "Diferença de conversão entre canais NÃO é estatisticamente significativa (p >= 0.05).",
        "ressalva": "Significância estatística não implica causalidade. LTV, score e tipo de imóvel podem explicar parte ou toda a diferença observada.",
    }


def detalhar_correspondentes(df: pd.DataFrame) -> dict:
    correspondentes = df[df["canal_origem"] == "Correspondente"]
    demais = df[df["canal_origem"] != "Correspondente"]
    if correspondentes.empty:
        logger.warning("Canal 'Correspondente' não encontrado após normalização")
        return {}

    def resumir(base: pd.DataFrame) -> dict:
        return {
            "n_propostas": len(base),
            "taxa_conversao": (base["status_final"] == "Contratada").mean(),
            "ticket_medio": base["valor_solicitado"].mean(),
            "ltv_medio": base["ltv"].mean(),
            "pct_ltv_acima_60": (base["ltv"] > LIMITE_LTV).mean() * 100,
            "score_medio": base["score_credito"].mean(),
            "prazo_medio": base["prazo_meses"].mean(),
        }

    corr = resumir(correspondentes)
    outros = resumir(demais)
    return {
        "correspondentes": corr,
        "demais_canais": outros,
        "diferenca_conversao_pp": (corr["taxa_conversao"] - outros["taxa_conversao"]) * 100,
        "nota": "Diferença de conversão em pontos percentuais; não determina a causa.",
    }


def analisar_temporal(df: pd.DataFrame) -> dict:
    base = df[df["data_entrada"].notna()].copy()
    excluidos = len(df) - len(base)
    if excluidos:
        logger.warning("Temporal: %s registro(s) com data_entrada nula excluídos", excluidos)
    # Period evita misturar dias diferentes de um mesmo mês na agregação.
    base["mes"] = base["data_entrada"].dt.to_period("M")
    mensal = base.groupby("mes").agg(
        n_propostas=("id_proposta", "count"),
        n_contratadas=("status_final", lambda valores: (valores == "Contratada").sum()),
        valor_proposto=("valor_solicitado", "sum"),
        valor_contratado=("valor_solicitado", lambda valores: valores[base.loc[valores.index, "status_final"] == "Contratada"].sum()),
    ).reset_index()
    mensal["taxa_conversao"] = mensal["n_contratadas"] / mensal["n_propostas"]
    mensal["mes_str"] = mensal["mes"].astype(str)
    # Os dois últimos meses podem conter propostas ainda em andamento.
    mensal["coorte_incompleta"] = mensal["mes"] >= mensal["mes"].max() - 1

    base["trimestre"] = base["data_entrada"].dt.to_period("Q")
    trimestral = base.groupby("trimestre").agg(
        n_propostas=("id_proposta", "count"),
        n_contratadas=("status_final", lambda valores: (valores == "Contratada").sum()),
        valor_proposto=("valor_solicitado", "sum"),
    ).reset_index()
    trimestral["taxa_conversao"] = trimestral["n_contratadas"] / trimestral["n_propostas"]
    trimestral["trimestre_str"] = trimestral["trimestre"].astype(str)

    canal_mensal = base.groupby(["mes", "canal_origem"]).agg(
        n_propostas=("id_proposta", "count"),
        n_contratadas=("status_final", lambda valores: (valores == "Contratada").sum()),
    ).reset_index()
    canal_mensal["taxa_conversao"] = canal_mensal["n_contratadas"] / canal_mensal["n_propostas"]
    canal_mensal["mes_str"] = canal_mensal["mes"].astype(str)
    return {"mensal": mensal, "trimestral": trimestral, "por_canal_mensal": canal_mensal, "resumo": resumir_temporal(mensal)}


def resumir_temporal(mensal: pd.DataFrame) -> dict:
    metade = len(mensal) // 2
    primeira = mensal.iloc[:metade]["taxa_conversao"].mean()
    segunda = mensal.iloc[metade:]["taxa_conversao"].mean()
    variacao = (segunda - primeira) * 100
    completos = mensal[~mensal["coorte_incompleta"]]
    n_incompletas = int(mensal["coorte_incompleta"].sum())
    return {
        "taxa_conversao_primeira_metade": primeira,
        "taxa_conversao_segunda_metade": segunda,
        "variacao_pp": variacao,
        "interpretacao": "Queda na segunda metade do período" if variacao < -2 else "Alta na segunda metade do período" if variacao > 2 else "Estabilidade ao longo do período",
        "mes_maior_conversao": completos.loc[completos["taxa_conversao"].idxmax(), "mes_str"] if len(completos) else "N/A",
        "mes_menor_conversao": completos.loc[completos["taxa_conversao"].idxmin(), "mes_str"] if len(completos) else "N/A",
        "n_coortes_potencialmente_incompletas": n_incompletas,
        "ressalva": f"Os {n_incompletas} meses mais recentes podem ter conversão subestimada pois propostas ainda podem estar em andamento.",
    }


def agrupar_contratacao(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    resultado = df.groupby(coluna, observed=False).agg(
        n_propostas=("id_proposta", "count"),
        n_contratadas=("status_final", lambda valores: (valores == "Contratada").sum()),
        ticket_medio=("valor_solicitado", "mean"),
        ltv_medio=("ltv", "mean"),
    ).reset_index()
    resultado["taxa_conversao"] = resultado["n_contratadas"] / resultado["n_propostas"]
    return resultado.sort_values("taxa_conversao", ascending=False).reset_index(drop=True)


def analisar_contratacao(df: pd.DataFrame) -> dict:
    base = df.copy()
    # Faixas fixas deixam a comparação legível no relatório e no Excel.
    base["faixa_ltv"] = pd.cut(base["ltv"], [0, .40, .50, .60, .70, float("inf")], labels=["<=40%", "40-50%", "50-60%", "60-70%", ">70%"], right=True)
    base["faixa_score"] = pd.cut(base["score_credito"], [0, 500, 600, 700, 800, float("inf")], labels=["<500", "500–600", "600–700", "700–800", ">800"], right=False)
    base["faixa_valor"] = pd.cut(base["valor_solicitado"], [0, 150_000, 300_000, 500_000, 800_000, float("inf")], labels=["<150k", "150k–300k", "300k–500k", "500k–800k", ">800k"], right=True)
    base["faixa_idade"] = pd.cut(base["idade_cliente"], [0, 25, 35, 45, 55, float("inf")], labels=["18–25", "25–35", "35–45", "45–55", ">55"], right=True)
    base["faixa_renda"] = pd.cut(base["renda_mensal_declarada"], [0, 3_000, 5_000, 8_000, 15_000, float("inf")], labels=["<3k", "3k–5k", "5k–8k", "8k–15k", ">15k"], right=True)
    base["cliente_recorrente"] = base["flag_cliente_recorrente"].map({1: "Recorrente", 0: "Novo"})
    return {
        "por_canal": agrupar_contratacao(base, "canal_origem"),
        "por_faixa_ltv": agrupar_contratacao(base, "faixa_ltv"),
        "por_tipo_imovel": agrupar_contratacao(base, "tipo_imovel"),
        "por_faixa_score": agrupar_contratacao(base, "faixa_score"),
        "por_faixa_valor": agrupar_contratacao(base, "faixa_valor"),
        "por_uf": agrupar_contratacao(base, "uf"),
        "por_prazo": agrupar_contratacao(base, "prazo_meses"),
        "por_cliente_recorrente": agrupar_contratacao(base, "cliente_recorrente"),
        "por_faixa_idade": agrupar_contratacao(base, "faixa_idade"),
        "por_faixa_renda": agrupar_contratacao(base, "faixa_renda"),
    }


def gerar_recomendacoes(fatores: dict, politica_ltv: dict, resumo_temporal: dict, detalhes_correspondentes: dict) -> list[dict]:
    faixa_ltv = fatores["por_faixa_ltv"]
    # Mantém a chave textual usada pela recomendação original.
    n_50_60 = faixa_ltv.loc[faixa_ltv["faixa_ltv"].astype(str) == "50–60%", "n_propostas"]
    n_50_60 = int(n_50_60.iloc[0]) if len(n_50_60) else 0
    corr = detalhes_correspondentes.get("correspondentes", {})
    demais = detalhes_correspondentes.get("demais_canais", {})
    recorrentes = fatores["por_cliente_recorrente"].set_index("cliente_recorrente")
    taxa_recorrente = recorrentes.loc["Recorrente", "taxa_conversao"] if "Recorrente" in recorrentes.index else 0
    taxa_novo = recorrentes.loc["Novo", "taxa_conversao"] if "Novo" in recorrentes.index else 0
    n_recorrente = recorrentes.loc["Recorrente", "n_propostas"] if "Recorrente" in recorrentes.index else 0
    return [
        {
            "titulo": "Priorizar propostas com LTV entre 50% e 60%",
            "problema_observado": f"{politica_ltv['n_propostas_acima_60']} propostas ({politica_ltv['pct_propostas_acima_60']:.1f}%) estão acima de 60%; a faixa 50–60% tem {n_50_60} propostas.",
            "acao_sugerida": "Criar triagem explícita para LTV acima de 60% e priorizar propostas entre 50% e 60%.",
            "justificativa": f"Conversão acima de 60%: {politica_ltv['taxa_conversao_acima_60']:.1%}; dentro da política: {politica_ltv['taxa_conversao_dentro_politica']:.1%}.",
            "impacto_estimado": f"Valor potencial não processado: R$ {politica_ltv['valor_solicitado_acima_60']:,.0f}.",
            "hipotese": "Contratos acima do limite podem ser exceções de negócio não documentadas.",
            "limitacoes": "LTV isolado não determina aprovação.",
        },
        {
            "titulo": "Investigar a captação via Correspondentes",
            "problema_observado": f"Correspondentes convertem {corr.get('taxa_conversao', 0):.1%}; os demais canais, {demais.get('taxa_conversao', 0):.1%}.",
            "acao_sugerida": "Mapear critérios de qualificação e diferenças de perfil das propostas captadas.",
            "justificativa": f"O canal tem LTV médio de {corr.get('ltv_medio', 0):.1%} e score médio de {corr.get('score_medio', 0):.0f}.",
            "impacto_estimado": f"Se atingisse a conversão dos demais canais, haveria cerca de {int((demais.get('taxa_conversao', 0) - corr.get('taxa_conversao', 0)) * corr.get('n_propostas', 0))} contratos adicionais.",
            "hipotese": "Parte da diferença pode estar no perfil das propostas, e não no atendimento.",
            "limitacoes": "Estimativa não controla a composição do portfólio.",
        },
        {
            "titulo": "Avaliar reativação de clientes recorrentes",
            "problema_observado": f"Há {n_recorrente} propostas recorrentes, com conversão de {taxa_recorrente:.1%}, contra {taxa_novo:.1%} dos clientes novos.",
            "acao_sugerida": "Identificar clientes com operações anteriores para uma campanha proativa de reabordagem.",
            "justificativa": "Clientes recorrentes já conhecem o produto e o processo.",
            "impacto_estimado": "Não calculado: depende da base histórica disponível.",
            "hipotese": "A experiência anterior pode estar associada a expectativas mais alinhadas.",
            "limitacoes": "A flag não informa quantidade nem data das operações anteriores.",
        },
    ]


def executar_analises(df: pd.DataFrame) -> dict:
    """Executa a Parte 1 e reúne os resultados consumidos pelo relatório."""
    funil = analisar_funil(df)
    canais = analisar_canais(df)
    temporal = analisar_temporal(df)
    fatores = analisar_contratacao(df)
    return {
        "funil": funil,
        "perda_financeira": calcular_perda_financeira_total(df),
        "canais": canais,
        "temporal": temporal,
        "fatores": fatores,
        "recomendacoes": gerar_recomendacoes(fatores, funil["ltv_policy"], temporal["resumo"], canais["detalhes_correspondentes"]),
    }
