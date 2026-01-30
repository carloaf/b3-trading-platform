#!/bin/bash

################################################################################
#
# RTD Bridge Container Manager
#
# Gerencia container Docker do RTD Bridge para integração
# ProfitChart → LibreOffice Calc
#
################################################################################

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

CONTAINER_NAME="b3-rtd-bridge"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║     📊 RTD Bridge Container Manager                          ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ️  $1${NC}"; }

cmd_build() {
    print_info "Building RTD Bridge container..."
    cd "$PROJECT_ROOT"
    docker build -t b3-rtd-bridge:latest services/rtd-bridge/
    print_success "Container built successfully"
}

cmd_start() {
    print_info "Starting RTD Bridge container..."
    cd "$PROJECT_ROOT"
    
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_info "Container already running"
    else
        docker run -d \
            --name $CONTAINER_NAME \
            --network b3-trading-platform_b3-network \
            -p 8765:8765 \
            -v "$PROJECT_ROOT/services/rtd-bridge:/app" \
            -e PROFITCHART_MODE=mock \
            --restart unless-stopped \
            b3-rtd-bridge:latest
        
        sleep 2
        print_success "Container started"
    fi
}

cmd_stop() {
    print_info "Stopping RTD Bridge container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    print_success "Container stopped"
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_logs() {
    docker logs -f $CONTAINER_NAME
}

cmd_exec() {
    docker exec -it $CONTAINER_NAME bash
}

cmd_status() {
    echo ""
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_success "Container Status: RUNNING"
        echo ""
        docker ps --filter name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        print_info "WebSocket: ws://localhost:8765"
    else
        print_error "Container Status: STOPPED"
    fi
    echo ""
}

cmd_test() {
    print_info "Testing RTD Bridge connection..."
    
    if ! docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        print_error "Container not running. Start it first: $0 start"
        exit 1
    fi
    
    # Testar cliente Python
    docker exec $CONTAINER_NAME python3 calc_client.py --mode simple
    
    if [ $? -eq 0 ]; then
        print_success "RTD Bridge is working!"
    else
        print_error "Connection failed"
    fi
}

cmd_calc_update() {
    local ODS_FILE="${1:-$HOME/Documentos/ProfitChart_RTD.ods}"
    
    if [ ! -f "$ODS_FILE" ]; then
        print_error "Planilha não encontrada: $ODS_FILE"
        echo "          Crie primeiro: $0 create-template"
        exit 1
    fi
    
    print_info "Starting ODS updater for: $ODS_FILE"
    docker exec $CONTAINER_NAME python3 ods_rtd_updater.py /tmp/template.ods &
    
    print_success "Updater started in background"
    print_info "Press Ctrl+C to stop"
}

cmd_create_template() {
    print_info "Creating LibreOffice Calc template..."
    docker exec $CONTAINER_NAME python3 create_calc_template.py
    print_success "Template created: ~/Documentos/ProfitChart_RTD.ods"
}

show_usage() {
    cat << EOF
Usage: $0 {command}

Commands:
  build          Build Docker container
  start          Start RTD Bridge container
  stop           Stop RTD Bridge container
  restart        Restart container
  status         Show container status
  logs           Show container logs (follow)
  exec           Open bash shell in container
  test           Test WebSocket connection
  create-template Create LibreOffice template
  update [file]  Start real-time updater for ODS file

Examples:
  $0 build              # Build container
  $0 start              # Start services
  $0 test               # Test connection
  $0 update             # Update default template
  $0 logs               # Watch logs

EOF
}

################################################################################
# MAIN
################################################################################

print_header

case "${1:-help}" in
    build)          cmd_build ;;
    start)          cmd_start ;;
    stop)           cmd_stop ;;
    restart)        cmd_restart ;;
    status)         cmd_status ;;
    logs)           cmd_logs ;;
    exec)           cmd_exec ;;
    test)           cmd_test ;;
    update)         cmd_calc_update "$2" ;;
    create-template) cmd_create_template ;;
    help|*)         show_usage ;;
esac
