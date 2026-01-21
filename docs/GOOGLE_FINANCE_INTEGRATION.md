# Google Finance Integration - Guia Completo

## 📊 Status Atual: LIMITADO ⚠️

**Data:** 19/01/2026  
**Autor:** Stock-IndiceDev Assistant

---

## 🚨 PROBLEMAS IDENTIFICADOS

### 1. Yahoo Finance API (yfinance)
- **Status:** ❌ BLOQUEADO
- **Erro:** `429 Too Many Requests`
- **Causa:** Rate limiting agressivo do Yahoo Finance
- **Sintoma:** `Expecting value: line 1 column 1 (char 0)`
- **Teste realizado:** 
  ```bash
  docker exec b3-data-collector python google_finance_integration.py test PETR4
  # Resultado: Sem dados retornados
  ```

### 2. Google Finance Direto
- **Formato sugerido:** `GOOGLEFINANCE("BVMF:B3SA3", "price", TODAY(), "DAILY")`
- **Problema:** Requer Google Sheets API ou web scraping
- **Complexidade:** Alta (requer credenciais OAuth2 ou Service Account)

---

## ✅ SOLUÇÕES DISPONÍVEIS

### Solução 1: Dados Simulados Intraday (IMPLEMENTADO)

**Arquivo:** `scripts/generate_intraday.py`

**Como funciona:**
1. Lê dados diários do TimescaleDB (ohlcv_daily)
2. Divide cada dia em N candles (baseado em 6h de pregão B3: 10h-16h)
3. Interpola preços linearmente com random walk
4. Distribui volume uniformemente
5. Salva em tabela `ohlcv_XXm` (15m, 60m, etc.)

**Uso:**
```bash
# Gerar 60 min para Ibovespa
docker exec b3-data-collector python /app/src/generate_intraday.py ibovespa 60

# Gerar 15 min para ativos específicos
docker exec b3-data-collector python /app/src/generate_intraday.py symbols PETR4 VALE3 15
```

**Vantagens:**
- ✅ Funciona offline
- ✅ Sem rate limits
- ✅ Baseado em dados reais (COTAHIST)
- ✅ Rápido (local)

**Desvantagens:**
- ⚠️ Não reflete padrões intraday REAIS
- ⚠️ Volume distribuído artificialmente
- ⚠️ Apenas para backtesting experimental
- ⚠️ Não tem gaps ou movimentos bruscos reais

---

### Solução 2: COTAHIST + B3 API (RECOMENDADO)

**Status:** ✅ IMPLEMENTADO

**Fluxo completo:**
1. **Descobrir tickers:** `b3_api_integration.py check-ibov`
2. **Baixar dados diários:** `import_cotahist.py --year 2024 --ibovespa`
3. **Gerar intraday:** `generate_intraday.py ibovespa 60`

**Cobertura:**
- 50 componentes Ibovespa
- 5.200+ ativos B3 disponíveis
- Histórico desde 2010
- Dados diários 100% reais (COTAHIST oficial B3)
- Dados intraday SIMULADOS (baseados em diário)

---

### Solução 3: APIs Pagas de Dados Financeiros

Para produção com dados intraday REAIS, considere:

#### 3.1. Alpha Vantage
- **Site:** https://www.alphavantage.co/
- **Plano Grátis:** 500 requests/dia
- **Intraday:** 1min, 5min, 15min, 30min, 60min
- **Cobertura:** B3 via BVMF:PETR4
- **Setup:**
  ```python
  import requests
  API_KEY = 'YOUR_API_KEY'
  url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=BVMF:PETR4&interval=60min&apikey={API_KEY}'
  ```

#### 3.2. Polygon.io
- **Site:** https://polygon.io/
- **Plano Grátis:** 5 requests/minuto
- **Intraday:** Agregados de 1min a 1 dia
- **Cobertura:** Global (incluindo Brasil via Polygon.io/markets)
- **Setup:**
  ```python
  from polygon import RESTClient
  client = RESTClient('API_KEY')
  aggs = client.get_aggs('BVMF:PETR4', 1, 'hour', '2024-01-01', '2024-12-31')
  ```

#### 3.3. IEX Cloud
- **Site:** https://iexcloud.io/
- **Plano Grátis:** 50k mensagens/mês
- **Intraday:** 1min, 5min, 10min, 15min, 30min, 1h
- **Cobertura:** US e international (verificar Brasil)

