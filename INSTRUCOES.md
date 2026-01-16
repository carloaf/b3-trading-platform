# 📋 INSTRUÇÕES DE DESENVOLVIMENTO - B3 Trading Platform

> **Data de Criação:** 12 de Janeiro de 2026  
> **Última Atualização:** 16 de Janeiro de 2026  
> **Status:** Em Desenvolvimento - PASSO 11 Completo (ML Integration)

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
| **Execution Engine** | `services/execution-engine/src/main.py` | ✅ Implementado | 2574 |
| **Strategies Module** | `services/execution-engine/src/strategies/` | ✅ Implementado | 3500+ |
| **Backtest Engine** | `services/execution-engine/src/backtest.py` | ✅ Implementado | 331 |
| **Walk-Forward Optimizer** | `services/execution-engine/src/walk_forward_optimizer.py` | ✅ Implementado | 435 |
| **ML Feature Engineering** | `services/execution-engine/src/ml/feature_engineering.py` | ✅ Implementado | 390 |
| **ML Training Script** | `services/execution-engine/src/ml/train_ml_model.py` | ✅ Implementado | 396 |
| **ML Signal Classifier** | `services/execution-engine/src/ml/signal_classifier.py` | ✅ Pronto | 412 |
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

### FASE 1: Configuração e Validação (✅ COMPLETA)

- [x] **PASSO 1:** Inicializar repositório Git ✅
  - Commit: `7173fc5` - feat: estrutura inicial do projeto B3 Trading Platform

- [x] **PASSO 2:** Configurar variáveis de ambiente ✅
  - `.env.example` criado com todas as variáveis necessárias

- [x] **PASSO 3:** Subir infraestrutura e validar ✅
  - Docker Compose v2 funcional
  - Commit: `4d4bd8d` - fix: corrigir Dockerfiles e dependências Python

- [x] **PASSO 4:** Testar endpoints básicos ✅
  - Health checks implementados em todos os serviços

### FASE 2: Integração com Dados Reais (✅ COMPLETA)

- [x] **PASSO 5:** Obter e configurar BRAPI Token ✅
  - Integração BRAPI implementada no data-collector

- [x] **PASSO 6:** Testar coleta de dados BRAPI ✅
  - Endpoints `/api/quote` e `/api/historical` funcionais
  - Commit: `ab4db77` - OPTION B: Coleta de dados históricos BRAPI + Wave3 multi-timeframe

- [x] **PASSO 7:** Wave3 Strategy Implementation ✅
  - Commit: `7f6c55b` - feat: Implementar Wave3 Strategy (André Moraes)
  - Commit: `953c082` - feat: OPÇÃO A - Wave3 Daily Strategy Completa
  - Multi-timeframe (Daily + 60min) + Daily-only versions
  - Regra dos 17 candles + Risk:Reward 1:3
  - Backtesting: ITUB4 +426.51% (51 trades, 2 anos)

### FASE 3: Estratégias Avançadas (✅ COMPLETA)

### FASE 3: Estratégias Avançadas (✅ COMPLETA)

- [x] **PASSO 8:** Implementar Regime-Adaptive Strategy ✅
  - ✅ Detector de regime de mercado (trending_up/trending_down/ranging/volatile)
  - ✅ Ajuste automático de parâmetros por regime
  - ✅ Endpoint `/api/adaptive-signal/{symbol}` implementado
  - ✅ Seleção automática de estratégia baseada em ADX/ATR
  - Commit: `70778bc` - PASSO 8-9: Implementação de arquitetura OOP para estratégias
  - Arquivo: `services/execution-engine/src/strategies/strategy_manager.py`

- [x] **PASSO 9:** Implementar Kelly Position Sizing ✅
  - ✅ Cálculo dinâmico de tamanho de posição com Kelly Criterion
  - ✅ Limites de risco por operação (máx 2%)
  - ✅ Integrado com ATR para ajuste de volatilidade
  - ✅ Estratégia `dynamic_position_sizing` implementada
  - Commit: `70778bc` - incluído no mesmo commit do PASSO 8
  - Arquivo: `services/execution-engine/src/strategies/dynamic_position_sizing.py`

