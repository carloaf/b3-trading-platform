#!/usr/bin/env python3
"""
ProfitChart RTD Bridge Server
==============================

Servidor Python que captura dados em tempo real do ProfitChart via DDE/COM
e disponibiliza via WebSocket para o LibreOffice Calc.

Arquitetura:
    ProfitChart (Wine) --> DDE/COM --> Python Bridge --> WebSocket --> LibreOffice Calc

Autor: B3 Trading Platform
Data: 30 Janeiro 2026
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProfitChartRTDServer:
    """
    Servidor de ponte RTD entre ProfitChart e LibreOffice Calc
    """
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.market_data: Dict[str, Dict] = {}
        self.profit_process: Optional[subprocess.Popen] = None
        self.running = False
        
        # Símbolos a monitorar
        self.symbols = ['PETR3', 'VALE3', 'PETR4', 'VALE5']
        
    async def start(self):
        """Inicia o servidor WebSocket e captura de dados"""
        logger.info(f"🚀 Iniciando RTD Bridge Server na porta {self.port}")
        
        # Verificar modo de operação
        mode = os.getenv('PROFITCHART_MODE', 'mock')
        
        if mode == 'production':
            # Apenas em produção: Iniciar ProfitChart se não estiver rodando
            try:
                await self.ensure_profitchart_running()
            except FileNotFoundError:
                logger.warning("⚠️ ProfitChart não encontrado, rodando em modo MOCK")
        else:
            logger.info("ℹ️ Rodando em modo MOCK (dados simulados)")
        
        # Iniciar servidor WebSocket
        async with websockets.serve(self.handle_client, "0.0.0.0", self.port):
            logger.info(f"✅ WebSocket Server rodando em ws://0.0.0.0:{self.port}")
            
            # Loop de captura de dados
            self.running = True
            try:
                await asyncio.gather(
                    self.data_capture_loop(),
                    self.keep_alive_loop()
                )
            except KeyboardInterrupt:
                logger.info("🛑 Encerrando servidor...")
                self.running = False
    
    async def ensure_profitchart_running(self):
        """Verifica se ProfitChart está rodando via Wine"""
        logger.info("🔍 Verificando ProfitChart...")
        
        # Verificar se processo já existe
        result = subprocess.run(
            ['pgrep', '-f', 'profitchart.exe'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ ProfitChart já está rodando")
            return
        
        # Iniciar ProfitChart
        logger.info("🚀 Iniciando ProfitChart via Wine...")
        profit_exe = Path.home() / ".wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit/profitchart.exe"
        
        if not profit_exe.exists():
            logger.error(f"❌ ProfitChart não encontrado em: {profit_exe}")
            raise FileNotFoundError(f"ProfitChart não encontrado: {profit_exe}")
        
        try:
            self.profit_process = subprocess.Popen(
                ['wine', str(profit_exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=profit_exe.parent
            )
            logger.info("✅ ProfitChart iniciado")
            
            # Aguardar inicialização
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar ProfitChart: {e}")
            raise
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """Manipula conexão de cliente WebSocket"""
        client_id = id(websocket)
        logger.info(f"📱 Cliente conectado: {client_id}")
        
        self.clients.add(websocket)
        
        try:
            # Enviar dados atuais imediatamente
            await self.send_current_data(websocket)
            
            # Manter conexão aberta e processar mensagens
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Cliente desconectado: {client_id}")
        finally:
            self.clients.discard(websocket)
    
    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Processa mensagens do cliente"""
        try:
            data = json.loads(message)
            command = data.get('command')
            
            if command == 'subscribe':
                symbols = data.get('symbols', [])
                logger.info(f"📊 Cliente solicitou inscrição: {symbols}")
                self.symbols.extend([s for s in symbols if s not in self.symbols])
                
            elif command == 'get_data':
                await self.send_current_data(websocket)
                
            elif command == 'ping':
                await websocket.send(json.dumps({'type': 'pong', 'timestamp': time.time()}))
                
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Mensagem inválida recebida: {message}")
    
    async def send_current_data(self, websocket: WebSocketServerProtocol):
        """Envia dados atuais para um cliente"""
        if self.market_data:
            message = {
                'type': 'market_data',
                'data': self.market_data,
                'timestamp': datetime.now().isoformat()
            }
            await websocket.send(json.dumps(message))
    
    async def broadcast_data(self):
        """Envia dados para todos os clientes conectados"""
        if not self.clients:
            return
        
        message = {
            'type': 'market_data',
            'data': self.market_data,
            'timestamp': datetime.now().isoformat()
        }
        
        # Enviar para todos os clientes
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        
        # Remover clientes desconectados
        self.clients -= disconnected
    
    async def data_capture_loop(self):
        """Loop principal de captura de dados do ProfitChart"""
        logger.info("🔄 Iniciando captura de dados...")
        
        while self.running:
            try:
                # Capturar dados via DDE wrapper
                await self.capture_market_data()
                
                # Broadcast para clientes
                if self.market_data:
                    await self.broadcast_data()
                
                # Aguardar antes da próxima captura (1 segundo)
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Erro na captura de dados: {e}")
                await asyncio.sleep(5)
    
    async def capture_market_data(self):
        """
        Captura dados do ProfitChart via script DDE Wine
        
        Nota: Esta função chama um script auxiliar que usa Wine + pywin32
        para acessar o DDE do ProfitChart
        """
        try:
            # Caminho do script no container
            script_dir = Path(__file__).parent
            dde_script = script_dir / "dde_wrapper.py"
            
            # Executar script DDE wrapper
            result = await asyncio.create_subprocess_exec(
                'python3',
                str(dde_script),
                *self.symbols,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and stdout:
                # Parse JSON retornado
                data = json.loads(stdout.decode())
                self.market_data.update(data)
                
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"📊 Dados capturados: {data}")
            else:
                if stderr:
                    logger.warning(f"⚠️ DDE wrapper error: {stderr.decode()}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao decodificar JSON: {e}")
        except Exception as e:
            logger.error(f"❌ Erro ao capturar dados: {e}")
    
    async def keep_alive_loop(self):
        """Loop de keep-alive para debug"""
        while self.running:
            await asyncio.sleep(30)
            logger.info(f"💓 Servidor ativo | Clientes: {len(self.clients)} | Símbolos: {len(self.market_data)}")
    
    def cleanup(self):
        """Limpeza ao encerrar"""
        logger.info("🧹 Limpando recursos...")
        
        if self.profit_process:
            try:
                self.profit_process.terminate()
                self.profit_process.wait(timeout=5)
                logger.info("✅ ProfitChart encerrado")
            except:
                self.profit_process.kill()


async def main():
    """Função principal"""
    server = ProfitChartRTDServer(port=8765)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("🛑 Encerrando por solicitação do usuário")
    finally:
        server.cleanup()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     📊 ProfitChart RTD Bridge Server                         ║
║                                                               ║
║     Ponte entre ProfitChart (Wine) e LibreOffice Calc        ║
║                                                               ║
║     🔌 WebSocket: ws://localhost:8765                        ║
║     📈 Símbolos: PETR3, VALE3, PETR4, VALE5                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())
