import redis
import json
from datetime import datetime
from typing import Optional, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка Redis-клиента
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# Время жизни кэша (в секундах)
CACHE_EXPIRY = 3600  # 1 час

def datetime_handler(obj):
    """Преобразует объекты datetime в строку для сериализации в JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def get_cached_url(short_code: str) -> Optional[str]:
    try:
        return redis_client.get(f"url:{short_code}")
    except redis.RedisError as e:
        logger.error(f"Error getting cache for {short_code}: {e}")
        return None

def set_cached_url(short_code: str, url: str):
    try:
        redis_client.setex(f"url:{short_code}", CACHE_EXPIRY, url)
    except redis.RedisError as e:
        logger.error(f"Error setting cache for {short_code}: {e}")

def delete_cached_url(short_code: str):
    try:
        redis_client.delete(f"url:{short_code}")
    except redis.RedisError as e:
        logger.error(f"Error deleting cache for {short_code}: {e}")

def get_cached_stats(short_code: str) -> Optional[Dict[str, Any]]:
    try:
        stats = redis_client.get(f"stats:{short_code}")
        if stats:
            return json.loads(stats)
        return None
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error getting cached stats for {short_code}: {e}")
        return None

def set_cached_stats(short_code: str, stats: dict):
    try:
        redis_client.setex(
            f"stats:{short_code}",
            CACHE_EXPIRY,
            json.dumps(stats, default=datetime_handler)
        )
    except redis.RedisError as e:
        logger.error(f"Error setting cache for stats {short_code}: {e}")

def delete_cached_stats(short_code: str):
    try:
        redis_client.delete(f"stats:{short_code}")
    except redis.RedisError as e:
        logger.error(f"Error deleting cached stats for {short_code}: {e}")
