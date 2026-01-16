# 📊 B3 COTAHIST Parser - Guia Completo

**Data**: 16 de Janeiro de 2026  
**Arquivo**: `scripts/cotahist_parser.py`  
**Fonte de Dados**: B3 - Brasil, Bolsa, Balcão (Oficial)

## 🎯 O que é COTAHIST?

**COTAHIST** é o arquivo histórico **oficial** da B3 contendo **todas as negociações** realizadas na bolsa brasileira.

### Características:
- ✅ **Fonte Oficial**: Dados diretos da B3
- ✅ **Histórico Completo**: Anos de dados (1986 até hoje)
- ✅ **Todas as Ações**: Todos os ativos negociados
- ✅ **Formato Padronizado**: Layout de largura fixa documentado
- ✅ **Gratuito**: Disponível publicamente no site da B3
- ✅ **Confiável**: Sem APIs de terceiros, sem rate limiting

### Download:
- **Site**: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/series-historicas/
- **Arquivos**:
  - `COTAHIST_AXXXX.TXT`: Histórico anual (ex: COTAHIST_A2025.TXT)
  - `COTAHIST_MXXXX.TXT`: Histórico mensal (ex: COTAHIST_M012025.TXT)
  - `COTAHIST_DXXXX.TXT`: Histórico diário (ex: COTAHIST_D15012025.TXT)

## 🚀 Instalação

### 1. Dependências

```bash
# No container Docker
docker exec -it b3-execution-engine bash
pip install pandas asyncpg

# Ou localmente
pip install pandas asyncpg
```

### 2. Copiar script para o container

```bash
# Da raiz do projeto
docker cp scripts/cotahist_parser.py b3-execution-engine:/app/scripts/
```

## 📖 Uso Básico

### 1. Parse Simples (Console)

```bash
# Parse com símbolos padrão (PETR4, VALE3, ITUB4, etc.)
python cotahist_parser.py COTAHIST_A2025.TXT

# Output:
# 📊 Parsing COTAHIST: COTAHIST_A2025.TXT
# 🎯 Filtrando símbolos: ABEV3, B3SA3, BBDC3, BBDC4, BBAS3, ITUB3, ITUB4, MGLU3, PETR3, PETR4, RENT3, SUZB3, VALE3, VALE5, WEGE3
# 📄 Header: Origem=BOVESPA, Data=20260116
# ✅ Parsing concluído!
#    Total de linhas: 1234567
#    Registros processados: 3850
#    Registros ignorados: 1230717
#    Símbolos encontrados: 15
```

### 2. Parse com Símbolos Específicos

```bash
# Apenas PETR4, VALE3 e ITUB4
python cotahist_parser.py COTAHIST_A2025.TXT --symbols PETR4 VALE3 ITUB4
```

### 3. Salvar em CSV

```bash
# Salvar cada símbolo em arquivo CSV separado
python cotahist_parser.py COTAHIST_A2025.TXT --csv

# Output:
# 💾 PETR4: 250 registros → data/cotahist/PETR4_2025.csv
# 💾 VALE3: 250 registros → data/cotahist/VALE3_2025.csv
# 💾 ITUB4: 250 registros → data/cotahist/ITUB4_2025.csv
# 💾 Consolidado: 3850 registros → data/cotahist/cotahist_2025_all.csv
```

### 4. Salvar no TimescaleDB

```bash
# Salvar diretamente no banco (dentro do container)
python cotahist_parser.py /tmp/COTAHIST_A2025.TXT \
  --db \
  --db-host timescaledb \
  --db-name trading_db \
  --db-user trading_user \
  --db-password trading_pass
```

### 5. Salvar em CSV + TimescaleDB

```bash
# Salvar em ambos os formatos
python cotahist_parser.py COTAHIST_A2025.TXT --csv --db
```

## 🔧 Uso no Container Docker

### Script Completo

```bash
#!/bin/bash
# Script: scripts/load_cotahist.sh

# 1. Copiar arquivo COTAHIST para o container
echo "📦 Copiando COTAHIST para container..."
docker cp ~/Downloads/COTAHIST_A2025.TXT b3-execution-engine:/tmp/

# 2. Copiar parser para o container
docker cp scripts/cotahist_parser.py b3-execution-engine:/app/scripts/

# 3. Instalar dependências (se necessário)
docker exec b3-execution-engine pip install pandas asyncpg

# 4. Executar parser
echo "🚀 Executando parser..."
docker exec b3-execution-engine python3 /app/scripts/cotahist_parser.py \
  /tmp/COTAHIST_A2025.TXT \
  --csv \
  --db \
  --db-host timescaledb \
  --output-dir /app/data/cotahist

# 5. Copiar CSVs de volta para host (opcional)
docker cp b3-execution-engine:/app/data/cotahist ./data/

echo "✅ Processamento concluído!"
```

## 📊 Estrutura dos Dados

### Formato CSV