- [x] **PASSO 8.5:** Implementar RSI Divergence Strategy ✅
  - ✅ 4 padrões de divergência (bullish, bearish, hidden_bullish, hidden_bearish)
  - ✅ Filtros: ADX > 20, Volume > 1.2x, RSI fora de zona neutra
  - ✅ Cálculo de força de sinal (5 componentes)
  - Commit: `70778bc` - incluído na refatoração de estratégias
  - Arquivo: `services/execution-engine/src/strategies/rsi_divergence.py`

- [x] **PASSO 8.6:** Endpoint de Comparação de Estratégias ✅
  - ✅ Endpoint `/api/backtest/compare` implementado
  - ✅ Compara múltiplas estratégias em paralelo
  - ✅ Ranking por Sharpe Ratio
  - ✅ Retorna métricas completas para cada estratégia
  - Commit: `4b7441f` - feat(PASSO 8-9): Implementar endpoints adaptativo e comparação

- [x] **PASSO 10:** Walk-Forward Optimization ✅
  - ✅ Divide dados em janelas de treino/teste
  - ✅ Otimiza parâmetros usando Optuna (TPE Sampler)
  - ✅ Valida em dados out-of-sample
  - ✅ Suporta Anchored e Rolling Walk-Forward
  - ✅ Endpoint `/api/optimize/walk-forward` implementado
  - ✅ Execução assíncrona com ThreadPoolExecutor
  - Commit: `01e1fb5` - feat(PASSO 10): Implementar Walk-Forward Optimization com Optuna
  - Arquivo: `services/execution-engine/src/walk_forward_optimizer.py`

---

### FASE 4: Machine Learning e Predição (✅ PASSO 11 COMPLETO, PASSOS 12-14 PENDENTES)

### FASE 4: Machine Learning e Predição (✅ PASSO 11 COMPLETO, PASSOS 12-14 PENDENTES)

- [x] **PASSO 11 (Versão Anterior):** Feature Engineering Básico ✅
  - Commit: `1e13245` - PASSO 11: Implementar Feature Engineering para ML
  - 40+ features técnicas iniciais

- [x] **PASSO 12 (Versão Anterior):** ML Signal Classifier ✅
  - Commit: `21eb2d8` - PASSO 12: Implementar ML Signal Classifier (Random Forest & XGBoost)
  - Random Forest + XGBoost para classificação de sinais
  - Arquivo: `services/execution-engine/src/ml/signal_classifier.py` (412 linhas)

- [x] **PASSO 13 (Versão Anterior):** Anomaly Detection ✅
  - Commit: `8bada51` - PASSO 13: Implementar Anomaly Detection com Isolation Forest
  - Isolation Forest para detectar condições anormais
  - Arquivo: `services/execution-engine/src/ml/anomaly_detector.py`

- [x] **PASSO 16 (Versão Anterior):** Dashboard ML + Backtest Comparativo ✅
  - Commit: `2685047` - Opção C: Dashboard Web ML - PASSO 16 COMPLETO
  - Commit: `91a1718` - Opções A e B: Backtesting Comparativo + Hiperparâmetros ML
  - Dashboard web interativo para ML
  - Hiperparâmetros tuning
  - Performance analytics

- [x] **PASSO 18 (Versão Anterior):** ML Paper Trading ✅
  - Commit: `ffdf2aa` - PASSO 18: Implementar ML Paper Trading Automatizado
  - Commit: `5e27fac` - Fix: Corrigir bugs do ML Paper Trader
  - Paper trading automatizado com ML
  - Arquivo: `services/execution-engine/src/ml/ml_paper_trader.py`

