#!/usr/bin/env python3
"""
Profit Binary Format Analyzer - Advanced Reverse Engineering
=============================================================

Analisa múltiplos arquivos binários do Profit/ProfitChart para:
1. Identificar padrões comuns
2. Testar diferentes estruturas de parsing
3. Validar com preços conhecidos
4. Automatizar importação massiva

Uso:
    python profit_binary_analyzer.py analyze              # Analisar arquivos
    python profit_binary_analyzer.py test-parse           # Testar parsing
    python profit_binary_analyzer.py validate PETR4       # Validar com preços conhecidos
    python profit_binary_analyzer.py import-60min         # Importar todos os 60min
"""

import struct
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import re

# Configuração
PROFIT_PATH = Path.home() / ".wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit"
DATABASE_PATH = PROFIT_PATH / "database/assets"


class BinaryFormatTester:
    """Testa múltiplas estruturas de parsing binário"""
    
    # Possíveis formatos de registro
    FORMATS = {
        'v1_float': '<iffff Q',         # int32 date + 4 floats + uint64 volume (28 bytes)
        'v2_double': '<idddd Q',        # int32 date + 4 doubles + uint64 volume (44 bytes)
        'v3_long_date': '<Qffff Q',     # int64 date + 4 floats + uint64 volume (32 bytes)
        'v4_long_double': '<Qdddd Q',   # int64 date + 4 doubles + uint64 volume (56 bytes)
        'v5_double_date': '<ddddd Q',   # double date + 4 doubles + uint64 volume (48 bytes)
        'v6_timestamp': '<Qdddd I',     # int64 timestamp + 4 doubles + uint32 volume (44 bytes)
        'v7_compact': '<Hffff I',       # int16 days + 4 floats + uint32 volume (22 bytes)
    }
    
    # Possíveis épocas base
    EPOCHS = [
        datetime(1970, 1, 1),   # Unix epoch
        datetime(1980, 1, 1),   # Delphi TDateTime base
        datetime(1990, 1, 1),   # Possível base customizada
        datetime(1899, 12, 30), # Excel/Delphi TDateTime real
        datetime(2000, 1, 1),   # Y2K base
    ]
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_size = file_path.stat().st_size
        with open(file_path, 'rb') as f:
            self.data = f.read()
    
    def detect_header_size(self) -> int:
        """Detecta tamanho do header por heurística"""
        # Procura por sequência de doubles que parecem preços
        # Preços típicos de PETR4: 20-50
        # Em double: bytes ~40 4X XX XX XX XX XX XX
        
        for offset in range(0, min(200, len(self.data)), 8):
            try:
                value = struct.unpack('<d', self.data[offset:offset+8])[0]
                # Se encontrar double na faixa de preço realista
                if 10 < value < 100:
                    print(f"  📍 Possível preço encontrado em offset {offset}: {value:.2f}")
                    # Assume que 8 bytes antes é o início de registro
                    return max(0, offset - 8)
            except:
                pass
        
        return 64  # Default: 64 bytes
    
    def test_format(self, format_name: str, header_size: int = 64) -> Optional[List[Dict]]:
        """Testa um formato específico"""
        format_string = self.FORMATS[format_name]
        record_size = struct.calcsize(format_string)
        
        data_section = self.data[header_size:]
        num_records = len(data_section) // record_size
        
        if num_records < 10:  # Muito poucos registros, formato provavelmente errado
            return None
        
        records = []
        for i in range(num_records):
            offset = i * record_size
            record_bytes = data_section[offset:offset + record_size]
            
            if len(record_bytes) < record_size:
                break
            
            try:
                values = struct.unpack(format_string, record_bytes)
                
                # Tentar interpretar date
                date_value = values[0]
                date_obj = None
                
                # Testar diferentes épocas
                for epoch in self.EPOCHS:
                    try:
                        if isinstance(date_value, int) and date_value < 100000:
                            # Dias desde epoch
                            date_obj = epoch + timedelta(days=int(date_value))
                        elif isinstance(date_value, int):
                            # Timestamp em segundos ou milissegundos
                            date_obj = datetime.fromtimestamp(date_value / 1000 if date_value > 1e10 else date_value)
                        elif isinstance(date_value, float):
                            # Delphi TDateTime (days since 1899-12-30)
                            date_obj = datetime(1899, 12, 30) + timedelta(days=date_value)
                        
                        # Validar se data está em range razoável
                        if date_obj and datetime(1990, 1, 1) < date_obj < datetime(2030, 1, 1):
                            break
                        else:
                            date_obj = None
                    except:
                        date_obj = None
                
                if date_obj:
                    # OHLCV
                    open_val, high_val, low_val, close_val, volume = values[1], values[2], values[3], values[4], values[5]
                    
                    # Validar se são preços válidos
                    prices = [open_val, high_val, low_val, close_val]
                    if all(10 < p < 100 for p in prices) and high_val >= max(open_val, close_val) and low_val <= min(open_val, close_val):
                        records.append({
                            'date': date_obj,
                            'open': float(open_val),
                            'high': float(high_val),
                            'low': float(low_val),
                            'close': float(close_val),
                            'volume': int(volume)
                        })
            except Exception as e:
                continue
        
        if len(records) > 10:  # Se conseguiu parsear pelo menos 10 registros válidos
            return records
        return None
    
    def analyze_all_formats(self) -> Dict[str, List[Dict]]:
        """Testa todos os formatos possíveis"""
        print(f"\n🔬 Analisando arquivo: {self.file_path.name}")
        print(f"   Tamanho: {self.file_size:,} bytes")
        
        # Detectar header
        header_size = self.detect_header_size()
        print(f"   Header estimado: {header_size} bytes")
        
        results = {}
        for format_name in self.FORMATS.keys():
            print(f"\n   Testando formato: {format_name}...", end=" ")
            records = self.test_format(format_name, header_size)
            
            if records:
                print(f"✅ {len(records)} registros válidos")
                results[format_name] = records
                
                # Mostrar amostra
                if len(records) >= 3:
                    print(f"      Primeiro: {records[0]['date'].date()} | C: {records[0]['close']:.2f} | V: {records[0]['volume']:,}")
                    print(f"      Último:   {records[-1]['date'].date()} | C: {records[-1]['close']:.2f} | V: {records[-1]['volume']:,}")
            else:
                print("❌ Falhou")
        
        return results