```csv
date,symbol,name,open,high,low,close,volume,trades,turnover,avg_price
2025-01-02,PETR4,PETROBRAS,38.50,39.20,38.30,39.00,125000000,45678,4875000000.00,39.00
2025-01-03,PETR4,PETROBRAS,39.10,39.50,38.90,39.30,110000000,42123,4323000000.00,39.30
```

### Campos Extraídos

| Campo | Descrição | Tipo |
|-------|-----------|------|
| `date` | Data do pregão | datetime |
| `symbol` | Código de negociação (ticker) | string |
| `name` | Nome resumido da empresa | string |
| `open` | Preço de abertura | float |
| `high` | Preço máximo | float |
| `low` | Preço mínimo | float |
| `close` | Preço de fechamento | float |
| `volume` | Quantidade de títulos negociados | int |
| `trades` | Número de negócios | int |
| `turnover` | Volume financeiro (R$) | float |
| `avg_price` | Preço médio | float |

### Tabela TimescaleDB

```sql
-- Estrutura da tabela ohlcv_daily
CREATE TABLE ohlcv_daily (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    trades INTEGER,
    turnover DOUBLE PRECISION,
    avg_price DOUBLE PRECISION,
    PRIMARY KEY (time, symbol)
);

-- Hypertable para performance
SELECT create_hypertable('ohlcv_daily', 'time', 
    chunk_time_interval => INTERVAL '1 month'
);
```

## 🎯 Casos de Uso

### 1. Atualizar Base Histórica

```bash
# Baixar COTAHIST_A2024.TXT da B3
# Processar e inserir no banco
python cotahist_parser.py COTAHIST_A2024.TXT --db

# Baixar COTAHIST_A2025.TXT
python cotahist_parser.py COTAHIST_A2025.TXT --db

# Resultado: Base histórica 2024-2025 completa
```

### 2. Preparar Dados para Wave3 Strategy

```bash
# Extrair apenas símbolos do Wave3
python cotahist_parser.py COTAHIST_A2025.TXT \
  --symbols ITUB4 MGLU3 \
  --csv \
  --output-dir data/wave3

# Resultado: 
# - data/wave3/ITUB4_2025.csv
# - data/wave3/MGLU3_2025.csv
```

### 3. Análise de Dados (Python)

```python
from cotahist_parser import COTAHISTParser

# Parse do arquivo
parser = COTAHISTParser('COTAHIST_A2025.TXT')
parser.parse(symbols={'PETR4', 'VALE3'})

# Converter para DataFrame
df = parser.to_dataframe()

# Análise
print(df.describe())
print(df.groupby('symbol')['volume'].sum())

# Salvar
parser.save_to_csv('data/analysis')
```

### 4. Backtesting com Dados Reais

```python
import pandas as pd
from cotahist_parser import COTAHISTParser

# Carregar dados
parser = COTAHISTParser('COTAHIST_A2025.TXT')
parser.parse(symbols={'ITUB4'})
df = parser.to_dataframe()

# Preparar para backtesting
df_backtest = df[['date', 'open', 'high', 'low', 'close', 'volume']]
df_backtest['date'] = pd.to_datetime(df_backtest['date'])
df_backtest.set_index('date', inplace=True)

# Executar Wave3 Strategy
from strategies import Wave3DailyStrategy
strategy = Wave3DailyStrategy()
results = strategy.backtest(df_backtest)
```

## 📋 Filtros Aplicados

O parser aplica automaticamente os seguintes filtros:

### 1. Tipo de Mercado
- ✅ **010**: Mercado à vista (ações)
- ❌ Outros: Opções, futuros, termo, etc.

### 2. Código BDI
- ✅ **02**: Lote padrão
- ❌ Outros: Lote fracionário, exercício de opções, etc.

### 3. Símbolos
- ✅ Apenas símbolos especificados (ou padrão)
- ❌ Outros ativos ignorados

### 4. Negociação
- ✅ Apenas registros com `trades > 0` e `volume > 0`
- ❌ Registros sem negociação ignorados

## 🔍 Validação de Dados

### SQL Queries para Verificação

```sql
-- 1. Contar registros por símbolo
SELECT symbol, COUNT(*) as total_dias
FROM ohlcv_daily
WHERE time >= '2025-01-01'
GROUP BY symbol
ORDER BY total_dias DESC;

-- 2. Verificar período de dados
SELECT 
    symbol,
    MIN(time) as primeira_data,
    MAX(time) as ultima_data,
    COUNT(*) as total_dias
FROM ohlcv_daily
GROUP BY symbol;

-- 3. Identificar gaps (dias sem dados)
WITH dates AS (
    SELECT generate_series('2025-01-01'::date, '2025-12-31'::date, '1 day'::interval) AS date
),
trading_days AS (
    SELECT DISTINCT time::date as date FROM ohlcv_daily
)
SELECT d.date
FROM dates d
LEFT JOIN trading_days t ON d.date = t.date
WHERE t.date IS NULL
  AND EXTRACT(DOW FROM d.date) NOT IN (0, 6)  -- Não é fim de semana
ORDER BY d.date;

-- 4. Verificar integridade OHLC
SELECT symbol, time, open, high, low, close
FROM ohlcv_daily
WHERE high < low  -- Erro: máximo menor que mínimo
   OR high < open  -- Erro: máximo menor que abertura
   OR high < close  -- Erro: máximo menor que fechamento
   OR low > open  -- Erro: mínimo maior que abertura
   OR low > close;  -- Erro: mínimo maior que fechamento

-- 5. Volume por período
SELECT 
    DATE_TRUNC('month', time) as mes,
    symbol,
    SUM(volume) as volume_total,
    SUM(turnover) as volume_financeiro,
    COUNT(*) as dias_negociados
FROM ohlcv_daily
GROUP BY mes, symbol
ORDER BY mes DESC, volume_total DESC;
```

