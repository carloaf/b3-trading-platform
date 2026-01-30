#!/usr/bin/env python3
"""
LibreOffice Calc Client - WebSocket
====================================

Cliente Python que se conecta ao RTD Bridge Server e fornece interface
simples para o LibreOffice Calc via stdin/stdout ou arquivo temporário.

Uso:
    1. Como script standalone: python3 calc_client.py
    2. Chamado pelo Calc macro: GetMarketDataFromPython()
    3. Via UNO bridge (avançado)

Autor: B3 Trading Platform
Data: 30 Janeiro 2026
"""

import asyncio
import json
import sys
from typing import Dict, Optional

try:
    import websockets
except ImportError:
    print("❌ Instale websockets: pip3 install websockets", file=sys.stderr)
    sys.exit(1)


class CalcRTDClient:
    """Cliente WebSocket para LibreOffice Calc"""
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.market_data: Dict = {}
        
    async def connect(self) -> bool:
        """Conecta ao servidor RTD"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            return True
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}", file=sys.stderr)
            return False
    
    async def get_market_data(self) -> Dict:
        """Obtém dados de mercado atuais"""
        if not self.websocket:
            return {}
        
        try:
            # Solicitar dados
            await self.websocket.send(json.dumps({'command': 'get_data'}))
            
            # Aguardar resposta (timeout 5s)
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=5.0
            )
            
            data = json.loads(response)
            
            if data.get('type') == 'market_data':
                self.market_data = data.get('data', {})
                return self.market_data
            
        except asyncio.TimeoutError:
            print("⚠️ Timeout ao obter dados", file=sys.stderr)
        except Exception as e:
            print(f"❌ Erro: {e}", file=sys.stderr)
        
        return {}
    
    async def subscribe(self, symbols: list):
        """Inscreve-se para receber atualizações de símbolos"""
        if not self.websocket:
            return
        
        await self.websocket.send(json.dumps({
            'command': 'subscribe',
            'symbols': symbols
        }))
    
    async def close(self):
        """Fecha conexão"""
        if self.websocket:
            await self.websocket.close()


async def main_simple():
    """Modo simples: obtém dados e imprime JSON"""
    client = CalcRTDClient()
    
    if not await client.connect():
        print(json.dumps({'error': 'Servidor não disponível'}))
        sys.exit(1)
    
    # Obter dados
    data = await client.get_market_data()
    
    # Imprimir JSON para stdout
    print(json.dumps(data))
    
    await client.close()


async def main_interactive():
    """Modo interativo: atualização contínua"""
    client = CalcRTDClient()
    
    print("🔌 Conectando ao RTD Bridge Server...")
    
    if not await client.connect():
        print("❌ Não foi possível conectar ao servidor")
        return
    
    print("✅ Conectado! Aguardando dados...\n")
    
    # Inscrever em símbolos
    await client.subscribe(['PETR3', 'VALE3', 'PETR4', 'VALE5'])
    
    try:
        while True:
            data = await client.get_market_data()
            
            if data:
                print("\n" + "="*70)
                print(f"📊 Dados de Mercado - {data.get('timestamp', 'N/A')}")
                print("="*70)
                
                for symbol, quote in data.items():
                    print(f"\n{symbol}:")
                    print(f"  Último:     R$ {quote.get('last', 0):.2f}")
                    print(f"  Variação:   {quote.get('variation', 0):+.2f}%")
                    print(f"  Abertura:   R$ {quote.get('open', 0):.2f}")
                    print(f"  Máxima:     R$ {quote.get('high', 0):.2f}")
                    print(f"  Mínima:     R$ {quote.get('low', 0):.2f}")
                    print(f"  Volume:     {quote.get('volume', 0):,}")
                    print(f"  Status:     {quote.get('status', 'N/A')}")
            
            await asyncio.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Encerrando...")
    finally:
        await client.close()


async def main_uno_bridge():
    """
    Modo UNO Bridge: integração direta com LibreOffice
    
    Requer: python3-uno instalado
    """
    try:
        import uno
        from com.sun.star.beans import PropertyValue
    except ImportError:
        print("❌ python3-uno não instalado", file=sys.stderr)
        print("   Instale: sudo apt install python3-uno", file=sys.stderr)
        return
    
    # TODO: Implementar integração UNO
    print("🚧 UNO Bridge em desenvolvimento")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cliente RTD para LibreOffice Calc")
    parser.add_argument('--mode', choices=['simple', 'interactive', 'uno'], 
                       default='simple',
                       help='Modo de operação')
    
    args = parser.parse_args()
    
    if args.mode == 'simple':
        asyncio.run(main_simple())
    elif args.mode == 'interactive':
        asyncio.run(main_interactive())
    elif args.mode == 'uno':
        asyncio.run(main_uno_bridge())
