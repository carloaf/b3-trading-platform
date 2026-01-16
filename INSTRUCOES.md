# 📋 INSTRUÇÕES DE DESENVOLVIMENTO - B3 Trading Platform

> **Data de Criação:** 12 de Janeiro de 2026  
> **Última Atualização:** 16 de Janeiro de 2026  
> **Status:** Em Desenvolvimento - FASE 4 (Machine Learning)

---

## 📊 ESTADO ATUAL DO PROJETO

### ✅ Componentes Implementados

| Componente | Arquivo(s) | Status | Linhas |
|------------|-----------|--------|--------|
| **PostgreSQL Schema** | `infrastructure/postgres/init-db.sql` | ✅ Pronto | - |
| **TimescaleDB Schema** | `infrastructure/timescaledb/init-timescale.sql` | ✅ Pronto | - |
| **Docker Compose** | `docker-compose.yml` | ✅ Pronto | 217 |
| **Makefile** | `Makefile` | ✅ Pronto | 182 |
| **Data Collector** | `services/data-collector/src/main.py` | ✅ Implementado | 419 |
| **Execution Engine** | `services/execution-engine/src/main.py` | ✅ Implementado | 1030 |
| **Strategies Module** | `services/execution-engine/src/strategies/` | ✅ Implementado | 2600+ |
| **Backtest Engine** | `services/execution-engine/src/backtest.py` | ✅ Implementado | 331 |
| **Walk-Forward Optimizer** | `services/execution-engine/src/walk_forward_optimizer.py` | ✅ Implementado | 435 |
| **Paper Trading** | `services/execution-engine/src/paper_trading.py` | ✅ Implementado | - |
| **API Gateway** | `services/api-gateway/src/index.js` | ✅ Implementado | - |
| **Frontend (React)** | `frontend/src/App.jsx` | ✅ Implementado | 496 |
| **Grafana Dashboards** | `infrastructure/grafana/provisioning/` | ✅ Configurado | - |

### 🔧 Estratégias de Trading Disponíveis

1. **`trend_following`** - EMA 9/21 + RSI + Volume
2. **`mean_reversion`** - Bollinger Bands + RSI
3. **`breakout`** - Suporte/Resistência + Volume
4. **`macd_crossover`** - MACD + Signal + Volume
5. **`rsi_divergence`** - RSI Divergence com 4 padrões (bullish, bearish, hidden_bullish, hidden_bearish)
6. **`dynamic_position_sizing`** - Kelly Criterion com ajuste ATR
7. **`wave3`** ⭐ **NOVO** - André Moraes Trend Following Multi-Timeframe
   - Contexto Diário: MME 72 + MME 17
   - Gatilho 60min: Onda 3 de Elliott
   - Regra dos 17 candles
   - Risk:Reward 1:3
   - Win Rate alvo: 50-52%

### 🏗️ Arquitetura de Serviços