## 🐛 Troubleshooting

### Problema 1: Arquivo não encontrado

```bash
# Erro: FileNotFoundError: Arquivo não encontrado: COTAHIST_A2025.TXT

# Solução: Verificar caminho
ls -lh COTAHIST_A2025.TXT

# Usar caminho absoluto
python cotahist_parser.py /home/user/Downloads/COTAHIST_A2025.TXT
```

### Problema 2: Encoding incorreto

```bash
# Erro: UnicodeDecodeError

# Solução: O parser usa 'latin-1' automaticamente
# Arquivos B3 sempre usam latin-1 (ISO-8859-1)
```

### Problema 3: Nenhum registro encontrado

```bash
# Parsing concluído: 0 registros

# Causas possíveis:
# 1. Símbolos especificados não existem no arquivo
# 2. Formato de símbolo incorreto (PETR4 vs PETR4F)
# 3. Arquivo corrompido

# Solução: Parse sem filtro de símbolos
python cotahist_parser.py COTAHIST_A2025.TXT  # Usa símbolos padrão
```

### Problema 4: Erro de conexão TimescaleDB

```bash
# Erro: Connection refused (port 5432)

# Solução 1: Verificar se container está rodando
docker ps | grep timescaledb

# Solução 2: Usar host correto
# Dentro do container: --db-host timescaledb
# Fora do container: --db-host localhost
```

## 📈 Comparação: COTAHIST vs Outras Fontes

| Característica | COTAHIST (B3) | Yahoo Finance | BRAPI | ADVFN |
|---------------|---------------|---------------|-------|-------|
| **Fonte** | ✅ Oficial B3 | ⚠️ Terceiro | ⚠️ Terceiro | ⚠️ Terceiro |
| **Histórico** | ✅ Completo (1986+) | ✅ Bom (anos) | ❌ 3 meses | ⚠️ Variável |
| **Intraday** | ❌ Não | ✅ 60 dias | ❌ Não | ⚠️ JS-rendered |
| **Confiabilidade** | ✅ 100% | ⚠️ ~95% | ⚠️ ~90% | ⚠️ ~85% |
| **Rate Limiting** | ✅ Não | ⚠️ Sim | ⚠️ Sim | ⚠️ Sim |
| **Gratuito** | ✅ Sim | ✅ Sim | ✅ Limitado | ⚠️ Parcial |
| **Complexidade** | ⭐⭐ Médio | ⭐ Fácil | ⭐ Fácil | ⭐⭐⭐⭐ Difícil |
| **Recomendação** | ✅ **MELHOR para histórico** | ✅ Bom para intraday | ⚠️ Backup | ❌ Evitar |

## 🎯 Estratégia Recomendada de Coleta de Dados

### Para o Projeto B3 Trading Platform:

1. **Dados Históricos Diários** (2+ anos): 
   - ✅ **COTAHIST** (B3 oficial)
   - Atualizar anualmente com `COTAHIST_AXXXX.TXT`

2. **Dados Intraday** (60 dias): 
   - ✅ **yfinance** (Yahoo Finance)
   - Atualizar semanalmente

3. **Dados Recentes** (últimos dias): 
   - ✅ **BRAPI** (backup/fallback)
   - Atualizar diariamente

### Implementação:

```bash
# 1. Base histórica (executar 1x por ano)
python cotahist_parser.py COTAHIST_A2025.TXT --db

# 2. Intraday (executar 1x por semana)
python yfinance_collector.py --symbols PETR4 VALE3 ITUB4 --timeframe 1h --period 60d --db

# 3. Atualização diária (executar todo dia)
python brapi_collector.py --symbols PETR4 VALE3 ITUB4 --days 7 --db
```

## 📚 Referências

- **B3 - Séries Históric**: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/
- **Layout COTAHIST**: http://www.b3.com.br/data/files/33/67/B9/50/D84057102C784E47AC094EA8/SeriesHistoricas_Layout.pdf
- **Documentação B3 Market Data**: http://www.b3.com.br/pt_br/market-data-e-indices/

---

**Autor**: B3 Trading Platform Team  
**Versão**: 1.0.0  
**Data**: 16 de Janeiro de 2026
