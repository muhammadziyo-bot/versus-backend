import redis
import json
from app.config import settings
from typing import Optional, Any
import os

class RedisClient:
    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.enabled = bool(os.getenv('REDIS_URL'))  # Only enable if REDIS_URL is set
        self.client = None
        self._fallback_storage = {}  # In-memory fallback when Redis is not available
        
        if self.enabled:
            try:
                self.client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                self.client.ping()
                print("✅ Redis connected successfully")
            except Exception as e:
                print(f"⚠️ Redis connection failed, using in-memory fallback: {e}")
                self.enabled = False
        else:
            print("⚠️ Redis not configured, using in-memory fallback")
    
    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set a key-value pair with expiration"""
        if self.enabled and self.client:
            try:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                return self.client.setex(key, expire, value)
            except Exception as e:
                print(f"Redis set error: {e}")
                # Fall back to in-memory storage
                self._fallback_storage[key] = value
                return True
        else:
            # Use in-memory fallback
            self._fallback_storage[key] = value
            return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value by key"""
        if self.enabled and self.client:
            try:
                value = self.client.get(key)
                if value:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
                return None
            except Exception as e:
                print(f"Redis get error: {e}")
                # Fall back to in-memory storage
                return self._fallback_storage.get(key)
        else:
            # Use in-memory fallback
            return self._fallback_storage.get(key)
    
    def delete(self, key: str) -> bool:
        """Delete a key"""
        if self.enabled and self.client:
            try:
                result = self.client.delete(key) > 0
                # Also remove from fallback
                if key in self._fallback_storage:
                    del self._fallback_storage[key]
                return result
            except Exception as e:
                print(f"Redis delete error: {e}")
                # Fall back to in-memory storage
                if key in self._fallback_storage:
                    del self._fallback_storage[key]
                    return True
                return False
        else:
            # Use in-memory fallback
            if key in self._fallback_storage:
                del self._fallback_storage[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists"""
        if self.enabled and self.client:
            try:
                return self.client.exists(key) > 0
            except Exception as e:
                print(f"Redis exists error: {e}")
                # Fall back to in-memory storage
                return key in self._fallback_storage
        else:
            # Use in-memory fallback
            return key in self._fallback_storage
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key"""
        if self.enabled and self.client:
            try:
                return self.client.expire(key, seconds)
            except Exception as e:
                print(f"Redis expire error: {e}")
                # In-memory fallback doesn't support expiration
                return False
        else:
            # In-memory fallback doesn't support expiration
            return False
    
    def ping(self) -> bool:
        """Check if Redis is connected"""
        if self.enabled and self.client:
            try:
                return self.client.ping()
            except Exception as e:
                print(f"Redis ping error: {e}")
                return False
        else:
            return False

# Global Redis client instance
redis_client = RedisClient()
