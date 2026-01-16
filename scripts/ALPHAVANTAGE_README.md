# 🌎 Alpha Vantage Data Collector

Coletor de dados históricos da B3 usando Alpha Vantage API (alternativa ao BRAPI e Yahoo Finance).

## 📊 Características

- ✅ **Daily Data**: 20+ anos de histórico completo
- ✅ **Intraday Data**: 1-2 meses (60min, 30min, 15min, 5min, 1min)
- ✅ **Free Tier Disponível**: 5 chamadas/minuto, 25 chamadas/dia
- ✅ **Rate Limiting Automático**: Respeita limites da API
- ✅ **Database Integration**: Salva direto no TimescaleDB

## 🚀 Como Usar

### 1. Obter API Key Gratuita

1. Acesse: https://www.alphavantage.co/support/#api-key
2. Preencha o formulário (email, nome, etc)
3. Receba a key por email instantaneamente
4. **Free Tier**: 5 req/min, 25 req/dia (suficiente para uso moderado)

### 2. Configurar API Key

```bash
# Copiar exemplo
cp .env.alphavantage.example .env.alphavantage

# Editar e adicionar sua key
nano .env.alphavantage
# Substituir YOUR_API_KEY_HERE pela key recebida
```

### 3. Instalar Dependências (Container)

```bash
# Copiar script para container
docker cp scripts/alphavantage_collector.py b3-execution-engine:/tmp/

# Instalar httpx (se não instalado)
docker exec b3-execution-engine pip install httpx
```

### 4. Executar Coleta

#### Teste com 1 Ativo (Daily + Hourly)

```bash
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ITUB4 \
  --api-key YOUR_API_KEY \
  --db-host timescaledb \
  --db-port 5432
```

**Uso de API calls**: 2 (1 daily + 1 hourly)

#### Coletar Múltiplos Ativos (Daily Only)

```bash
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ITUB4,VALE3,PETR4,MGLU3,BBDC4 \
  --api-key YOUR_API_KEY \
  --db-host timescaledb \
  --db-port 5432 \
  --daily-only
```

**Uso de API calls**: 5 (1 por ativo, somente daily)

#### Coletar Tudo (10 Ativos Daily + Hourly)

⚠️ **IMPORTANTE**: 10 ativos × 2 = **20 calls**. Respeita o limite de 25/dia.

```bash
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ITUB4,VALE3,PETR4,MGLU3,BBDC4,ABEV3,WEGE3,RENT3,SUZB3,B3SA3 \
  --api-key YOUR_API_KEY \
  --db-host timescaledb \
  --db-port 5432
```

**Uso de API calls**: 20 (10 daily + 10 hourly)

## 📋 Opções de Linha de Comando

```bash
python alphavantage_collector.py --help

Options:
  --symbols        Símbolos B3 separados por vírgula (ex: ITUB4,VALE3)
  --api-key        Alpha Vantage API key (obrigatório)
  --daily-only     Coletar apenas dados daily (economiza API calls)
  --db-host        Host do banco (default: localhost)
  --db-port        Porta do banco (default: 5433)
  --db-name        Nome do banco (default: trading_timescale)
  --db-user        Usuário do banco (default: trading_user)
  --db-password    Senha do banco (default: trading_pass)
```

## 📊 Planejamento de Coleta (Free Tier)

### Estratégia Recomendada para 10 Ativos

| Dia | Ação | API Calls | Dados Coletados |
|-----|------|-----------|-----------------|
| **Dia 1** | Daily data (todos) | 10 | 20+ anos × 10 ativos |
| **Dia 2** | Hourly data (parte 1) | 5 | 1-2 meses × 5 ativos |
| **Dia 3** | Hourly data (parte 2) | 5 | 1-2 meses × 5 ativos |

**Total**: 3 dias para coleta completa (respeitando limites)

### Comandos para Estratégia Multi-Dia

```bash
# DIA 1: Daily data para todos (10 calls)
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ITUB4,VALE3,PETR4,MGLU3,BBDC4,ABEV3,WEGE3,RENT3,SUZB3,B3SA3 \
  --api-key YOUR_KEY \
  --db-host timescaledb \
  --db-port 5432 \
  --daily-only

# DIA 2: Hourly data parte 1 (5 calls)
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ITUB4,VALE3,PETR4,MGLU3,BBDC4 \
  --api-key YOUR_KEY \
  --db-host timescaledb \
  --db-port 5432

# Mas só pegar hourly (script já tem daily do dia 1)

# DIA 3: Hourly data parte 2 (5 calls)
docker exec b3-execution-engine python3 /tmp/alphavantage_collector.py \
  --symbols ABEV3,WEGE3,RENT3,SUZB3,B3SA3 \
  --api-key YOUR_KEY \
  --db-host timescaledb \
  --db-port 5432
```

## 🎯 Comparação com Outras Fontes

| Fonte | Daily History | Intraday History | Custo | Limite API |
|-------|--------------|------------------|-------|------------|
| **BRAPI Free** | 3 meses | 3 meses (4 ativos) | Grátis | - |
| **Yahoo Finance** | 10+ anos | 60 dias | Grátis | ❌ Bloqueado B3 |
| **Alpha Vantage Free** | 20+ anos | 1-2 meses | Grátis | 25 calls/dia |
| **Alpha Vantage Premium** | 20+ anos | Anos | $49.99/mês | 1200 calls/min |
| **Polygon.io** | 2+ anos | Anos | $7/mês | Sem limite |

## 📈 Dados Disponíveis

### Daily (TIME_SERIES_DAILY)
- **História**: 20+ anos completos
- **Campos**: Open, High, Low, Close, Volume
- **Atualização**: Diária (fim do pregão)
- **API Calls**: 1 por símbolo

### Intraday (TIME_SERIES_INTRADAY)
- **Intervalos**: 1min, 5min, 15min, 30min, 60min
- **História** (Free): 1-2 meses
- **História** (Premium): Anos
- **Campos**: Open, High, Low, Close, Volume
- **API Calls**: 1 por símbolo + intervalo

## 🔧 Troubleshooting

### Erro "Note: Thank you for using Alpha Vantage!"

**Causa**: Atingiu o limite de 5 calls/minuto

**Solução**: O script já tem rate limiting automático (12s entre calls)

### Erro "API call frequency is limited"

**Causa**: Atingiu o limite de 25 calls/dia

**Solução**: Aguarde até o próximo dia (reset às 00:00 UTC) ou upgrade para Premium

### Erro "Invalid API key"

**Causa**: API key incorreta ou não ativada

**Solução**: 
1. Verificar key no email de registro
2. Testar manualmente: `curl "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey=YOUR_KEY"`

### Símbolo não encontrado

**Causa**: Símbolo B3 não disponível no Alpha Vantage

**Solução**: Verificar mapping em `symbol_mapping` no script (usa sufixo `.SAO`)

## 📞 Suporte

- **Alpha Vantage Docs**: https://www.alphavantage.co/documentation/
- **API Support**: support@alphavantage.co
- **Premium Plans**: https://www.alphavantage.co/premium/

## 🎁 Upgrade para Premium

**Benefícios**:
- ✅ 1200 API calls/minuto (vs 5/min)
- ✅ História intraday completa (anos vs 1-2 meses)
- ✅ Dados fundamentais (balanços, demonstrativos)
- ✅ Suporte prioritário
- 💰 **Custo**: $49.99/mês

**Indicado para**: Produção com trading ativo multi-timeframe

---

**Criado em**: 15 de Janeiro de 2026  
**Projeto**: B3 Trading Platform
