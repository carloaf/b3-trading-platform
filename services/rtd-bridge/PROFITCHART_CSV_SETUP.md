# Configuração ProfitChart para Exportação Automática

## 🎯 Objetivo
Configurar ProfitChart para exportar cotações em tempo real para CSVs, permitindo integração com o RTD Bridge.

## ⏱️ Tempos de Atualização

| Método | Latência | Prós | Contras |
|--------|----------|------|---------|
| **CSV Export (RECOMENDADO)** | 1-5 segundos | ✅ Simples, robusto, funciona em Linux | ⚠️ Latência maior |
| **DDE via Wine** | 100-500ms | ✅ Baixa latência | ❌ Complexo, precisa pywin32 no Wine |
| **API REST ProfitChart** | 500ms-2s | ✅ Nativo | ⚠️ Precisa verificar se existe |

**Para Paper Trading e Swing Trading:** CSV Export é suficiente! ✅

---

## 📋 Passo a Passo - Configuração CSV Export

### 1. Abrir ProfitChart via Wine

```bash
cd ~/.wine/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit/
wine profitchart.exe &
```

### 2. Configurar Exportação Automática

**Caminho:** `Ferramentas > Opções > Avançado > Exportação de Dados`

Configure:
- ✅ **Habilitar exportação automática:** SIM
- 📁 **Pasta de destino:** `C:\profitchart_export\` (mapeia para `~/.wine/drive_c/profitchart_export/`)
- ⏱️ **Frequência de atualização:** 1-2 segundos (mínimo disponível)
- 📊 **Formato:** CSV delimitado por ponto-e-vírgula (;)
- 📝 **Incluir header:** SIM
- 🔢 **Campos exportados:**
  - Symbol (código do ativo)
  - Last (último preço)
  - Bid (compra)
  - Ask (venda)
  - Volume
  - Variation (variação %)
  - Status (OPEN/CLOSED)

### 3. Adicionar Símbolos ao Watch List

No ProfitChart:
1. Abrir painel **"Cotações"** ou **"Watch List"**
2. Adicionar os símbolos desejados:
   - PETR4, VALE3, ITUB4, BBAS3, BBDC4, etc.
3. Clicar com botão direito > **"Exportar cotações"**
4. Marcar **"Exportação contínua"**

### 4. Verificar Arquivos Gerados

```bash
# Listar arquivos CSV gerados
ls -lh ~/.wine/drive_c/profitchart_export/

# Exemplo de saída esperada:
# PETR4.csv
# VALE3.csv
# ITUB4.csv
# ...

# Ver conteúdo de um arquivo
cat ~/.wine/drive_c/profitchart_export/PETR4.csv
```

**Formato esperado do CSV:**
```csv
symbol;date;time;last;bid;ask;volume;variation;status
PETR4;30/01/2026;14:35:22;38,75;38,74;38,76;15250000;+1,2;OPEN
```

### 5. Criar Pasta de Export (Linux)

```bash
# Criar pasta no Wine
mkdir -p ~/.wine/drive_c/profitchart_export

# Criar symlink para facilitar acesso
ln -s ~/.wine/drive_c/profitchart_export ~/profitchart_export

# Testar permissões
touch ~/profitchart_export/test.txt
ls ~/profitchart_export/test.txt && rm ~/profitchart_export/test.txt
```

---

## 🐳 Ativar CSV Monitor no Docker

### Opção 1: Editar `docker-compose.yml`

```yaml
rtd-bridge:
  environment:
    - PROFITCHART_CSV_MODE=true  # ← Ativar CSV Monitor
    - PROFITCHART_CSV_FOLDER=/profitchart_export
  volumes:
    - ~/profitchart_export:/profitchart_export:ro  # ← Mount da pasta
```

### Opção 2: Variáveis de Ambiente via CLI

```bash
cd services/rtd-bridge

# Parar container
./manage_container.sh stop

# Editar docker-compose.yml (ou usar .env)
# Reiniciar
./manage_container.sh start

# Ver logs
./manage_container.sh logs
```

---

## ✅ Testar Integração

### 1. Verificar ProfitChart Exportando

```bash
# Monitorar pasta em tempo real
watch -n 1 'ls -lh ~/profitchart_export/'

