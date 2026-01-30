# 📊 Integração RTD ProfitChart → LibreOffice Calc

**Data:** 30 Janeiro 2026  
**Status:** ✅ IMPLEMENTADO | 🧪 MODO DESENVOLVIMENTO

---

## 📋 Visão Geral

Sistema de integração em tempo real entre ProfitChart (rodando via Wine) e LibreOffice Calc, permitindo atualização automática de cotações de ativos brasileiros (PETR3, VALE3, etc.) em planilhas.

### Arquitetura

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │  DDE    │                  │ WebSocket│                 │
│  ProfitChart    │────────▶│  Python Bridge   │◀────────▶│ LibreOffice     │
│  (Wine)         │         │  (RTD Server)    │          │ Calc            │
│                 │         │                  │          │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
     PETR3, VALE3           ws://localhost:8765           Planilha .ods
```

---

## 🚀 Quick Start

### 1. Setup Inicial (primeira vez)

```bash
cd /home/dellno/worksapace/b3-trading-platform/services/rtd-bridge
./start_rtd.sh setup
```

Isso irá:
- ✅ Verificar dependências (Python, Wine, LibreOffice)
- ✅ Instalar bibliotecas Python necessárias
- ✅ Criar template da planilha ODS
- ✅ Validar instalação do ProfitChart

### 2. Iniciar Serviços

```bash
./start_rtd.sh start
```

Isso irá:
- 🚀 Iniciar ProfitChart via Wine
- 🌐 Iniciar RTD Bridge Server (WebSocket na porta 8765)
- 📡 Começar captura de cotações

### 3. Abrir Planilha

**Opção A: Atualização Manual (via cliente Python)**

```bash
# Terminal 1: Verificar dados
cd services/rtd-bridge
python3 calc_client.py --mode interactive

# Terminal 2: Abrir planilha
./start_rtd.sh calc
```

**Opção B: Atualização Automática (recomendado)**

```bash
# Atualiza planilha automaticamente a cada 1 segundo
./start_rtd.sh update
```

---

## 📁 Estrutura de Arquivos

```
services/rtd-bridge/
├── profitchart_rtd_server.py    # Servidor WebSocket principal
├── dde_wrapper.py                # Wrapper DDE para Wine/COM
├── calc_client.py                # Cliente WebSocket para Calc
├── calc_rtd_macro.bas            # Macro LibreOffice (alternativo)
├── create_calc_template.py       # Gerador de template ODS
├── ods_rtd_updater.py            # Atualizador automático ODS
├── start_rtd.sh                  # Script de gerenciamento
└── README_RTD_INTEGRATION.md     # Esta documentação
```

---

## 🔧 Componentes

### 1. RTD Bridge Server (`profitchart_rtd_server.py`)

Servidor WebSocket que:
- 📊 Captura dados do ProfitChart via DDE wrapper
- 🌐 Disponibiliza via WebSocket (ws://localhost:8765)
- 📡 Broadcast para múltiplos clientes
- ⏱️ Atualização a cada 1 segundo

**Uso:**
```bash
python3 profitchart_rtd_server.py
```

### 2. DDE Wrapper (`dde_wrapper.py`)

Script auxiliar para acessar DDE do ProfitChart:
- 🍷 Roda via Wine quando necessário
- 🔌 Conecta ao DDE do ProfitChart
- 📤 Retorna JSON com cotações

**Modo atual:** MOCK (dados simulados para desenvolvimento)

**Para produção:** Implementar conexão DDE real via pywin32

### 3. Cliente Calc (`calc_client.py`)

Cliente Python WebSocket com 3 modos:

**Modo Simple:** Obtém dados uma vez e imprime JSON
```bash
python3 calc_client.py --mode simple
```

**Modo Interactive:** Exibe dados continuamente no terminal
```bash
python3 calc_client.py --mode interactive
```

**Modo UNO:** Integração direta com LibreOffice (em desenvolvimento)
```bash
python3 calc_client.py --mode uno
```

### 4. Atualizador ODS (`ods_rtd_updater.py`)

Atualiza arquivo ODS diretamente:
- 📝 Modifica planilha em disco
- 🔄 Atualização automática a cada 1s
- 💾 Salva automaticamente

**Uso:**
```bash
python3 ods_rtd_updater.py ~/Documentos/ProfitChart_RTD.ods
```

### 5. Macro LibreOffice (`calc_rtd_macro.bas`)

Macro Basic para LibreOffice:
- 📞 Chama calc_client.py
- 🔄 Atualiza células via Basic
- ⚙️ Alternativa ao updater Python

**Instalação:**
1. Abra LibreOffice Calc
2. Ferramentas → Macros → Editar Macros
3. Cole o conteúdo de `calc_rtd_macro.bas`
4. Execute: `StartRTDConnection()`

---

## 🎯 Símbolos Suportados

Atualmente configurados:
- 📈 PETR3 - Petrobras PN
- 📈 VALE3 - Vale ON
- 📈 PETR4 - Petrobras PN (novo)
- 📈 VALE5 - Vale PNA (novo)
- 📈 ITUB4 - Itaú Unibanco PN
- 📈 BBAS3 - Banco do Brasil ON

Para adicionar mais símbolos, edite:
```python
# Em profitchart_rtd_server.py
self.symbols = ['PETR3', 'VALE3', 'NOVO_SIMBOLO']
```

---

## 📊 Dados Disponíveis

Para cada símbolo:

```json
{
  "PETR3": {
    "symbol": "PETR3",
    "last": 38.50,         // Última cotação
    "bid": 38.48,          // Melhor compra
    "ask": 38.52,          // Melhor venda
    "open": 38.30,         // Abertura
    "high": 38.75,         // Máxima
    "low": 38.20,          // Mínima
    "volume": 12500000,    // Volume negociado
    "variation": 0.52,     // Variação % do dia
    "timestamp": "2026-01-30T10:30:45",
    "status": "OPEN"       // OPEN, CLOSED, AUCTION
  }
}
```

---

## 🔨 Comandos Úteis

### Gerenciamento de Serviços

```bash
# Ver status
./start_rtd.sh status

