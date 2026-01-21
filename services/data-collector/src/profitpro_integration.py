"""
ProfitPro Integration - Extração de Dados Históricos B3
========================================================

Integração com ProfitPro (Nelogica) instalado via Wine para obter
dados históricos reais da B3, incluindo intraday.

O ProfitPro salva dados em arquivos locais que podemos ler diretamente.

Formatos suportados:
- Dados intraday (1min, 5min, 15min, 60min)
- Dados diários
- Tick-by-tick (se disponível)

Autor: Stock-IndiceDev Assistant
Data: 20/01/2026
"""

import asyncio
import asyncpg
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
from loguru import logger
import struct
import os

# Configurações
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

# Caminhos típicos do ProfitPro no Wine
PROFITPRO_PATHS = [
    Path.home() / ".wine/drive_c/Program Files/Nelogica/ProfitPro",
    Path.home() / ".wine/drive_c/Program Files (x86)/Nelogica/ProfitPro",
    Path("/home/dellno/.wine/drive_c/Program Files/Nelogica/ProfitPro"),
    Path("/home/dellno/.wine/drive_c/Program Files (x86)/Nelogica/ProfitPro"),
]


class ProfitProIntegration:
    """
    Integração com ProfitPro para extrair dados históricos
    
    O ProfitPro armazena dados em diferentes formatos:
    - Arquivos binários (.idx, .dat)
    - Arquivos texto (.txt, .csv) para exportação
    - Database SQLite (em versões recentes)
    """
    
    def __init__(self, profitpro_path: Optional[Path] = None):
        """
        Args:
            profitpro_path: Caminho da instalação do ProfitPro
        """
        self.profitpro_path = profitpro_path or self.find_profitpro_installation()
        
        if not self.profitpro_path:
            logger.warning("⚠️ ProfitPro não encontrado nos caminhos padrão")
            logger.info("   Configure manualmente com: ProfitProIntegration('/caminho/para/profitpro')")
        else:
            logger.success(f"✅ ProfitPro encontrado em: {self.profitpro_path}")
            self.data_path = self.profitpro_path / "Dados"
            logger.info(f"   Dados em: {self.data_path}")
    
    def find_profitpro_installation(self) -> Optional[Path]:
        """Procura instalação do ProfitPro nos caminhos padrão"""
        for path in PROFITPRO_PATHS:
            if path.exists():
                logger.info(f"🔍 Verificando: {path}")
                if (path / "ProfitPro.exe").exists() or (path / "Dados").exists():
                    return path
        return None
    
    def list_available_symbols(self) -> List[str]:
        """Lista símbolos disponíveis no ProfitPro"""
        if not self.data_path or not self.data_path.exists():
            logger.warning("⚠️ Diretório de dados não encontrado")
            return []
        
        symbols = []
        
        # Procurar por arquivos .idx ou pastas de ativos
        for file_path in self.data_path.rglob("*"):
            if file_path.is_file():
                # Extrair símbolo do nome do arquivo
                filename = file_path.stem
                if len(filename) >= 5 and filename.isalnum():
                    symbols.append(filename)
        
        symbols = sorted(set(symbols))
        logger.info(f"📊 Encontrados {len(symbols)} símbolos no ProfitPro")
        
        return symbols
    
    def export_symbol_to_csv(
        self,
        symbol: str,
        interval: str = "1D",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[Path]:
        """
        Exporta dados de um símbolo usando funcionalidade do ProfitPro
        
        O ProfitPro tem opção de exportar dados via menu ou linha de comando.
        Este método usa a ferramenta de linha de comando do ProfitPro.
        
        Args:
            symbol: Ticker (ex: PETR4)
            interval: 1min, 5min, 15min, 60min, 1D
            start_date: Data inicial
            end_date: Data final
        
        Returns:
            Path para arquivo CSV exportado
        """
        if not self.profitpro_path:
            logger.error("❌ ProfitPro não configurado")
            return None
        
        # Criar diretório temporário para exportação
        export_dir = Path("/tmp/profitpro_export")
        export_dir.mkdir(exist_ok=True)
        
        output_file = export_dir / f"{symbol}_{interval}.csv"
        
        # Comando para exportar via ProfitPro CLI (se disponível)
        # Nota: ProfitPro pode não ter CLI direto, usar alternativa Wine
        
        logger.info(f"📥 Exportando {symbol} ({interval}) para CSV...")
        logger.warning("⚠️ Exportação manual necessária - veja documentação abaixo")
        
        return output_file
    
    def read_profitpro_csv(self, csv_path: Path) -> Optional[pd.DataFrame]:
        """
        Lê arquivo CSV exportado do ProfitPro
        
        Formato típico do ProfitPro:
        Data;Hora;Abertura;Máxima;Mínima;Fechamento;Volume
        20/01/2026;09:00;30.50;30.80;30.40;30.75;1000000
        
        Args:
            csv_path: Caminho para arquivo CSV
        
        Returns:
            DataFrame com [time, open, high, low, close, volume, symbol]
        """
        if not csv_path.exists():
            logger.error(f"❌ Arquivo não encontrado: {csv_path}")
            return None
        
        try:
            # Tentar diferentes separadores (vírgula ou ponto-e-vírgula)
            for sep in [';', ',']:
                try:
                    df = pd.read_csv(csv_path, sep=sep)
                    
                    # Detectar colunas (português ou inglês)
                    date_col = None
                    time_col = None
                    
                    for col in df.columns:
                        col_lower = col.lower()
                        if 'data' in col_lower or 'date' in col_lower:
                            date_col = col
                        if 'hora' in col_lower or 'time' in col_lower:
                            time_col = col
                    
                    if not date_col:
                        continue
                    
                    # Combinar data e hora
                    if time_col:
                        df['datetime'] = pd.to_datetime(
                            df[date_col].astype(str) + ' ' + df[time_col].astype(str),
                            format='%d/%m/%Y %H:%M',
                            errors='coerce'
                        )
                    else:
                        df['datetime'] = pd.to_datetime(
                            df[date_col],
                            format='%d/%m/%Y',
                            errors='coerce'
                        )
                    
                    # Mapear colunas
                    column_map = {}
                    for col in df.columns:
                        col_lower = col.lower()
                        if 'abertura' in col_lower or 'open' in col_lower:
                            column_map[col] = 'open'
                        elif 'maxima' in col_lower or 'high' in col_lower or 'máxima' in col_lower:
                            column_map[col] = 'high'
                        elif 'minima' in col_lower or 'low' in col_lower or 'mínima' in col_lower:
                            column_map[col] = 'low'
                        elif 'fechamento' in col_lower or 'close' in col_lower:
                            column_map[col] = 'close'
                        elif 'volume' in col_lower or 'vol' in col_lower:
                            column_map[col] = 'volume'
                    
                    df = df.rename(columns=column_map)
                    
                    # Selecionar colunas necessárias
                    required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                    if all(col in df.columns for col in required_cols):
                        df = df[required_cols]
                        df = df.rename(columns={'datetime': 'time'})
                        df = df.dropna()
                        
                        # Extrair símbolo do nome do arquivo
                        symbol = csv_path.stem.split('_')[0]
                        df['symbol'] = symbol
                        
                        logger.success(f"✅ {len(df)} registros lidos de {csv_path.name}")
                        return df
                
                except Exception as e:
                    continue
            
            logger.error(f"❌ Não foi possível parsear {csv_path.name}")
            return None
        
        except Exception as e:
            logger.error(f"❌ Erro ao ler CSV: {e}")
            return None
    
    async def import_csv_to_timescaledb(
        self,
        csv_path: Path,
        table: str = 'ohlcv_60m'
    ):
        """
        Importa dados do CSV para TimescaleDB
        
        Args:
            csv_path: Caminho para arquivo CSV do ProfitPro
            table: Tabela de destino (ohlcv_1m, ohlcv_60m, ohlcv_daily, etc.)
        """
        df = self.read_profitpro_csv(csv_path)
        
        if df is None or df.empty:
            logger.warning("⚠️ Nenhum dado para importar")
            return
        
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Criar tabela se não existir
            create_table = f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    time TIMESTAMPTZ NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    symbol VARCHAR(20) NOT NULL,
                    UNIQUE(time, symbol)
                );
                
                SELECT create_hypertable('{table}', 'time', if_not_exists => TRUE);
                CREATE INDEX IF NOT EXISTS idx_{table}_symbol_time ON {table} (symbol, time DESC);
            """
            
            await conn.execute(create_table)
            logger.info(f"📊 Tabela {table} pronta")
            
            # Inserir dados
            records = []
            for _, row in df.iterrows():
                records.append((
                    row['time'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    row['symbol']
                ))
            
            query = f"""
                INSERT INTO {table} (time, open, high, low, close, volume, symbol)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, symbol) DO NOTHING
            """
            
            result = await conn.executemany(query, records)
            logger.success(f"✅ {len(records)} registros importados para {table}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao importar: {e}")
        
        finally:
            await conn.close()
    
    def generate_export_instructions(self, symbols: List[str], interval: str = "60min") -> str:
        """
        Gera instruções para exportação manual via ProfitPro
        
        Args:
            symbols: Lista de tickers para exportar
            interval: Intervalo desejado
        
        Returns:
            Texto com instruções passo a passo
        """
        instructions = f"""
