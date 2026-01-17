/**
 * B3 Trading Platform - API Gateway
 * ==================================
 * Gateway central para roteamento e autenticação.
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const { createProxyMiddleware } = require('http-proxy-middleware');
const jwt = require('jsonwebtoken');
const { createClient } = require('redis');

// Configuração
const config = {
    port: process.env.PORT || 3000,
    jwtSecret: process.env.JWT_SECRET || 'b3-trading-secret-key',
    redis: {
        host: process.env.REDIS_HOST || 'localhost',
        port: process.env.REDIS_PORT || 6379
    },
    services: {
        executionEngine: process.env.EXECUTION_ENGINE_URL || 'http://localhost:3008',
        dataCollector: process.env.DATA_COLLECTOR_URL || 'http://localhost:3002'
    }
};

// App Express
const app = express();

// Middlewares de segurança
app.use(helmet({
    contentSecurityPolicy: false // Desabilitar para desenvolvimento
}));
app.use(cors());
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(morgan('combined'));

// Rate Limiting
const limiter = rateLimit({
    windowMs: 1 * 60 * 1000, // 1 minuto
    max: 100, // 100 requests por minuto
    message: { error: 'Too many requests, please try again later.' }
});
app.use('/api/', limiter);

// Redis Client
let redisClient;

async function initRedis() {
    try {
        redisClient = createClient({
            socket: {
                host: config.redis.host,
                port: config.redis.port
            }
        });
        
        redisClient.on('error', err => console.error('Redis Error:', err));
        await redisClient.connect();
        console.log('✅ Redis conectado');
    } catch (err) {
        console.warn('⚠️ Redis não disponível:', err.message);
    }
}

// Middleware de autenticação JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    
    if (!token) {
        return res.status(401).json({ error: 'Token não fornecido' });
    }
    
    jwt.verify(token, config.jwtSecret, (err, user) => {
        if (err) {
            return res.status(403).json({ error: 'Token inválido' });
        }
        req.user = user;
        next();
    });
};

// Middleware opcional de autenticação
const optionalAuth = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    
    if (token) {
        jwt.verify(token, config.jwtSecret, (err, user) => {
            if (!err) {
                req.user = user;
            }
        });
    }
    next();
};

// ============================================
// ROTAS PÚBLICAS
// ============================================

// Health Check
app.get('/health', async (req, res) => {
    const services = {
        gateway: 'healthy',
        redis: 'unknown',
        executionEngine: 'unknown',
        dataCollector: 'unknown'
    };
    
    // Check Redis
    try {
        if (redisClient && redisClient.isOpen) {
            await redisClient.ping();
            services.redis = 'healthy';
        } else {
            services.redis = 'disconnected';
        }
    } catch (err) {
        services.redis = 'unhealthy';
    }
    
    // Check Execution Engine
    try {
        const response = await fetch(`${config.services.executionEngine}/health`);
        services.executionEngine = response.ok ? 'healthy' : 'unhealthy';
    } catch (err) {
        services.executionEngine = 'unreachable';
    }
    
    // Check Data Collector
    try {
        const response = await fetch(`${config.services.dataCollector}/health`);
        services.dataCollector = response.ok ? 'healthy' : 'unhealthy';
    } catch (err) {
        services.dataCollector = 'unreachable';
    }
    
    const allHealthy = Object.values(services).every(s => s === 'healthy');
    
    res.status(allHealthy ? 200 : 503).json({
        status: allHealthy ? 'healthy' : 'degraded',
        timestamp: new Date().toISOString(),
        services
    });
});

// Login
app.post('/auth/login', async (req, res) => {
    try {
        const { email, password } = req.body;
        
        if (!email || !password) {
            return res.status(400).json({ error: 'Email e senha são obrigatórios' });
        }
        
        // Em produção, validar contra o banco de dados
        // Por simplicidade, aceitar admin/admin123
        if (email === 'admin@b3trading.local' && password === 'admin123') {
            const token = jwt.sign(
                { userId: '1', email, role: 'admin' },
                config.jwtSecret,
                { expiresIn: '24h' }
            );
            
            return res.json({
                success: true,
                token,
                user: {
                    id: '1',
                    email,
                    name: 'Administrador',
                    role: 'admin'
                }
            });
        }
        
        return res.status(401).json({ error: 'Credenciais inválidas' });
    } catch (err) {
        console.error('Login error:', err);
        res.status(500).json({ error: 'Erro interno' });
    }
});

// Registro (simplificado)
app.post('/auth/register', async (req, res) => {
    try {
        const { email, password, name } = req.body;
        
        if (!email || !password) {
            return res.status(400).json({ error: 'Email e senha são obrigatórios' });
        }
        
        // Em produção, salvar no banco de dados
        const token = jwt.sign(
            { userId: Date.now().toString(), email, role: 'user' },
            config.jwtSecret,
            { expiresIn: '24h' }
        );
        
        return res.status(201).json({
            success: true,
            token,
            user: {
                id: Date.now().toString(),
                email,
                name: name || email.split('@')[0],
                role: 'user'
            }
        });
    } catch (err) {
        console.error('Register error:', err);
        res.status(500).json({ error: 'Erro interno' });
    }
});

// ============================================
// ROTAS ML (PASSO 14)
// ============================================

const mlRoutes = require('./routes/ml');
app.use('/api/ml', mlRoutes);

// ============================================
// PROXY PARA SERVIÇOS
// ============================================

// Proxy para Execution Engine
app.use('/api/backtest', optionalAuth, createProxyMiddleware({
    target: config.services.executionEngine,
    changeOrigin: true,
    pathRewrite: {
        '^/api/backtest': '/api/backtest'
    },
    onError: (err, req, res) => {
        console.error('Proxy error (execution-engine):', err);
        res.status(502).json({ error: 'Serviço indisponível' });
    }
}));

app.use('/api/signals', optionalAuth, createProxyMiddleware({
    target: config.services.executionEngine,
    changeOrigin: true,
    pathRewrite: {
        '^/api/signals': '/api/signals'
    }
}));

app.use('/api/paper', authenticateToken, createProxyMiddleware({
    target: config.services.executionEngine,
    changeOrigin: true,
    pathRewrite: {
        '^/api/paper': '/api/paper'
    }
}));

app.use('/api/strategies', optionalAuth, createProxyMiddleware({
    target: config.services.executionEngine,
    changeOrigin: true,
    pathRewrite: {
        '^/api/strategies': '/api/strategies'
    }
}));

// Proxy para Data Collector
app.use('/api/quote', optionalAuth, createProxyMiddleware({
    target: config.services.dataCollector,
    changeOrigin: true,
    pathRewrite: {
        '^/api/quote': '/api/quote'
    }
}));

app.use('/api/historical', optionalAuth, createProxyMiddleware({
    target: config.services.dataCollector,
    changeOrigin: true,
    pathRewrite: {
        '^/api/historical': '/api/historical'
    }
}));

app.use('/api/data', optionalAuth, createProxyMiddleware({
    target: config.services.dataCollector,
    changeOrigin: true,
    pathRewrite: {
        '^/api/data': '/api/data'
    }
}));

app.use('/api/symbols', optionalAuth, createProxyMiddleware({
    target: config.services.dataCollector,
    changeOrigin: true,
    pathRewrite: {
        '^/api/symbols': '/api/symbols'
    }
}));

app.use('/api/b3', optionalAuth, createProxyMiddleware({
    target: config.services.dataCollector,
    changeOrigin: true,
    pathRewrite: {
        '^/api/b3': '/api/b3'
    }
}));

// ============================================
// ROTAS PROTEGIDAS
// ============================================

// Perfil do usuário
app.get('/api/user/profile', authenticateToken, (req, res) => {
    res.json({
        user: req.user
    });
});

// ============================================
// ERROR HANDLING
// ============================================

// 404
app.use((req, res) => {
    res.status(404).json({ error: 'Endpoint não encontrado' });
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({ error: 'Erro interno do servidor' });
});

// ============================================
// START SERVER
// ============================================

async function start() {
    await initRedis();
    
    app.listen(config.port, () => {
        console.log(`
╔══════════════════════════════════════════════════════════════╗
║       🇧🇷 B3 TRADING PLATFORM - API GATEWAY                   ║
╠══════════════════════════════════════════════════════════════╣
║  URL:              http://localhost:${config.port}                      ║
║  Execution Engine: ${config.services.executionEngine.padEnd(30)}     ║
║  Data Collector:   ${config.services.dataCollector.padEnd(30)}     ║
╚══════════════════════════════════════════════════════════════╝
        `);
    });
}

start().catch(console.error);

module.exports = app;
