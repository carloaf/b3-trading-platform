# 📋 PLANO DE IMPLEMENTAÇÃO - B3 Trading Platform

## 🎯 Visão Geral

Este documento detalha o plano de implementação passo a passo para a plataforma de trading B3.

---

## 📁 Estrutura do Projeto

```
b3-trading-platform/
├── README.md                    # Documentação principal
├── docker-compose.yml           # Orquestração de containers
├── .env.example                 # Template de variáveis de ambiente
├── Makefile                     # Comandos de build/deploy
│
├── infrastructure/
│   ├── postgres/
│   │   └── init-db.sql         # Schema do PostgreSQL
│   ├── timescaledb/
│   │   └── init-timescale.sql  # Schema do TimescaleDB
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           └── dashboards/
│
├── services/
│   ├── execution-engine/        # Motor de execução (FastAPI)
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── strategies.py
│   │   │   ├── backtest.py
│   │   │   └── paper_trading.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── data-collector/          # Coleta de dados (FastAPI)
│   │   ├── src/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── api-gateway/             # Gateway API (Express)
│       ├── src/
│       │   └── index.js
│       ├── Dockerfile
│       └── package.json
│
└── frontend/                    # Dashboard (React + Vite)
    ├── src/
    │   ├── App.jsx
    │   └── main.jsx
    ├── Dockerfile
    └── package.json
```

---

## 🚀 Passo a Passo de Implementação

### Passo 1: Configuração Inicial (10 min)

```bash
# 1. Navegue até a pasta do projeto
cd /home/dellno/worksapace/b3-trading-platform

# 2. Copie o arquivo de ambiente
cp .env.example .env

# 3. Edite as configurações conforme necessário
nano .env
```

**Variáveis obrigatórias:**
- `DB_PASSWORD`: Senha do banco de dados
- `JWT_SECRET`: Chave secreta para tokens JWT
- `BRAPI_TOKEN`: Token da API BRAPI (obtenha em brapi.dev)

---

### Passo 2: Subir Infraestrutura (5 min)

```bash
# Usando Make
make setup

# OU usando Docker Compose diretamente
docker compose up -d postgres timescaledb redis
```

**Verificar saúde dos serviços:**
```bash
docker compose ps
docker compose logs postgres
```

---

### Passo 3: Inicializar Banco de Dados (5 min)

O schema é inicializado automaticamente pelo Docker, mas você pode verificar:

```bash
# Conectar ao PostgreSQL
docker compose exec postgres psql -U b3user -d b3trading

# Listar tabelas
\dt

# Verificar estrutura
\d+ trades
```

---

### Passo 4: Subir Serviços Backend (10 min)

```bash
# Subir todos os serviços
make up

# OU individualmente
docker compose up -d data-collector
docker compose up -d execution-engine
docker compose up -d api-gateway
```

**Verificar saúde:**
```bash
curl http://localhost:3000/health
curl http://localhost:3008/health
curl http://localhost:3002/health
```

---

### Passo 5: Subir Frontend (5 min)

```bash
# Com Docker
docker compose up -d frontend

# OU localmente para desenvolvimento
cd frontend
npm install
npm run dev
```

**Acessar:** http://localhost:8080

---

### Passo 6: Configurar Grafana (5 min)

1. Acesse: http://localhost:3001
2. Login: admin / admin (altere na primeira vez)
3. Os dashboards já estão pré-configurados
4. Configure alertas conforme necessário

---

## 📊 Uso da Plataforma

### Executar Backtest via API

```bash
curl -X POST http://localhost:3000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "trend_following",
    "symbol": "PETR4",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000,
    "timeframe": "1d"
  }'
```

### Obter Sinais

```bash
curl http://localhost:3000/api/signals/WINFUT?strategy=trend_following
```

### Paper Trading

```bash
# Status
curl http://localhost:3000/api/paper/status

# Resetar
curl -X POST http://localhost:3000/api/paper/reset
```

---

## 🔧 Comandos Úteis

```bash
# Ver logs de todos os serviços
make logs

# Ver logs de um serviço específico
docker compose logs -f execution-engine

# Reiniciar serviço
docker compose restart execution-engine

# Parar tudo
make down

# Limpar volumes (CUIDADO: apaga dados)
docker compose down -v
```

---

## 📈 Estratégias Disponíveis

| Estratégia | Descrição | Indicadores |
|------------|-----------|-------------|
| `trend_following` | Seguir tendência | EMA 9/21, RSI, Volume |
| `mean_reversion` | Reversão à média | Bollinger Bands, RSI |
| `breakout` | Rompimentos | Suporte/Resistência, Volume |
| `macd_crossover` | Cruzamento MACD | MACD, Signal, Volume |
| `rsi_divergence` | Divergências RSI | RSI, ADX, Volume, MACD (4 padrões) |
| `dynamic_position_sizing` | Kelly Criterion | EMA 20/50, RSI, ATR, Volatilidade |

---

## 🔐 Autenticação

Para usar endpoints protegidos:

1. **Registrar usuário:**
```bash
curl -X POST http://localhost:3000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "trader", "email": "trader@example.com", "password": "senha123"}'
```

2. **Login:**
```bash
curl -X POST http://localhost:3000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "trader", "password": "senha123"}'
```

3. **Usar token:**
```bash
curl http://localhost:3000/api/protected-endpoint \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

---

## ⚠️ Avisos Importantes

1. **BRAPI Token**: Obtenha em https://brapi.dev gratuitamente
2. **Paper Trading**: Sempre teste estratégias em paper trading antes de ir live
3. **Riscos**: Trading envolve riscos. Use stop loss sempre.
4. **Horários B3**: 
   - Futuros: 09:00 - 18:00
   - Ações: 10:00 - 17:00

---

## 🐛 Troubleshooting

### Serviço não inicia
```bash
docker compose logs <service-name>
docker compose restart <service-name>
```

### Banco não conecta
```bash
docker compose exec postgres pg_isready -U b3user -d b3trading
```

### Redis não conecta
```bash
docker compose exec redis redis-cli ping
```

### Frontend não carrega
```bash
cd frontend
npm install
npm run dev
```

---

## 📞 Próximos Passos

1. [ ] Integrar MetaTrader 5 para futuros em tempo real
2. [ ] Adicionar mais estratégias
3. [ ] Implementar alertas via Telegram/Discord
4. [ ] Adicionar análise de sentimento
5. [ ] Implementar ML para filtrar sinais
6. [ ] Adicionar suporte a mais timeframes

---

## 📚 Referências

- [BRAPI Documentação](https://brapi.dev/docs)
- [B3 - Derivativos](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/derivativos/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [TimescaleDB](https://docs.timescale.com/)

---

*Última atualização: Janeiro 2025*