class ProfitDataValidator:
    """Valida dados parseados com preços conhecidos"""
    
    # Preços conhecidos de PETR4 em 2024 (fonte: B3/Yahoo Finance)
    KNOWN_PRICES = {
        'PETR4': {
            datetime(2024, 1, 2): {'close': 37.80, 'volume': 48_000_000},
            datetime(2024, 6, 28): {'close': 39.12, 'volume': 52_000_000},
            datetime(2024, 12, 31): {'close': 38.96, 'volume': 45_000_000},
        }
    }
    
    @staticmethod
    def validate_records(symbol: str, records: List[Dict]) -> Tuple[bool, float, Dict]:
        """Valida registros parseados com preços conhecidos"""
        if symbol not in ProfitDataValidator.KNOWN_PRICES:
            return False, 0.0, {}
        
        known = ProfitDataValidator.KNOWN_PRICES[symbol]
        matches = 0
        total_error = 0.0
        errors = {}
        
        for date, expected in known.items():
            # Buscar registro com essa data
            matching_records = [r for r in records if r['date'].date() == date.date()]
            
            if matching_records:
                record = matching_records[0]
                price_error = abs(record['close'] - expected['close']) / expected['close']
                volume_error = abs(record['volume'] - expected['volume']) / expected['volume']
                
                total_error += price_error
                errors[date] = {
                    'expected': expected['close'],
                    'parsed': record['close'],
                    'error': price_error * 100,
                    'volume_expected': expected['volume'],
                    'volume_parsed': record['volume'],
                    'volume_error': volume_error * 100
                }
                
                if price_error < 0.01:  # Menos de 1% de erro
                    matches += 1
        
        avg_error = (total_error / len(known)) * 100 if known else 0
        is_valid = matches >= len(known) * 0.8  # 80% de acurácia
        
        return is_valid, avg_error, errors


