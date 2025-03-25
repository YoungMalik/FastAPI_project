import redis
from dotenv import load_dotenv
import os
import json

load_dotenv()

redis_client = redis.from_url(os.getenv("REDIS_URL"))

def get_cached_url(short_code: str) -> str:
    """Получить URL из кэша"""
    cached_data = redis_client.get(f"url:{short_code}")
    if cached_data:
        return json.loads(cached_data)
    return None

def set_cached_url(short_code: str, original_url: str, expire_time: int = 3600):
    """Сохранить URL в кэш"""
    redis_client.setex(
        f"url:{short_code}",
        expire_time,
        json.dumps(original_url)
    )

def delete_cached_url(short_code: str):
    """Удалить URL из кэша"""
    redis_client.delete(f"url:{short_code}")

def get_cached_stats(short_code: str) -> dict:
    """Получить статистику из кэша"""
    cached_data = redis_client.get(f"stats:{short_code}")
    if cached_data:
        return json.loads(cached_data)
    return None

def set_cached_stats(short_code: str, stats: dict, expire_time: int = 3600):
    """Сохранить статистику в кэш"""
    redis_client.setex(
        f"stats:{short_code}",
        expire_time,
        json.dumps(stats)
    )

def delete_cached_stats(short_code: str):
    """Удалить статистику из кэша"""
    redis_client.delete(f"stats:{short_code}")