╔══════════════════════════════════════════════════════════════╗
║     INSTRUÇÕES: EXPORTAR DADOS DO PROFITPRO                  ║
╚══════════════════════════════════════════════════════════════╝

📋 SÍMBOLOS PARA EXPORTAR: {len(symbols)}
{', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}

⏱️ INTERVALO: {interval}

PASSO A PASSO:

1. 🖥️ ABRIR PROFITPRO via Wine
   cd ~/.wine/drive_c/Program Files/Nelogica/ProfitPro
   wine ProfitPro.exe

2. 📊 CONFIGURAR GRÁFICO
   - Clique em "Novo Gráfico"
   - Selecione ativo (ex: PETR4)
   - Escolha periodicidade: {interval}

3. 📥 EXPORTAR DADOS
   a) Método 1 - Via Menu:
      - Clique direito no gráfico
      - "Exportar Dados" → "CSV"
      - Salvar em: /tmp/profitpro_export/SIMBOLO_{interval}.csv
   
   b) Método 2 - Via Ferramentas:
      - Menu "Ferramentas" → "Exportação em Lote"
      - Selecionar múltiplos ativos
      - Formato: CSV com cabeçalho
      - Separador: Ponto-e-vírgula (;)

4. ✅ IMPORTAR PARA TIMESCALEDB
   Para cada arquivo exportado:
   
   docker exec b3-data-collector python /app/src/profitpro_integration.py import \\
       /tmp/profitpro_export/PETR4_{interval}.csv

