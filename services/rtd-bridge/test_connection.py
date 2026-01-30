#!/usr/bin/env python3
"""
Teste rápido do RTD Bridge via WebSocket
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("❌ Instale: python3 -m pip install --user websockets")
    sys.exit(1)


async def test_rtd():
    """Testa conexão com RTD Bridge"""
    uri = "ws://localhost:8765"
    
    try:
        print(f"🔌 Conectando ao RTD Bridge: {uri}")
        async with websockets.connect(uri) as websocket:
            print("✅ Conectado!")
            
            # Solicitar dados
            await websocket.send(json.dumps({'command': 'get_data'}))
            print("📤 Solicitação enviada")
            
            # Aguardar resposta
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            print("\n📊 Dados recebidos:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            return True
            
    except asyncio.TimeoutError:
        print("❌ Timeout ao aguardar resposta")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_rtd())
    sys.exit(0 if success else 1)
