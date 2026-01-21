/**
 * PASSO 14: API REST Endpoints para ML
 * Rotas para predições, backtests e gerenciamento de modelos ML
 */

const express = require('express');
const axios = require('axios');
const router = express.Router();

// Configuração do Execution Engine
const EXECUTION_ENGINE_URL = process.env.EXECUTION_ENGINE_URL || 'http://execution-engine:8000';

/**
 * @route   POST /api/ml/predict/b3
 * @desc    Predição para ações B3 usando Wave3 pura (validada)
 * @access  Public
 * @body    {symbol: string, date?: string}
 * @returns {prediction: string, confidence: number, details: object}
 */
router.post('/predict/b3', async (req, res) => {
    try {
        const { symbol, date } = req.body;

        // Validação
        if (!symbol) {
            return res.status(400).json({
                error: 'Missing required field: symbol',
                example: { symbol: 'PETR4', date: '2025-01-17' }
            });
        }

        // Chamar Execution Engine
        const response = await axios.post(
            `${EXECUTION_ENGINE_URL}/api/ml/predict/b3`,
            { symbol, date },
            { timeout: 30000 }
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /predict/b3:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Prediction failed',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   POST /api/ml/predict/crypto
 * @desc    Predição para criptomoedas usando ML puro (Walk-Forward)
 * @access  Public
 * @body    {symbol: string, date?: string}
 * @returns {prediction: string, confidence: number, ml_features: object}
 */
router.post('/predict/crypto', async (req, res) => {
    try {
        const { symbol, date } = req.body;

        // Validação
        if (!symbol) {
            return res.status(400).json({
                error: 'Missing required field: symbol',
                example: { symbol: 'BTCUSDT', date: '2025-01-17' }
            });
        }

        // Chamar Execution Engine
        const response = await axios.post(
            `${EXECUTION_ENGINE_URL}/api/ml/predict/crypto`,
            { symbol, date },
            { timeout: 30000 }
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /predict/crypto:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Prediction failed',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   POST /api/ml/backtest/compare
 * @desc    Compara múltiplas estratégias (Wave3, ML, Híbrido)
 * @access  Public
 * @body    {symbols: string[], strategies: string[], start_date: string, end_date: string}
 * @returns {results: array, ranking: array, summary: object}
 */
router.post('/backtest/compare', async (req, res) => {
    try {
        const { symbols, strategies, start_date, end_date } = req.body;

        // Validação
        if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
            return res.status(400).json({
                error: 'Missing or invalid field: symbols (must be non-empty array)',
                example: {
                    symbols: ['PETR4', 'VALE3'],
                    strategies: ['wave3', 'ml'],
                    start_date: '2024-01-01',
                    end_date: '2025-01-01'
                }
            });
        }

        // Chamar Execution Engine
        const response = await axios.post(
            `${EXECUTION_ENGINE_URL}/api/ml/backtest/compare`,
            { symbols, strategies, start_date, end_date },
            { timeout: 120000 } // 2 minutos para backtests
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /backtest/compare:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Backtest failed',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   GET /api/ml/model-info
 * @desc    Retorna informações do modelo ML atual
 * @access  Public
 * @query   model_type?: string (b3, crypto, hybrid)
 * @returns {model_type: string, features: array, metrics: object, trained_on: string}
 */
router.get('/model-info', async (req, res) => {
    try {
        const { model_type } = req.query;

        // Chamar Execution Engine
        const response = await axios.get(
            `${EXECUTION_ENGINE_URL}/api/ml/model-info`,
            { 
                params: { model_type },
                timeout: 10000 
            }
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /model-info:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Failed to get model info',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   POST /api/ml/train
 * @desc    Treina um novo modelo ML
 * @access  Public
 * @body    {symbols: string[], model_type: string, use_smote: boolean, test_size: number}
 * @returns {model_id: string, metrics: object, training_time: number}
 */
router.post('/train', async (req, res) => {
    try {
        const { symbols, model_type, use_smote, test_size } = req.body;

        // Validação
        if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
            return res.status(400).json({
                error: 'Missing or invalid field: symbols (must be non-empty array)',
                example: {
                    symbols: ['PETR4', 'VALE3', 'ITUB4'],
                    model_type: 'random_forest',
                    use_smote: true,
                    test_size: 0.2
                }
            });
        }

        // Chamar Execution Engine (async training)
        const response = await axios.post(
            `${EXECUTION_ENGINE_URL}/api/ml/train`,
            { symbols, model_type, use_smote, test_size },
            { timeout: 300000 } // 5 minutos para treinamento
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /train:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Training failed',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   GET /api/ml/feature-importance
 * @desc    Retorna as features mais importantes do modelo
 * @access  Public
 * @query   top_n?: number (default: 20)
 * @returns {features: array, chart_data: object}
 */
router.get('/feature-importance', async (req, res) => {
    try {
        const { top_n = 20 } = req.query;

        // Chamar Execution Engine
        const response = await axios.get(
            `${EXECUTION_ENGINE_URL}/api/ml/feature-importance`,
            { 
                params: { top_n },
                timeout: 10000 
            }
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /feature-importance:', error.message);
        
        if (error.response) {
            return res.status(error.response.status).json({
                error: error.response.data.detail || 'Failed to get feature importance',
                status: error.response.status
            });
        }

        res.status(500).json({
            error: 'Internal server error',
            message: error.message
        });
    }
});

/**
 * @route   GET /api/ml/health
 * @desc    Health check do módulo ML
 * @access  Public
 * @returns {status: string, models_loaded: object, db_connected: boolean}
 */
router.get('/health', async (req, res) => {
    try {
        // Chamar Execution Engine
        const response = await axios.get(
            `${EXECUTION_ENGINE_URL}/api/ml/health`,
            { timeout: 5000 }
        );

        res.json(response.data);

    } catch (error) {
        console.error('Error in /health:', error.message);
        
        res.status(503).json({
            status: 'unhealthy',
            error: 'ML service unavailable',
            message: error.message
        });
    }
});

module.exports = router;
