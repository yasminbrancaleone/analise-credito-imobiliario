"""Geração de gráficos e relatórios da Parte 2.

Este módulo recebe resultados já calculados em ``analise.py``. Ele apenas
apresenta e salva os dados em ``output/``; não contém regras analíticas.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from jinja2 import BaseLoader, Environment

logger = logging.getLogger(__name__)

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["font.size"] = 10


def preparar_saida(pasta_saida: str | Path) -> tuple[Path, Path]:
    """Cria a pasta de saída e a subpasta dos gráficos quando necessário."""
    pasta = Path(pasta_saida)
    graficos = pasta / "graficos"
    graficos.mkdir(parents=True, exist_ok=True)
    return pasta, graficos


def gerar_graficos(resultados: dict, pasta_graficos: str | Path) -> list[Path]:
    """Gera os oito gráficos usados no relatório."""
    pasta = Path(pasta_graficos)
    pasta.mkdir(parents=True, exist_ok=True)
    funil, canais = resultados["funil"], resultados["canais"]
    temporal, fatores = resultados["temporal"], resultados["fatores"]
    # Cada item associa um arquivo final à função que desenha aquele gráfico.
    tarefas = [
        ("funil_volume.png", grafico_funil_volume, funil),
        ("funil_valor.png", grafico_funil_valor, funil),
        ("conversao_temporal.png", grafico_conversao_temporal, temporal),
        ("conversao_por_canal.png", grafico_conversao_por_canal, canais),
        ("ltv_contratacao.png", grafico_ltv_contratacao, fatores),
        ("score_contratacao.png", grafico_score_contratacao, fatores),
        ("tipo_imovel_contratacao.png", grafico_tipo_imovel, fatores),
        ("uf_contratacao.png", grafico_uf, fatores),
    ]
    arquivos = []
    for nome, funcao, dados in tarefas:
        caminho = pasta / nome
        try:
            funcao(dados, caminho)
            arquivos.append(caminho)
            logger.info("Gráfico gerado: %s", caminho)
        except Exception as erro:
            logger.error("Erro ao gerar %s: %s", nome, erro)
    return arquivos


def _salvar(figura: plt.Figure, caminho: Path) -> None:
    figura.tight_layout()
    figura.savefig(caminho, bbox_inches="tight")
    plt.close(figura)


def grafico_funil_volume(funil: dict, caminho: Path) -> None:
    dados = funil["volume_por_etapa"]
    figura, eixo = plt.subplots(figsize=(9, 5))
    barras = eixo.barh(dados["etapa_nome"], dados["n_propostas"], color=["#e74c3c" if etapa < 6 else "#2ecc71" for etapa in dados["etapa_max_funil"]])
    for barra, quantidade in zip(barras, dados["n_propostas"]):
        eixo.text(barra.get_width() + 10, barra.get_y() + barra.get_height() / 2, f"{quantidade:,}", va="center", fontsize=9)
    eixo.set_xlabel("Quantidade de propostas")
    eixo.set_title("Onde o funil perde mais volume?\n(Vermelho = abandono | Verde = contratação)")
    eixo.xaxis.set_major_formatter(mticker.FuncFormatter(lambda valor, _: f"{valor:,.0f}"))
    _salvar(figura, caminho)


def grafico_funil_valor(funil: dict, caminho: Path) -> None:
    dados = funil["valor_por_etapa"]
    figura, eixo = plt.subplots(figsize=(9, 5))
    barras = eixo.barh(dados["etapa_nome"], dados["valor_total"] / 1e6, color=["#e74c3c" if etapa < 6 else "#2ecc71" for etapa in dados["etapa_max_funil"]])
    for barra, valor in zip(barras, dados["valor_total"]):
        eixo.text(barra.get_width() + .5, barra.get_y() + barra.get_height() / 2, f"R$ {valor / 1e6:.1f}M", va="center", fontsize=9)
    eixo.set_xlabel("Valor solicitado total (R$ milhões)")
    eixo.set_title("Onde o funil perde mais valor financeiro?\n(Vermelho = não convertido | Verde = contratado)")
    _salvar(figura, caminho)


def grafico_conversao_temporal(temporal: dict, caminho: Path) -> None:
    dados = temporal["mensal"]
    figura, eixo_taxa = plt.subplots(figsize=(12, 5))
    eixo_taxa.plot(dados["mes_str"], dados["taxa_conversao"] * 100, marker="o", color="#2980b9", linewidth=2, markersize=5, label="Taxa de conversão (%)")
    eixo_taxa.set_ylabel("Taxa de conversão (%)", color="#2980b9")
    # O segundo eixo mostra volume sem distorcer a escala percentual da conversão.
    eixo_volume = eixo_taxa.twinx()
    eixo_volume.bar(dados["mes_str"], dados["n_propostas"], alpha=.3, color="#95a5a6", label="Nº de propostas")
    eixo_volume.set_ylabel("Nº de propostas", color="#7f8c8d")
    for mes in dados.loc[dados["coorte_incompleta"], "mes_str"]:
        indice = dados["mes_str"].tolist().index(mes)
        eixo_taxa.axvspan(indice - .5, indice + .5, alpha=.15, color="orange")
    eixo_taxa.set_xlabel("Mês")
    eixo_taxa.set_title("Evolução mensal da taxa de conversão\n(Área laranja = coorte possivelmente incompleta)")
    plt.xticks(rotation=45, ha="right")
    linhas, rotulos = eixo_taxa.get_legend_handles_labels()
    linhas2, rotulos2 = eixo_volume.get_legend_handles_labels()
    eixo_taxa.legend(linhas + linhas2, rotulos + rotulos2, loc="upper left", fontsize=8)
    _salvar(figura, caminho)


def grafico_conversao_por_canal(canais: dict, caminho: Path) -> None:
    dados = canais["conversao_por_canal"].sort_values("taxa_conversao")
    figura, eixos = plt.subplots(1, 2, figsize=(12, 5))
    cores = ["#e74c3c" if canal == "Correspondente" else "#3498db" for canal in dados["canal_origem"]]
    eixos[0].barh(dados["canal_origem"], dados["taxa_conversao"] * 100, color=cores)
    for indice, (taxa, quantidade) in enumerate(zip(dados["taxa_conversao"], dados["n_propostas"])):
        eixos[0].text(taxa * 100 + .2, indice, f"{taxa:.1%} (n={quantidade:,})", va="center", fontsize=9)
    eixos[0].set_xlabel("Taxa de conversão (%)")
    eixos[0].set_title("Taxa de conversão por canal\n(Vermelho = Correspondentes)")
    eixos[0].set_xlim(0, max(dados["taxa_conversao"] * 100) * 1.3)
    eixos[1].barh(dados["canal_origem"], dados["n_propostas"], color=cores)
    for indice, quantidade in enumerate(dados["n_propostas"]):
        eixos[1].text(quantidade + 10, indice, f"{quantidade:,}", va="center", fontsize=9)
    eixos[1].set_xlabel("Nº de propostas")
    eixos[1].set_title("Volume de propostas por canal")
    figura.suptitle("Desempenho por canal de origem", y=1.02)
    _salvar(figura, caminho)


def _grafico_por_faixa(dados: pd.DataFrame, coluna: str, titulo: str, cor: str, caminho: Path, limite_ltv: bool = False) -> None:
    dados = dados.dropna(subset=[coluna])
    figura, eixo = plt.subplots(figsize=(9, 5))
    cores = ["#e74c3c" if limite_ltv and ("60" in str(faixa) or "70" in str(faixa)) else cor for faixa in dados[coluna]]
    barras = eixo.bar(dados[coluna].astype(str), dados["taxa_conversao"] * 100, color=cores)
    for barra, (taxa, quantidade) in zip(barras, zip(dados["taxa_conversao"], dados["n_propostas"])):
        eixo.text(barra.get_x() + barra.get_width() / 2, barra.get_height() + .3, f"{taxa:.1%}\nn={quantidade:,}", ha="center", va="bottom", fontsize=8)
    if limite_ltv:
        # A linha marca a fronteira da política usada na análise.
        eixo.axvline(x=2.5, color="orange", linestyle="--", linewidth=1.5, label="Limite 60% (política)")
        eixo.legend()
    eixo.set_xlabel(coluna.replace("faixa_", "Faixa de ").replace("_", " ").title())
    eixo.set_ylabel("Taxa de conversão (%)")
    eixo.set_title(titulo)
    _salvar(figura, caminho)


def grafico_ltv_contratacao(fatores: dict, caminho: Path) -> None:
    _grafico_por_faixa(fatores["por_faixa_ltv"], "faixa_ltv", "Taxa de conversão por faixa de LTV\n(Vermelho = acima da política de 60%)", "#3498db", caminho, limite_ltv=True)


def grafico_score_contratacao(fatores: dict, caminho: Path) -> None:
    _grafico_por_faixa(fatores["por_faixa_score"], "faixa_score", "Taxa de conversão por score de crédito", "#27ae60", caminho)


def _grafico_horizontal(dados: pd.DataFrame, coluna: str, titulo: str, cor: str, caminho: Path) -> None:
    dados = dados.sort_values("taxa_conversao")
    figura, eixo = plt.subplots(figsize=(9, 5))
    eixo.barh(dados[coluna], dados["taxa_conversao"] * 100, color=cor)
    for indice, (taxa, quantidade) in enumerate(zip(dados["taxa_conversao"], dados["n_propostas"])):
        eixo.text(taxa * 100 + .2, indice, f"{taxa:.1%} (n={quantidade:,})", va="center", fontsize=9)
    eixo.set_xlabel("Taxa de conversão (%)")
    eixo.set_title(titulo)
    _salvar(figura, caminho)


def grafico_tipo_imovel(fatores: dict, caminho: Path) -> None:
    _grafico_horizontal(fatores["por_tipo_imovel"], "tipo_imovel", "Taxa de conversão por tipo de imóvel", "#8e44ad", caminho)


def grafico_uf(fatores: dict, caminho: Path) -> None:
    _grafico_horizontal(fatores["por_uf"], "uf", "Taxa de conversão por UF", "#e67e22", caminho)


def gerar_excel(df: pd.DataFrame, relatorio_tratamento: list[dict], resultados: dict, caminho_saida: str | Path) -> None:
    """Salva o relatório detalhado em Excel, mantendo as 14 abas existentes."""
    caminho = Path(caminho_saida)
    funil, canais = resultados["funil"], resultados["canais"]
    temporal, fatores = resultados["temporal"], resultados["fatores"]
    try:
        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            pd.DataFrame(relatorio_tratamento).to_excel(writer, sheet_name="Tratamento", index=False)
            funil["volume_por_etapa"].to_excel(writer, sheet_name="Funil_Volume", index=False)
            funil["valor_por_etapa"].to_excel(writer, sheet_name="Funil_Valor", index=False)
            canais["conversao_por_canal"].to_excel(writer, sheet_name="Canais", index=False)
            canais["composicao_por_canal"].to_excel(writer, sheet_name="Canais_Composicao", index=False)
            # Period não é serializado diretamente pelo Excel; por isso vira texto.
            mensal = temporal["mensal"].copy(); mensal["mes"] = mensal["mes"].astype(str)
            mensal.to_excel(writer, sheet_name="Temporal_Mensal", index=False)
            trimestral = temporal["trimestral"].copy(); trimestral["trimestre"] = trimestral["trimestre"].astype(str)
            trimestral.to_excel(writer, sheet_name="Temporal_Trimestral", index=False)
            fatores["por_canal"].to_excel(writer, sheet_name="Fatores_Canal", index=False)
            _serializar_categoria(fatores["por_faixa_ltv"], "faixa_ltv").to_excel(writer, sheet_name="Fatores_LTV", index=False)
            _serializar_categoria(fatores["por_faixa_score"], "faixa_score").to_excel(writer, sheet_name="Fatores_Score", index=False)
            fatores["por_uf"].to_excel(writer, sheet_name="Fatores_UF", index=False)
            pd.DataFrame([{"metrica": chave, "valor": valor} for chave, valor in funil["ltv_policy"].items()]).to_excel(writer, sheet_name="Politica_LTV", index=False)
            pd.DataFrame(resultados["recomendacoes"]).to_excel(writer, sheet_name="Recomendacoes", index=False)
            perda = resultados["perda_financeira"]
            pd.DataFrame([{"metrica": chave, "valor": valor} for chave, valor in perda.items()]).to_excel(writer, sheet_name="Resumo_Financeiro", index=False)
    except Exception as erro:
        raise RuntimeError(f"Falha ao gerar relatório Excel: {erro}") from erro
    logger.info("Relatório Excel gerado: %s", caminho)


def _serializar_categoria(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    copia = df.copy()
    copia[coluna] = copia[coluna].astype(str)
    return copia


def _formatar_brl(valor: float) -> str:
    if valor >= 1e9:
        return f"R$ {valor / 1e9:.2f} bi"
    if valor >= 1e6:
        return f"R$ {valor / 1e6:.1f} mi"
    return f"R$ {valor:,.0f}"


def _tabela_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, float_format=lambda valor: f"{valor:.4f}")


TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>Diagnóstico do Funil</title>
<style>body{font-family:Arial,sans-serif;max-width:960px;margin:40px auto;color:#222}h1{color:#2c3e50;border-bottom:2px solid #2980b9;padding-bottom:8px}h2{color:#2980b9;margin-top:32px}table{border-collapse:collapse;width:100%;margin:16px 0;font-size:13px}th{background:#2980b9;color:#fff;padding:8px 12px;text-align:left}td{padding:7px 12px;border-bottom:1px solid #ddd}tr:nth-child(even){background:#f5f8fc}.alerta{background:#fef9e7;border-left:4px solid #f39c12;padding:12px 16px;margin:12px 0}.destaque{background:#eaf4fb;border-left:4px solid #2980b9;padding:12px 16px;margin:12px 0}.rec{background:#eafaf1;border-left:4px solid #27ae60;padding:12px 16px;margin:12px 0}img{max-width:100%;margin:12px 0;border:1px solid #ddd}</style></head><body>
<h1>Diagnóstico do Funil de Crédito com Garantia de Imóvel</h1><p>Gerado em <strong>{{ data }}</strong>. Base do funil: <strong>{{ total }}</strong> propostas.</p>
<div class="alerta"><strong>Hipótese:</strong> a conversão caiu nos últimos meses e o canal Correspondente não está performando.</div>
<h2>1. Onde o funil perde mais valor?</h2><div class="destaque"><strong>Taxa de conversão geral: {{ conversao }}</strong><br>Valor total proposto: {{ total_valor }}<br>Valor contratado: {{ contratado }} ({{ pct_contratado }})<br><strong>Valor potencial perdido: {{ perdido }} ({{ pct_perdido }})</strong></div>
<h3>Volume por etapa</h3>{{ funil_volume }}<h3>Valor por etapa</h3>{{ funil_valor }}<img src="graficos/funil_volume.png" alt="Funil por volume"><img src="graficos/funil_valor.png" alt="Funil por valor">
<h2>2. Política de LTV</h2><div class="alerta"><strong>{{ acima_60 }}</strong> propostas estão acima de 60% de LTV. Há <strong>{{ contratos_acima }}</strong> contratos acima do limite. Conversão acima: {{ conversao_acima }}; dentro da política: {{ conversao_dentro }}.</div>
<h2>3. Análise temporal</h2><div class="destaque">Primeira metade: <strong>{{ primeira }}</strong><br>Segunda metade: <strong>{{ segunda }}</strong><br>Variação: <strong>{{ variacao }}</strong><br>{{ interpretacao }}</div><p class="alerta">{{ ressalva_temporal }}</p><img src="graficos/conversao_temporal.png" alt="Conversão temporal">
<h2>4. Canais</h2>{{ canais }}<div class="alerta"><strong>Qui-quadrado:</strong> {{ teste }}<br><em>{{ ressalva_teste }}</em></div><div class="destaque">Correspondente: {{ conv_correspondente }}; demais canais: {{ conv_demais }}; diferença: {{ diferenca }}.</div><img src="graficos/conversao_por_canal.png" alt="Conversão por canal">
<h2>5. Fatores associados à contratação</h2><h3>Tipo de imóvel</h3>{{ tipo_imovel }}<h3>Faixa de LTV</h3>{{ faixa_ltv }}<h3>Faixa de score</h3>{{ faixa_score }}<img src="graficos/ltv_contratacao.png" alt="LTV"><img src="graficos/score_contratacao.png" alt="Score">
<h2>6. Recomendações</h2>{% for rec in recomendacoes %}<div class="rec"><strong>{{ loop.index }}. {{ rec.titulo }}</strong><br><strong>Problema:</strong> {{ rec.problema_observado }}<br><strong>Ação:</strong> {{ rec.acao_sugerida }}<br><strong>Justificativa:</strong> {{ rec.justificativa }}<br><strong>Impacto:</strong> {{ rec.impacto_estimado }}<br><em>Limitações: {{ rec.limitacoes }}</em></div>{% endfor %}
<h2>7. Tratamento dos dados</h2>{{ tratamento }}<p><em>Dados sintéticos. Associação não implica causalidade.</em></p></body></html>"""


