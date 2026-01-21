# B3 API Integration - Guia de Uso

## 📋 Visão Geral

Integração com a API B3 de dados históricos para descobrir ativos disponíveis e suas datas de cobertura.

**API Source:** https://cvscarlos.github.io/b3-api-dados-historicos/

## ⚠️ Importante

Esta API fornece apenas a **LISTA de ativos disponíveis**, não os dados históricos completos. Para baixar dados históricos, use:

1. **COTAHIST** (dados oficiais B3) - `scripts/cotahist_parser.py`
2. **BRAPI** (dados em tempo real) - API REST

## 🚀 Comandos Disponíveis

### 1. Verificar Disponibilidade Ibovespa

Verifica quais componentes do Ibovespa estão disponíveis na API:

```bash
docker exec -it b3-data-collector python /app/src/b3_api_integration.py check-ibov
```

**Resultado:**
- ✅ **50/50 componentes disponíveis (100%)**
- Dados desde 2010 até 16/01/2026
- Ativos principais: PETR4, VALE3, ITUB4, BBDC4, etc.

### 2. Análise Completa de Ativos

Analisa todos os 5.200+ ativos disponíveis:

```bash
docker exec -it b3-data-collector python /app/src/b3_api_integration.py analyze
```

**Saída:**
- Total de ativos disponíveis
- Tipos de ativos (PN, ON, Units, etc.)
- Blue chips brasileiras
- Top 20 por histórico

### 3. Recomendações de Download

Sugere quais ativos baixar baseado em liquidez e relevância:

```bash
docker exec -it b3-data-collector python /app/src/b3_api_integration.py recommend
```

**Critérios:**
- **Prioridade 1:** Componentes Ibovespa (50 ativos)
- **Prioridade 2:** Blue chips adicionais (20 ativos)
- **Prioridade 3:** Ativos com histórico longo (>10 anos)

### 4. Exportar Lista Completa (CSV)

Exporta todos os ativos para CSV:

```bash
docker exec -it b3-data-collector python /app/src/b3_api_integration.py export-csv
```

**Arquivo gerado:** `b3_tickers_list.csv`

**Colunas:**
- `ticker` - Código de negociação
- `nome` - Nome curto do ativo
- `especificacao` - Tipo (PN, ON, Unit, etc.)
- `data_min` - Data mínima disponível (YYYYMMDD)
- `data_max` - Data máxima disponível (YYYYMMDD)

## 📊 Ativos Disponíveis

### Componentes Ibovespa (Top 50)

| Ticker | Nome | Histórico |
|--------|------|-----------|
| PETR4 | Petrobras PN | 2010-2026 (16 anos) |
| VALE3 | Vale ON | 2010-2026 (16 anos) |
| ITUB4 | Itaú PN | 2010-2026 (16 anos) |
| BBDC4 | Bradesco PN | 2010-2026 (16 anos) |
| WEGE3 | WEG ON | 2010-2026 (16 anos) |
| B3SA3 | B3 ON | 2018-2026 (8 anos) |
| MGLU3 | Magazine Luiza ON | 2011-2026 (15 anos) |
| ... | ... | ... |

**Total:** 50/50 disponíveis (100%)

### Blue Chips Brasileiras

Além do Ibovespa, temos:
- PETR4, VALE3, ITUB4, BBDC4, ABEV3
- B3SA3, WEGE3, RENT3, SUZB3, RAIL3
- BBAS3, JBSS3, MGLU3, VIVT3, ELET3
- ... (20 ativos principais)

## 🔄 Workflow Completo

### Passo 1: Descobrir Ativos Disponíveis

```bash
# Verificar componentes Ibovespa
docker exec -it b3-data-collector python /app/src/b3_api_integration.py check-ibov

# Resultado: 50/50 disponíveis ✅
```

### Passo 2: Baixar Dados Históricos (COTAHIST)

```bash
# Baixar dados oficiais B3 via COTAHIST
docker exec -it b3-data-collector python /app/src/import_cotahist.py \
    --year 2024 \
    --symbols PETR4 VALE3 ITUB4 BBDC4 ABEV3 WEGE3 MGLU3 B3SA3

# Ou baixar todos os componentes Ibovespa:
docker exec -it b3-data-collector python /app/src/import_cotahist.py \
    --year 2024 \
    --ibovespa
```

### Passo 3: Executar Estratégias de Trading

```bash
# Rodar backtest com Wave3
docker exec -it b3-execution-engine python /app/src/backtest.py \
    --strategy wave3 \
    --symbols PETR4 VALE3 ITUB4

# Ou usar API REST
curl -X POST http://localhost:3000/api/ml/predict/b3 \
    -H "Content-Type: application/json" \
    -d '{"symbol": "PETR4"}'
```

