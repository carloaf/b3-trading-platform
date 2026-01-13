# ============================================
# B3 TRADING PLATFORM - MAKEFILE
# ============================================

.PHONY: help dev up down logs test build clean db-migrate download-hist backtest paper-start paper-stop health-check

# Variáveis
DOCKER_COMPOSE = docker compose
EXEC_ENGINE = b3-execution-engine
DATA_COLLECTOR = b3-data-collector

# ============================================
# HELP
# ============================================

help: ## Mostra esta ajuda
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║           B3 TRADING PLATFORM - COMANDOS                     ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "║  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo "╚══════════════════════════════════════════════════════════════╝"

# ============================================
# DOCKER COMMANDS
# ============================================

dev: ## Inicia em modo desenvolvimento (com logs)
	$(DOCKER_COMPOSE) up --build

up: ## Inicia todos os containers em background
	$(DOCKER_COMPOSE) up -d --build
	@echo "✅ Serviços iniciados!"
	@echo "📊 Dashboard: http://localhost:8080"
	@echo "🔌 API: http://localhost:3000"
	@echo "📈 Grafana: http://localhost:3001"

down: ## Para todos os containers
	$(DOCKER_COMPOSE) down
	@echo "✅ Serviços parados"

restart: ## Reinicia todos os containers
	$(DOCKER_COMPOSE) restart
	@echo "✅ Serviços reiniciados"

logs: ## Mostra logs de todos os serviços
	$(DOCKER_COMPOSE) logs -f

logs-engine: ## Logs do execution engine
	$(DOCKER_COMPOSE) logs -f execution-engine

logs-collector: ## Logs do data collector
	$(DOCKER_COMPOSE) logs -f data-collector

build: ## Rebuild dos containers
	$(DOCKER_COMPOSE) build --no-cache

clean: ## Remove containers, volumes e imagens
	$(DOCKER_COMPOSE) down -v --rmi local
	@echo "✅ Limpeza completa"

ps: ## Status dos containers
	$(DOCKER_COMPOSE) ps

# ============================================
# DATABASE
# ============================================

db-migrate: ## Aplica migrações do banco
	docker exec $(EXEC_ENGINE) python -m alembic upgrade head
	@echo "✅ Migrações aplicadas"

db-shell: ## Acessa shell do PostgreSQL
	docker exec -it b3-postgres psql -U b3trading_user -d b3trading_db

db-timescale: ## Acessa shell do TimescaleDB
	docker exec -it b3-timescaledb psql -U b3trading_ts -d b3trading_market

db-reset: ## Reset completo do banco (CUIDADO!)
	@echo "⚠️  ATENÇÃO: Isso vai APAGAR todos os dados!"
	@read -p "Tem certeza? (y/N) " confirm && [ "$$confirm" = "y" ]
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) up -d postgres timescaledb
	@echo "✅ Banco resetado"

# ============================================
# DATA MANAGEMENT
# ============================================

download-hist: ## Baixa dados históricos (WIN, WDO)
	docker exec $(DATA_COLLECTOR) python -m src.download_historical \
		--symbols WINFUT,WDOFUT \
		--timeframes 1m,5m,15m,1h,1d \
		--days 365
	@echo "✅ Download concluído"

download-stocks: ## Baixa dados de ações (PETR4, VALE3, etc.)
	docker exec $(DATA_COLLECTOR) python -m src.download_stocks \
		--symbols PETR4,VALE3,ITUB4,BBDC4,ABEV3,BOVA11 \
		--days 365
	@echo "✅ Download de ações concluído"

health-check: ## Verifica saúde dos dados
	docker exec $(EXEC_ENGINE) python -m src.data_health_check
	@echo "✅ Health check concluído"

# ============================================
# TRADING
# ============================================

backtest: ## Executa backtest (default: trend_following, WINFUT)
	docker exec $(EXEC_ENGINE) python -m src.run_backtest \
		--strategy trend_following \
		--symbol WINFUT \
		--start 2024-01-01 \
		--end 2024-12-31
	@echo "✅ Backtest concluído"

backtest-all: ## Executa backtest de todas as estratégias
	docker exec $(EXEC_ENGINE) python -m src.run_backtest --all-strategies
	@echo "✅ Backtest completo"

paper-start: ## Inicia paper trading
	docker exec $(EXEC_ENGINE) python -m src.paper_trading --start
	@echo "✅ Paper trading iniciado"

paper-stop: ## Para paper trading
	docker exec $(EXEC_ENGINE) python -m src.paper_trading --stop
	@echo "✅ Paper trading parado"

paper-status: ## Status do paper trading
	docker exec $(EXEC_ENGINE) python -m src.paper_trading --status

# ============================================
# DEVELOPMENT
# ============================================

test: ## Executa testes
	docker exec $(EXEC_ENGINE) pytest tests/ -v --cov=src
	@echo "✅ Testes concluídos"

lint: ## Verifica qualidade do código
	docker exec $(EXEC_ENGINE) ruff check src/
	docker exec $(EXEC_ENGINE) mypy src/
	@echo "✅ Lint concluído"

format: ## Formata código
	docker exec $(EXEC_ENGINE) ruff format src/
	@echo "✅ Código formatado"

shell-engine: ## Shell do execution engine
	docker exec -it $(EXEC_ENGINE) bash

shell-collector: ## Shell do data collector
	docker exec -it $(DATA_COLLECTOR) bash

# ============================================
# QUICK START
# ============================================

setup: ## Setup inicial completo
	@echo "🚀 Iniciando setup do B3 Trading Platform..."
	@cp -n .env.example .env 2>/dev/null || true
	@echo "📝 Arquivo .env criado (edite com suas credenciais)"
	$(DOCKER_COMPOSE) up -d postgres timescaledb redis
	@echo "⏳ Aguardando bancos de dados..."
	@sleep 10
	$(DOCKER_COMPOSE) up -d --build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              ✅ SETUP COMPLETO!                              ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  📊 Dashboard:  http://localhost:8080                        ║"
	@echo "║  🔌 API:        http://localhost:3000                        ║"
	@echo "║  📈 Grafana:    http://localhost:3001 (admin/admin123)       ║"
	@echo "║                                                              ║"
	@echo "║  Próximos passos:                                            ║"
	@echo "║  1. Edite .env com suas credenciais MT5/BRAPI                ║"
	@echo "║  2. make download-hist (baixar dados históricos)             ║"
	@echo "║  3. make backtest (testar estratégia)                        ║"
	@echo "║  4. make paper-start (iniciar paper trading)                 ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