- [x] **PASSO 11 (NOVA VERSÃO - COMPLETO):** Feature Engineering + ML Integration ✅ 🆕
  - ✅ **114 indicadores técnicos** implementados nativamente (pandas/numpy)
  - ✅ 8 categorias de features: Trend, Momentum, Volatility, Volume, Patterns, Regime, Price Action, Statistical
  - ✅ Feature engineering sem dependências externas (pandas_ta reescrito)
  - ✅ Script CLI completo: `train_ml_model.py`
  - ✅ Random Forest classifier treinado (1,485 amostras, 2 anos, 3 ativos)
  - ✅ Cross-validation (5 folds) + feature importance analysis
  - ✅ Model persistence (pickle)
  - ✅ **Resultados**: Train 96.2%, CV 57.8% ± 13.8%, Test 69.0%, ROC-AUC 0.54
  - ✅ **Top Features**: ema_72, ema_50, vpt, resistance_20, kc_middle
  - ✅ Documentação: `docs/PASSO_11_ML_INTEGRATION.md` + `docs/QUICK_START_ML.md`
  - ⚠️ **Limitação identificada**: Class imbalance (28% lucrativos vs 72%)
  - Commit: `aa8a7a6` - PASSO 11: ML Integration - Feature Engineering (114 indicators) + Random Forest Training
  - Commit: `8f74333` - Merge PASSO 11: ML Integration (Feature Engineering + RF Training)
  - Commit: `c3c9ec1` - Merge dev: PASSO 11 ML Integration complete
  - Commit: `e8e6c9f` - docs: Add QUICK_START_ML.md - comprehensive ML integration guide
  - Arquivo: `services/execution-engine/src/ml/feature_engineering.py` (390 linhas)
  - Arquivo: `services/execution-engine/src/ml/train_ml_model.py` (396 linhas)

- [ ] **PASSO 12 (NOVA VERSÃO):** Integração ML com Estratégias + Melhorias 🎯 PRÓXIMO
  - [ ] Implementar SMOTE para balanceamento de classes
  - [ ] Ajustar threshold de classificação (testar 0.3, 0.4 vs 0.5)
  - [ ] Integrar ML classifier com Wave3 Strategy
    - Adicionar filtro ML em `wave3_daily_strategy.py`
    - Modificar `generate_signal()` para usar `classifier.predict()`
    - Filtrar sinais onde `ml_signal==1` AND `ml_confidence>0.6`
  - [ ] Comparar backtests: Wave3 puro vs Wave3 + ML filtering
  - [ ] Testar XGBoost com `scale_pos_weight` ajustado
  - [ ] Feature selection (reduzir de 114 para ~50 features top)

- [ ] **PASSO 13 (NOVA VERSÃO):** Hyperparameter Tuning + Walk-Forward ML
  - [ ] Utilizar `ml/hyperparameter_tuner.py` com Optuna
  - [ ] GridSearch: `n_estimators`, `max_depth`, `min_samples_split`
  - [ ] Testar diferentes `profit_threshold` (0.01, 0.015, 0.02, 0.03)
  - [ ] Testar diferentes `forward_periods` (3, 5, 10, 20 dias)
  - [ ] Walk-forward optimization para ML (retrain a cada 60 dias)
  - [ ] Avaliar degradação de performance ao longo do tempo

- [ ] **PASSO 14 (NOVA VERSÃO):** Ensemble Methods + Production Ready
  - [ ] Ensemble: Random Forest + XGBoost (voting/stacking)
  - [ ] Integrar anomaly detector com paper trading (já existe)
  - [ ] Auto-retrain trigger baseado em performance degradation
  - [ ] Model versioning e A/B testing

---

### FASE 5: Alertas e Notificações

- [ ] **PASSO 15:** Integração Telegram Bot
  - Criar bot no @BotFather
  - Implementar notificações de sinais
  - Comandos de status via chat

- [ ] **PASSO 16:** Integração Discord Webhook
  - Criar webhook no Discord
  - Notificações em canal dedicado

---

### FASE 6: Produção e Monitoramento

- [ ] **PASSO 17:** Configurar Alertas Grafana
  - Alertas de drawdown > 5%
  - Alertas de serviço degradado
  - Notificação por email/Telegram

