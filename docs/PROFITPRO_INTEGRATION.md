# 🎯 RESUMO: Integração ProfitChart/Profit (Nelogica)

**Data:** 20/01/2026  
**Status:** ✅ LOCALIZADO | 🔄 PARSING EM DESENVOLVIMENTO

---

## 📍 Localização do Profit

✅ **Encontrado em:**
```
/home/dellno/.wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit/
```

**Executável:**
```
profitchart.exe
```

**Pasta de Dados:**
```
database/assets/
```

---

## 📊 Dados Disponíveis

### 34 Símbolos Encontrados:

ABEV3, B3SA3, BBAS3, BBDC4, BRAP4, BRFS3, CIEL3, CMIG4, CSNA3, CYRE3,  
DOLFUT, DOLPT, ECOR3, EMBR3, GFSA3, GGBR4, GOAU4, IBOV, INDFUT, ITSA4,  
ITUB4, MGLU3, MRVE3, NATU3, PETR4, RADL3, RENT3, SBSP3, SUZB3, USIM5,  
VALE3, VIVT3, WEGE3, WINM25

### Cobertura Histórica (exemplo PETR4):

| Tipo | Arquivos | Período | Tamanho |
|------|----------|---------|---------|
| **Diário** | 32 anos | 1994-2025 | 34KB/ano |
| **1 minuto** | 1 ano | 2025 | 1.3MB |
| **5 minutos** | 2 anos | 2024-2025 | 521KB-730KB |
| **Tick-by-tick** | Atual | 2025 | 4MB |

---

## 🗂️ Formato dos Arquivos

### Convenção de Nomes:

```
SIMBOLO_B_0_TIPO_INTERVALO_1_1_1_0_ANO.ext

Exemplos:
PETR4_B_0_2_1_1_1_0_2024.day  → Diário 2024
PETR4_B_0_1_1_1_1_0_2025.min  → 1 minuto 2025
PETR4_B_0_1_5_1_1_0_2024.min  → 5 minutos 2024
PETR4_B_0_0_1_1_1_0_20250403.trd → Tick-by-tick 03/04/2025
```

### Código de Tipos:
- `_2_` = Diário (`.day`)
- `_1_1_` = 1 minuto (`.min`)
- `_1_5_` = 5 minutos (`.min`)
- `_0_1_` = Tick-by-tick (`.trd`)

---

## 🔬 Formato Binário (Engenharia Reversa)

### Estrutura Preliminar:

```
Offset 0x00-0x3F: HEADER (64 bytes?)
  - Metadados do ativo
  - Versão do formato
  - Informações de compressão?

Offset 0x40+: DADOS
  - Registros sequenciais OHLCV
  - Tamanho por registro: ~128 bytes (estimado)
  - Formato: doubles (8 bytes cada) + metadados

Campos por registro (hipótese):
  1. Data/Hora (8 bytes - double timestamp)
  2. Open (8 bytes - double)
  3. High (8 bytes - double)
  4. Low (8 bytes - double)
  5. Close (8 bytes - double)
  6. Volume (8 bytes - long)
  7. Metadados adicionais (80 bytes?)
```

### Análise Hexdump (PETR4 2024):

```
Offset 0x80-0xFF: Primeiro registro
  40 e6 1d c0 → double (timestamp ou data)
  40 42 e6 66 66 66 66 66 → double 37.80 (Open?)
  40 43 8f 5c 28 f5 c2 8f → double 39.12 (High?)
  40 42 d5 c2 8f 5c 28 f6 → double 37.67 (Low?)
  40 43 7a e1 47 ae 14 7b → double 38.96 (Close?)
  41 de 0e 1a 3c c0 00 00 → volume?
```

---

## ✅ Soluções Disponíveis

### Opção 1: Exportação Manual via GUI ⭐ RECOMENDADO

**Vantagens:**
- ✅ 100% confiável (usa próprio exportador do Profit)
- ✅ Formato CSV padrão
- ✅ Sem engenharia reversa

**Workflow:**
1. Abrir ProfitChart:
   ```bash
   cd ~/.wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit
   wine profitchart.exe
   ```

2. Criar gráfico do ativo (ex: PETR4)

