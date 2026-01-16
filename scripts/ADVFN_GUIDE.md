# 📊 ADVFN Data Collector - Guia de Uso

## 🎯 Objetivo

Coletar dados históricos e intraday do ADVFN (https://br.advfn.com), incluindo:
- Dados diários (histórico completo)
- Dados intraday (1min, 5min, 15min, 30min, 60min)
- Salvamento em CSV e TimescaleDB

## 🚀 Instalação de Dependências

```bash
# No container execution-engine
docker exec -it b3-execution-engine bash
pip install beautifulsoup4 lxml python-dateutil
```

## 📖 Uso Básico

### 1. Dados Diários (1 ano)

```bash
python scripts/advfn_collector.py \
  --symbols PETR4,VALE3,ITUB4 \
  --timeframe 1d \
  --period 1y
```

### 2. Dados Diários (Máximo Histórico)

```bash
python scripts/advfn_collector.py \
  --symbols PETR4 \
  --timeframe 1d \
  --period max
```

### 3. Dados Intraday (5 minutos - última semana)

```bash
python scripts/advfn_collector.py \
  --symbols PETR4,VALE3 \
  --timeframe 5min \
  --period 5d
```

### 4. Dados Intraday (1 minuto - últimas 24 horas)

```bash
python scripts/advfn_collector.py \
  --symbols PETR4 \
  --timeframe 1min \
  --period 1d
```

### 5. Salvar no TimescaleDB

```bash
python scripts/advfn_collector.py \
  --symbols PETR4,VALE3,ITUB4 \
  --timeframe 1d \
  --period 2y \
  --save-to-db \
  --db-host localhost \
  --db-port 5433 \
  --db-name trading_data \
  --db-user postgres \
  --db-password postgres
```

## 🔧 Parâmetros

| Parâmetro | Descrição | Padrão | Exemplos |
|-----------|-----------|--------|----------|
| `--symbols` | Símbolos B3 (separados por vírgula) | - | `PETR4,VALE3,ITUB4` |
| `--timeframe` | Intervalo de tempo | `1d` | `1min`, `5min`, `15min`, `30min`, `60min`, `1d`, `1w` |
| `--period` | Período histórico | `1y` | `1d`, `5d`, `1w`, `1m`, `3m`, `6m`, `1y`, `2y`, `5y`, `max` |
| `--output-dir` | Diretório de saída para CSVs | `data/advfn` | `data/historical` |
| `--save-to-db` | Salvar no TimescaleDB | `False` | (flag, sem valor) |
| `--db-host` | Host do TimescaleDB | `localhost` | `localhost` |
| `--db-port` | Porta do TimescaleDB | `5433` | `5433` |
| `--db-name` | Nome do banco | `trading_data` | `trading_data` |
| `--db-user` | Usuário do banco | `postgres` | `postgres` |
| `--db-password` | Senha do banco | `postgres` | `postgres` |

## 📊 Timeframes Disponíveis

| Timeframe | Descrição | Período Recomendado |
|-----------|-----------|---------------------|
| `1min` | 1 minuto | 1d (limitado pelo site) |
| `5min` | 5 minutos | 5d |
| `15min` | 15 minutos | 2w |
| `30min` | 30 minutos | 1m |
| `60min` | 60 minutos (1 hora) | 3m |
| `1d` | Diário | max (anos de histórico) |
| `1w` | Semanal | max |

## 🎯 Casos de Uso

### Caso 1: Atualizar Dados Diários (Todos os Ativos)

```bash
# Coletar 2 anos de dados diários para os principais ativos B3
python scripts/advfn_collector.py \
  --symbols PETR4,VALE3,ITUB4,BBDC4,ABEV3,B3SA3,MGLU3,WEGE3 \
  --timeframe 1d \
  --period 2y \
  --save-to-db
```

### Caso 2: Dados Intraday para Wave3 Strategy

```bash
# Contexto diário (2 anos)
python scripts/advfn_collector.py \
  --symbols ITUB4,MGLU3,VALE3 \
  --timeframe 1d \
  --period 2y \
  --save-to-db

# Gatilho 60min (3 meses)
python scripts/advfn_collector.py \
  --symbols ITUB4,MGLU3,VALE3 \
  --timeframe 60min \
  --period 3m \
  --save-to-db
```

### Caso 3: Backtest com Dados de 5min

```bash
# Coletar 1 mês de dados de 5 minutos
python scripts/advfn_collector.py \
  --symbols PETR4 \
  --timeframe 5min \
  --period 1m \
  --save-to-db
```

## 📁 Estrutura de Saída

### CSV

Os dados são salvos em:
```
data/advfn/
  ├── PETR4_advfn_20260116_143052.csv
  ├── VALE3_advfn_20260116_143055.csv
  └── ITUB4_advfn_20260116_143058.csv
```

Formato CSV:
```csv
timestamp,open,high,low,close,volume,symbol
2024-01-15 00:00:00,38.45,38.92,38.12,38.75,45678900,PETR4
2024-01-16 00:00:00,38.80,39.15,38.50,39.00,52341200,PETR4
...
```

### TimescaleDB

Dados são inseridos nas tabelas apropriadas:
- `ohlcv_1d` - Dados diários
- `ohlcv_1h` - Dados de 60 minutos
- `ohlcv_5min` - Dados de 5 minutos
- `ohlcv_1min` - Dados de 1 minuto

## ⚠️ Limitações e Notas

### 1. Rate Limiting
- Delay de 2 segundos entre requests (padrão)
- ADVFN pode bloquear se muitos requests em curto período
- Recomendado: não mais que 10 símbolos por vez

### 2. Dados Intraday
- Disponibilidade limitada (geralmente últimos 30-90 dias)
- 1min: apenas últimas 24-48 horas
- 5min: últimos 5-7 dias
- 60min: últimos 3 meses

### 3. Símbolos Suportados
O script tem mapeamento para principais ativos B3:
- PETR3, PETR4 (Petrobras)
- VALE3 (Vale)
- ITUB3, ITUB4 (Itaú)
- BBDC3, BBDC4 (Bradesco)
- ABEV3 (Ambev)
- B3SA3 (B3)
- MGLU3 (Magazine Luiza)
- WEGE3 (WEG)
- RENT3 (Localiza)
- SUZB3 (Suzano)

Para outros símbolos, pode ser necessário ajustar o mapeamento `name_map` no código.

### 4. Qualidade dos Dados
- Dados podem ter gaps (feriados, fins de semana)
- Volume pode estar em formato abreviado (K, M, B)
- Preços já estão ajustados por splits/proventos (geralmente)

## 🔍 Debugging

### Verificar Logs

```bash
# Ver logs em tempo real
tail -f logs/advfn_collector_*.log
```

### Testar Manualmente

```python
from advfn_collector import ADVFNCollector

collector = ADVFNCollector()
df = collector.fetch_historical_data('PETR4', timeframe='1d', period='1y')
print(df.head())
print(f"Total bars: {len(df)}")
```

### Verificar Dados no TimescaleDB

```sql
-- Contar registros por símbolo
SELECT symbol, COUNT(*) as bars, MIN(timestamp) as first, MAX(timestamp) as last
FROM ohlcv_1d
GROUP BY symbol
ORDER BY bars DESC;

-- Ver últimos 10 registros
SELECT * FROM ohlcv_1d
WHERE symbol = 'PETR4'
ORDER BY timestamp DESC
LIMIT 10;
```

## 🚨 Solução de Problemas

### Erro: Tabela não encontrada

**Problema**: Script não consegue encontrar a tabela HTML com dados

**Solução**:
1. Verificar se o símbolo está no `name_map`
2. Acessar URL manualmente no navegador
3. Verificar se o site mudou a estrutura
4. Adicionar log de debug para ver o HTML retornado

### Erro: Nenhum dado extraído

**Problema**: Parsing falha ao extrair dados da tabela

**Solução**:
1. Verificar formato de data (DD/MM/YYYY)
2. Verificar formato de preço (vírgula vs ponto)
3. Inspecionar HTML com BeautifulSoup
4. Ajustar seletores CSS/XPath

### Erro: Conexão recusada

**Problema**: ADVFN bloqueia requests

**Solução**:
1. Aumentar `rate_limit_delay` (ex: 5 segundos)
2. Adicionar User-Agent variado
3. Usar proxy/VPN
4. Aguardar algumas horas antes de tentar novamente

## 📚 Referências

- ADVFN: https://br.advfn.com
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/
- pandas: https://pandas.pydata.org/
- asyncpg: https://magicstack.github.io/asyncpg/

---

**Próximos Passos**:
1. Testar collector com símbolos reais
2. Validar qualidade dos dados coletados
3. Comparar com BRAPI para verificar consistência
4. Implementar rotina de atualização automática
5. Integrar com pipeline de backtesting
