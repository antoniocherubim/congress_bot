/**
 * Configuração e conexão Redis para BullMQ
 */
require('dotenv').config();
const { Redis } = require('ioredis');

const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
const REDIS_PORT = parseInt(process.env.REDIS_PORT || '6379', 10);
const REDIS_PASSWORD = process.env.REDIS_PASSWORD || undefined;
const REDIS_DB = parseInt(process.env.REDIS_DB || '0', 10);

/**
 * Cria e retorna uma conexão Redis configurada
 * @returns {Redis} Instância do cliente Redis
 */
function createRedisConnection() {
  const redisConfig = {
    host: REDIS_HOST,
    port: REDIS_PORT,
    db: REDIS_DB,
    retryStrategy: (times) => {
      const delay = Math.min(times * 50, 2000);
      console.log(`[Redis] Tentando reconectar (tentativa ${times}) em ${delay}ms...`);
      return delay;
    },
    maxRetriesPerRequest: 3,
  };

  if (REDIS_PASSWORD) {
    redisConfig.password = REDIS_PASSWORD;
  }

  const redis = new Redis(redisConfig);

  redis.on('connect', () => {
    console.log(`[Redis] Conectado em ${REDIS_HOST}:${REDIS_PORT}`);
  });

  redis.on('error', (error) => {
    console.error('[Redis] Erro de conexão:', error.message);
  });

  redis.on('close', () => {
    console.warn('[Redis] Conexão fechada');
  });

  return redis;
}

/**
 * Obtém uma conexão Redis compartilhada (singleton)
 */
let redisInstance = null;

function getRedisConnection() {
  if (!redisInstance) {
    redisInstance = createRedisConnection();
  }
  return redisInstance;
}

module.exports = {
  createRedisConnection,
  getRedisConnection,
  REDIS_HOST,
  REDIS_PORT,
  REDIS_DB,
};

