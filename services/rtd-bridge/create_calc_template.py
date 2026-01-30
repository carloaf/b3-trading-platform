#!/usr/bin/env python3
"""
LibreOffice Calc Template Generator
====================================

Gera planilha .ods com fórmulas e formatação para dados em tempo real
do ProfitChart via RTD Bridge.

Autor: B3 Trading Platform
Data: 30 Janeiro 2026
"""

import subprocess
import sys
from pathlib import Path


def create_calc_template():
    """
    Cria template ODS com estrutura para RTD
    
    Nota: Requer libreoffice instalado para conversão
    """
    
    template_csv = """Símbolo,Última,Variação %,Abertura,Máxima,Mínima,Volume,Status
PETR3,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO
VALE3,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO
PETR4,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO
VALE5,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO
ITUB4,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO
BBAS3,0.00,0.00,0.00,0.00,0.00,0,AGUARDANDO"""
    
    # Salvar CSV temporário
    csv_path = Path("/tmp/rtd_template.csv")
    csv_path.write_text(template_csv)
    
    # Converter para ODS usando LibreOffice
    ods_path = Path.home() / "Documentos/ProfitChart_RTD.ods"
    
    print(f"📄 Criando template ODS em: {ods_path}")
    
    try:
        result = subprocess.run([
            'libreoffice',
            '--headless',
            '--convert-to', 'ods',
            '--outdir', str(ods_path.parent),
            str(csv_path)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Renomear arquivo
            generated = ods_path.parent / "rtd_template.ods"
            if generated.exists():
                generated.rename(ods_path)
                print(f"✅ Template criado: {ods_path}")
                return True
        else:
            print(f"❌ Erro: {result.stderr}")
            
    except FileNotFoundError:
        print("❌ LibreOffice não encontrado")
        print("   Instale: sudo apt install libreoffice")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    return False


def create_python_updater_script():
    """
    Cria script Python que atualiza a planilha ODS diretamente
    
    Alternativa mais robusta que macros Basic
    """
    
    script_content = '''#!/usr/bin/env python3
"""
ODS RTD Updater - Atualiza planilha LibreOffice em tempo real
"""

import asyncio
import json
import sys
from pathlib import Path

try:
    import websockets
    from odfpy import opendocument, table, text
except ImportError:
    print("❌ Instale dependências: pip3 install websockets odfpy")
    sys.exit(1)


class ODSRTDUpdater:
    """Atualizador de planilha ODS via RTD Bridge"""
    
    def __init__(self, ods_path: str, server_url: str = "ws://localhost:8765"):
        self.ods_path = Path(ods_path)
        self.server_url = server_url
        self.websocket = None
        
    async def connect(self):
        """Conecta ao servidor RTD"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            print(f"✅ Conectado ao RTD Bridge: {self.server_url}")
            return True
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            return False
    
    async def update_loop(self):
        """Loop de atualização da planilha"""
        while True:
            try:
                # Obter dados
                await self.websocket.send(json.dumps({'command': 'get_data'}))
                response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                
                data = json.loads(response)
                if data.get('type') == 'market_data':
                    market_data = data.get('data', {})
                    
                    # Atualizar planilha
                    self.update_ods(market_data)
                    
                    print(f"🔄 Atualizado: {len(market_data)} símbolos")
                
                await asyncio.sleep(1)
                
            except asyncio.TimeoutError:
                print("⚠️ Timeout")
            except Exception as e:
                print(f"❌ Erro: {e}")
                await asyncio.sleep(5)
    
    def update_ods(self, market_data: dict):
        """Atualiza arquivo ODS com novos dados"""
        if not self.ods_path.exists():
            print(f"⚠️ Arquivo não encontrado: {self.ods_path}")
            return
        
        try:
            # Abrir documento
            doc = opendocument.load(str(self.ods_path))
            
            # Obter primeira planilha
            sheets = doc.spreadsheet.getElementsByType(table.Table)
            if not sheets:
                return
            
            sheet = sheets[0]
            rows = sheet.getElementsByType(table.TableRow)
            
            # Atualizar linhas (começar da linha 2, após cabeçalho)
            for i, (symbol, quote) in enumerate(market_data.items(), start=1):
                if i >= len(rows):
                    break
                
                row = rows[i]
                cells = row.getElementsByType(table.TableCell)
                
                # Atualizar células
                # A1: Símbolo, B1: Última, C1: Variação, etc.
                if len(cells) >= 8:
                    self._set_cell_value(cells[0], symbol)
                    self._set_cell_value(cells[1], f"{quote.get('last', 0):.2f}")
                    self._set_cell_value(cells[2], f"{quote.get('variation', 0):+.2f}")
                    self._set_cell_value(cells[3], f"{quote.get('open', 0):.2f}")
                    self._set_cell_value(cells[4], f"{quote.get('high', 0):.2f}")
                    self._set_cell_value(cells[5], f"{quote.get('low', 0):.2f}")
                    self._set_cell_value(cells[6], f"{quote.get('volume', 0):,}")
                    self._set_cell_value(cells[7], quote.get('status', 'N/A'))
            
            # Salvar documento
            doc.save(str(self.ods_path))
            
        except Exception as e:
            print(f"❌ Erro ao atualizar ODS: {e}")
    
    def _set_cell_value(self, cell, value):
        """Define valor de uma célula"""
        # Remover conteúdo existente
        for child in list(cell.childNodes):
            cell.removeChild(child)
        
        # Adicionar novo valor
        p = text.P()
        p.addText(str(value))
        cell.addElement(p)


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 ods_rtd_updater.py <caminho_planilha.ods>")
        sys.exit(1)
    
    ods_path = sys.argv[1]
    
    updater = ODSRTDUpdater(ods_path)
    
    if not await updater.connect():
        sys.exit(1)
    
    print(f"\\n📊 Atualizando planilha: {ods_path}")
    print("   Pressione Ctrl+C para parar\\n")
    
    try:
        await updater.update_loop()
    except KeyboardInterrupt:
        print("\\n🛑 Encerrando...")


if __name__ == "__main__":
    asyncio.run(main())
'''
    
    script_path = Path("/home/dellno/worksapace/b3-trading-platform/services/rtd-bridge/ods_rtd_updater.py")
    script_path.write_text(script_content)
    script_path.chmod(0o755)
    
    print(f"✅ Script criado: {script_path}")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     📊 Gerador de Template LibreOffice Calc                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Criar template
    if create_calc_template():
        print("\n✅ Template ODS criado com sucesso!")
        print("\n📝 Para usar:")
        print("   1. Abra: ~/Documentos/ProfitChart_RTD.ods")
        print("   2. Execute: python3 services/rtd-bridge/ods_rtd_updater.py ~/Documentos/ProfitChart_RTD.ods")
    
    # Criar script updater
    print("\n📦 Criando script Python updater...")
    create_python_updater_script()
    
    print("\n✅ Concluído!")