def gerar_html(relatorio_tratamento: list[dict], resultados: dict, caminho_saida: str | Path) -> None:
    """Gera uma versão HTML do relatório com caminhos relativos para os gráficos."""
    funil, canais = resultados["funil"], resultados["canais"]
    temporal, fatores, perda = resultados["temporal"], resultados["fatores"], resultados["perda_financeira"]
    funil_valor = funil["valor_por_etapa"].copy()
    # Formatação é feita em cópias para não alterar os resultados analíticos.
    for coluna in ("valor_total", "ticket_medio"):
        funil_valor[coluna] = funil_valor[coluna].map(_formatar_brl)
    conversao_canais = canais["conversao_por_canal"].copy()
    conversao_canais["taxa_conversao"] = conversao_canais["taxa_conversao"].map(lambda valor: f"{valor:.2%}")
    ltv = _serializar_categoria(fatores["por_faixa_ltv"], "faixa_ltv")
    score = _serializar_categoria(fatores["por_faixa_score"], "faixa_score")
    for tabela in (ltv, score):
        tabela["taxa_conversao"] = tabela["taxa_conversao"].map(lambda valor: f"{valor:.2%}")
    tipo = fatores["por_tipo_imovel"].copy(); tipo["taxa_conversao"] = tipo["taxa_conversao"].map(lambda valor: f"{valor:.2%}")
    politica, resumo, corr = funil["ltv_policy"], temporal["resumo"], canais["detalhes_correspondentes"]
    html = Environment(loader=BaseLoader()).from_string(TEMPLATE_HTML).render(
        data=datetime.now().strftime("%d/%m/%Y %H:%M"), total=f"{funil['total_propostas']:,}", conversao=f"{funil['taxa_conversao_geral']:.2%}", total_valor=_formatar_brl(perda["valor_total_proposto"]), contratado=_formatar_brl(perda["valor_contratado"]), pct_contratado=f"{perda['pct_valor_contratado']:.1f}%", perdido=_formatar_brl(perda["valor_perdido_funil"]), pct_perdido=f"{perda['pct_valor_perdido']:.1f}%", funil_volume=_tabela_html(funil["volume_por_etapa"]), funil_valor=_tabela_html(funil_valor), acima_60=f"{politica['n_propostas_acima_60']:,}", contratos_acima=politica["n_contratos_acima_60"], conversao_acima=f"{politica['taxa_conversao_acima_60']:.2%}", conversao_dentro=f"{politica['taxa_conversao_dentro_politica']:.2%}", primeira=f"{resumo['taxa_conversao_primeira_metade']:.2%}", segunda=f"{resumo['taxa_conversao_segunda_metade']:.2%}", variacao=f"{resumo['variacao_pp']:+.1f} pp", interpretacao=resumo["interpretacao"], ressalva_temporal=resumo["ressalva"], canais=_tabela_html(conversao_canais), teste=canais["teste_estatistico"]["conclusao"], ressalva_teste=canais["teste_estatistico"]["ressalva"], conv_correspondente=f"{corr['correspondentes']['taxa_conversao']:.2%}", conv_demais=f"{corr['demais_canais']['taxa_conversao']:.2%}", diferenca=f"{corr['diferenca_conversao_pp']:.1f} pp", tipo_imovel=_tabela_html(tipo), faixa_ltv=_tabela_html(ltv.dropna(subset=["faixa_ltv"])), faixa_score=_tabela_html(score.dropna(subset=["faixa_score"])), recomendacoes=resultados["recomendacoes"], tratamento=_tabela_html(pd.DataFrame(relatorio_tratamento)),
    )
    try:
        Path(caminho_saida).write_text(html, encoding="utf-8")
    except Exception as erro:
        raise RuntimeError(f"Falha ao gerar relatório HTML: {erro}") from erro
    logger.info("Relatório HTML gerado: %s", caminho_saida)


def gerar_relatorios(df: pd.DataFrame, relatorio_tratamento: list[dict], resultados: dict, pasta_saida: str | Path) -> dict:
    """Gera gráficos, Excel e HTML em uma única pasta de saída."""
    pasta, graficos = preparar_saida(pasta_saida)
    arquivos_graficos = gerar_graficos(resultados, graficos)
    excel = pasta / "relatorio_funil.xlsx"
    html = pasta / "relatorio_funil.html"
    gerar_excel(df, relatorio_tratamento, resultados, excel)
    gerar_html(relatorio_tratamento, resultados, html)
    return {"excel": excel, "html": html, "graficos": arquivos_graficos}
