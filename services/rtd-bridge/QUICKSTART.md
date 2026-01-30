# 🚀 Quick Start - RTD Bridge

## ✅ Sistema Testado e Funcionando!

O RTD Bridge está rodando em **container Docker** e pronto para uso.

## 📊 Status Atual

```bash
Container:  b3-rtd-bridge  ✅ HEALTHY
WebSocket:  ws://localhost:8765
Modo:       MOCK (dados simulados)
Símbolos:   PETR3, VALE3, PETR4, VALE5
```

---

## 🎯 Uso Básico

### 1. Gerenciar Container

```bash
cd services/rtd-bridge

# Ver status
./manage_container.sh status

# Parar
./manage_container.sh stop

# Iniciar
./manage_container.sh start

# Reiniciar
./manage_container.sh restart

# Ver logs
./manage_container.sh logs
```

### 2. Testar Conexão

```bash
# Teste simples (retorna JSON)
docker exec b3-rtd-bridge python3 calc_client.py --mode simple

# Teste interativo (atualização contínua)
docker exec b3-rtd-bridge python3 calc_client.py --mode interactive
```

### 3. Integrar com LibreOffice Calc

**Opção A: Via Python (recomendado)**

```bash
# 1. Criar template de planilha
./manage_container.sh create-template

# 2. Iniciar atualizador automático
./manage_container.sh update ~/Documentos/ProfitChart_RTD.ods

# 3. Abrir LibreOffice Calc normalmente
libreoffice ~/Documentos/ProfitChart_RTD.ods
```

**Opção B: Via Script Host**

No host (fora do container), você pode criar um script que consulta o WebSocket:

```python
#!/usr/bin/env python3
import asyncio
import websockets
import json

async def get_quotes():
    async with websockets.connect('ws://localhost:8765') as ws:
        await ws.send(json.dumps({'command': 'get_data'}))
        response = await ws.recv()
        return json.loads(response)

quotes = asyncio.run(get_quotes())
print(quotes)
```

---

## 🔧 Configuração

### Adicionar Símbolos

Edite `profitchart_rtd_server.py`:

```python
self.symbols = ['PETR3', 'VALE3', 'ITUB4', 'BBAS3', 'NOVO_SIMBOLO']
```

Depois:
```bash
./manage_container.sh restart
```

### Mudar para Modo Produção

No `docker-compose.yml`, altere:

```yaml
environment:
  - PROFITCHART_MODE=production  # Tentará conectar ao ProfitChart real
```

---

## 📱 API WebSocket

### Conectar

```javascript
// JavaScript/Node.js
const ws = new WebSocket('ws://localhost:8765');
```

```python
# Python
import websockets
ws = await websockets.connect('ws://localhost:8765')
```

### Comandos Disponíveis

**1. Obter Dados**
```json
{"command": "get_data"}
```

Resposta:
```json
{
  "type": "market_data",
  "data": {
    "PETR3": {
      "last": 38.50,
      "variation": 1.2,
      "open": 38.30,
      "high": 38.75,
      "low": 38.20,
      "volume": 12500000,
      "status": "OPEN"
    }
  },
  "timestamp": "2026-01-30T20:53:27.984300"
}
```

**2. Inscrever-se em Símbolos**
```json
{"command": "subscribe", "symbols": ["ITUB4", "BBAS3"]}
```

**3. Ping**
```json
{"command": "ping"}
```

Resposta:
```json
{"type": "pong", "timestamp": 1706647207.984}
```

---

## 📊 Exemplo: Integração Completa

```python
#!/usr/bin/env python3
"""
Exemplo: Atualizar planilha LibreOffice em tempo real
"""

import asyncio
import websockets
import json
from odfpy import opendocument, table, text

async def update_calc_realtime(ods_file):
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as ws:
        print("✅ Conectado ao RTD Bridge")
        
        while True:
            # Solicitar dados
            await ws.send(json.dumps({'command': 'get_data'}))
            response = await ws.recv()
            data = json.loads(response)
            
            if data.get('type') == 'market_data':
                quotes = data['data']
                
                # Atualizar planilha
                doc = opendocument.load(ods_file)
                sheet = doc.spreadsheet.getElementsByType(table.Table)[0]
                
                # Atualizar células...
                # (veja ods_rtd_updater.py para implementação completa)
                
                doc.save(ods_file)
                print(f"🔄 Atualizado: {len(quotes)} símbolos")
            
            await asyncio.sleep(1)

# Uso
asyncio.run(update_calc_realtime('~/Documentos/ProfitChart_RTD.ods'))
```

---

## 🎯 Próximos Passos

### Para usar dados REAIS do ProfitChart:

1. **Instalar pywin32 no Wine**
   ```bash
   wine python -m pip install pywin32
   ```

2. **Implementar cliente DDE real**
   
   Edite `dde_wrapper.py` e substitua a função `connect_dde_wine()` por:
   
   ```python
   def connect_dde_wine(symbols: list) -> dict:
       # Chamar script Windows via Wine
       result = subprocess.run([
           'wine', 'python',
           'dde_windows_client.py',
           *symbols
       ], capture_output=True, text=True)
       
       return json.loads(result.stdout)
   ```

3. **Criar dde_windows_client.py**
   
   Script Python Windows que usa pywin32 para acessar DDE do ProfitChart.

4. **Testar conexão**
   ```bash
   # Garantir que ProfitChart está rodando
   wine ~/.wine*/path/to/profitchart.exe &
   
   # Testar RTD
   ./manage_container.sh test
   ```

---

## 🆘 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker logs b3-rtd-bridge

# Reconstruir
./manage_container.sh stop
docker rmi b3-rtd-bridge:latest
./manage_container.sh build
./manage_container.sh start
```

### WebSocket não conecta

```bash
# Verificar se porta está aberta
netstat -tlnp | grep 8765

# Testar do host
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Host: localhost:8765" \
     -H "Origin: http://localhost" \
     http://localhost:8765
```

### Dados não atualizam

```bash
# Ver logs em tempo real
./manage_container.sh logs

# Verificar se está em modo MOCK
docker exec b3-rtd-bridge env | grep PROFITCHART_MODE
```

---

## 📚 Documentação Completa

- [README_RTD_INTEGRATION.md](README_RTD_INTEGRATION.md) - Documentação técnica detalhada
- [calc_rtd_macro.bas](calc_rtd_macro.bas) - Macro LibreOffice (alternativa)
- [Docker Compose](../../docker-compose.yml) - Configuração do container

---

**Autor:** B3 Trading Platform Team  
**Data:** 30 Janeiro 2026  
**Status:** ✅ Testado e Funcionando (Modo MOCK)