## 📈 Estatísticas

- **Total de ativos:** 5.200+
- **Cobertura histórica:** 2010 - 2026
- **Ibovespa disponível:** 100% (50/50)
- **Blue chips disponíveis:** 100% (20/20)
- **Atualização:** Diária (dados até 16/01/2026)

## 🎯 Casos de Uso

### 1. Backtesting Histórico (Wave3)

Para backtesting de longo prazo, use ativos com histórico desde 2010:

```python
# Ativos ideais para backtesting:
PETR4, VALE3, ITUB4, BBDC4, WEGE3, BBAS3, CSNA3, USIM5, GGBR4, EMBR3
```

### 2. Trading em Produção (Paper/Live)

Para trading em produção, foque em blue chips com alta liquidez:

```python
# Top 10 liquidez:
PETR4, VALE3, ITUB4, BBDC4, ABEV3, B3SA3, WEGE3, MGLU3, BBAS3, RENT3
```

### 3. Machine Learning (Features Engineering)

Para ML, use ativos com dados consistentes e sem gaps:

```python
# Recomendados para ML:
- Ibovespa completo (50 ativos)
- Filtrar: data_min < 20140101 (>10 anos de histórico)
- Evitar: Ativos com muitos gaps (low liquidity)
```

## 🔧 Implementação Técnica

### Classe Principal: `B3APIIntegration`

```python
from b3_api_integration import B3APIIntegration

api = B3APIIntegration()

# Baixar lista de ativos
tickers = api.get_available_tickers()
# Resultado: 5200+ ativos

# Filtrar blue chips
bluechips = api.get_bluechips()
# Resultado: ['PETR4', 'VALE3', ...]

# Filtrar Ibovespa
ibov = api.get_ibov_components()
# Resultado: ['PETR4', 'VALE3', 'ITUB4', ...] (50 ativos)

# Exportar para CSV
api.export_to_csv('b3_tickers_list.csv')
```

### Métodos Disponíveis

| Método | Descrição | Retorno |
|--------|-----------|---------|
| `get_available_tickers()` | Lista todos os ativos | Dict[str, Dict] |
| `get_bluechips()` | Blue chips brasileiras | List[str] |
| `get_ibov_components()` | Componentes Ibovespa | List[str] |
| `filter_top_liquidity(n)` | Top N por histórico | List[str] |
| `export_to_csv(file)` | Exporta para CSV | None |

## ⚙️ Configuração

### Requirements

```txt
requests==2.31.0
pandas==2.1.4
asyncpg==0.29.0
loguru  # Já incluído no projeto
```

### Database Config

```python
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}
```

## 📝 Logs e Debugging

O script usa `loguru` para logs detalhados:

```bash
# Logs mostram:
2026-01-19 20:12:48 | INFO     | 📥 Baixando lista de ativos
2026-01-19 20:12:48 | SUCCESS  | ✅ 5200 ativos disponíveis
2026-01-19 20:12:48 | INFO     | ✓ PETR4    | PETROBRAS | 20100104 -> 20260116
```

## 🚨 Limitações

1. **API não fornece dados históricos completos** - apenas lista de ativos
2. **Atualização dependente do repo original** - pode haver atraso
3. **Alguns ativos têm gaps** - verificar `data_min` e `data_max`
4. **Não inclui dados intraday** - apenas fechamento diário

## 📚 Referências

- **API Original:** https://github.com/cvscarlos/b3-api-dados-historicos
- **B3 Official:** http://www.b3.com.br/
- **COTAHIST Format:** [B3 Documentation](http://www.b3.com.br/data/files/33/67/B9/50/D84057102C784E47AC094EA8/SeriesHistoricas_Layout.pdf)

## 🔗 Integração com Outras Ferramentas

### COTAHIST Parser

```bash
# Após descobrir ativos com B3 API:
python b3_api_integration.py check-ibov

# Baixar dados via COTAHIST:
python import_cotahist.py --year 2024 --ibovespa
```

### Walk-Forward ML

```bash
# Treinar ML com dados B3:
python walk_forward_ml.py \
    --symbols PETR4 VALE3 ITUB4 \
    --table ohlcv_daily \
    --folds 4
```

### Wave3 Strategy

```bash
# Executar Wave3 em ativos B3:
python backtest_wave3_optimized.py
```

---

**Última Atualização:** 19/01/2026  
**Autor:** Stock-IndiceDev Assistant  
**Versão:** 1.0
