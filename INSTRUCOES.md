# 📋 INSTRUÇÕES DE DESENVOLVIMENTO - B3 Trading Platform

> **Data de Criação:** 12 de Janeiro de 2026  
> **Última Atualização:** 13 de Janeiro de 2026  
> **Status:** Em Desenvolvimento

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
| **Execution Engine** | `services/execution-engine/src/main.py` | ✅ Implementado | 876 |
| **Strategies Module** | `services/execution-engine/src/strategies/` | ✅ Implementado | 2600+ |
| **Backtest Engine** | `services/execution-engine/src/backtest.py` | ✅ Implementado | 331 |
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

---

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

- [ ] **PASSO 10:** Walk-Forward Optimization
  - Dividir dados em janelas de treino/teste
  - Otimizar parâmetros por janela
  - Validar out-of-sample performance

---

### FASE 4: Machine Learning

- [ ] **PASSO 11:** Feature Engineering
  - Criar features técnicas adicionais
  - Normalização e scaling
  - Feature selection

- [ ] **PASSO 12:** Modelo de Classificação de Sinais
  - Random Forest / XGBoost para filtrar sinais
  - Treinamento com dados históricos
  - Integração com estratégias existentes

- [ ] **PASSO 13:** Detecção de Anomalias
  - Isolation Forest para detectar condições anormais
  - Alerta automático em situações atípicas

---

### FASE 5: Alertas e Notificações

- [ ] **PASSO 14:** Integração Telegram Bot
  - Criar bot no @BotFather
  - Implementar notificações de sinais
  - Comandos de status via chat

- [ ] **PASSO 15:** Integração Discord Webhook
  - Criar webhook no Discord
  - Notificações em canal dedicado

---

### FASE 6: Produção e Monitoramento

- [ ] **PASSO 16:** Configurar Alertas Grafana
  - Alertas de drawdown > 5%
  - Alertas de serviço degradado
  - Notificação por email/Telegram

- [ ] **PASSO 17:** Otimização de Performance
  - Cache agressivo no Redis
  - Compressão de dados históricos
  - Rate limiting na API

- [ ] **PASSO 18:** Documentação Final
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

*Atualizado em: 12 de Janeiro de 2026*