```
┌─────────────────────────────────────────────────────────────┐
│                 PORTAS DOS SERVIÇOS                         │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL:      localhost:5432                            │
│  TimescaleDB:     localhost:5433                            │
│  Redis:           localhost:6379                            │
│  Data Collector:  localhost:3002                            │
│  Execution Engine: localhost:3008                           │
│  API Gateway:     localhost:3000                            │
│  Frontend:        localhost:8080                            │
│  Grafana:         localhost:3001                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 PRÓXIMOS PASSOS DE DESENVOLVIMENTO

### FASE 1: Configuração e Validação (Prioridade Alta)

- [ ] **PASSO 1:** Inicializar repositório Git
  ```bash
  cd /home/dellno/worksapace/b3-trading-platform
  git init
  git checkout -b main
  git add -A
  git commit -m "feat: estrutura inicial do projeto"
  git checkout -b dev
  ```

- [ ] **PASSO 2:** Configurar variáveis de ambiente
  ```bash
  cp .env.example .env
  # Editar .env com credenciais reais
  ```

- [ ] **PASSO 3:** Subir infraestrutura e validar
  ```bash
  make up
  make health-check
  ```

- [ ] **PASSO 4:** Testar endpoints básicos
  ```bash
  curl http://localhost:3000/health
  curl http://localhost:3008/health
  curl http://localhost:3002/health
  ```

### FASE 2: Integração com Dados Reais

- [ ] **PASSO 5:** Obter e configurar BRAPI Token
  - Acessar https://brapi.dev
  - Criar conta gratuita
  - Obter token e adicionar ao `.env`

- [ ] **PASSO 6:** Testar coleta de dados BRAPI
  ```bash
  curl http://localhost:3000/api/quote/PETR4
  curl http://localhost:3000/api/historical/PETR4?range=1mo
  ```

- [ ] **PASSO 7:** Configurar MetaTrader 5 (para futuros)
  - Instalar MT5 via Wine ou VM Windows
  - Configurar credenciais no `.env`
  - Implementar conexão MT5 no data-collector
  ---

### FASE 3: Estratégias Avançadas

- [x] **PASSO 8:** Implementar Regime-Adaptive Strategy ✅
  - ✅ Detector de regime de mercado (trending_up/trending_down/ranging/volatile)
  - ✅ Ajuste automático de parâmetros por regime
  - ✅ Endpoint `/api/adaptive-signal/{symbol}` implementado
  - ✅ Seleção automática de estratégia baseada em ADX/ATR
  - Arquivo: `services/execution-engine/src/strategies/strategy_manager.py`

- [x] **PASSO 9:** Implementar Kelly Position Sizing ✅
  - ✅ Cálculo dinâmico de tamanho de posição com Kelly Criterion
  - ✅ Limites de risco por operação (máx 2%)
  - ✅ Integrado com ATR para ajuste de volatilidade
  - ✅ Estratégia `dynamic_position_sizing` implementada
  - Arquivo: `services/execution-engine/src/strategies/dynamic_position_sizing.py`

- [x] **PASSO 8.5:** Implementar RSI Divergence Strategy ✅
  - ✅ 4 padrões de divergência (bullish, bearish, hidden_bullish, hidden_bearish)
  - ✅ Filtros: ADX > 20, Volume > 1.2x, RSI fora de zona neutra
  - ✅ Cálculo de força de sinal (5 componentes)
  - Arquivo: `services/execution-engine/src/strategies/rsi_divergence.py`

- [x] **PASSO 8.6:** Endpoint de Comparação de Estratégias ✅
  - ✅ Endpoint `/api/backtest/compare` implementado
  - ✅ Compara múltiplas estratégias em paralelo
  - ✅ Ranking por Sharpe Ratio
  - ✅ Retorna métricas completas para cada estratégia

- [x] **PASSO 10:** Walk-Forward Optimization ✅
  - ✅ Divide dados em janelas de treino/teste
  - ✅ Otimiza parâmetros usando Optuna (TPE Sampler)
  - ✅ Valida em dados out-of-sample
  - ✅ Suporta Anchored e Rolling Walk-Forward
  - ✅ Endpoint `/api/optimize/walk-forward` implementado
  - ✅ Execução assíncrona com ThreadPoolExecutor
  - Arquivo: `services/execution-engine/src/walk_forward_optimizer.py`

---

### FASE 4: Machine Learning Integration

- [x] **PASSO 11 v1:** Feature Engineering Básico ✅
  - ✅ Indicadores técnicos (EMAs, RSI, MACD, ATR, etc.)
  - ✅ Feature selection básica
  - Arquivo: `services/execution-engine/src/ml/feature_engineering.py`

- [x] **PASSO 11 v2:** Feature Engineering Avançado ✅ **16/01/2026**
  - ✅ 114+ features multi-categoria implementadas
  - ✅ Dados COTAHIST B3: 43 ativos × 250 dias = 10,316 registros
  - ✅ Dados sintéticos intraday: 330k+ registros (15min, 60min, 4h)
  - ✅ Total: 340,428 registros prontos para ML
  - Arquivos: `scripts/cotahist_parser.py`, `scripts/generate_intraday.py`

- [x] **PASSO 12 v2:** ML + Wave3 + SMOTE Integration ✅ **16/01/2026**
  - ✅ **Feature Engineering v2: 114+ features**
    * Trend (30): EMAs, SMAs, MACD, ADX, DI+/DI-
    * Momentum (25): RSI, Stochastic, ROC, Williams %R, CCI, MFI
    * Volatility (20): ATR, Bollinger Bands, Keltner, Historical Vol
    * Volume (15): OBV, VWAP, A/D, CMF, Volume ratios
    * Price Action (12): Body/Shadow ratios, Gaps, Ranges
    * Market Regime (12): Trend detection, Vol regime, Extremes
  
  - ✅ **SMOTE Class Balancing**
    * Antes: 35.24% positives (74/210 samples)
    * Depois: 50.00% balanced (109/109 samples)
    * Biblioteca: imbalanced-learn 0.14.1
  
  - ✅ **Random Forest Performance**
    * **Accuracy: 80.95%** ⭐⭐⭐⭐
    * **Precision: 70.59%** ⭐⭐⭐
    * **Recall: 80.00%** ⭐⭐⭐⭐
    * **F1-Score: 75.00%** ⭐⭐⭐⭐
    * **ROC-AUC: 82.22%** ⭐⭐⭐⭐⭐ (Excelente!)
    * Treinamento: ITUB4, MGLU3, VALE3, PETR4, BBDC4
    * Samples: 210 total (168 train + 42 test)
    * Modelo salvo: `/app/models/ml_wave3_v2.pkl`
  
  - ✅ **Wave3MLStrategy**
    * Workflow: Wave3 → ML Filter → Trade
    * Confidence threshold: 0.6 (default) ou 0.7 (conservador)
    * Filtra falsos positivos do Wave3
    * Meta: Win Rate 50% → 55-60%
  
  - ✅ **Top Features Importantes**
    1. Historical Volatility (30d) - 2.26%
    2. O/C Range - 1.46%
    3. Bollinger Band Width - 1.42%
    💡 Insight: VOLATILIDADE é o preditor mais importante!
  
  - Arquivos: 
    * `services/execution-engine/src/ml/ml_wave3_integration_v2.py` (650 linhas)
    * `services/execution-engine/src/strategies/wave3_ml_strategy.py` (450 linhas)
    * `docs/PASSO_12_V2.md` (documentação completa)
  - Commit: 2d19769 (dev branch)

- [ ] **PASSO 13:** Walk-Forward Optimization para ML 🔄 **PRÓXIMO**
  - Implementar Walk-Forward com retreino periódico
  - Dividir dataset em 4 folds (3 meses train + 1 mês test)
  - Retreinar modelo a cada fold
  - Validar performance out-of-sample
  - Gráficos de equity curve
  - Métricas acumuladas por fold
  - Comparação: ML estático vs ML walk-forward
  - **Objetivo:** Evitar overfitting, modelo adaptativo ao tempo
  
  **Implementação Planejada:**
  ```python
  # walk_forward_ml.py
  class MLWalkForward:
      def __init__(self, folds=4, train_months=3, test_months=1):
          self.folds = folds
          self.train_months = train_months
          self.test_months = test_months
      
      def run_walk_forward(self, symbols, start_date, end_date):
          # Dividir timeline em folds
          # Para cada fold:
          #   - Treinar modelo com train window
          #   - Testar em test window
          #   - Salvar métricas e modelo
          # Consolidar resultados
          pass
  ```
  
  **Métricas a Calcular:**
  - Accuracy média por fold
  - ROC-AUC médio
  - Win Rate por fold
  - Sharpe Ratio por fold
  - Drawdown máximo
  - Consistência entre folds (desvio padrão)
  
  **Endpoint:** `POST /api/ml/walk-forward`
  
  **Arquivo a Criar:** `services/execution-engine/src/ml/walk_forward_ml.py`

- [ ] **PASSO 14:** API REST Endpoints para ML
  - Criar endpoints RESTful para ML
  - Documentação Swagger/OpenAPI
  - Autenticação e rate limiting
  - Validação de inputs
  - Error handling robusto
  
  **Endpoints a Implementar:**
  
  1. **POST /api/ml/train**
     - Treinar modelo ML com símbolos e período customizados
     - Body: `{symbols, model_type, use_smote, test_size}`
     - Response: Métricas de performance + model_id
  
  2. **POST /api/ml/predict**
     - Predição ML para símbolo específico
     - Body: `{symbol, date, model_id}`
     - Response: `{prediction, confidence, features_used}`
  
  3. **POST /api/backtest/wave3-ml**
     - Backtest comparativo: Wave3 puro vs Wave3+ML
     - Body: `{symbols, start_date, end_date, confidence_thresholds}`
     - Response: Métricas lado a lado, gráficos
  
  4. **GET /api/ml/model-info**
     - Informações do modelo treinado
     - Response: `{model_type, features, metrics, trained_on, timestamp}`
  
  5. **GET /api/ml/feature-importance**
     - Top N features mais importantes
     - Query: `?top=20`
     - Response: Lista de features com importâncias
  
  6. **POST /api/ml/retrain**
     - Retreinar modelo com novos dados
     - Body: `{model_id, symbols, incremental}`
     - Response: Novas métricas
  
  7. **POST /api/ml/walk-forward**
     - Executar Walk-Forward optimization
     - Body: `{symbols, folds, train_months, test_months}`
     - Response: Métricas por fold + gráficos
  
  8. **GET /api/ml/models**
     - Listar todos os modelos treinados
     - Response: Lista com model_id, timestamp, metrics
  
  **Autenticação:**
  - JWT tokens
  - API keys para clientes externos
  
  **Rate Limiting:**
  - `/api/ml/train`: 10 requests/hour
  - `/api/ml/predict`: 1000 requests/hour
  - Outros endpoints: 100 requests/minute
  
  **Arquivo a Criar:** `services/api-gateway/src/routes/ml.js`

- [ ] **PASSO 15:** Paper Trading com ML
  - Integrar ML com paper trading existente
  - Testar Wave3+ML em tempo real (dados simulados)
  - Dashboard com sinais ML
  - Alertas quando confidence > threshold
  - Comparação em tempo real: Wave3 vs Wave3+ML
  
  **Implementação Planejada:**
  ```python
  # paper_trading_ml.py
  class MLPaperTrader:
      def __init__(self, strategy='wave3_ml', confidence_threshold=0.6):
          self.strategy = Wave3MLStrategy(confidence_threshold)
          self.positions = []
          self.trades_history = []
      
      async def run_paper_trading(self, symbols):
          while True:
              for symbol in symbols:
                  # Buscar dados atualizados
                  df = await fetch_latest_data(symbol)
                  
                  # Gerar sinal ML
                  signal = self.strategy.generate_signal(df)
                  
                  # Executar trade simulado
                  if signal['action'] == 'buy':
                      self.open_position(symbol, signal)
                  elif signal['action'] == 'sell':
                      self.close_position(symbol)
                  
                  # Atualizar métricas
                  self.update_metrics()
              
              await asyncio.sleep(60)  # 1 minuto
  ```
  
  **Dashboard Features:**
  - Posições abertas (Wave3 vs Wave3+ML)
  - Equity curve em tempo real
  - Win rate acumulado
  - Número de trades filtrados pelo ML
  - Confidence scores dos últimos sinais
  - Alertas visuais para high-confidence signals
  
  **Alertas:**
  - Telegram: "🚀 HIGH CONFIDENCE BUY: ITUB4 @ R$32.50 (confidence: 0.85)"
  - Discord webhook: Embed com gráfico + métricas
  - Email: Resumo diário de performance
  
  **Métricas a Monitorar:**
  - Win Rate: Wave3 puro vs Wave3+ML
  - Sharpe Ratio comparativo
  - Número de trades: redução esperada
  - Average confidence dos trades executados
  - False positive rate (ML filtering effectiveness)
  
  **Endpoint:** `GET /api/paper/ml-status`
  
  **Arquivo a Criar:** `services/execution-engine/src/paper_trading_ml.py`

- [ ] **PASSO 16:** Detecção de Anomalias com Isolation Forest
  - Detectar condições anormais de mercado
  - Alerta automático em situações atípicas
  - Integração com estratégias para pausar trading

---

### FASE 5: Alertas e Notificações

- [ ] **PASSO 17:** Integração Telegram Bot
  - Criar bot no @BotFather
  - Implementar notificações de sinais
  - Comandos de status via chat
  - Alertas de high-confidence ML signals

- [ ] **PASSO 18:** Integração Discord Webhook
  - Criar webhook no Discord
  - Notificações em canal dedicado
  - Embeds com gráficos e métricas

---

### FASE 6: Produção e Monitoramento

- [ ] **PASSO 19:** Configurar Alertas Grafana
  - Alertas de drawdown > 5%
  - Alertas de serviço degradado
  - Notificação por email/Telegram
  - Dashboard ML metrics

- [ ] **PASSO 20:** Otimização de Performance
  - Cache agressivo no Redis
  - Compressão de dados históricos
  - Rate limiting na API
  - Connection pooling

- [ ] **PASSO 21:** Documentação Final
  - API documentation com Swagger
  - Guia de deployment
  - Runbook operacional
  - ML model documentation

---

## 📁 ESTRUTURA DE BRANCHES

```
main (produção)
  └── dev (desenvolvimento)
       ├── feature/passo-08-regime-adaptive
       ├── feature/passo-09-kelly-sizing
       ├── feature/passo-10-walk-forward
       └── feature/passo-XX-descricao