# Iniciar tudo
./start_rtd.sh start

# Parar tudo
./start_rtd.sh stop

# Ajuda
./start_rtd.sh help
```

### Debug

```bash
# Ver log do RTD Server
tail -f /tmp/rtd_server.log

# Ver log do ProfitChart
tail -f /tmp/profitchart.log

# Testar WebSocket manualmente
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8765') as ws:
        await ws.send(json.dumps({'command': 'get_data'}))
        print(await ws.recv())
asyncio.run(test())
"
```

### Verificar Processos

```bash
# ProfitChart rodando?
pgrep -f profitchart.exe

# RTD Server rodando?
lsof -i :8765

# LibreOffice rodando?
pgrep -f soffice
```

---

## 🐛 Troubleshooting

### Problema: RTD Server não inicia

**Sintomas:** Porta 8765 não abre

**Solução:**
```bash
# Verificar se porta já está em uso
lsof -i :8765

# Matar processo antigo
kill $(lsof -t -i :8765)

# Reiniciar
./start_rtd.sh start
```

### Problema: ProfitChart não inicia via Wine

**Sintomas:** `profitchart.exe` não encontrado

**Solução:**
```bash
# Localizar instalação
find ~/.wine* -name "profitchart.exe"

# Atualizar caminho em start_rtd.sh
vim services/rtd-bridge/start_rtd.sh
# Editar linha: PROFITCHART_PATH="..."
```

### Problema: Dependências Python faltando

**Sintomas:** `ModuleNotFoundError: No module named 'websockets'`

**Solução:**
```bash
pip3 install --user websockets odfpy
```

### Problema: Planilha não atualiza

**Sintomas:** Valores permanecem em 0.00

**Verificações:**
1. RTD Server está rodando? `./start_rtd.sh status`
2. Cliente está conectado? Veja `/tmp/rtd_server.log`
3. ProfitChart fornecendo dados? (Atualmente em modo MOCK)

---

## 🚧 Status de Desenvolvimento

### ✅ Implementado

- [x] Servidor WebSocket RTD Bridge
- [x] Wrapper DDE (mock para desenvolvimento)
- [x] Cliente Python para Calc
- [x] Atualizador automático ODS
- [x] Script de gerenciamento (`start_rtd.sh`)
- [x] Template de planilha ODS
- [x] Macro LibreOffice Basic
- [x] Documentação completa

### 🚧 Em Desenvolvimento

- [ ] Conexão DDE real com ProfitChart via Wine/pywin32
- [ ] UNO Bridge para integração nativa com LibreOffice
- [ ] Testes automatizados
- [ ] Docker container para RTD Server

### 🎯 Próximos Passos

#### 1. Implementar DDE Real (Alta Prioridade)

Atualmente, o `dde_wrapper.py` usa dados MOCK. Para conectar ao ProfitChart real:

**Passo A: Instalar Python no Wine**
```bash
# Baixar Python 3.x installer
wget https://www.python.org/ftp/python/3.11.7/python-3.11.7-amd64.exe

