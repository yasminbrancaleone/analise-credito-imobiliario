# Diagnóstico do Funil de Crédito

Projeto em Python para tratar e analisar propostas de crédito com garantia de imóvel, gerar relatórios e, opcionalmente, extrair informações dos laudos de avaliação com a API da OpenAI. Os dados fornecidos para a case são sintéticos.

## Estrutura do projeto

```text
analise-credito-imobiliario/
├── .env.example
├── .gitignore
├── DIARIO.md
├── README.md
├── RESUMO_EXECUTIVO.pdf
├── analise.py
├── extracao_laudos.py
├── main.py
├── relatorio.py
├── requirements.txt
├── data/
│   ├── propostas_credito.csv
│   ├── golden_dataset.json
│   └── laudos_avaliacao/
│       ├── laudo_01.txt
│       └── ... laudo_17.txt
├── output/                         # Saídas geradas; ignorada pelo Git
│   ├── evaluation_results.csv      # Avaliação da extração (--laudos)
│   ├── laudos_extraidos.json       # Extração estruturada (--laudos)
│   ├── pipeline.log                # Log da execução pelo main.py
│   ├── relatorio_funil.html        # Relatório da análise
│   ├── relatorio_funil.xlsx        # Relatório da análise
│   ├── graficos/                   # Oito gráficos da análise
│   └── pdf/
│       └── resumo_executivo.tex    # Arquivo auxiliar presente no projeto
├── tests/
│   └── test_case.py
└── tmp/
    └── pdfs/
        └── generate_summary.py     # Utilitário auxiliar; não chamado pelo pipeline
```

Os arquivos de `output/` são artefatos de execução: alguns já acompanham a cópia do projeto, e outros são criados quando o pipeline correspondente é executado. A execução padrão gera o relatório Excel, o relatório HTML e os gráficos. Os arquivos de extração são gerados somente com `--laudos`.

### Responsabilidade de cada código

| Arquivo | Função |
|---|---|
| `main.py` | Ponto de entrada. Lê as opções da linha de comando, configura o log e coordena a análise e, opcionalmente, a extração dos laudos. |
| `analise.py` | Carrega e valida o CSV, trata os dados e calcula as métricas do funil, perdas financeiras, canais, evolução temporal e características associadas à contratação. |
| `relatorio.py` | Recebe os resultados da análise e gera oito gráficos, `relatorio_funil.xlsx` e `relatorio_funil.html`. |
| `extracao_laudos.py` | Lê os laudos TXT, solicita a extração ao modelo `gpt-4o-mini`, valida os campos com Pydantic e compara os resultados com o conjunto de referência. |
| `tests/test_case.py` | Testa regras de limpeza, cálculos do funil e validação/avaliação dos dados dos laudos sem chamar a API. |
| `tmp/pdfs/generate_summary.py` | Utilitário separado para montar um resumo em PDF. Não é chamado por `main.py` e depende de `reportlab`, que não está listado em `requirements.txt`. |

### Responsabilidade de cada pasta e arquivo de apoio

| Pasta/arquivo | Função |
|---|---|
| `data/` | Entradas da análise e da extração. |
| `data/propostas_credito.csv` | Base de propostas usada por padrão por `main.py`. |
| `data/laudos_avaliacao/` | Os 17 laudos TXT processados com `--laudos`. |
| `data/golden_dataset.json` | Valores de referência usados para avaliar a extração dos laudos. |
| `output/` | Relatórios, gráficos, resultados da extração e log. É preenchida pelas execuções e está no `.gitignore`. |
| `tests/` | Testes automatizados do projeto. |
| `tmp/pdfs/` | Código auxiliar para gerar o resumo PDF; não faz parte do fluxo padrão. |
| `RESUMO_EXECUTIVO.pdf` | Resumo executivo incluído na raiz do projeto. |
| `DIARIO.md` | Diário de desenvolvimento, aprendizados e decisões da case. |
| `requirements.txt` | Dependências Python da análise, dos relatórios, da extração e dos testes. |
| `.env.example` | Modelo de configuração da chave da API. |
| `.gitignore` | Ignora, entre outros itens, `.env`, ambientes virtuais, caches Python, logs e `output/`. |

## Fluxo da aplicação

```text
data/propostas_credito.csv
        ↓
main.py → validação e tratamento (analise.py)
        ↓
análises e métricas
        ↓
relatorio.py → output/relatorio_funil.xlsx
             → output/relatorio_funil.html
             → output/graficos/*.png

Opcional: --laudos
data/laudos_avaliacao/*.txt + data/golden_dataset.json
        ↓
extracao_laudos.py → output/laudos_extraidos.json
                   → output/evaluation_results.csv
```