```

---

## 🛠️ COMANDOS ÚTEIS

### Docker

```bash
# Subir todos os serviços
make up

# Ver logs em tempo real
make logs

# Parar tudo
make down

# Rebuild específico
docker compose up -d --build execution-engine
```

### Desenvolvimento

```bash
# Executar backtest via API
curl -X POST http://localhost:3000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "trend_following",
    "symbol": "PETR4",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000
  }'

# Obter sinais
curl http://localhost:3000/api/signals/PETR4?strategy=trend_following

# Status do paper trading
curl http://localhost:3000/api/paper/status
```

### Git

```bash
# Criar feature branch
git checkout dev
git checkout -b feature/passo-XX-nome

# Commitar e fazer merge
git add -A
git commit -m "PASSO XX: Descrição"
git checkout dev
git merge feature/passo-XX-nome
git push origin dev

# Sync para main
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

## ⚠️ NOTAS IMPORTANTES

1. **Nunca desenvolver na branch `main`** - usar sempre `dev` ou feature branches
2. **Todas as dependências devem ser instaladas via Docker** - não instalar localmente
3. **Testar em paper trading antes de qualquer mudança em estratégias**
4. **Manter logs detalhados** - usar `loguru` com níveis apropriados
5. **Backups do TimescaleDB** - configurar rotina de backup

---

## 📞 RECURSOS

- **BRAPI Docs:** https://brapi.dev/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **TimescaleDB:** https://docs.timescale.com/
- **pandas-ta:** https://github.com/twopirllc/pandas-ta
- **MetaTrader 5 Python:** https://www.mql5.com/en/docs/integration/python_metatrader5

---

*Última atualização: 16 de Janeiro de 2026*  
*Status Atual: PASSO 12 v2 COMPLETO ✅ | Próximo: PASSO 13 (Walk-Forward ML)*
