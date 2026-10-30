"""Testes das regras críticas do projeto, sem chamadas à API."""

import pandas as pd
import pytest
from pydantic import ValidationError

from analise import (
    COLUNAS_OBRIGATORIAS,
    analisar_funil,
    calcular_ltv,
    calcular_perda_financeira_total,
    converter_datas,
    normalizar_canal_origem,
    remover_terrenos,
    tratar_valor_imovel,
    validar_dados,
)
from extracao_laudos import CampoExtraido, LaudoExtraido, avaliar_campo, avaliar_extracao


def dados_base() -> pd.DataFrame:
    # Base pequena com um Terreno e textos que exigem normalização.
    return pd.DataFrame({
        "id_proposta": ["P-1", "P-2", "P-3"],
        "data_entrada": ["2024-01-10", "2024-02-15", "2024-03-20"],
        "canal_origem": ["organico", " Correspondente ", "Indicação"],
        "cidade": ["São Paulo", "Belo Horizonte", "Curitiba"],
        "uf": ["SP", "MG", "PR"],
        "tipo_imovel": ["Apartamento", "Terreno", "Casa"],
        "valor_imovel": ["R$ 500000", "400000", "300000"],
        "valor_solicitado": [250000.0, 200000.0, 150000.0],
        "prazo_meses": [120, 180, 240],
        "score_credito": [700, 650, 600],
        "idade_cliente": [35, 42, 50],
        "renda_mensal_declarada": [5000.0, 4000.0, 3000.0],
        "flag_cliente_recorrente": [0, 1, 0],
        "consultor_id": ["C-1", "C-2", "C-3"],
        "etapa_max_funil": [6, 3, 4],
        "status_final": ["Contratada", "Desistiu", "Sem retorno"],
        "tempo_analise_dias": [15, 30, 25],
        "data_assinatura_contrato": ["2024-01-25", None, None],
        "taxa_juros_aa": [1.37, None, None],
    })


def dados_funil() -> pd.DataFrame:
    # Uma proposta por etapa deixa os cálculos de conversão verificáveis.
    return pd.DataFrame({
        "id_proposta": [f"P-{numero}" for numero in range(1, 7)],
        "etapa_max_funil": [1, 2, 3, 4, 5, 6],
        "status_final": ["Sem retorno", "Desistiu", "Reprovada crédito", "Problema garantia", "Documentação pendente", "Contratada"],
        "valor_solicitado": [100_000, 200_000, 150_000, 300_000, 120_000, 400_000],
        "ltv": [0.4, 0.5, 0.55, 0.65, 0.45, 0.5],
    })


def test_valor_imovel_com_prefixo_eh_convertido():
    df, _ = tratar_valor_imovel(dados_base(), [])
    assert df.loc[0, "valor_imovel"] == pytest.approx(500000.0)
    assert pd.api.types.is_numeric_dtype(df["valor_imovel"])


def test_ltv_eh_valor_solicitado_dividido_por_valor_imovel():
    df, _ = tratar_valor_imovel(dados_base(), [])
    df, _ = calcular_ltv(df, [])
    assert df.loc[0, "ltv"] == pytest.approx(0.5)


def test_canal_eh_normalizado_sem_separar_grupos_equivalentes():
    df, _ = normalizar_canal_origem(dados_base(), [])
    assert df["canal_origem"].tolist() == ["Organico", "Correspondente", "Indicação"]


def test_data_invalida_vira_nat_sem_interromper_limpeza():
    df = dados_base()
    df.loc[0, "data_entrada"] = "data_invalida"
    df, _ = converter_datas(df, [])
    assert pd.isna(df.loc[0, "data_entrada"])


def test_terreno_eh_removido_e_outros_imoveis_sao_preservados():
    df, relatorio = remover_terrenos(dados_base(), [])
    assert len(df) == 2
    assert "Terreno" not in df["tipo_imovel"].values
    assert relatorio[0]["registros_afetados"] == 1


def test_coluna_obrigatoria_ausente_interrompe_execucao():
    df = dados_base().drop(columns=["score_credito"])
    with pytest.raises(ValueError, match="ausentes"):
        validar_dados(df)


def test_csv_vazio_interrompe_execucao():
    with pytest.raises(ValueError, match="vazio"):
        validar_dados(pd.DataFrame({coluna: [] for coluna in COLUNAS_OBRIGATORIAS}))


def test_muitos_valores_invalidos_em_coluna_numerica_sao_reportados():
    df = dados_base()
    df["valor_solicitado"] = "invalido"
    assert validar_dados(df)


def test_conversao_do_funil_e_contagem_de_contratadas():
    resultado = analisar_funil(dados_funil())
    assert resultado["total_contratadas"] == 1
    assert resultado["taxa_conversao_geral"] == pytest.approx(1 / 6)


def test_etapa_invalida_nao_entra_no_funil():
    df = pd.concat([dados_funil(), pd.DataFrame([{"id_proposta": "P-7", "etapa_max_funil": 7, "status_final": "Contratada", "valor_solicitado": 1, "ltv": .5}])], ignore_index=True)
    assert analisar_funil(df)["total_propostas"] == 6


def test_valor_potencial_perdido_soma_etapas_um_a_cinco():
    resultado = calcular_perda_financeira_total(dados_funil())
    assert resultado["valor_perdido_funil"] == pytest.approx(870_000)
    assert resultado["valor_contratado"] == pytest.approx(400_000)
    assert resultado["valor_perdido_funil"] + resultado["valor_contratado"] == pytest.approx(resultado["valor_total_proposto"])


def test_pydantic_aceita_campo_ausente_e_conflitante():
    assert CampoExtraido(status="nao_informado").valor is None
    conflito = CampoExtraido(status="conflitante", valores_encontrados=["95", "92"])
    assert conflito.valores_encontrados == ["95", "92"]


def test_pydantic_rejeita_status_desconhecido():
    with pytest.raises(ValidationError):
        CampoExtraido(status="inventado")


def test_estrutura_completa_do_laudo_eh_validada():
    campo = CampoExtraido(status="encontrado", valor="teste", evidencia="trecho")
    laudo = LaudoExtraido(arquivo="laudo.txt", **{nome: campo for nome in [
        "tipo_imovel", "endereco", "area_privativa_m2", "area_total_m2", "ano_construcao",
        "valor_avaliacao", "matricula", "onus", "data_vistoria", "responsavel_tecnico",
    ]})
    assert laudo.arquivo == "laudo.txt"


def test_avaliacao_classifica_campo_ausente_como_correto():
    assert avaliar_campo({"status": "nao_informado", "valor": None}, {"status": "nao_informado", "valor": None}) == "correto"


def test_avaliacao_detecta_alucinacao():
    assert avaliar_campo({"status": "encontrado", "valor": "inventado"}, {"status": "nao_informado", "valor": None}) == "alucinacao"


def test_avaliacao_detecta_conflito():
    assert avaliar_campo({"status": "conflitante", "valores_encontrados": ["95", "92"]}, {"status": "conflitante", "valores_encontrados": ["95", "92"]}) == "conflito_correto"


def test_avaliacao_retorna_uma_linha_por_campo():
    campos = {campo: {"status": "nao_informado", "valor": None} for campo in [
        "tipo_imovel", "endereco", "area_privativa_m2", "area_total_m2", "ano_construcao",
        "valor_avaliacao", "matricula", "onus", "data_vistoria", "responsavel_tecnico",
    ]}
    assert len(avaliar_extracao([{"arquivo": "laudo.txt", **campos}], [{"arquivo": "laudo.txt", **campos}])) == 10
