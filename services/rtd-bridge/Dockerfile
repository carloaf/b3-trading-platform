FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    lsof \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY *.py ./

# Criar diretórios necessários
RUN mkdir -p /tmp/rtd_logs

# Expor porta WebSocket
EXPOSE 8765

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import socket; s=socket.socket(); s.connect(('localhost', 8765)); s.close()" || exit 1

# Comando padrão
CMD ["python3", "profitchart_rtd_server.py"]
