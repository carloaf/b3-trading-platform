FROM node:20-alpine

WORKDIR /app

# Copiar package.json
COPY package*.json ./

# Instalar dependências
RUN npm ci

# Copiar código
COPY . .

# Build
RUN npm run build

# Porta
EXPOSE 8080

# Comando (serve build estático)
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8080"]