# Instalar no Wine
wine python-3.11.7-amd64.exe
```

**Passo B: Instalar pywin32 no Wine**
```bash
wine python -m pip install pywin32
```

**Passo C: Criar script DDE Windows**

Crie `services/rtd-bridge/dde_windows_client.py`:

```python
import win32ui
import ddeml
import json
import sys

# Criar servidor DDE
server = ddeml.CreateServer()
server.Create("PythonDDE")

# Conectar ao ProfitChart
# Nota: Sintaxe exata depende da documentação do ProfitChart
conversation = server.ConnectTo("PROFITCHART", "QUOTE")

symbols = sys.argv[1:]
result = {}

for symbol in symbols:
    try:
        # Requisitar cotação
        data = conversation.Request(symbol)
        # Parse e adicionar ao resultado
        result[symbol] = parse_quote_data(data)
    except Exception as e:
        result[symbol] = {"error": str(e)}

print(json.dumps(result))
```

**Passo D: Atualizar dde_wrapper.py**

Modificar função `connect_dde_wine()` para chamar script Windows:

```python
def connect_dde_wine(symbols: list) -> dict:
    result = subprocess.run([
        'wine', 'python',
        'dde_windows_client.py',
        *symbols
    ], capture_output=True, text=True)
    
    return json.loads(result.stdout)
```

#### 2. Implementar UNO Bridge (Opcional)

Para integração mais profunda com LibreOffice:

```python
import uno
from com.sun.star.beans import PropertyValue

# Conectar ao LibreOffice
local_context = uno.getComponentContext()
resolver = local_context.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", local_context)

# Obter documento
ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
desktop = ctx.ServiceManager.createInstanceWithContext(
    "com.sun.star.frame.Desktop", ctx)

doc = desktop.getCurrentComponent()
sheet = doc.Sheets.getByIndex(0)

# Atualizar célula
cell = sheet.getCellByPosition(1, 1)  # B2
cell.Value = 38.50
```

#### 3. Docker Container (Produção)

Criar `services/rtd-bridge/Dockerfile`:

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip wine64 libreoffice

WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 8765

CMD ["python3", "profitchart_rtd_server.py"]
```

---

## 📚 Referências

### Documentação Técnica

- **DDE Protocol:** https://docs.microsoft.com/en-us/windows/win32/dataxchg/dynamic-data-exchange
- **pywin32:** https://github.com/mhammond/pywin32
- **WebSocket Protocol:** https://datatracker.ietf.org/doc/html/rfc6455
- **LibreOffice UNO:** https://wiki.documentfoundation.org/Documentation/DevGuide

### Projeto B3 Trading Platform

- [PROFITPRO_INTEGRATION.md](../../docs/PROFITPRO_INTEGRATION.md) - Integração ProfitChart
- [INSTRUCOES.md](../../INSTRUCOES.md) - Instruções gerais do projeto
- [README.md](../../README.md) - Visão geral da plataforma

---

## 📞 Suporte

Para problemas ou dúvidas:

1. Verifique logs: `/tmp/rtd_server.log` e `/tmp/profitchart.log`
2. Execute: `./start_rtd.sh status` para diagnóstico
3. Consulte seção de Troubleshooting acima
4. Revise documentação do ProfitChart sobre DDE/RTD

---

## 📄 Licença

Este componente é parte do B3 Trading Platform.

**Autor:** B3 Trading Platform Team  
**Data:** 30 Janeiro 2026  
**Versão:** 1.0.0

---

## ✨ Changelog

### v1.0.0 - 30/01/2026
- ✅ Implementação inicial
- ✅ Servidor WebSocket RTD Bridge
- ✅ DDE Wrapper (modo mock)
- ✅ Cliente Python para Calc
- ✅ Atualizador ODS automático
- ✅ Script de gerenciamento completo
- ✅ Documentação abrangente
