"""Extração e avaliação dos laudos da Parte 3.

Fluxo: TXT → prompt → LLM → JSON → Pydantic → evidências → avaliação.
Não há agentes, RAG ou persistência externa: cada laudo é tratado de forma
independente e uma falha é registrada sem interromper os demais documentos.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError, field_validator

logger = logging.getLogger(__name__)

STATUS_VALIDOS = {"encontrado", "nao_informado", "nao_aplicavel", "nao_verificavel", "conflitante"}
CAMPOS_AVALIADOS = [
    "tipo_imovel", "endereco", "area_privativa_m2", "area_total_m2",
    "ano_construcao", "valor_avaliacao", "matricula", "onus",
    "data_vistoria", "responsavel_tecnico",
]


class CampoExtraido(BaseModel):
    """Campo extraído, seu status e a evidência textual correspondente."""

    valor: Optional[str] = None
    status: str
    evidencia: Optional[str] = None
    valores_encontrados: Optional[list[str]] = None

    @field_validator("status")
    @classmethod
    def validar_status(cls, valor: str) -> str:
        if valor not in STATUS_VALIDOS:
            raise ValueError(f"Status '{valor}' inválido. Esperado: {sorted(STATUS_VALIDOS)}")
        return valor


class LaudoExtraido(BaseModel):
    """Estrutura esperada para a resposta de um laudo."""

    arquivo: str
    tipo_imovel: CampoExtraido
    endereco: CampoExtraido
    area_privativa_m2: CampoExtraido
    area_total_m2: CampoExtraido
    ano_construcao: CampoExtraido
    valor_avaliacao: CampoExtraido
    matricula: CampoExtraido
    onus: CampoExtraido
    data_vistoria: CampoExtraido
    responsavel_tecnico: CampoExtraido
    erro_extracao: Optional[str] = None


PROMPT_SISTEMA = """Você é um especialista em análise de laudos de avaliação imobiliária.

Extraia os campos solicitados do texto. Nunca invente informação.

Regras:
1. Campo ausente: status "nao_informado" e valor null.
2. Informação explicitamente não verificável: status "nao_verificavel".
3. Campo que não se aplica, como ano de construção de terreno: status "nao_aplicavel".
4. Dois valores diferentes para o mesmo campo: status "conflitante", valor null e ambos em valores_encontrados.
5. Campo encontrado normalmente: status "encontrado".
6. Em evidencia, copie trecho curto de até 80 caracteres que sustente a resposta.