## Requisitos e instalação

Use Python 3.10 ou superior.

## Tecnologias utilizadas

| Tecnologia | Onde é usada |
|---|---|
| **Python** | Linguagem da aplicação e dos testes. |
| **Pandas** | Leitura, limpeza, transformação e análise dos dados tabulares. |
| **SciPy** | Teste qui-quadrado para analisar a associação entre canal e contratação. |
| **Matplotlib e Seaborn** | Geração e formatação dos gráficos do relatório. |
| **OpenPyXL** | Escrita do relatório Excel. |
| **Jinja2** | Montagem do relatório HTML. |
| **LangChain (`langchain-openai`)** | Integração com o modelo `gpt-4o-mini` na extração opcional dos laudos. |
| **API da OpenAI** | Interpretação dos textos dos laudos; requer `OPENAI_API_KEY` e é chamada somente com `--laudos`. |
| **Pydantic** | Validação da estrutura dos campos extraídos dos laudos. |
| **python-dotenv** | Leitura da chave da API a partir do arquivo `.env`. |
| **pytest** | Execução dos testes automatizados, sem chamadas à API. |

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se a política de execução do PowerShell impedir a ativação do ambiente, use o executável diretamente: `.\.venv\Scripts\python.exe`.

## Como executar

### Análise do funil e relatórios

```powershell
python main.py
```

Por padrão, a aplicação lê `data/propostas_credito.csv`. Para usar outra base:

```powershell
python main.py --csv "caminho\para\propostas.csv"
```

O CSV precisa conter estas colunas:

```text
id_proposta, data_entrada, canal_origem, cidade, uf, tipo_imovel,
valor_imovel, valor_solicitado, prazo_meses, score_credito, idade_cliente,
renda_mensal_declarada, flag_cliente_recorrente, consultor_id,
etapa_max_funil, status_final, tempo_analise_dias,
data_assinatura_contrato, taxa_juros_aa
```

O LTV é calculado durante o tratamento como `valor_solicitado / valor_imovel`. A aplicação valida a presença das colunas e interrompe a execução se o CSV estiver vazio ou se mais de 10% dos valores de um campo numérico não puderem ser convertidos.

### Extração dos laudos

A opção `--laudos` executa primeiro a análise do funil e, em seguida, processa os laudos. Essa etapa faz chamadas à API da OpenAI e requer uma chave válida.

1. Copie `.env.example` para `.env`.
2. Preencha `OPENAI_API_KEY` no arquivo `.env`.
3. Execute:

```powershell
python main.py --laudos
```

Sem `--laudos`, a chave da API não é necessária. Não compartilhe nem versione o arquivo `.env`.

### Testes

```powershell
python -m pytest tests/ -v
```

Os testes cobrem regras de tratamento, métricas e avaliação estruturada dos laudos. Eles não fazem chamadas à API.

## Saídas

| Caminho | Quando é gerado | Conteúdo |
|---|---|---|
| `output/relatorio_funil.xlsx` | Sempre que `main.py` conclui a análise | Abas com tratamento, funil, canais, séries temporais, fatores, política de LTV e recomendações. |
| `output/relatorio_funil.html` | Sempre que `main.py` conclui a análise | Relatório navegável com tabelas e gráficos. |
| `output/graficos/` | Sempre que `main.py` conclui a análise | Volume e valor do funil, conversão temporal e por canal, LTV, score, tipo de imóvel e UF. |
| `output/pipeline.log` | Ao executar `main.py` | Eventos, avisos e erros da execução. |
| `output/laudos_extraidos.json` | Somente com `--laudos` | Campos extraídos, status, evidências e eventuais erros por arquivo. |
| `output/evaluation_results.csv` | Somente com `--laudos` | Comparação dos campos extraídos com o `golden_dataset.json`. |

## Decisões e limitações

- Valores de imóvel com prefixo `R$` são convertidos para número; o LTV é reconstruído a partir dos valores solicitados e dos imóveis.
- Propostas acima de 60% de LTV são mantidas para análise, não descartadas automaticamente.
- Datas inválidas são convertidas para ausentes e ficam fora das análises temporais.
- A análise estatística identifica associações, não causalidade; coortes recentes podem ainda estar incompletas.
- A extração por IA depende de acesso à API e pode exigir revisão humana, especialmente para campos conflitantes.