#### 3.4. Twelve Data
- **Site:** https://twelvedata.com/
- **Plano Grátis:** 800 requests/dia
- **Intraday:** 1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h
- **Cobertura:** B3 via BVMF:PETR4

---

### Solução 4: Broker APIs (Melhor para Trading Ao Vivo)

#### 4.1. MetaTrader 5
- **Status:** Planejado (INSTRUCOES.md PASSO 7)
- **Dados:** Real-time tick-by-tick
- **Cobertura:** Depende do broker
- **Setup:** Requer conta em broker MT5

#### 4.2. Interactive Brokers (IBKR)
- **API:** TWS API ou IB Gateway
- **Dados:** Real-time Level I/II
- **Cobertura:** B3 completo
- **Custo:** Requer conta IBKR

---

## 📝 IMPLEMENTAÇÃO: Google Finance Integration (yfinance)

**Arquivo:** `services/data-collector/src/google_finance_integration.py`

**Status:** ❌ NÃO FUNCIONAL (rate limit)

**Classe:** `GoogleFinanceIntegration`

**Métodos:**
- `convert_b3_to_yahoo(symbol)` - PETR4 → PETR4.SA
- `get_intraday_data_yfinance(symbol, interval, period)` - Download via yfinance
- `get_intraday_data_gsheets(symbol, credentials_path)` - Via Google Sheets API (não implementado)
- `save_to_timescaledb(df, table)` - Salva em ohlcv_XXm

**CLI Commands:**
```bash
# Testar um ticker
python google_finance_integration.py test PETR4

# Download Ibovespa
python google_finance_integration.py download-ibovespa 60m 60d

# Download customizado
python google_finance_integration.py download PETR4 VALE3 --interval 15m --period 7d
```

**Dependências:**
```txt
yfinance==0.2.38  # Google/Yahoo Finance
google-auth==2.28.0  # Para Google Sheets API (opcional)
google-api-python-client==2.115.0  # Google Sheets (opcional)
```

**Limitações Atuais:**
- ❌ Yahoo Finance bloqueando requests (429)
- ❌ Google Sheets API não implementado completamente
- ⚠️ Dados intraday limitados: max 60d para 60m, 7d para 15m

---

## 🎯 RECOMENDAÇÃO FINAL

### Para Desenvolvimento/Backtesting:
✅ **Usar:** `generate_intraday.py` (simulação baseada em COTAHIST)
- Suficiente para testar estratégias
- Sem custos
- Sem rate limits

### Para Produção:
✅ **Usar:** Alpha Vantage (500 req/dia grátis) ou Twelve Data (800 req/dia)
- Dados intraday reais
- APIs REST simples
- Cobertura B3

### Para Trading Ao Vivo:
✅ **Usar:** MetaTrader 5 (PASSO 7) ou Interactive Brokers
- Real-time tick-by-tick
- Baixa latência
- Execução integrada

---

## 📊 PRÓXIMOS PASSOS

1. **Implementar Alpha Vantage integration** (alternativa ao Yahoo Finance)
   - Criar `alpha_vantage_integration.py`
   - Suportar intraday 1min-60min
   - Rate limiting: 5 req/minuto (free tier)

2. **Completar Google Sheets API** (se necessário)
   - Requer Service Account credentials
   - Fórmula: `=GOOGLEFINANCE("BVMF:B3SA3", "all", TODAY()-60, TODAY(), "DAILY")`
   - Complexidade: Criar sheet temporário + parsear resultado

3. **Implementar MetaTrader 5 integration** (PASSO 7 de INSTRUCOES.md)
   - Real-time data via MT5 Python API
   - Requer broker com MT5 (XP, Rico, Modal, etc.)

---

## 📚 REFERÊNCIAS

- Yahoo Finance: https://finance.yahoo.com/
- Google Finance: https://www.google.com/finance/
- Alpha Vantage Docs: https://www.alphavantage.co/documentation/
- Polygon.io Docs: https://polygon.io/docs/stocks
- IEX Cloud Docs: https://iexcloud.io/docs/
- Twelve Data Docs: https://twelvedata.com/docs
- yfinance GitHub: https://github.com/ranaroussi/yfinance
- B3 COTAHIST: http://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/

---

*Última atualização: 19/01/2026*  
*Conclusão: Yahoo Finance bloqueado, usar dados simulados ou APIs pagas*
