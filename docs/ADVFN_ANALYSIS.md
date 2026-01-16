# 🔍 ADVFN Data Collection - Análise e Alternativas

**Data**: 16 de Janeiro de 2026  
**Status**: ⚠️ ADVFN usa renderização JavaScript - scraping tradicional não funciona

## 🔎 Descoberta

Ao tentar fazer scraping do ADVFN (https://br.advfn.com), descobrimos que:

1. ✅ **Site responde normalmente** (HTTP 200)
2. ✅ **HTML é retornado** (146KB)
3. ❌ **Dados históricos NÃO estão no HTML inicial**
4. ⚠️ **Dados são carregados via JavaScript/AJAX**

### Evidência

```python
# Request simples retorna HTML sem dados
response = requests.get('https://br.advfn.com/bolsa-de-valores/bovespa/petrobras-pn-PETR4/historico')
# HTML contém apenas estrutura vazia
# Dados são populados via JavaScript após carregamento da página
```

## 🛠️ Soluções Possíveis

### ⭐ OPÇÃO 1: Yahoo Finance (yfinance) - **RECOMENDADO**

**Vantagens**:
- ✅ Biblioteca Python oficial
- ✅ Dados históricos completos (anos)
- ✅ Intraday: 1min, 2min, 5min, 15min, 30min, 60min, 90min
- ✅ Sem necessidade de web scraping
- ✅ Fácil de usar
- ✅ Gratuito

**Instalação**:
```bash
pip install yfinance
```

**Uso**:
```python
import yfinance as yf

# Dados diários (máximo histórico)
ticker = yf.Ticker("PETR4.SA")
df = ticker.history(period="max")  # Todos os dados disponíveis

# Dados intraday (últimos 60 dias, 5min)
df_5min = ticker.history(period="60d", interval="5m")

# Dados intraday (última semana, 1min)
df_1min = ticker.history(period="7d", interval="1m")
```

**Limitações**:
- Dados intraday: máximo 60 dias
- 1min: máximo 7 dias
- Rate limiting: ~2000 requests/hora

### OPÇÃO 2: Selenium + ChromeDriver

**Vantagens**:
- ✅ Renderiza JavaScript
- ✅ Funciona com ADVFN
- ✅ Flexível

**Desvantagens**:
- ❌ Complexo de configurar (Docker + Chrome)
- ❌ Lento (carrega página inteira)
- ❌ Consome muitos recursos
- ❌ Frágil (quebra se site mudar)

**Implementação** (não recomendado):
```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)
driver.get('https://br.advfn.com/...')
# Esperar JavaScript carregar
time.sleep(5)
html = driver.page_source
# Parse com BeautifulSoup
```

### OPÇÃO 3: ADVFN API (se existir - pago)

Pesquisa rápida mostra que ADVFN pode ter API paga:
- https://br.advfn.com/produtos/market-data
- Consultar preços e disponibilidade

### OPÇÃO 4: Investing.com (API não oficial)

Biblioteca Python: `investpy`
```bash
pip install investpy
```

**Uso**:
```python
import investpy

# Dados históricos
df = investpy.get_stock_historical_data(
    stock='PETR4',
    country='brazil',
    from_date='01/01/2023',
    to_date='01/01/2024'
)
```

**Limitações**:
- Intraday limitado
- API não oficial (pode quebrar)

### OPÇÃO 5: B3 Market Data (oficial - pago)

B3 oferece dados oficiais via FTP/API:
- http://www.b3.com.br/pt_br/market-data-e-indices/
- Dados históricos completos
- Intraday em tempo real
- **Custo**: Consultar B3

## 📊 Comparação de Fontes

| Fonte | Histórico | Intraday | Gratuito | Complexidade | Recomendação |
|-------|-----------|----------|----------|--------------|--------------|
| **yfinance** | ✅ Max | ✅ 60d | ✅ Sim | ⭐ Baixa | **✅ MELHOR** |
| BRAPI | ⚠️ 3 meses | ❌ Não | ✅ Sim | ⭐ Baixa | ⚠️ Limitado |
| ADVFN (scrape) | ✅ Max | ✅ ? | ✅ Sim | ⭐⭐⭐⭐ Alta | ❌ Não funciona |
| ADVFN (API) | ✅ Max | ✅ Sim | ❌ Pago | ⭐⭐ Média | ⚠️ Consultar preço |
| Alpha Vantage | ✅ 20y | ⚠️ Pago | ⚠️ 25/dia | ⭐⭐ Média | ⚠️ Limitado |
| Investing.com | ✅ Max | ⚠️ Limitado | ✅ Sim | ⭐⭐ Média | ⚠️ API não oficial |
| B3 Official | ✅ Max | ✅ Real-time | ❌ Pago | ⭐⭐⭐ Alta | 💰 Empresarial |

## 🎯 Recomendação Final

### Para o Projeto B3 Trading Platform

**Implementar Yahoo Finance (yfinance)** porque:

1. ✅ **Melhor custo-benefício** (gratuito, robusto)
2. ✅ **Dados históricos completos** (anos de dados diários)
3. ✅ **Intraday suficiente** (60 dias de 5min é bom para backtesting)
4. ✅ **Fácil manutenção** (biblioteca oficial)
5. ✅ **Já testado** em sessões anteriores (funcionou)

### Para Wave3 Strategy (Daily + 60min)

**Combinação Perfeita**:
- **Contexto Diário**: yfinance período="max" (anos de dados)
- **Gatilho 60min**: yfinance período="60d" interval="1h" (suficiente)
- **Fallback**: BRAPI para dados mais recentes

### Próximos Passos

1. ✅ Criar `yfinance_collector.py` (melhorado)
2. ✅ Coletar 2+ anos de dados diários (ITUB4, MGLU3, VALE3, PETR4)
3. ✅ Coletar 60 dias de dados de 60min
4. ✅ Validar qualidade dos dados
5. ✅ Popular TimescaleDB
6. ✅ Integrar com Wave3 Strategy
7. ✅ Proceder para PASSO 12 v2 (ML Integration)

## 📝 Implementação Recomendada

Vou criar um novo collector usando yfinance que:
- Suporta múltiplos timeframes (1min até monthly)
- Download em batch de múltiplos símbolos
- Salvamento em CSV + TimescaleDB
- Retry logic e error handling
- Progress bar
- Validação de dados

**Arquivo**: `scripts/yfinance_collector.py`

---

**Conclusão**: ADVFN não é viável para scraping tradicional. **Yahoo Finance é a melhor alternativa gratuita** com dados históricos completos e intraday suficiente para backtesting profissional.