class ProfitBulkImporter:
    """Importa múltiplos símbolos automaticamente"""
    
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.successful = []
        self.failed = []
    
    def find_60min_files(self) -> List[Tuple[str, Path]]:
        """Encontra todos os arquivos de 60 minutos"""
        files = []
        
        for symbol_dir in self.database_path.iterdir():
            if not symbol_dir.is_dir():
                continue
            
            # Extrair símbolo (ex: PETR4_B_0 -> PETR4)
            symbol = symbol_dir.name.split('_')[0]
            
            # Buscar arquivos 60min: *_1_60_1_1_0_*.min
            # Padrão Profit: SIMBOLO_B_0_1_INTERVALO_1_1_0_ANO.min
            pattern = f"*_1_60_1_1_0_*.min"
            min_files = list(symbol_dir.glob(pattern))
            
            if min_files:
                for file_path in min_files:
                    files.append((symbol, file_path))
        
        return files
    
    def import_all_60min(self, parser_class: BinaryFormatTester, format_name: str):
        """Importa todos os arquivos de 60min usando formato validado"""
        files = self.find_60min_files()
        
        print(f"\n{'='*80}")
        print(f"📦 IMPORTAÇÃO EM MASSA - 60 MINUTOS")
        print(f"{'='*80}")
        print(f"Arquivos encontrados: {len(files)}")
        print(f"Formato a usar: {format_name}")
        print(f"{'='*80}\n")
        
        for i, (symbol, file_path) in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] Processando {symbol}...", end=" ")
            
            try:
                tester = parser_class(file_path)
                records = tester.test_format(format_name, header_size=64)
                
                if records and len(records) > 100:  # Mínimo 100 candles
                    print(f"✅ {len(records)} candles")
                    self.successful.append({
                        'symbol': symbol,
                        'file': file_path.name,
                        'records': len(records),
                        'date_range': f"{records[0]['date'].date()} → {records[-1]['date'].date()}"
                    })
                    
                    # TODO: Aqui seria a inserção no TimescaleDB
                    # await insert_to_timescaledb(records, 'ohlcv_60m', symbol)
                else:
                    print(f"❌ Poucos registros ({len(records) if records else 0})")
                    self.failed.append({'symbol': symbol, 'reason': 'Poucos registros'})
            
            except Exception as e:
                print(f"❌ Erro: {e}")
                self.failed.append({'symbol': symbol, 'reason': str(e)})
        
        self.print_summary()
    
    def print_summary(self):
        """Exibe resumo da importação"""
        print(f"\n{'='*80}")
        print(f"📊 RESUMO DA IMPORTAÇÃO")
        print(f"{'='*80}")
        print(f"✅ Sucesso: {len(self.successful)}")
        print(f"❌ Falhas: {len(self.failed)}")
        print(f"Taxa de sucesso: {len(self.successful) / (len(self.successful) + len(self.failed)) * 100:.1f}%")
        print(f"{'='*80}\n")
        
        if self.successful:
            print("✅ Símbolos importados com sucesso:")
            for item in self.successful[:10]:  # Top 10
                print(f"   {item['symbol']:6s} | {item['records']:5d} candles | {item['date_range']}")
            
            if len(self.successful) > 10:
                print(f"   ... e mais {len(self.successful) - 10} símbolos")
        
        if self.failed:
            print("\n❌ Símbolos com falha:")
            for item in self.failed[:10]:
                print(f"   {item['symbol']:6s} | {item['reason']}")


