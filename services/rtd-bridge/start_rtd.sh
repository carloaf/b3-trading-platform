#!/bin/bash

################################################################################
#
# ProfitChart RTD Bridge - Script de Inicialização
#
# Gerencia integração entre ProfitChart (Wine) e LibreOffice Calc
# via WebSocket Real-Time Data Bridge
#
# Autor: B3 Trading Platform
# Data: 30 Janeiro 2026
#
################################################################################

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Diretórios
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RTD_BRIDGE_DIR="$PROJECT_ROOT/services/rtd-bridge"

# Configurações
RTD_SERVER_PORT=8765
PROFITCHART_PATH="$HOME/.wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit/profitchart.exe"
ODS_TEMPLATE="$HOME/Documentos/ProfitChart_RTD.ods"

################################################################################
# FUNÇÕES AUXILIARES
################################################################################

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║     📊 ProfitChart RTD Bridge                                ║"
    echo "║                                                               ║"
    echo "║     Integração Tempo Real: ProfitChart → LibreOffice Calc    ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    echo -e "\n${BLUE}═══ $1 ═══${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

check_dependencies() {
    print_section "Verificando Dependências"
    
    local missing_deps=()
    
    # Python 3
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        print_success "Python 3: $(python3 --version)"
    fi
    
    # pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    else
        print_success "pip3 instalado"
    fi
    
    # Wine
    if ! command -v wine &> /dev/null; then
        missing_deps+=("wine")
    else
        print_success "Wine: $(wine --version | head -n1)"
    fi
    
    # LibreOffice
    if ! command -v libreoffice &> /dev/null; then
        missing_deps+=("libreoffice")
    else
        print_success "LibreOffice instalado"
    fi
    
    # Verificar dependências Python
    print_info "Verificando bibliotecas Python..."
    
    if ! python3 -c "import websockets" 2>/dev/null; then
        print_warning "websockets não instalado"
        echo "          Instalando: pip3 install websockets"
        pip3 install --user websockets
    else
        print_success "websockets instalado"
    fi
    
    if ! python3 -c "import odfpy" 2>/dev/null; then
        print_warning "odfpy não instalado"
        echo "          Instalando: pip3 install odfpy"
        pip3 install --user odfpy
    else
        print_success "odfpy instalado"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Dependências faltando: ${missing_deps[*]}"
        echo ""
        echo "Instale com:"
        echo "  sudo apt install ${missing_deps[*]}"
        exit 1
    fi
    
    print_success "Todas as dependências estão instaladas"
}

check_profitchart() {
    print_section "Verificando ProfitChart"
    
    if [ ! -f "$PROFITCHART_PATH" ]; then
        print_error "ProfitChart não encontrado em:"
        echo "          $PROFITCHART_PATH"
        echo ""
        print_info "Localizações alternativas:"
        find ~/.wine* -name "profitchart.exe" 2>/dev/null || echo "  Nenhuma encontrada"
        return 1
    fi
    
    print_success "ProfitChart encontrado: $PROFITCHART_PATH"
    
    # Verificar se já está rodando
    if pgrep -f "profitchart.exe" > /dev/null; then
        print_success "ProfitChart já está rodando"
        return 0
    fi
    
    return 0
}

start_profitchart() {
    print_section "Iniciando ProfitChart"
    
    if pgrep -f "profitchart.exe" > /dev/null; then
        print_info "ProfitChart já está rodando"
        return 0
    fi
    
    print_info "Iniciando ProfitChart via Wine..."
    
    cd "$(dirname "$PROFITCHART_PATH")"
    wine profitchart.exe &> /tmp/profitchart.log &
    
    sleep 3
    
    if pgrep -f "profitchart.exe" > /dev/null; then
        print_success "ProfitChart iniciado"
    else
        print_error "Falha ao iniciar ProfitChart"
        print_info "Veja o log: /tmp/profitchart.log"
        return 1
    fi
}

start_rtd_server() {
    print_section "Iniciando RTD Bridge Server"
    
    # Verificar se já está rodando
    if lsof -i :$RTD_SERVER_PORT > /dev/null 2>&1; then
        print_warning "Servidor já está rodando na porta $RTD_SERVER_PORT"
        return 0
    fi
    
    print_info "Iniciando servidor WebSocket na porta $RTD_SERVER_PORT..."
    
    cd "$RTD_BRIDGE_DIR"
    python3 profitchart_rtd_server.py &> /tmp/rtd_server.log &
    
    local server_pid=$!
    echo $server_pid > /tmp/rtd_server.pid
    
    sleep 2
    
    if lsof -i :$RTD_SERVER_PORT > /dev/null 2>&1; then
        print_success "RTD Server iniciado (PID: $server_pid)"
        print_info "WebSocket: ws://localhost:$RTD_SERVER_PORT"
    else
        print_error "Falha ao iniciar servidor"
        print_info "Veja o log: /tmp/rtd_server.log"
        return 1
    fi
}

create_template() {
    print_section "Criando Template ODS"
    
    if [ -f "$ODS_TEMPLATE" ]; then
        print_info "Template já existe: $ODS_TEMPLATE"
        return 0
    fi
    
    print_info "Gerando template..."
    
    cd "$RTD_BRIDGE_DIR"
    python3 create_calc_template.py
    
    if [ -f "$ODS_TEMPLATE" ]; then
        print_success "Template criado: $ODS_TEMPLATE"
    else
        print_warning "Template não foi criado"
    fi
}

open_calc() {
    print_section "Abrindo LibreOffice Calc"
    
    if [ ! -f "$ODS_TEMPLATE" ]; then
        print_error "Template não encontrado: $ODS_TEMPLATE"
        echo "          Execute: ./start_rtd.sh setup"
        return 1
    fi
    
    print_info "Abrindo planilha..."
    libreoffice "$ODS_TEMPLATE" &> /dev/null &
    
    print_success "LibreOffice Calc aberto"
}

start_updater() {
    print_section "Iniciando Atualizador ODS"
    
    if [ ! -f "$ODS_TEMPLATE" ]; then
        print_error "Template não encontrado"
        return 1
    fi
    
    # Verificar se servidor está rodando
    if ! lsof -i :$RTD_SERVER_PORT > /dev/null 2>&1; then
        print_error "RTD Server não está rodando"
        echo "          Execute: ./start_rtd.sh start"
        return 1
    fi
    
    print_info "Iniciando atualizador em tempo real..."
    
    cd "$RTD_BRIDGE_DIR"
    python3 ods_rtd_updater.py "$ODS_TEMPLATE"
}

stop_services() {
    print_section "Parando Serviços"
    
    # Parar RTD Server
    if [ -f /tmp/rtd_server.pid ]; then
        local pid=$(cat /tmp/rtd_server.pid)
        if ps -p $pid > /dev/null; then
            kill $pid
            print_success "RTD Server parado"
        fi
        rm /tmp/rtd_server.pid
    fi
    
    # Parar ProfitChart (opcional)
    read -p "Parar ProfitChart também? [s/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        pkill -f profitchart.exe
        print_success "ProfitChart parado"
    fi
}

show_status() {
    print_section "Status dos Serviços"
    
    echo ""
    
    # ProfitChart
    if pgrep -f "profitchart.exe" > /dev/null; then
        print_success "ProfitChart: RODANDO"
    else
        print_warning "ProfitChart: PARADO"
    fi
    
    # RTD Server
    if lsof -i :$RTD_SERVER_PORT > /dev/null 2>&1; then
        print_success "RTD Server: RODANDO (porta $RTD_SERVER_PORT)"
    else
        print_warning "RTD Server: PARADO"
    fi
    
    # LibreOffice
    if pgrep -f "soffice" > /dev/null; then
        print_success "LibreOffice: RODANDO"
    else
        print_warning "LibreOffice: PARADO"
    fi
    
    echo ""
}

show_usage() {
    echo "Uso: $0 {setup|start|stop|status|calc|update|help}"
    echo ""
    echo "Comandos:"
    echo "  setup   - Verifica dependências e cria template"
    echo "  start   - Inicia ProfitChart e RTD Server"
    echo "  stop    - Para todos os serviços"
    echo "  status  - Mostra status dos serviços"
    echo "  calc    - Abre LibreOffice Calc com template"
    echo "  update  - Inicia atualizador em tempo real"
    echo "  help    - Mostra esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 setup    # Primeira vez: configurar tudo"
    echo "  $0 start    # Iniciar serviços"
    echo "  $0 calc     # Abrir planilha"
    echo "  $0 update   # Atualizar planilha em tempo real"
    echo ""
}

################################################################################
# COMANDO PRINCIPAL
################################################################################

main() {
    print_header
    
    case "${1:-help}" in
        setup)
            check_dependencies
            check_profitchart
            create_template
            print_success "\n✅ Setup concluído!"
            echo ""
            print_info "Próximo passo: ./start_rtd.sh start"
            ;;
        
        start)
            check_profitchart
            start_profitchart
            start_rtd_server
            print_success "\n✅ Serviços iniciados!"
            echo ""
            print_info "Abra a planilha: ./start_rtd.sh calc"
            print_info "Ou ative atualização: ./start_rtd.sh update"
            ;;
        
        stop)
            stop_services
            print_success "\n✅ Serviços parados"
            ;;
        
        status)
            show_status
            ;;
        
        calc)
            open_calc
            ;;
        
        update)
            start_updater
            ;;
        
        help|*)
            show_usage
            ;;
    esac
}

main "$@"
