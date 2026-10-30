"""Ponto de entrada do projeto.

Uso:
    python main.py
    python main.py --csv caminho/para/propostas.csv
    python main.py --laudos
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from analise import carregar_dados, executar_analises, limpar_dados, validar_dados
from extracao_laudos import processar_laudos
from relatorio import gerar_relatorios

BASE_DIR = Path(__file__).resolve().parent
CSV_PADRAO = BASE_DIR / "data" / "propostas_credito.csv"
LAUDOS_DIR = BASE_DIR / "data" / "laudos_avaliacao"
GOLDEN_DATASET = BASE_DIR / "data" / "golden_dataset.json"
OUTPUT_DIR = BASE_DIR / "output"


def configurar_logging(pasta_saida: Path) -> None:
    """Registra eventos úteis no terminal e em um único arquivo de saída."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(pasta_saida / "pipeline.log", encoding="utf-8", mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Análise do funil de crédito com garantia de imóvel.")
    parser.add_argument("--csv", default=str(CSV_PADRAO), help="Caminho do CSV de propostas.")
    parser.add_argument("--laudos", action="store_true", help="Processa também os laudos com a API OpenAI.")
    return parser.parse_args()


def executar_analise(caminho_csv: str | Path) -> dict:
    """Executa as Partes 1 e 2 e retorna os resultados e arquivos gerados."""
    logger = logging.getLogger(__name__)
    logger.info("Início da análise")
    dados_brutos = carregar_dados(caminho_csv)
    erros = validar_dados(dados_brutos)
    if erros:
        raise ValueError("Formato inválido do CSV: " + " | ".join(erros))
    dados_tratados, tratamento = limpar_dados(dados_brutos)
    removidos = len(dados_brutos) - len(dados_tratados)
    logger.info("Registros após limpeza: %s | Removidos: %s", len(dados_tratados), removidos)
    resultados = executar_analises(dados_tratados)
    caminhos = gerar_relatorios(dados_tratados, tratamento, resultados, OUTPUT_DIR)
    logger.info("Relatórios gerados: Excel=%s | HTML=%s", caminhos["excel"], caminhos["html"])
    return {"dados": dados_tratados, "tratamento": tratamento, "resultados": resultados, "arquivos": caminhos}


def main() -> None:
    # A chave é opcional na análise do funil e só é exigida com --laudos.
    load_dotenv(BASE_DIR / ".env")
    args = argumentos()
    configurar_logging(OUTPUT_DIR)
    logger = logging.getLogger(__name__)
    try:
        executar_analise(args.csv)
        if args.laudos:
            logger.info("Início do processamento dos laudos")
            caminhos = processar_laudos(LAUDOS_DIR, OUTPUT_DIR, GOLDEN_DATASET)
            logger.info("Laudos processados: JSON=%s | Avaliação=%s", caminhos["json"], caminhos["avaliacao"])
    # Erros previstos são mostrados sem ocultar a causa para quem executa.
    except (FileNotFoundError, ValueError, RuntimeError, EnvironmentError) as erro:
        logger.error("Execução interrompida: %s", erro)
        sys.exit(1)
    except Exception as erro:
        logger.exception("Erro inesperado: %s", erro)
        sys.exit(1)
    logger.info("Execução finalizada com sucesso")


if __name__ == "__main__":
    main()