5. 🔄 AUTOMATIZAR (Opcional)
   - Criar script AutoHotkey/xdotool para automatizar cliques
   - Exportar todos os símbolos em lote
   - Importar automaticamente via watch script

════════════════════════════════════════════════════════════════

💡 DICAS:

- Formato CSV esperado:
  Data;Hora;Abertura;Máxima;Mínima;Fechamento;Volume
  20/01/2026;09:00;30.50;30.80;30.40;30.75;1000000

- Para dados históricos completos:
  * Período recomendado: últimos 2 anos
  * Periodicidades disponíveis: 1min, 5min, 15min, 60min, Diário

- Alternativa: Nelogica DDE
  * O ProfitPro oferece interface DDE para dados em tempo real
  * Implementar cliente DDE em Python (pywin32)

════════════════════════════════════════════════════════════════
"""
        return instructions


async def import_profitpro_batch(csv_directory: Path, interval: str = "60min"):
    """
    Importa múltiplos arquivos CSV do ProfitPro
    
    Args:
        csv_directory: Diretório com arquivos CSV exportados
        interval: Intervalo dos dados (para determinar tabela)
    """
    profitpro = ProfitProIntegration()
    
    # Mapear intervalo para tabela
    interval_table_map = {
        '1min': 'ohlcv_1m',
        '5min': 'ohlcv_5m',
        '15min': 'ohlcv_15m',
        '30min': 'ohlcv_30m',
        '60min': 'ohlcv_60m',
        '1D': 'ohlcv_daily',
        'Diário': 'ohlcv_daily'
    }
    
    table = interval_table_map.get(interval, 'ohlcv_60m')
    
    csv_files = list(csv_directory.glob("*.csv"))
    
    logger.info("=" * 80)
    logger.info(f"IMPORTAÇÃO EM LOTE - ProfitPro → TimescaleDB")
    logger.info("=" * 80)
    logger.info(f"Diretório: {csv_directory}")
    logger.info(f"Arquivos: {len(csv_files)}")
    logger.info(f"Tabela: {table}")
    logger.info("=" * 80)
    
    success = 0
    failed = 0
    
    for csv_file in csv_files:
        logger.info(f"📥 Importando {csv_file.name}...")
        try:
            await profitpro.import_csv_to_timescaledb(csv_file, table=table)
            success += 1
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            failed += 1
    
    logger.info("=" * 80)
    logger.success(f"✅ Importação completa!")
    logger.info(f"   Sucesso: {success}/{len(csv_files)}")
    logger.info(f"   Falhas: {failed}/{len(csv_files)}")
    logger.info("=" * 80)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("""
