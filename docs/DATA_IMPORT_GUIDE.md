# 📥 Guia de Importação de Dados - ProfitChart CSV

**Última Atualização:** 28 de Janeiro de 2026  
**Status:** ✅ 775.259 registros importados com sucesso

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Localização dos Arquivos](#localização-dos-arquivos)
3. [Formatos CSV](#formatos-csv)
4. [Banco de Dados](#banco-de-dados)
5. [Scripts de Importação](#scripts-de-importação)
6. [Procedimento de Importação](#procedimento-de-importação)
7. [Validação](#validação)
8. [Troubleshooting](#troubleshooting)
9. [Histórico de Importações](#histórico-de-importações)

---

## 🎯 Visão Geral

Este documento descreve o processo completo de importação de dados históricos do ProfitChart para o sistema B3 Trading Platform.

**Estatísticas Atuais:**
- **Total de registros:** 775.259
- **Símbolos únicos:** 58
- **Período coberto:** Janeiro/2023 → Janeiro/2026 (3 anos)
- **Timeframes:** 15min, 60min, Diário
- **Taxa de sucesso:** 100%

---

## 📂 Localização dos Arquivos

### Pasta Principal

```
/home/dellno/Área de trabalho/dadoshistoricos.csv/
├── dados23e24/          # Histórico 2023-2025
│   ├── PETR4_B_0_15min.csv
│   ├── PETR4_B_0_60min.csv
│   ├── PETR4_B_0_Diário.csv
│   ├── VALE3_B_0_15min.csv
│   └── ... (157 arquivos totais)
│
└── dados26/             # Janeiro 2026
    ├── PETR4_B_0_15min.csv
    ├── PETR4_B_0_60min.csv
    ├── PETR4_B_0_Diário.csv
    └── ... (72 arquivos totais)
```

### Nomenclatura dos Arquivos

**Padrão:** `{SYMBOL}_B_0_{TIMEFRAME}.csv`

Onde:
- `{SYMBOL}`: Código do ativo (ex: PETR4, VALE3)
- `B`: Fonte (ProfitChart B3)
- `0`: Versão do arquivo
- `{TIMEFRAME}`: 15min, 60min ou Diário

**Exemplos:**
- `PETR4_B_0_15min.csv` - Petrobras PN, 15 minutos
- `VALE3_B_0_60min.csv` - Vale ON, 60 minutos
- `ITUB4_B_0_Diário.csv` - Itaú Unibanco PN, diário

---

## 📊 Formatos CSV

### ⚠️ ATENÇÃO: Formatos Diferentes!

O ProfitChart exporta arquivos com **formatos diferentes** dependendo do timeframe:

### Formato Intraday (15min, 60min)

**Colunas:** 9 campos separados por `;`

```csv
symbol;date;time;open;high;low;close;volume_brl;volume_qty
PETR4;30/12/2024;17:00:00;32,83;32,97;32,80;32,80;215181183,90;6552300
PETR4;30/12/2024;16:00:00;32,86;32,90;32,75;32,83;189234567,80;5789123
PETR4;30/12/2024;15:00:00;32,90;33,05;32,85;32,86;156789234,50;4789234
```

**Descrição dos Campos:**

| Campo | Tipo | Formato | Descrição | Exemplo |
|-------|------|---------|-----------|---------|
| symbol | String | - | Código do ativo | PETR4 |
| date | String | DD/MM/YYYY | Data da cotação | 30/12/2024 |
| **time** | String | HH:MM:SS | **Horário da cotação** | 17:00:00 |
| open | Float | Vírgula | Preço de abertura | 32,83 |
| high | Float | Vírgula | Preço máximo | 32,97 |
| low | Float | Vírgula | Preço mínimo | 32,80 |
| close | Float | Vírgula | Preço de fechamento | 32,80 |
| volume_brl | Float | Vírgula | Volume financeiro (R$) | 215181183,90 |
| volume_qty | Integer | - | Quantidade negociada | 6552300 |

### Formato Diário

**Colunas:** 8 campos separados por `;` (SEM campo `time`)

```csv
symbol;date;open;high;low;close;volume_brl;volume_qty
PETR4;30/12/2024;32,43;32,97;32,42;32,80;733138158,20;22355600
PETR4;27/12/2024;32,63;32,63;32,28;32,33;784245347,60;24167200
PETR4;26/12/2024;32,30;32,63;32,27;32,42;743936420,70;22920700
```

**Descrição dos Campos:**

| Campo | Tipo | Formato | Descrição | Exemplo |
|-------|------|---------|-----------|---------|
| symbol | String | - | Código do ativo | PETR4 |
| date | String | DD/MM/YYYY | Data da cotação | 30/12/2024 |
| open | Float | Vírgula | Preço de abertura | 32,43 |
| high | Float | Vírgula | Preço máximo | 32,97 |
| low | Float | Vírgula | Preço mínimo | 32,42 |
| close | Float | Vírgula | Preço de fechamento | 32,80 |
| volume_brl | Float | Vírgula | Volume financeiro (R$) | 733138158,20 |
| volume_qty | Integer | - | Quantidade negociada | 22355600 |

### 🔑 Diferença Crítica

```
📌 INTRADAY: symbol;date;TIME;open;high;low;close;volume_brl;volume_qty  (9 campos)
📌 DIÁRIO:   symbol;date;open;high;low;close;volume_brl;volume_qty       (8 campos)
```

**NUNCA confundir os formatos!** O parser precisa detectar o timeframe e usar o parser correto.

---

## 🗄️ Banco de Dados

### TimescaleDB

**Conexão:**
- Host: `b3-timescaledb` (via Docker network)
- Porta: `5432` (interna) / `5433` (host)
- Database: `b3trading_market`
- Usuário: `b3trading_ts`
- Password: `b3trading_ts_pass`

### Hypertables

#### 1. ohlcv_15min

**Descrição:** Dados de 15 minutos

```sql
CREATE TABLE ohlcv_15min (
    symbol VARCHAR(10) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (symbol, time)
);

SELECT create_hypertable('ohlcv_15min', 'time', chunk_time_interval => INTERVAL '7 days');
```

**Estatísticas:**
- Registros: ~338.847 (28/01/2026)
- Particionamento: Chunks de 7 dias
- Símbolos: 42 (nem todos têm dados 15min)

#### 2. ohlcv_60min

**Descrição:** Dados de 60 minutos (1 hora)

```sql
CREATE TABLE ohlcv_60min (
    symbol VARCHAR(10) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (symbol, time)
);

SELECT create_hypertable('ohlcv_60min', 'time', chunk_time_interval => INTERVAL '30 days');
```

**Estatísticas:**
- Registros: ~407.470 (28/01/2026)
- Particionamento: Chunks de 30 dias
- Símbolos: 57 (quase todos têm dados 60min)

#### 3. ohlcv_daily

**Descrição:** Dados diários

```sql
CREATE TABLE ohlcv_daily (
    symbol VARCHAR(10) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    PRIMARY KEY (symbol, time)
);

SELECT create_hypertable('ohlcv_daily', 'time', chunk_time_interval => INTERVAL '365 days');
```

**Estatísticas:**
- Registros: ~28.942 (28/01/2026)
- Particionamento: Chunks de 365 dias
- Símbolos: 58 (todos têm dados diários)

---

## 🔧 Scripts de Importação

### Script Principal

**Localização:** `scripts/import_historical_data.py`

**Linguagem:** Python 3.11+

**Dependências:**
```python
asyncpg==0.29.0    # PostgreSQL async driver
loguru==0.7.2      # Structured logging
```

### Arquitetura do Script

```python
class HistoricalDataImporter:
    """Importador de dados históricos para TimescaleDB"""
    
    def __init__(self):
        self.pool = None  # asyncpg connection pool
        self.stats = {...}  # Estatísticas de importação
    
    async def connect(self):
        """Conecta ao TimescaleDB"""
    
    def parse_csv_line(self, line: list, is_daily: bool = False) -> dict:
        """
        Parse condicional:
        - is_daily=True: 8 campos (sem time)
        - is_daily=False: 9 campos (com time)
        """
    
    async def import_file(self, file_path: Path, phase: str):
        """Importa um arquivo CSV usando COPY"""
    
    async def import_symbol(self, symbol: str, folder: Path, phase: str):
        """Importa todos os timeframes de um símbolo"""
    
    async def import_priority_symbols(self):
        """Fase 1: Importa 5 símbolos prioritários"""
    
    async def import_remaining_symbols(self):
        """Fase 2: Importa 53 símbolos restantes"""
    
    async def validate_import(self, symbols: list):
        """Valida importação mostrando estatísticas"""
```

### Funcionalidades Principais

1. **Parse Condicional**
   - Detecta se é arquivo Diário (8 campos) ou Intraday (9 campos)
   - Usa parser apropriado para cada tipo

2. **Bulk Insert via COPY**
   - Performance otimizada: ~28.000 registros/segundo
   - Mais rápido que INSERT VALUES

3. **Validação de Duplicatas**
   - Verifica se dados já existem no período
   - Oferece opção de remover e reimportar

4. **Logging Estruturado**
   - Estatísticas em tempo real
   - Erros detalhados com context

5. **Execução em Fases**
   - Fase 1: 5 prioritários (PETR4, VALE3, ITUB4, BBDC4, ABEV3)
   - Fase 2: 53 restantes (opcional)

---

## 🚀 Procedimento de Importação

### Pré-requisitos

1. **Container TimescaleDB rodando:**
```bash
docker ps | grep b3-timescaledb
# Deve retornar uma linha com status "Up"
```

2. **Arquivos CSV disponíveis:**
```bash
ls -l "/home/dellno/Área de trabalho/dadoshistoricos.csv/dados23e24/" | wc -l
# Deve retornar 157+ (incluindo diretório)
```

3. **Rede Docker disponível:**
```bash
docker network ls | grep b3-trading-platform_b3-network
# Deve retornar uma linha
```

### Backup (Recomendado)

Antes de importar, fazer backup do banco:

```bash
docker exec b3-timescaledb pg_dump -U b3trading_ts b3trading_market > backup_$(date +%Y%m%d).sql
```

### Execução

**Comando Completo:**

```bash
docker run --rm -it \
  -v "/home/dellno/Área de trabalho/dadoshistoricos.csv:/data" \
  -v /home/dellno/worksapace/b3-trading-platform/scripts:/scripts \
  --network b3-trading-platform_b3-network \
  python:3.11-slim bash -c "pip install -q asyncpg loguru && python3 /scripts/import_historical_data.py"
```

**Explicação dos Parâmetros:**

- `--rm`: Remove container após execução
- `-it`: Modo interativo (permite input do usuário)
- `-v "...:/data"`: Monta pasta de dados como `/data` no container
- `-v .../scripts:/scripts`: Monta pasta de scripts
- `--network`: Conecta à rede Docker do projeto
- `pip install -q`: Instala dependências silenciosamente
- `python3 /scripts/...`: Executa script de importação

### Fluxo de Execução

1. **Conexão ao Banco:**
   ```
   Conectando ao TimescaleDB: b3-timescaledb:5432
   ✅ Conexão estabelecida!
   ```

2. **Fase 1 - Prioritários:**
   ```
   🎯 FASE 1: ATIVOS PRIORITÁRIOS (5 símbolos)
   Símbolos: PETR4, VALE3, ITUB4, BBDC4, ABEV3
   Pasta: dados23e24 (2023-2025)
   
   📊 PETR4
     ✅ 1,888 registros importados (15min)
     ✅ 3,994 registros importados (60min)
     ✅ 499 registros importados (Diário)
   
   [... continua para outros 4 símbolos]
   ```

3. **Validação Fase 1:**
   ```
   ✅ VALIDAÇÃO DA IMPORTAÇÃO
   
   📊 PETR4:
     15min: 2,498 candles | 2024-09-30 → 2026-01-28
     60min: 4,150 candles | 2023-01-02 → 2026-01-28
     Diário: 499 candles | 2023-01-02 → 2024-12-30
   ```

4. **Prompt Fase 2:**
   ```
   🔄 Deseja continuar com a FASE 2 (53 símbolos restantes)? (s/N):
   ```
   - Digitar `s` para continuar
   - Digitar `n` para cancelar

5. **Fase 2 - Restantes:**
   ```
   📈 FASE 2: SÍMBOLOS RESTANTES (53 símbolos)
   
   📊 AZUL4
     ✅ 3,994 registros importados (60min)
     ✅ 499 registros importados (Diário)
   
   [... continua para outros 52 símbolos]
   ```

6. **Estatísticas Finais:**
   ```
   📊 ESTATÍSTICAS FINAIS
   
   Prioritários:
     Arquivos: 15
     Registros: 62,674
     Erros: 0
   
   Restantes:
     Arquivos: 142
     Registros: 712,585
     Erros: 0
   
   TOTAL:
     Arquivos: 157
     Registros: 775,259
     Erros: 0
   
   🎉 Importação concluída com sucesso!
   ```

---

## ✅ Validação

### Queries de Validação

#### 1. Total de Registros por Tabela

```sql
SELECT 'ohlcv_15min' as tabela, COUNT(*) as total 
FROM ohlcv_15min
UNION ALL
SELECT 'ohlcv_60min', COUNT(*) 
FROM ohlcv_60min
UNION ALL
SELECT 'ohlcv_daily', COUNT(*) 
FROM ohlcv_daily;
```

**Resultado Esperado (28/01/2026):**
```
tabela         | total
---------------|--------
ohlcv_15min    | 338847
ohlcv_60min    | 407470
ohlcv_daily    |  28942
```

#### 2. Cobertura dos Prioritários

```sql
SELECT 
    symbol,
    COUNT(*) as candles,
    MIN(time) as primeiro,
    MAX(time) as ultimo,
    MAX(time) - MIN(time) as periodo_dias
FROM ohlcv_daily
WHERE symbol IN ('PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3')
GROUP BY symbol
ORDER BY symbol;
```

**Resultado Esperado:**
```
symbol | candles | primeiro   | ultimo     | periodo_dias
-------|---------|------------|------------|-------------
ABEV3  | 499     | 2023-01-02 | 2024-12-30 | 728 days
BBDC4  | 499     | 2023-01-02 | 2024-12-30 | 728 days
ITUB4  | 499     | 2023-01-02 | 2024-12-30 | 728 days
PETR4  | 499     | 2023-01-02 | 2024-12-30 | 728 days
VALE3  | 499     | 2023-01-02 | 2024-12-30 | 728 days
```

#### 3. Símbolos com Dados Intraday

```sql
-- Símbolos com dados 15min
SELECT symbol, COUNT(*) as candles_15min
FROM ohlcv_15min
GROUP BY symbol
ORDER BY candles_15min DESC
LIMIT 10;

-- Símbolos com dados 60min
SELECT symbol, COUNT(*) as candles_60min
FROM ohlcv_60min
GROUP BY symbol
ORDER BY candles_60min DESC
LIMIT 10;
```

#### 4. Verificar Gaps de Dados

```sql
-- Verificar se há gaps maiores que 7 dias (para 60min)
WITH gaps AS (
    SELECT 
        symbol,
        time,
        LAG(time) OVER (PARTITION BY symbol ORDER BY time) as prev_time,
        time - LAG(time) OVER (PARTITION BY symbol ORDER BY time) as gap
    FROM ohlcv_60min
    WHERE symbol = 'PETR4'
)
SELECT * FROM gaps
WHERE gap > INTERVAL '7 days'
ORDER BY time;
```

#### 5. Validar OHLC (Preços)

```sql
-- Verificar se high >= close >= low (regra OHLC)
SELECT 
    symbol,
    time,
    open, high, low, close
FROM ohlcv_daily
WHERE NOT (high >= close AND close >= low AND high >= open AND open >= low)
LIMIT 10;

-- Resultado esperado: 0 registros (todos devem ser válidos)
```

---

## 🐛 Troubleshooting

### Problema 1: "Pasta não encontrada"

**Erro:**
```
❌ Pasta não encontrada: /home/dellno/Área de trabalho/dadoshistoricos.csv/dados23e24
```

**Causas Possíveis:**
1. Path incorreto (verificar espaços, acentuação)
2. Volume mount não configurado
3. Pasta vazia ou sem permissões

**Solução:**
```bash
# Verificar se pasta existe
ls -la "/home/dellno/Área de trabalho/dadoshistoricos.csv/dados23e24/"

# Verificar permissões
chmod -R 755 "/home/dellno/Área de trabalho/dadoshistoricos.csv/"

# Verificar volume mount no comando docker run
# Deve ter: -v "/home/dellno/Área de trabalho/dadoshistoricos.csv:/data"
```

### Problema 2: "Nenhum registro válido"

**Erro:**
```
⚠️ Nenhum registro válido encontrado
```

**Causas Possíveis:**
1. Formato CSV incorreto
2. Parser esperando 9 colunas mas arquivo tem 8 (Diário)
3. Encoding do arquivo incorreto

**Solução:**
```bash
# Verificar formato do arquivo
head -3 PETR4_B_0_Diário.csv

# Contar colunas (deve ser 8 para Diário, 9 para Intraday)
head -1 PETR4_B_0_Diário.csv | awk -F';' '{print NF}'

# Verificar encoding
file -i PETR4_B_0_Diário.csv
```

### Problema 3: "Connection refused"

**Erro:**
```
Error: Connection refused - b3-timescaledb:5432
```

**Causas Possíveis:**
1. Container TimescaleDB não está rodando
2. Rede Docker incorreta
3. Credenciais incorretas

**Solução:**
```bash
# Verificar se container está rodando
docker ps | grep timescaledb

# Subir container se necessário
cd /home/dellno/worksapace/b3-trading-platform
docker compose up -d b3-timescaledb

# Verificar rede
docker network ls | grep b3

# Testar conexão manualmente
docker exec -it b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "SELECT 1;"
```

### Problema 4: "Dados já existem"

**Aviso:**
```
⚠️ PETR4 já tem 3994 registros em ohlcv_60min (2023-01-01 → 2025-12-31)
Remover e reimportar? (s/N):
```

**Causas:**
- Importação anterior já foi feita

**Opções:**
1. **Reimportar:** Digite `s` (remove dados antigos e importa novos)
2. **Pular:** Digite `n` (mantém dados existentes)

### Problema 5: "ModuleNotFoundError: asyncpg"

**Erro:**
```
ModuleNotFoundError: No module named 'asyncpg'
```

**Causa:**
- Dependências não foram instaladas

**Solução:**
```bash
# Garantir que comando inclui instalação de dependências
# O comando docker run DEVE ter:
bash -c "pip install -q asyncpg loguru && python3 /scripts/import_historical_data.py"
```

---

## 📜 Histórico de Importações

### Importação 1: 28 de Janeiro de 2026

**Data:** 28/01/2026 às 00:58 UTC  
**Executor:** Script `import_historical_data.py` v1.0  
**Resultado:** ✅ Sucesso

**Detalhes:**
- **Origem:** ProfitChart CSV (manual)
- **Pastas:** dados23e24 + dados26
- **Arquivos processados:** 157
- **Registros inseridos:** 775.259
- **Erros:** 0
- **Duração:** ~29 segundos
- **Performance:** ~26.733 registros/segundo

**Estatísticas por Timeframe:**
- 15min: 338.847 registros (42 símbolos)
- 60min: 407.470 registros (57 símbolos)
- Diário: 28.942 registros (58 símbolos)

**Símbolos Prioritários:**
- PETR4: 6.641 registros totais
- VALE3: 24.180 registros totais
- ITUB4: 16.588 registros totais
- BBDC4: 16.590 registros totais
- ABEV3: 16.600 registros totais

**Problemas Resolvidos:**
1. Parser CSV para arquivos Diários (8 colunas vs 9)
2. Volume mount para acesso a pastas do host
3. Rede Docker para conexão com TimescaleDB

**Commit:** [pendente]

---

## 🔄 Atualizações Futuras

### Próximas Importações

**Frequência Recomendada:** Mensal (até dados ao vivo via API)

**Checklist para Próxima Importação:**
- [ ] Baixar dados atualizados do ProfitChart
- [ ] Colocar em pasta `dados{MES}{ANO}`
- [ ] Fazer backup do banco: `pg_dump > backup.sql`
- [ ] Executar script de importação
- [ ] Validar com queries de verificação
- [ ] Atualizar este documento com estatísticas
- [ ] Commitar mudanças no Git

### Melhorias Planejadas

1. **Script Incremental:**
   - Detectar novos arquivos automaticamente
   - Importar apenas dados novos (não duplicar)

2. **Validação Automática:**
   - Rodar queries de validação após importação
   - Alertar se houver gaps ou dados inconsistentes

3. **Logging Persistente:**
   - Salvar logs de importação em arquivo
   - Dashboard com histórico de importações

4. **API de Importação:**
   - Endpoint REST para trigger de importação
   - Upload de arquivos CSV via web

---

## 📞 Referências

- **Script:** [scripts/import_historical_data.py](../scripts/import_historical_data.py)
- **Documentação Geral:** [INSTRUCOES.md](../INSTRUCOES.md)
- **TimescaleDB Docs:** https://docs.timescale.com/
- **asyncpg Docs:** https://magicstack.github.io/asyncpg/

---

**Última Atualização:** 28 de Janeiro de 2026  
**Autor:** Stock-IndiceDev Assistant  
**Status:** ✅ Documentação Completa
