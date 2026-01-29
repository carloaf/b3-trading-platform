#!/usr/bin/env python3
"""
Runner para Paper Trading Wave3 v2.1
====================================

Script para iniciar e monitorar paper trading em produção.

Uso:
    # Modo teste (10 ciclos de 30s)
    python run_paper_trading_wave3.py --test
    
    # Modo produção (contínuo 24/7)
    python run_paper_trading_wave3.py --symbols PETR4 VALE3 ITUB4 BBDC4 ABEV3
    
    # Com parâmetros customizados
    python run_paper_trading_wave3.py \
        --capital 100000 \
        --min-score 60 \
        --max-positions 3 \
        --interval 3600 \
        --symbols PETR4 VALE3
"""

import asyncio
import argparse
import signal
from datetime import datetime
from loguru import logger
import sys
sys.path.append('/app/src')

from paper_trading_wave3 import Wave3PaperTrader


class PaperTradingRunner:
    """Runner para gerenciar execução do paper trading."""
    
    def __init__(
        self,
        symbols: list,
        initial_capital: float = 100000.0,
        min_score: int = 55,
        max_positions: int = 5,
        scan_interval: int = 3600,  # 1 hora
        test_mode: bool = False
    ):
        self.symbols = symbols
        self.scan_interval = scan_interval
        self.test_mode = test_mode
        self.running = True
        
        # Configuração TimescaleDB (container Docker)
        self.trader = Wave3PaperTrader(
            initial_capital=initial_capital,
            quality_score_threshold=min_score,
            max_positions=max_positions,
            risk_per_trade=0.02,
            db_host='b3-postgres',
            db_port=5432,
            db_user='b3trading_user',
            db_password='b3trading_pass',
            db_name='b3trading_db',
            timescale_host='b3-timescaledb',
            timescale_port=5432,
            timescale_user='b3trading_ts',
            timescale_password='b3trading_ts_pass',
            timescale_db='b3trading_market'
        )
        
        # Handler para Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handler para sinais de interrupção."""
        logger.warning(f"\n⚠️ Sinal recebido: {signum}")
        logger.warning("🛑 Parando paper trading gracefully...")
        self.running = False
    
    async def run(self):
        """Executa o paper trading."""
        try:
            # Conectar databases
            await self.trader.connect_databases()
            
            # Banner de inicialização
            logger.info("\n" + "="*70)
            logger.info("🚀 PAPER TRADING WAVE3 v2.1 - PRODUÇÃO")
            logger.info("="*70)
            logger.info(f"💰 Capital: R$ {self.trader.initial_capital:,.2f}")
            logger.info(f"⭐ Score mínimo: {self.trader.quality_threshold}")
            logger.info(f"📊 Max posições: {self.trader.max_positions}")
            logger.info(f"🎯 Símbolos: {', '.join(self.symbols)}")
            logger.info(f"⏱️ Intervalo: {self.scan_interval}s")
            if self.test_mode:
                logger.warning("⚠️ MODO TESTE ATIVADO (10 ciclos)")
            logger.info("="*70 + "\n")
            
            # Iniciar trader
            await self.trader.start(
                symbols=self.symbols,
                scan_interval=self.scan_interval,
                trading_hours_only=False  # Desabilitar para testes 24/7
            )
            
            # Loop de monitoramento
            cycle = 0
            max_cycles = 10 if self.test_mode else float('inf')
            
            while self.running and cycle < max_cycles:
                cycle += 1
                
                # Header do ciclo
                logger.info("\n" + "─"*70)
                logger.info(f"🔄 CICLO #{cycle} - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                logger.info("─"*70)
                
                # Aguardar próximo scan (ou 30s no modo teste)
                wait_time = 30 if self.test_mode else self.scan_interval
                
                for remaining in range(wait_time, 0, -10):
                    if not self.running:
                        break
                    
                    # Status a cada 10 segundos
                    status = self.trader.get_status()
                    
                    logger.info(
                        f"⏳ Próximo scan em {remaining}s | "
                        f"💰 Capital: R$ {status['current_capital']:,.2f} | "
                        f"📊 P&L: {status['total_pnl_pct']:+.2f}% | "
                        f"📍 Posições: {status['open_positions']}/{self.trader.max_positions} | "
                        f"🎯 Trades: {status['total_trades']} ({status['win_rate']:.1f}% win)"
                    )
                    
                    await asyncio.sleep(10)
            
            # Finalização
            logger.info("\n" + "="*70)
            logger.success("✅ PAPER TRADING FINALIZADO")
            logger.info("="*70)
            
            # Relatório final
            await self.print_final_report()
            
        except KeyboardInterrupt:
            logger.warning("\n⚠️ Interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro durante execução: {e}")
            raise
        finally:
            # Cleanup
            await self.trader.stop()
            logger.success("✅ Cleanup completo")
    
    async def print_final_report(self):
        """Imprime relatório final de performance."""
        status = self.trader.get_status()
        
        logger.info("\n📊 RELATÓRIO FINAL")
        logger.info("─"*70)
        logger.info(f"Capital inicial:     R$ {status['initial_capital']:>15,.2f}")
        logger.info(f"Capital final:       R$ {status['current_capital']:>15,.2f}")
        logger.info(f"P&L realizado:       R$ {status['realized_pnl']:>15,.2f}")
        logger.info(f"P&L não realizado:   R$ {status['unrealized_pnl']:>15,.2f}")
        logger.info(f"P&L total:           R$ {status['total_pnl']:>15,.2f} ({status['total_pnl_pct']:+.2f}%)")
        logger.info("─"*70)
        logger.info(f"Total de trades:     {status['total_trades']:>20}")
        logger.info(f"Trades vencedores:   {status['winning_trades']:>20}")
        logger.info(f"Trades perdedores:   {status['losing_trades']:>20}")
        logger.info(f"Win rate:            {status['win_rate']:>19.2f}%")
        if status['total_trades'] > 0:
            logger.info(f"Média win:           {status['avg_win_pct']:>19.2f}%")
            logger.info(f"Média loss:          {status['avg_loss_pct']:>19.2f}%")
        logger.info("─"*70)
        logger.info(f"Posições abertas:    {status['open_positions']:>20}")
        
        # Posições abertas
        if status['open_positions'] > 0:
            logger.info("\n📍 POSIÇÕES ABERTAS:")
            for pos in status.get('positions', []):
                emoji = "🟢" if pos['unrealized_pnl_pct'] > 0 else "🔴"
                logger.info(
                    f"  {emoji} {pos['symbol']}: "
                    f"R$ {pos['current_price']:.2f} | "
                    f"P&L: {pos['unrealized_pnl_pct']:+.2f}% "
                    f"(R$ {pos['unrealized_pnl']:+,.2f})"
                )
        
        logger.info("\n" + "="*70 + "\n")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='Runner para Paper Trading Wave3 v2.1',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Modo teste (10 ciclos de 30s)
  python run_paper_trading_wave3.py --test
  
  # 5 ativos prioritários (produção)
  python run_paper_trading_wave3.py --symbols PETR4 VALE3 ITUB4 BBDC4 ABEV3
  
  # Com parâmetros customizados
  python run_paper_trading_wave3.py \\
      --capital 50000 \\
      --min-score 60 \\
      --max-positions 3 \\
      --interval 1800 \\
      --symbols PETR4 VALE3
        """
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3'],
        help='Símbolos B3 para monitorar (default: 5 prioritários)'
    )
    
    parser.add_argument(
        '--capital',
        type=float,
        default=100000.0,
        help='Capital inicial em R$ (default: 100000)'
    )
    
    parser.add_argument(
        '--min-score',
        type=int,
        default=55,
        help='Score Wave3 mínimo para aceitar sinal (default: 55)'
    )
    
    parser.add_argument(
        '--max-positions',
        type=int,
        default=5,
        help='Máximo de posições simultâneas (default: 5)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Intervalo entre scans em segundos (default: 3600 = 1h)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Modo teste (10 ciclos de 30s)'
    )
    
    args = parser.parse_args()
    
    # Criar runner
    runner = PaperTradingRunner(
        symbols=args.symbols,
        initial_capital=args.capital,
        min_score=args.min_score,
        max_positions=args.max_positions,
        scan_interval=args.interval,
        test_mode=args.test
    )
    
    # Executar
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
