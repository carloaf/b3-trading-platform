#!/bin/bash
# B3 Trading Platform - Script de início rápido
# Uso: ./start.sh [dev|prod]

set -e

MODE=${1:-dev}
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 B3 Trading Platform - Iniciando em modo: $MODE"
echo "================================================"

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker não está rodando. Por favor, inicie o Docker primeiro."
    exit 1
fi

# Verificar arquivo .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  Arquivo .env não encontrado. Copiando de .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "📝 Por favor, edite o arquivo .env com suas configurações antes de continuar."
    echo "   Variáveis obrigatórias:"
    echo "   - BRAPI_TOKEN (obtenha em https://brapi.dev)"
    echo "   - JWT_SECRET (chave secreta para autenticação)"
    echo ""
    read -p "Pressione Enter para continuar após editar o .env..."
fi

cd "$PROJECT_DIR"

# Parar containers existentes
echo "🛑 Parando containers existentes..."
docker compose down 2>/dev/null || true

# Subir infraestrutura
echo "🗄️  Iniciando infraestrutura (PostgreSQL, TimescaleDB, Redis)..."
docker compose up -d postgres timescaledb redis

echo "⏳ Aguardando bancos de dados ficarem prontos..."
sleep 10

# Verificar saúde do PostgreSQL
echo "🔍 Verificando PostgreSQL..."
until docker compose exec -T postgres pg_isready -U b3user -d b3trading > /dev/null 2>&1; do
    echo "   Aguardando PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL pronto!"

# Verificar saúde do TimescaleDB
echo "🔍 Verificando TimescaleDB..."
until docker compose exec -T timescaledb pg_isready -U b3user -d b3trading_ts > /dev/null 2>&1; do
    echo "   Aguardando TimescaleDB..."
    sleep 2
done
echo "✅ TimescaleDB pronto!"

# Verificar saúde do Redis
echo "🔍 Verificando Redis..."
until docker compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "   Aguardando Redis..."
    sleep 2
done
echo "✅ Redis pronto!"

# Subir serviços de aplicação
echo "🔧 Iniciando serviços de aplicação..."
docker compose up -d data-collector execution-engine api-gateway

echo "⏳ Aguardando serviços ficarem prontos..."
sleep 15

# Verificar API Gateway
echo "🔍 Verificando API Gateway..."
for i in {1..30}; do
    if curl -s http://localhost:3000/health > /dev/null 2>&1; then
        echo "✅ API Gateway pronto!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  API Gateway ainda não está respondendo. Verifique os logs."
    fi
    sleep 2
done

# Subir frontend
if [ "$MODE" = "dev" ]; then
    echo "🎨 Modo desenvolvimento: Frontend local..."
    echo "   Execute: cd frontend && npm install && npm run dev"
else
    echo "🎨 Iniciando frontend..."
    docker compose up -d frontend
fi

# Subir Grafana
echo "📊 Iniciando Grafana..."
docker compose up -d grafana

echo ""
echo "================================================"
echo "✅ B3 Trading Platform iniciada com sucesso!"
echo "================================================"
echo ""
echo "📍 URLs disponíveis:"
echo "   - Frontend:      http://localhost:8080"
echo "   - API Gateway:   http://localhost:3000"
echo "   - Grafana:       http://localhost:3001 (admin/admin)"
echo ""
echo "📋 Comandos úteis:"
echo "   - Ver logs:      docker compose logs -f"
echo "   - Parar:         docker compose down"
echo "   - Status:        docker compose ps"
echo ""
echo "🎯 Próximos passos:"
echo "   1. Acesse o frontend em http://localhost:8080"
echo "   2. Execute um backtest para testar"
echo "   3. Configure alertas no Grafana"
echo ""
echo "📚 Documentação: README.md"
echo "📋 Plano completo: PLANO_IMPLEMENTACAO.md"
echo ""