Responda apenas com JSON, sem markdown, contendo exatamente estes campos:
tipo_imovel, endereco, area_privativa_m2, area_total_m2, ano_construcao,
valor_avaliacao, matricula, onus, data_vistoria e responsavel_tecnico.
Cada campo deve ter valor, status, evidencia e valores_encontrados.
"""


def ler_laudo(caminho: str | Path) -> str:
    """Lê um laudo TXT e falha claramente para arquivo ausente ou vazio."""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Laudo não encontrado: {arquivo}")
    texto = arquivo.read_text(encoding="utf-8").strip()
    if not texto:
        raise ValueError(f"Laudo vazio: {arquivo.name}")
    return texto


def criar_modelo(api_key: Optional[str] = None) -> ChatOpenAI:
    """Cria o único modelo usado na extração."""
    chave = api_key or os.getenv("OPENAI_API_KEY")
    if not chave:
        raise EnvironmentError("OPENAI_API_KEY não encontrada. Configure o arquivo .env.")
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=chave)


def extrair_laudo(texto: str, nome_arquivo: str, llm: ChatOpenAI) -> LaudoExtraido:
    """Extrai e valida um único laudo; erros viram resultado rastreável."""
    try:
        resposta = llm.invoke([
            SystemMessage(content=PROMPT_SISTEMA),
            HumanMessage(content=f"LAUDO:\n\n{texto}"),
        ])
        conteudo = str(resposta.content).strip()
        # Alguns modelos envolvem o JSON em markdown; o parser recebe só o conteúdo.
        if conteudo.startswith("```"):
            conteudo = "\n".join(conteudo.splitlines()[1:-1]).strip()
        dados = json.loads(conteudo)
        return LaudoExtraido.model_validate({"arquivo": nome_arquivo, **dados})
    except json.JSONDecodeError as erro:
        logger.error("JSON inválido para %s: %s", nome_arquivo, erro)
        return laudo_com_erro(nome_arquivo, f"JSON inválido: {erro}")
    except ValidationError as erro:
        logger.error("Estrutura inválida para %s: %s", nome_arquivo, erro)
        return laudo_com_erro(nome_arquivo, f"Estrutura inválida: {erro}")
    except Exception as erro:
        logger.error("Erro ao extrair %s: %s", nome_arquivo, erro)
        return laudo_com_erro(nome_arquivo, f"Erro na extração: {erro}")


def laudo_com_erro(nome_arquivo: str, mensagem: str) -> LaudoExtraido:
    """Mantém o arquivo no resultado quando a chamada ou validação falha."""
    # O resultado mantém a mesma estrutura para facilitar auditoria posterior.
    campos = {campo: CampoExtraido(status="nao_informado") for campo in CAMPOS_AVALIADOS}
    return LaudoExtraido(arquivo=nome_arquivo, erro_extracao=mensagem, **campos)


def extrair_todos_laudos(pasta_laudos: str | Path, llm: Optional[ChatOpenAI] = None) -> list[dict]:
    """Processa todos os ``.txt`` em ordem, preservando resultados parciais."""
    pasta = Path(pasta_laudos)
    if not pasta.is_dir():
        raise FileNotFoundError(f"Pasta de laudos não encontrada: {pasta}")
    arquivos = sorted(pasta.glob("*.txt"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo .txt encontrado em: {pasta}")
    modelo = llm or criar_modelo()
    logger.info("Processando %s laudos em %s", len(arquivos), pasta)
    resultados = []
    for arquivo in arquivos:
        try:
            texto = ler_laudo(arquivo)
            laudo = extrair_laudo(texto, arquivo.name, modelo)
        except (FileNotFoundError, ValueError) as erro:
            logger.error("Erro ao ler %s: %s", arquivo.name, erro)
            laudo = laudo_com_erro(arquivo.name, str(erro))
        resultados.append(laudo.model_dump())
    return resultados


def normalizar_valor(valor: object) -> str:
    return "" if valor is None else str(valor).lower().strip()


def avaliar_campo(extraido: dict, esperado: dict) -> str:
    """Classifica a comparação de um campo extraído com o golden dataset."""
    status_extraido = extraido.get("status", "nao_informado")
    status_esperado = esperado.get("status", "nao_informado")
    valor_extraido = normalizar_valor(extraido.get("valor"))
    valor_esperado = normalizar_valor(esperado.get("valor"))
    if status_esperado == "conflitante":
        return "conflito_correto" if status_extraido == "conflitante" else "conflito_incorreto"
    if status_esperado in {"nao_informado", "nao_aplicavel", "nao_verificavel"}:
        if status_extraido == "encontrado":
            return "alucinacao"
        return "correto" if status_extraido == status_esperado else "status_incorreto"
    if status_extraido != status_esperado:
        return "status_incorreto"
    if valor_extraido == valor_esperado or valores_numericos_iguais(valor_extraido, valor_esperado):
        return "correto"
    return "status_correto_valor_errado"


def valores_numericos_iguais(valor_a: str, valor_b: str) -> bool:
    """Aceita diferenças de formatação monetária, sem flexibilizar textos."""
    try:
        def converter(valor: str) -> float:
            valor = valor.replace("r$", "").replace(" ", "")
            if "," in valor and "." in valor:
                valor = valor.replace(".", "").replace(",", ".")
            elif "," in valor:
                valor = valor.replace(",", ".")
            return float(valor)
        return converter(valor_a) == converter(valor_b)
    except ValueError:
        return False


def avaliar_extracao(resultados: list[dict], golden: list[dict]) -> list[dict]:
    """Gera uma linha de avaliação por campo para cada laudo conhecido."""
    # Indexar por arquivo evita procurar o mesmo laudo repetidamente.
    esperados = {item["arquivo"]: item for item in golden}
    linhas = []
    for resultado in resultados:
        arquivo = resultado.get("arquivo", "desconhecido")
        esperado = esperados.get(arquivo)
        if not esperado:
            logger.warning("Laudo '%s' não encontrado no golden dataset", arquivo)
            continue
        for campo in CAMPOS_AVALIADOS:
            campo_extraido = resultado.get(campo) or {}
            campo_esperado = esperado.get(campo) or {}
            linhas.append({
                "arquivo": arquivo,
                "campo": campo,
                "resultado": avaliar_campo(campo_extraido, campo_esperado),
                "status_extraido": campo_extraido.get("status", "ausente"),
                "status_esperado": campo_esperado.get("status", "ausente"),
                "valor_extraido": campo_extraido.get("valor"),
                "valor_esperado": campo_esperado.get("valor"),
            })
    if linhas:
        corretos = sum(linha["resultado"] in {"correto", "conflito_correto"} for linha in linhas)
        logger.info("Avaliação: %s/%s campos corretos (%.1f%%)", corretos, len(linhas), corretos / len(linhas) * 100)
    return linhas


def carregar_golden(caminho: str | Path) -> list[dict]:
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Golden dataset não encontrado: {arquivo}")
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError(f"Golden dataset inválido: {erro}") from erro


def processar_laudos(pasta_laudos: str | Path, pasta_saida: str | Path, caminho_golden: str | Path) -> dict:
    """Executa extração, salva JSON com evidências e avalia contra o golden dataset."""
    saida = Path(pasta_saida)
    saida.mkdir(parents=True, exist_ok=True)
    # O JSON guarda a evidência; o CSV facilita a leitura da avaliação por campo.
    resultados = extrair_todos_laudos(pasta_laudos)
    caminho_json = saida / "laudos_extraidos.json"
    caminho_json.write_text(json.dumps(resultados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    golden = carregar_golden(caminho_golden)
    avaliacao = avaliar_extracao(resultados, golden)
    caminho_avaliacao = saida / "evaluation_results.csv"
    pd.DataFrame(avaliacao).to_csv(caminho_avaliacao, index=False, encoding="utf-8")
    logger.info("Laudos extraídos: %s | Avaliação: %s", caminho_json, caminho_avaliacao)
    return {"resultados": resultados, "json": caminho_json, "avaliacao": caminho_avaliacao}