- [ ] **PASSO 18:** Otimização de Performance
  - Cache agressivo no Redis
  - Compressão de dados históricos
  - Rate limiting na API

- [ ] **PASSO 19:** Documentação Final
  - API documentation com Swagger
  - Guia de deployment
  - Runbook operacional

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

# Treinar modelo ML (Random Forest)
docker exec b3-execution-engine python3 /app/src/ml/train_ml_model.py \
  --symbols ITUB4,MGLU3,VALE3 \
  --model-type random_forest \
  --profit-threshold 0.02 \
  --forward-periods 5

# Ver modelos ML salvos
docker exec b3-execution-engine ls -lh /tmp/ml_models/
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
- **scikit-learn:** https://scikit-learn.org/stable/
- **XGBoost:** https://xgboost.readthedocs.io/

---

## 📊 PROGRESSO DO PROJETO

### ✅ Completado (PASSOS 1-11)
- ✅ Infraestrutura Docker completa (PASSOS 1-4)
- ✅ Integração BRAPI + coleta de dados (PASSOS 5-6)
- ✅ Wave3 Strategy (André Moraes) - Multi-timeframe + Daily (PASSO 7)
- ✅ 7 estratégias de trading implementadas
- ✅ Regime-Adaptive Strategy (PASSO 8)
- ✅ Kelly Position Sizing (PASSO 9)
- ✅ RSI Divergence (PASSO 8.5)
- ✅ Comparação de Estratégias (PASSO 8.6)
- ✅ Walk-Forward Optimization (PASSO 10)
- ✅ **Feature Engineering Básico** (PASSO 11 versão 1 - 40+ features)
- ✅ **ML Signal Classifier** (PASSO 12 versão 1 - RF/XGBoost)
- ✅ **Anomaly Detection** (PASSO 13 versão 1 - Isolation Forest)
- ✅ **Dashboard ML + Performance Analytics** (PASSO 16 versão 1)
- ✅ **ML Paper Trading** (PASSO 18 versão 1)
- ✅ **ML Integration v2** (PASSO 11 versão 2 - 114 features + RF training)

### 🔄 Em Andamento (PASSO 12 v2)
- Integração ML v2 com Wave3 Strategy
- SMOTE para balanceamento de classes
- Threshold tuning para melhorar recall

### 📋 Próximos (PASSOS 12-19)
- PASSO 12 v2: Integração ML + Melhorias
- PASSO 13 v2: Hyperparameter tuning + Walk-Forward ML
- PASSO 14 v2: Ensemble methods + Production ready
- PASSO 15: Telegram Bot notifications
- PASSO 16: Discord Webhook
- PASSO 17: Alertas Grafana
- PASSO 18: Otimização de Performance
- PASSO 19: Documentação Final

### 📈 Histórico de Commits Principais
```
e8e6c9f - docs: Add QUICK_START_ML.md (16/01/2026)
c3c9ec1 - Merge dev: PASSO 11 ML Integration complete (16/01/2026)
aa8a7a6 - PASSO 11 v2: Feature Engineering (114 indicators) + RF Training (16/01/2026)
ab4db77 - OPTION B: Coleta de dados BRAPI + Wave3 multi-timeframe (15/01/2026)
953c082 - Wave3 Daily Strategy Completa (15/01/2026)
ffdf2aa - PASSO 18 v1: ML Paper Trading Automatizado
2685047 - PASSO 16 v1: Dashboard Web ML
91a1718 - Backtesting Comparativo + Hiperparâmetros ML
8bada51 - PASSO 13 v1: Anomaly Detection
21eb2d8 - PASSO 12 v1: ML Signal Classifier
1e13245 - PASSO 11 v1: Feature Engineering Básico
01e1fb5 - PASSO 10: Walk-Forward Optimization
4b7441f - PASSO 8-9: Endpoints adaptativo e comparação
70778bc - PASSO 8-9: Arquitetura OOP + RSI Divergence + Kelly
7173fc5 - feat: estrutura inicial do projeto
```

---

*Atualizado em: 16 de Janeiro de 2026*