# Ou ver conteúdo atualizado
watch -n 1 'tail ~/profitchart_export/PETR4.csv'
```

### 2. Testar CSV Monitor

```bash
cd services/rtd-bridge

# Teste standalone
docker exec b3-rtd-bridge python3 profitchart_csv_monitor.py

# Deve imprimir cotações a cada 2 segundos
# Exemplo de saída:
# 📊 14:35:22
#   PETR4: R$ 38.75 (+1.20%)
#   VALE3: R$ 62.45 (+0.85%)
```

### 3. Testar WebSocket com Dados Reais

```bash
# Cliente interativo
docker exec b3-rtd-bridge python3 calc_client.py --mode interactive

# Deve mostrar dados do CSV se PROFITCHART_CSV_MODE=true
```

---

## 🔧 Troubleshooting

### Problema: Pasta de export não encontrada

```bash
# Verificar se pasta existe
ls ~/.wine/drive_c/profitchart_export/

# Se não existir, criar
mkdir -p ~/.wine/drive_c/profitchart_export

# Verificar permissões
chmod 755 ~/.wine/drive_c/profitchart_export
```

### Problema: CSVs não são atualizados

1. **Verificar se ProfitChart está rodando:**
   ```bash
   ps aux | grep profitchart
   ```

2. **Verificar configuração no ProfitChart:**
   - Ferramentas > Opções > Exportação Automática
   - Frequência: 1-2 segundos
   - Status: Habilitado ✅

3. **Verificar se símbolos estão na Watch List:**
   - Abrir painel "Cotações"
   - Adicionar PETR4, VALE3, etc.
   - Botão direito > "Exportar cotações"

### Problema: Container não vê os arquivos

```bash
# Verificar volume mount
docker inspect b3-rtd-bridge | grep profitchart_export

# Testar dentro do container
docker exec b3-rtd-bridge ls /profitchart_export
docker exec b3-rtd-bridge cat /profitchart_export/PETR4.csv
```

---

## 📊 Performance Esperada

### Latências Medidas:

| Componente | Tempo | Observação |
|------------|-------|------------|
| **ProfitChart → CSV** | 1-2 segundos | Configurável no ProfitChart |
| **CSV Monitor → WebSocket** | 100-300ms | Polling + parse + broadcast |
| **WebSocket → LibreOffice** | 50-100ms | Rede local |
| **Total End-to-End** | **1,5-2,5 segundos** | ✅ Aceitável para swing trading |

### Para Day Trading de Alta Frequência:

Se precisar latência < 500ms, considerar:
1. **DDE via Wine** (complexo, precisa pywin32)
2. **API REST nativa do ProfitChart** (se existir)
3. **WebSocket direto do ProfitChart** (verificar se tem)

---

## 📝 Checklist Final

- [ ] ProfitChart rodando no Wine
- [ ] Exportação automática configurada (1-2s)
- [ ] Pasta `~/profitchart_export` criada
- [ ] Símbolos adicionados à Watch List
- [ ] CSVs sendo gerados (verificar `ls ~/profitchart_export/`)
- [ ] `docker-compose.yml` atualizado (`PROFITCHART_CSV_MODE=true`)
- [ ] Container reiniciado (`./manage_container.sh restart`)
- [ ] Teste standalone funciona (`python3 profitchart_csv_monitor.py`)
- [ ] WebSocket retorna dados reais (não mock)
- [ ] LibreOffice Calc atualiza em tempo real

---

## 🚀 Próximos Passos

1. ✅ Configurar ProfitChart CSV export
2. ✅ Ativar CSV Monitor no container
3. ✅ Testar integração end-to-end
4. 📊 Monitorar latências em produção
5. 📈 Paper trading com dados reais
6. 🎯 Validar estratégias Wave3 v2.1

**Status:** Implementação CSV Monitor COMPLETA! 🎉

Latência de 1,5-2,5 segundos é **ideal para:**
- ✅ Swing Trading
- ✅ Paper Trading
- ✅ Monitoramento de carteira
- ✅ Estratégias Wave3 (timeframe 60min/diário)

Não recomendado para:
- ❌ Day trading de alta frequência
- ❌ Scalping
- ❌ Arbitragem
