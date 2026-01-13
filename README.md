# 🇧🇷 B3 Trading Platform - Mini Índice & Mini Dólar

Sistema de trading automatizado para o mercado brasileiro B3, focado em Mini Índice (WIN) e Mini Dólar (WDO).

## 🎯 Funcionalidades

- ✅ **Coleta de Dados** - MetaTrader 5 + BRAPI
- ✅ **Análise Técnica** - Indicadores (RSI, MACD, EMA, Bollinger)
- ✅ **Backtesting** - Walk-Forward Optimization
- ✅ **Paper Trading** - Simulação em tempo real
- ✅ **Dashboard** - Monitoramento e análise visual
- ✅ **Alertas** - Telegram/Discord

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    B3 Trading Platform                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ MetaTrader5 │    │   BRAPI     │    │  Profit     │     │
│  │  (Futuros)  │    │  (Ações)    │    │  Chart API  │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            ▼                                │
│                 ┌─────────────────────┐                     │
│                 │   Data Collector    │                     │
│                 │   (Python/FastAPI)  │                     │
│                 └──────────┬──────────┘                     │
│                            │                                │
│         ┌──────────────────┼──────────────────┐            │
│         ▼                  ▼                  ▼            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │ PostgreSQL  │    │    Redis    │    │ TimescaleDB │    │
│  │  (Config)   │    │   (Cache)   │    │   (OHLCV)   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                            │                                │
│                            ▼                                │
│                 ┌─────────────────────┐                     │
│                 │  Execution Engine   │                     │
│                 │  - Strategies       │                     │
│                 │  - Backtesting      │                     │
│                 │  - Paper Trading    │                     │
│                 └──────────┬──────────┘                     │
│                            │                                │
│                            ▼                                │
│                 ┌─────────────────────┐                     │
│                 │     Frontend        │                     │
│                 │   (React + Charts)  │                     │
│                 └─────────────────────┘                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Pré-requisitos
- Docker & Docker Compose v2
- Python 3.11+
- MetaTrader 5 (para futuros)
- Conta em corretora brasileira (XP, Clear, etc.)

### Instalação

```bash
# 1. Clone o repositório
cd /home/dellno/worksapace/b3-trading-platform

# 2. Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais

# 3. Inicie os containers
docker compose up -d

# 4. Verifique os serviços
docker compose ps

# 5. Acesse o dashboard
# http://localhost:8080
```

## 📊 Instrumentos Suportados

| Símbolo | Nome | Tipo | Horário |
|---------|------|------|---------|
| **WINFUT** | Mini Índice Ibovespa | Futuro | 09:00-18:00 |
| **WDOFUT** | Mini Dólar | Futuro | 09:00-18:00 |
| **PETR4** | Petrobras PN | Ação | 10:00-17:00 |
| **VALE3** | Vale ON | Ação | 10:00-17:00 |
| **BOVA11** | ETF Ibovespa | ETF | 10:00-17:00 |

## 📁 Estrutura do Projeto

```
b3-trading-platform/
├── docker-compose.yml          # Orquestração de containers
├── .env.example                 # Template de variáveis
├── Makefile                     # Comandos úteis
├── README.md                    # Este arquivo
├── PLANO_IMPLEMENTACAO.md       # Roadmap detalhado
│
├── services/
│   ├── data-collector/         # Coleta de dados MT5/BRAPI
│   ├── execution-engine/       # Backtesting + Paper Trading
│   └── api-gateway/            # API REST principal
│
├── frontend/                   # Dashboard React
│
├── infrastructure/
│   ├── postgres/               # Scripts SQL
│   └── redis/                  # Config Redis
│
├── scripts/                    # Scripts utilitários
│
└── docs/                       # Documentação adicional
```

## 🔧 Configuração

### MetaTrader 5

```python
# services/data-collector/config.py
MT5_CONFIG = {
    "login": 12345678,           # Seu login MT5
    "password": "sua_senha",
    "server": "XP-DEMO",         # Servidor da corretora
    "path": "/path/to/mt5"       # Caminho do terminal (Linux via Wine)
}
```

### BRAPI (Ações)

```python
# Obtenha token em: https://brapi.dev
BRAPI_TOKEN = "seu_token_aqui"
```

## 📈 Estratégias Implementadas

1. **Trend Following** - EMA 9/21 + RSI + Volume
2. **Mean Reversion** - Bollinger Bands + RSI oversold/overbought
3. **Breakout** - Rompimento de suporte/resistência
4. **Scalping** - Análise de fluxo de ordens (tape reading)

## 🛠️ Comandos Úteis

```bash
# Desenvolvimento
make dev              # Inicia em modo desenvolvimento
make logs             # Ver logs dos serviços
make test             # Rodar testes

# Banco de Dados
make db-migrate       # Aplicar migrações
make db-seed          # Popular dados iniciais

# Dados
make download-hist    # Baixar dados históricos
make health-check     # Verificar saúde dos dados

# Trading
make backtest         # Rodar backtest
make paper-start      # Iniciar paper trading
make paper-stop       # Parar paper trading
```

## ⚠️ Disclaimer

**Este software é apenas para fins educacionais.**

- Trading envolve risco de perda de capital
- Resultados passados não garantem resultados futuros
- Teste extensivamente em paper trading antes de usar capital real
- Consulte um profissional de investimentos

## 📄 Licença

MIT License - Veja [LICENSE](LICENSE) para detalhes.

## 🤝 Contribuição

Contribuições são bem-vindas! Veja [CONTRIBUTING.md](docs/CONTRIBUTING.md).

---

**Desenvolvido para o mercado brasileiro 🇧🇷**
