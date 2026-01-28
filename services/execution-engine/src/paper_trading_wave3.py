#!/usr/bin/env python3
"""
Wave3 Paper Trading Manager - Produção
=======================================

Gerenciador completo de paper trading integrado com Wave3 v2.1

Features:
- Scan automático de múltiplos símbolos
- Geração de sinais Wave3 em tempo real
- Execução simulada de trades
- Coleta automática de features ML (103 features)
- Gerenciamento de posições (stop loss / take profit)
- Persistência PostgreSQL
- Snapshots diários de capital
- Logging estruturado

Autor: B3 Trading Platform
Data: 27 de Janeiro de 2026
Versão: 1.0 Production
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple
from loguru import logger
import sys
import os

# Adicionar path para importar estratégias
sys.path.append('/app/src')

from strategies.wave3_enhanced import Wave3Enhanced, EnhancedWave3Signal


class Wave3PaperTrader:
    """
    Gerenciador de Paper Trading com Wave3 v2.1
    
    Responsabilidades:
    - Scan periódico de símbolos
    - Geração de sinais Wave3
    - Execução simulada de trades
    - Gerenciamento de posições
    - Coleta de dados ML
    - Persistência em PostgreSQL
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        quality_score_threshold: int = 55,
        max_positions: int = 5,
        risk_per_trade: float = 0.02,  # 2% do capital por trade
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_user: str = 'b3trading_user',
        db_password: str = 'b3trading_pass',
        db_name: str = 'b3trading_db',
        timescale_host: str = 'localhost',
        timescale_port: int = 5433,
        timescale_user: str = 'b3trading_ts',
        timescale_password: str = 'b3trading_ts_pass',
        timescale_db: str = 'b3trading_market'
    ):
        """
        Inicializa o Wave3 Paper Trader
        
        Args:
            initial_capital: Capital inicial em R$
            quality_score_threshold: Score mínimo para aceitar sinal (55-100)
            max_positions: Máximo de posições simultâneas
            risk_per_trade: % do capital arriscado por trade
            db_*: Credenciais PostgreSQL (posições, trades, ML)
            timescale_*: Credenciais TimescaleDB (OHLCV data)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.quality_threshold = quality_score_threshold
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        
        # Credenciais bancos de dados
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'user': db_user,
            'password': db_password,
            'database': db_name
        }
        
        self.timescale_config = {
            'host': timescale_host,
            'port': timescale_port,
            'user': timescale_user,
            'password': timescale_password,
            'database': timescale_db
        }
        
        # Estratégia Wave3
        self.wave3 = Wave3Enhanced(
            min_quality_score=quality_score_threshold
        )
        
        # Estado
        self.positions: Dict[str, Dict] = {}
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.last_snapshot_time: Optional[datetime] = None
        
        # Pools de conexão
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.ts_pool: Optional[asyncpg.Pool] = None
        
        logger.info(f"🚀 Wave3 Paper Trader inicializado")
        logger.info(f"💰 Capital inicial: R$ {initial_capital:,.2f}")
        logger.info(f"⭐ Quality threshold: {quality_score_threshold}")
        logger.info(f"📊 Max posições: {max_positions}")
    
    async def connect_databases(self):
        """Conecta aos bancos de dados PostgreSQL e TimescaleDB"""
        
        try:
            # PostgreSQL (posições, trades, ML)
            self.pg_pool = await asyncpg.create_pool(
                **self.db_config,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("✅ Conectado ao PostgreSQL")
            
            # TimescaleDB (OHLCV data)
            self.ts_pool = await asyncpg.create_pool(
                **self.timescale_config,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("✅ Conectado ao TimescaleDB")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar bancos de dados: {e}")
            raise
    
    async def start(
        self,
        symbols: List[str],
        scan_interval: int = 300,  # 5 minutos
        trading_hours_only: bool = True
    ):
        """
        Inicia o paper trading
        
        Args:
            symbols: Lista de símbolos para monitorar (ex: ['PETR4', 'VALE3'])
            scan_interval: Intervalo entre scans em segundos (padrão: 5min)
            trading_hours_only: Operar apenas em horário de pregão (09:00-18:00 BRT)
        """
        
        if not self.pg_pool or not self.ts_pool:
            await self.connect_databases()
        
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info("=" * 60)
        logger.info("▶️  PAPER TRADING INICIADO - Wave3 v2.1")
        logger.info("=" * 60)
        logger.info(f"📊 Símbolos: {', '.join(symbols)}")
        logger.info(f"⏱️  Scan interval: {scan_interval}s ({scan_interval/60:.1f} min)")
        logger.info(f"🕐 Horário pregão: {'Sim' if trading_hours_only else 'Não'}")
        logger.info("=" * 60)
        
        scan_count = 0
        
        while self.is_running:
            try:
                scan_count += 1
                now = datetime.now()
                
                # Verificar se está em horário de pregão
                if trading_hours_only and not self._is_trading_hours(now):
                    logger.debug(f"⏸️  Fora do horário de pregão (scan #{scan_count})")
                    await asyncio.sleep(scan_interval)
                    continue
                
                logger.info(f"🔍 Scan #{scan_count} - {now.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 1. Escanear todos os símbolos
                for symbol in symbols:
                    try:
                        await self.scan_symbol(symbol)
                    except Exception as e:
                        logger.error(f"❌ Erro ao escanear {symbol}: {e}")
                
                # 2. Atualizar posições abertas
                await self.update_positions()
                
                # 3. Snapshot diário (às 18:00)
                if self._should_take_snapshot(now):
                    await self.take_capital_snapshot()
                
                # 4. Log de status a cada hora
                if now.minute == 0:
                    await self.log_status()
                
                # 5. Aguardar próximo scan
                await asyncio.sleep(scan_interval)
                
            except KeyboardInterrupt:
                logger.warning("⚠️  Interrupção detectada (Ctrl+C)")
                break
                
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                await asyncio.sleep(60)  # Retry após 1 minuto
        
        logger.info("⏹️  Paper Trading PARADO")
        await self.cleanup()
    
    async def scan_symbol(self, symbol: str):
        """
        Escaneia um símbolo e gera sinais Wave3
        
        Args:
            symbol: Código do ativo (ex: 'PETR4')
        """
        
        try:
            # 1. Buscar dados do TimescaleDB
            df_daily = await self.fetch_ohlcv(symbol, 'daily', days=365)
            df_60min = await self.fetch_ohlcv(symbol, '60min', days=180)
            
            if df_daily is None or len(df_daily) < 100:
                logger.warning(f"⚠️  {symbol}: dados daily insuficientes ({len(df_daily) if df_daily is not None else 0} candles)")
                return
            
            if df_60min is None or len(df_60min) < 100:
                logger.warning(f"⚠️  {symbol}: dados 60min insuficientes ({len(df_60min) if df_60min is not None else 0} candles)")
                return
            
            # 2. Gerar sinal Wave3
            signal = self.wave3.generate_signal(df_daily, df_60min)
            
            if signal is None:
                logger.debug(f"📉 {symbol}: nenhum sinal")
                return
            
            # 3. Verificar quality score
            if signal.quality_score < self.quality_threshold:
                logger.debug(
                    f"❌ {symbol}: score {signal.quality_score} < {self.quality_threshold}"
                )
                return
            
            # 4. Verificar se já existe posição
            if symbol in self.positions:
                logger.debug(f"⏭️  {symbol}: posição já aberta")
                return
            
            # 5. Verificar limite de posições
            if len(self.positions) >= self.max_positions:
                logger.warning(f"⏸️  Limite de {self.max_positions} posições atingido")
                return
            
            # 6. Executar sinal
            await self.execute_signal(symbol, signal, df_daily, df_60min)
            
        except Exception as e:
            logger.error(f"❌ Erro ao escanear {symbol}: {e}")
    
    async def execute_signal(
        self,
        symbol: str,
        signal: EnhancedWave3Signal,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame
    ):
        """
        Executa um sinal Wave3 (abre posição simulada)
        
        Args:
            symbol: Código do ativo
            signal: Sinal gerado pela estratégia Wave3
            df_daily: Dados diários (para features ML)
            df_60min: Dados 60min (para features ML)
        """
        
        # 1. Calcular tamanho da posição (Kelly Criterion simplificado)
        risk_amount = self.current_capital * self.risk_per_trade
        stop_distance = signal.entry_price - signal.stop_loss
        
        if stop_distance <= 0:
            logger.error(f"❌ {symbol}: stop_distance inválido ({stop_distance})")
            return
        
        position_size = int(risk_amount / stop_distance)
        
        if position_size <= 0:
            logger.warning(f"⚠️  {symbol}: position_size = 0 (capital insuficiente)")
            return
        
        # 2. Gerar features ML (para coleta futura)
        features = self._generate_ml_features(df_daily, df_60min, signal)
        
        # 3. Criar posição no PostgreSQL
        position_id = f"POS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{symbol}"
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO paper_positions (
                    position_id, symbol, side, quantity,
                    entry_price, entry_time, stop_loss, take_profit,
                    wave3_score, quality_score, signal_data
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ''',
                position_id,
                symbol,
                'BUY',
                position_size,
                signal.entry_price,
                datetime.now(),
                signal.stop_loss,
                signal.target_3,  # Alvo final
                int(signal.quality_score),
                int(signal.quality_score),
                {
                    'type': signal.signal_type,
                    'entry': float(signal.entry_price),
                    'stop': float(signal.stop_loss),
                    'targets': [
                        float(signal.target_1),
                        float(signal.target_2),
                        float(signal.target_3)
                    ],
                    'indicators': {k: float(v) if isinstance(v, (int, float)) else v 
                                   for k, v in signal.indicators.items()},
                    'context': {k: float(v) if isinstance(v, (int, float)) else v 
                                for k, v in signal.context_daily.items()}
                }
            )
        
        # 4. Adicionar ao tracking local
        self.positions[symbol] = {
            'position_id': position_id,
            'symbol': symbol,
            'side': 'BUY',
            'quantity': position_size,
            'entry_price': signal.entry_price,
            'entry_time': datetime.now(),
            'stop_loss': signal.stop_loss,
            'take_profit': signal.target_3,
            'wave3_score': int(signal.quality_score),
            'signal_data': signal,
            'features': features  # Guardar para ML futuro
        }
        
        # 5. Log detalhado
        reward_risk = (signal.target_3 - signal.entry_price) / (signal.entry_price - signal.stop_loss)
        
        logger.info("=" * 60)
        logger.info(f"🟢 NOVA POSIÇÃO ABERTA")
        logger.info("=" * 60)
        logger.info(f"📊 Símbolo: {symbol}")
        logger.info(f"💰 Entry: R$ {signal.entry_price:.2f}")
        logger.info(f"🛑 Stop: R$ {signal.stop_loss:.2f} (-{((signal.entry_price - signal.stop_loss)/signal.entry_price*100):.2f}%)")
        logger.info(f"🎯 Target: R$ {signal.target_3:.2f} (+{((signal.target_3 - signal.entry_price)/signal.entry_price*100):.2f}%)")
        logger.info(f"⭐ Score: {signal.quality_score:.0f}/100")
        logger.info(f"📈 R:R: 1:{reward_risk:.2f}")
        logger.info(f"🔢 Size: {position_size} ações (R$ {position_size * signal.entry_price:,.2f})")
        logger.info(f"⚠️  Risco: R$ {risk_amount:,.2f} ({self.risk_per_trade*100:.1f}% do capital)")
        logger.info("=" * 60)
    
    async def update_positions(self):
        """Atualiza preços das posições abertas e verifica stops/targets"""
        
        if not self.positions:
            return
        
        for symbol, position in list(self.positions.items()):
            try:
                # 1. Buscar preço atual
                current_price = await self.get_current_price(symbol)
                
                if current_price is None:
                    logger.warning(f"⚠️  {symbol}: preço atual não disponível")
                    continue
                
                # 2. Calcular P&L
                entry = position['entry_price']
                qty = position['quantity']
                pnl = (current_price - entry) * qty
                return_pct = (current_price - entry) / entry * 100
                
                # 3. Atualizar no PostgreSQL
                async with self.pg_pool.acquire() as conn:
                    await conn.execute('''
                        UPDATE paper_positions
                        SET current_price = $1,
                            unrealized_pnl = $2,
                            unrealized_pnl_pct = $3,
                            updated_at = NOW()
                        WHERE position_id = $4
                    ''', current_price, pnl, return_pct, position['position_id'])
                
                # 4. Verificar STOP LOSS
                if current_price <= position['stop_loss']:
                    logger.warning(f"🔴 {symbol}: STOP LOSS atingido!")
                    await self.close_position(
                        symbol,
                        position['stop_loss'],
                        'stop_loss'
                    )
                    continue
                
                # 5. Verificar TAKE PROFIT
                if current_price >= position['take_profit']:
                    logger.info(f"🟢 {symbol}: TAKE PROFIT atingido!")
                    await self.close_position(
                        symbol,
                        position['take_profit'],
                        'take_profit'
                    )
                    continue
                
                # 6. Log se P&L significativo
                if abs(return_pct) > 2:
                    emoji = "📈" if pnl > 0 else "📉"
                    logger.debug(
                        f"{emoji} {symbol}: R$ {current_price:.2f} | "
                        f"P&L: R$ {pnl:,.2f} ({return_pct:+.2f}%)"
                    )
                
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar {symbol}: {e}")
    
    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str
    ):
        """
        Fecha uma posição e salva no histórico
        
        Args:
            symbol: Código do ativo
            exit_price: Preço de saída
            exit_reason: Motivo (stop_loss, take_profit, manual, etc.)
        """
        
        if symbol not in self.positions:
            logger.warning(f"⚠️  {symbol}: posição não encontrada")
            return
        
        position = self.positions[symbol]
        
        # 1. Calcular P&L final
        entry = position['entry_price']
        qty = position['quantity']
        pnl = (exit_price - entry) * qty
        return_pct = (exit_price - entry) / entry * 100
        
        # 2. Atualizar capital
        self.current_capital += pnl
        
        # 3. Calcular holding period
        entry_time = position['entry_time']
        exit_time = datetime.now()
        holding_days = (exit_time - entry_time).days
        holding_hours = (exit_time - entry_time).total_seconds() / 3600
        
        # 4. Determinar resultado
        result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BE')
        
        # 5. Salvar trade no PostgreSQL
        trade_id = f"TRD-{exit_time.strftime('%Y%m%d-%H%M%S')}-{symbol}"
        
        async with self.pg_pool.acquire() as conn:
            # Salvar trade
            await conn.execute('''
                INSERT INTO paper_trades (
                    trade_id, symbol, side, quantity,
                    entry_price, entry_time, entry_signal,
                    exit_price, exit_time, exit_reason,
                    pnl, pnl_pct, return_pct,
                    holding_days, holding_hours,
                    wave3_score, quality_score, signal_type, result
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            ''',
                trade_id, symbol, 'BUY', qty,
                entry, entry_time, position['signal_data'].indicators,
                exit_price, exit_time, exit_reason,
                pnl, return_pct, return_pct,
                holding_days, int(holding_hours),
                position['wave3_score'], position['wave3_score'],
                position['signal_data'].signal_type, result
            )
            
            # Salvar features ML
            await conn.execute('''
                INSERT INTO ml_training_data (
                    trade_id, symbol, trade_date, result, return_pct,
                    wave3_score, quality_score, signal_type, features,
                    holding_days
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ''',
                trade_id, symbol, entry_time.date(), result, return_pct,
                position['wave3_score'], position['wave3_score'],
                position['signal_data'].signal_type,
                position['features'],
                holding_days
            )
            
            # Remover da tabela positions
            await conn.execute('''
                DELETE FROM paper_positions
                WHERE position_id = $1
            ''', position['position_id'])
        
        # 6. Remover do tracking local
        del self.positions[symbol]
        
        # 7. Log final
        emoji = '🟢' if pnl > 0 else '🔴'
        logger.info("=" * 60)
        logger.info(f"{emoji} TRADE FECHADO - {result}")
        logger.info("=" * 60)
        logger.info(f"📊 Símbolo: {symbol}")
        logger.info(f"🚪 Exit: R$ {exit_price:.2f}")
        logger.info(f"💵 P&L: R$ {pnl:,.2f} ({return_pct:+.2f}%)")
        logger.info(f"🕐 Holding: {holding_days} dias ({holding_hours:.1f}h)")
        logger.info(f"📝 Reason: {exit_reason.replace('_', ' ').title()}")
        logger.info(f"💰 Capital: R$ {self.current_capital:,.2f} (Return: {((self.current_capital - self.initial_capital)/self.initial_capital*100):+.2f}%)")
        logger.info("=" * 60)
        
        # 8. Verificar progresso ML
        await self.check_ml_progress()
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        days: int
    ) -> Optional[pd.DataFrame]:
        """
        Busca dados OHLCV do TimescaleDB
        
        Args:
            symbol: Código do ativo
            timeframe: 'daily' ou '60min'
            days: Quantidade de dias de histórico
            
        Returns:
            DataFrame com colunas: time, open, high, low, close, volume
        """
        
        table = 'ohlcv_daily' if timeframe == 'daily' else 'ohlcv_60min'
        
        try:
            async with self.ts_pool.acquire() as conn:
                rows = await conn.fetch(f'''
                    SELECT time, open, high, low, close, volume
                    FROM {table}
                    WHERE symbol = $1
                      AND time >= NOW() - INTERVAL '{days} days'
                    ORDER BY time ASC
                ''', symbol)
            
            if not rows:
                return None
            
            df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar OHLCV {symbol} ({timeframe}): {e}")
            return None
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Busca preço mais recente (close do último candle 60min)"""
        
        try:
            async with self.ts_pool.acquire() as conn:
                price = await conn.fetchval('''
                    SELECT close
                    FROM ohlcv_60min
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT 1
                ''', symbol)
            
            return float(price) if price else None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar preço {symbol}: {e}")
            return None
    
    def _generate_ml_features(
        self,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame,
        signal: EnhancedWave3Signal
    ) -> Dict:
        """
        Gera features ML para coleta futura
        
        Simplified: apenas features básicas por enquanto
        Futuramente: integrar com FeatureEngineerV2 (103 features)
        """
        
        # Features básicas do sinal
        features = {
            'entry_price': float(signal.entry_price),
            'stop_loss': float(signal.stop_loss),
            'target': float(signal.target_3),
            'quality_score': float(signal.quality_score),
            'reward_risk': float((signal.target_3 - signal.entry_price) / (signal.entry_price - signal.stop_loss)),
            
            # Indicadores técnicos
            **{k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else str(v)
               for k, v in signal.indicators.items()},
            
            # Contexto daily
            **{f"daily_{k}": float(v) if isinstance(v, (int, float, np.integer, np.floating)) else str(v)
               for k, v in signal.context_daily.items()},
            
            # Timestamp
            'timestamp': signal.timestamp.isoformat()
        }
        
        return features
    
    async def log_status(self):
        """Log de status a cada hora"""
        
        # Calcular métricas
        unrealized_pnl = 0
        for symbol, pos in self.positions.items():
            current_price = await self.get_current_price(symbol)
            if current_price:
                unrealized_pnl += (current_price - pos['entry_price']) * pos['quantity']
        
        total_pnl = self.current_capital - self.initial_capital
        return_pct = total_pnl / self.initial_capital * 100
        
        # Buscar estatísticas de trades
        async with self.pg_pool.acquire() as conn:
            stats = await conn.fetchrow('''
                SELECT * FROM paper_trading_summary
            ''')
        
        logger.info("┌" + "─" * 58 + "┐")
        logger.info("│" + " " * 18 + "📊 STATUS PAPER TRADING" + " " * 17 + "│")
        logger.info("├" + "─" * 58 + "┤")
        logger.info(f"│ Capital: R$ {self.current_capital:>12,.2f} ({return_pct:+6.2f}%) " + " " * 10 + "│")
        logger.info(f"│ P&L Total: R$ {total_pnl:>10,.2f} " + " " * 24 + "│")
        logger.info(f"│ Unrealized: R$ {unrealized_pnl:>9,.2f} " + " " * 24 + "│")
        logger.info(f"│ Posições Abertas: {len(self.positions):>2} / {self.max_positions} " + " " * 28 + "│")
        
        if stats and stats['total_trades']:
            logger.info("├" + "─" * 58 + "┤")
            logger.info(f"│ Trades: {stats['total_trades']:>3} | Wins: {stats['winning_trades']:>3} | Losses: {stats['losing_trades']:>3} " + " " * 13 + "│")
            logger.info(f"│ Win Rate: {stats['win_rate']:>5.1f}% " + " " * 37 + "│")
            logger.info(f"│ Avg Return: {stats['avg_return_pct']:>+6.2f}% " + " " * 32 + "│")
        
        logger.info("└" + "─" * 58 + "┘")
    
    async def take_capital_snapshot(self):
        """Tira snapshot diário de capital"""
        
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute('SELECT take_capital_snapshot()')
            
            self.last_snapshot_time = datetime.now()
            logger.info("📸 Snapshot de capital salvo")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar snapshot: {e}")
    
    async def check_ml_progress(self):
        """Verifica progresso da coleta ML e loga milestones"""
        
        try:
            async with self.pg_pool.acquire() as conn:
                progress = await conn.fetchrow('''
                    SELECT * FROM ml_collection_progress
                ''')
            
            if progress:
                samples = progress['samples_collected']
                readiness = progress['ml_readiness']
                to_next = progress['trades_to_next_milestone']
                
                # Log em milestones
                if samples in [25, 50, 75, 100]:
                    logger.info("🎉" + "=" * 58 + "🎉")
                    logger.info(f"🎯 MILESTONE: {samples} trades coletados!")
                    logger.info(f"📊 Status ML: {readiness.replace('_', ' ').title()}")
                    if to_next > 0:
                        logger.info(f"📈 Próxima meta: {to_next} trades restantes")
                    logger.info("🎉" + "=" * 58 + "🎉")
                
        except Exception as e:
            logger.error(f"❌ Erro ao verificar progresso ML: {e}")
    
    def _is_trading_hours(self, dt: datetime) -> bool:
        """Verifica se está em horário de pregão B3 (09:00-18:00 BRT)"""
        
        # Segunda a Sexta
        if dt.weekday() >= 5:  # Sábado=5, Domingo=6
            return False
        
        # 09:00 - 18:00
        market_open = dt_time(9, 0)
        market_close = dt_time(18, 0)
        
        return market_open <= dt.time() <= market_close
    
    def _should_take_snapshot(self, dt: datetime) -> bool:
        """Verifica se deve tirar snapshot (diário às 18:00)"""
        
        if self.last_snapshot_time is None:
            return True
        
        # Snapshot diário às 18:00
        if dt.hour == 18 and dt.minute == 0:
            last_snapshot_date = self.last_snapshot_time.date()
            current_date = dt.date()
            
            return current_date > last_snapshot_date
        
        return False
    
    async def cleanup(self):
        """Cleanup de recursos ao parar"""
        
        logger.info("🧹 Limpando recursos...")
        
        # Fechar pools de conexão
        if self.pg_pool:
            await self.pg_pool.close()
            logger.info("✅ PostgreSQL pool fechado")
        
        if self.ts_pool:
            await self.ts_pool.close()
            logger.info("✅ TimescaleDB pool fechado")
    
    async def stop(self):
        """Para o paper trading"""
        
        self.is_running = False
        logger.info("⏹️  Parando paper trading...")


# ========================================
# MAIN - Execução
# ========================================

async def main():
    """
    Ponto de entrada principal
    
    Usage:
        python paper_trading_wave3.py
    """
    
    # Configurar logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "/app/logs/paper_trading_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )
    
    # Criar trader
    trader = Wave3PaperTrader(
        initial_capital=100000.0,
        quality_score_threshold=55,
        max_positions=5,
        risk_per_trade=0.02
    )
    
    # Símbolos validados (PAPER_TRADING_SETUP.md)
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    try:
        # Iniciar (scans a cada 5 minutos)
        await trader.start(
            symbols=symbols,
            scan_interval=300,  # 5 min
            trading_hours_only=True
        )
    except KeyboardInterrupt:
        logger.info("⚠️  Interrompido pelo usuário")
    finally:
        await trader.stop()


if __name__ == '__main__':
    asyncio.run(main())
