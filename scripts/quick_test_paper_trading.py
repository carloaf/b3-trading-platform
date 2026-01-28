#!/usr/bin/env python3
"""
Quick Test - Wave3 Paper Trading
Teste rápido de 5 minutos com PETR4
"""

import asyncio
import sys
sys.path.append('/app/src')

from paper_trading_wave3 import Wave3PaperTrader
from loguru import logger
import os

# Configurar logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

async def main():
    """Teste rápido de 5 minutos"""
    
    logger.info("=" * 60)
    logger.info("🧪 TESTE RÁPIDO - WAVE3 PAPER TRADING")
    logger.info("=" * 60)
    logger.info("⏱️  Duração: 5 minutos (5 scans de 60s)")
    logger.info("📊 Símbolo: PETR4")
    logger.info("⚙️  Config: capital=100k, max_pos=1, quality≥55")
    logger.info("=" * 60)
    logger.info("")
    
    # Criar trader
    trader = Wave3PaperTrader(
        initial_capital=100000.0,
        quality_score_threshold=55,
        max_positions=1,  # Apenas 1 posição no teste
        risk_per_trade=0.02,
        db_host='b3-postgres',
        db_port=5432,
        timescale_host='b3-timescaledb',
        timescale_port=5432
    )
    
    try:
        # Conectar databases
        logger.info("🔌 Conectando aos bancos de dados...")
        await trader.connect_databases()
        logger.info("")
        
        # Executar 5 scans
        trader.is_running = True
        
        for i in range(5):
            logger.info(f"🔍 Scan {i+1}/5 - Escaneando PETR4...")
            
            try:
                # Scan do símbolo
                await trader.scan_symbol('PETR4')
                
                # Atualizar posições abertas
                await trader.update_positions()
                
            except Exception as e:
                logger.error(f"❌ Erro no scan: {e}")
            
            # Aguardar 60s (exceto no último scan)
            if i < 4:
                logger.info(f"⏸️  Aguardando 60 segundos...\n")
                await asyncio.sleep(60)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 STATUS FINAL")
        logger.info("=" * 60)
        
        # Status final
        await trader.log_status()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ TESTE CONCLUÍDO COM SUCESSO!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        await trader.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