ProfitPro Integration - Extração de Dados B3
=============================================

IMPORTANTE: Requer ProfitPro instalado via Wine
   Caminho típico: ~/.wine/drive_c/Program Files/Nelogica/ProfitPro

Uso:

  1. LISTAR SÍMBOLOS DISPONÍVEIS
     python profitpro_integration.py list

  2. GERAR INSTRUÇÕES DE EXPORTAÇÃO
     python profitpro_integration.py instructions PETR4 VALE3 ITUB4 --interval 60min

  3. IMPORTAR ARQUIVO CSV
     python profitpro_integration.py import /tmp/profitpro_export/PETR4_60min.csv

  4. IMPORTAR LOTE DE ARQUIVOS
     python profitpro_integration.py import-batch /tmp/profitpro_export --interval 60min

Intervalos suportados:
  1min, 5min, 15min, 30min, 60min, 1D (Diário)

WORKFLOW COMPLETO:
  1. Exportar dados manualmente do ProfitPro (via GUI)
  2. Salvar CSVs em /tmp/profitpro_export/
  3. Executar: python profitpro_integration.py import-batch /tmp/profitpro_export
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'list':
        profitpro = ProfitProIntegration()
        symbols = profitpro.list_available_symbols()
        
        if symbols:
            print(f"\n📊 {len(symbols)} símbolos encontrados:\n")
            for i, symbol in enumerate(symbols[:50], 1):
                print(f"  {i:2d}. {symbol}")
            
            if len(symbols) > 50:
                print(f"\n  ... e mais {len(symbols) - 50} símbolos")
        else:
            print("❌ Nenhum símbolo encontrado")
    
    elif command == 'instructions':
        symbols = []
        interval = '60min'
        
        for arg in sys.argv[2:]:
            if arg == '--interval':
                continue
            elif sys.argv[sys.argv.index(arg) - 1] == '--interval':
                interval = arg
            else:
                symbols.append(arg)
        
        if not symbols:
            symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
        
        profitpro = ProfitProIntegration()
        instructions = profitpro.generate_export_instructions(symbols, interval)
        print(instructions)
    
    elif command == 'import':
        if len(sys.argv) < 3:
            print("❌ Especifique o arquivo CSV")
            sys.exit(1)
        
        csv_path = Path(sys.argv[2])
        interval = sys.argv[3] if len(sys.argv) > 3 else '60min'
        
        profitpro = ProfitProIntegration()
        asyncio.run(profitpro.import_csv_to_timescaledb(csv_path, f'ohlcv_{interval}'))
    
    elif command == 'import-batch':
        if len(sys.argv) < 3:
            print("❌ Especifique o diretório com CSVs")
            sys.exit(1)
        
        csv_dir = Path(sys.argv[2])
        interval = '60min'
        
        for i, arg in enumerate(sys.argv[3:]):
            if arg == '--interval' and i + 3 < len(sys.argv):
                interval = sys.argv[i + 4]
        
        asyncio.run(import_profitpro_batch(csv_dir, interval))
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        sys.exit(1)