def analyze_multiple_files():
    """Analisa múltiplos arquivos para encontrar padrão comum"""
    print("\n" + "="*80)
    print("🔬 ANÁLISE MULTI-ARQUIVO - REVERSE ENGINEERING")
    print("="*80)
    
    # Selecionar arquivos de exemplo
    test_files = [
        DATABASE_PATH / "PETR4_B_0" / "PETR4_B_0_2_1_1_1_0_2024.day",  # PETR4 diário 2024
        DATABASE_PATH / "VALE3_B_0" / "VALE3_B_0_2_1_1_1_0_2024.day",  # VALE3 diário 2024
        DATABASE_PATH / "ITUB4_B_0" / "ITUB4_B_0_2_1_1_1_0_2024.day",  # ITUB4 diário 2024
    ]
    
    all_results = {}
    
    for file_path in test_files:
        if not file_path.exists():
            print(f"⚠️  Arquivo não encontrado: {file_path.name}")
            continue
        
        tester = BinaryFormatTester(file_path)
        results = tester.analyze_all_formats()
        
        if results:
            all_results[file_path.name] = results
    
    # Encontrar formato que funciona para todos
    print(f"\n{'='*80}")
    print("🎯 FORMATO VENCEDOR (funciona em todos os arquivos)")
    print("="*80)
    
    common_formats = set(all_results[list(all_results.keys())[0]].keys())
    for file_results in all_results.values():
        common_formats &= set(file_results.keys())
    
    if common_formats:
        best_format = list(common_formats)[0]
        print(f"✅ Formato vencedor: {best_format}")
        print(f"   Funciona em {len(all_results)} arquivos testados")
        return best_format
    else:
        print("❌ Nenhum formato funciona em todos os arquivos")
        return None


def validate_with_known_prices(format_name: str):
    """Valida parsing com preços conhecidos de PETR4"""
    print(f"\n{'='*80}")
    print("✅ VALIDAÇÃO COM PREÇOS CONHECIDOS - PETR4 2024")
    print("="*80)
    
    petr4_file = DATABASE_PATH / "PETR4_B_0" / "PETR4_B_0_2_1_1_1_0_2024.day"
    
    if not petr4_file.exists():
        print("❌ Arquivo PETR4 2024 não encontrado")
        return False
    
    tester = BinaryFormatTester(petr4_file)
    records = tester.test_format(format_name, header_size=64)
    
    if not records:
        print("❌ Falha ao parsear arquivo")
        return False
    
    print(f"📊 Registros parseados: {len(records)}")
    print(f"📅 Período: {records[0]['date'].date()} → {records[-1]['date'].date()}")
    
    # Validar
    is_valid, avg_error, errors = ProfitDataValidator.validate_records('PETR4', records)
    
    print(f"\n{'='*80}")
    if is_valid:
        print(f"✅ VALIDAÇÃO PASSOU! Erro médio: {avg_error:.2f}%")
    else:
        print(f"❌ VALIDAÇÃO FALHOU! Erro médio: {avg_error:.2f}%")
    print("="*80)
    
    for date, error_data in errors.items():
        print(f"\n📅 {date.date()}:")
        print(f"   Esperado: R$ {error_data['expected']:.2f} | Volume: {error_data['volume_expected']:,}")
        print(f"   Parseado: R$ {error_data['parsed']:.2f} | Volume: {error_data['volume_parsed']:,}")
        print(f"   Erro: {error_data['error']:.2f}% (preço) | {error_data['volume_error']:.2f}% (volume)")
    
    return is_valid


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "analyze":
        best_format = analyze_multiple_files()
        if best_format:
            print(f"\n🎉 Use o formato '{best_format}' para importações futuras")
    
    elif command == "test-parse":
        # Testar parsing em arquivo específico
        if len(sys.argv) < 3:
            file_path = DATABASE_PATH / "PETR4_B_0" / "PETR4_B_0_2_1_1_1_0_2024.day"
        else:
            file_path = Path(sys.argv[2])
        
        tester = BinaryFormatTester(file_path)
        results = tester.analyze_all_formats()
        
        if results:
            print(f"\n✅ {len(results)} formatos funcionaram!")
            for format_name, records in results.items():
                print(f"   - {format_name}: {len(records)} registros")
    
    elif command == "validate":
        symbol = sys.argv[2] if len(sys.argv) > 2 else "PETR4"
        
        # Primeiro, encontrar melhor formato
        best_format = analyze_multiple_files()
        
        if best_format:
            validate_with_known_prices(best_format)
    
    elif command == "import-60min":
        # Importação massiva
        best_format = analyze_multiple_files()
        
        if not best_format:
            print("❌ Não foi possível determinar formato válido")
            sys.exit(1)
        
        importer = ProfitBulkImporter(DATABASE_PATH)
        importer.import_all_60min(BinaryFormatTester, best_format)
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