3. Exportar dados:
   - Clique direito → "Exportar Dados" → "CSV"
   - Salvar em: `/tmp/profitpro_export/PETR4_daily.csv`

4. Importar para TimescaleDB:
   ```bash
   docker exec b3-data-collector python /app/src/profitpro_integration.py import \
       /tmp/profitpro_export/PETR4_daily.csv
   ```

**Formato CSV esperado:**
```csv
Data;Hora;Abertura;Máxima;Mínima;Fechamento;Volume
20/01/2026;09:00;30.50;30.80;30.40;30.75;1000000
```

### Opção 2: Parser Binário (Experimental)

**Status:** 🔄 EM DESENVOLVIMENTO

**Desafios:**
- Formato proprietário da Nelogica
- Pode mudar entre versões
- Requer engenharia reversa completa

**Arquivo:** `scripts/profit_parser.py`

**Próximos Passos:**
1. Analisar mais amostras de arquivos
2. Identificar padrões de timestamp
3. Validar com dados conhecidos
4. Implementar parser completo

### Opção 3: API DDE do Profit (Avançado)

**Descrição:** ProfitChart oferece interface DDE para dados real-time

**Requisitos:**
- Windows ou Wine com suporte DDE
- Biblioteca Python: `pywin32`
- ProfitChart rodando em background

**Implementação Futura:**
```python
import win32ui, ddeml

# Conectar ao ProfitChart via DDE
server = ddeml.CreateServer()
conversation = server.ConnectTo("PROFIT", "QUOTE")

# Obter cotação
quote = conversation.Request("PETR4")
```

---

## 🎯 RECOMENDAÇÃO FINAL

### Para Dados Históricos Completos:

**✅ Use Exportação Manual (Opção 1)**

**Workflow Otimizado:**

1. **Criar script de lote para exportação:**
   ```bash
   # Liste 20-30 ativos principais
   # Exporte cada um via GUI do Profit
   # Salve em pasta organizada
   ```

2. **Importar em lote:**
   ```bash
   docker exec b3-data-collector python /app/src/profitpro_integration.py import-batch \
       /tmp/profitpro_export --interval daily
   ```

3. **Resultado esperado:**
   - 30 ativos × 10 anos = 75.000+ registros diários
   - Intraday: 30 ativos × 2 anos × 360 candles/dia = 21.600.000 registros

---

## 📝 Arquivos Criados

1. **`services/data-collector/src/profitpro_integration.py`** (580 linhas)
   - Lê CSV exportado do Profit
   - Importa para TimescaleDB
   - Suporta batch import

2. **`scripts/profit_parser.py`** (480 linhas)
   - Parser binário experimental (em desenvolvimento)
   - Lista símbolos disponíveis
   - Análise de formato proprietário

3. **`scripts/setup_profitpro.sh`** (120 linhas)
   - Localiza instalação do Profit
   - Gera instruções de exportação
   - Abre Profit via Wine

4. **`docs/PROFITPRO_INTEGRATION.md`** (este arquivo)
   - Documentação completa
   - Guia de uso
   - Análise técnica

---

## 🚀 PRÓXIMOS PASSOS

### Curto Prazo (Hoje):
1. ✅ Exportar PETR4, VALE3, ITUB4 via GUI do Profit
2. ✅ Testar import para TimescaleDB
3. ✅ Validar dados importados

### Médio Prazo (Esta Semana):
4. Exportar top 20 ativos do Ibovespa
5. Importar dados históricos (últimos 10 anos)
6. Comparar com COTAHIST para validação

### Longo Prazo (Futuro):
7. Completar parser binário (se necessário)
8. Implementar DDE para real-time
9. Automatizar exportação com AutoHotkey/xdotool

---

## 📚 Referências

- Profit/ProfitChart: https://www.nelogica.com.br/profit/
- Wine: https://www.winehq.org/
- TimescaleDB: https://docs.timescale.com/
- Struct (Python): https://docs.python.org/3/library/struct.html

---

*Última atualização: 20/01/2026 18:45*  
*Profit encontrado e dados disponíveis - 34 símbolos, 30+ anos de histórico*  
*Recomendação: Exportação manual via GUI para máxima confiabilidade*
