"""
Redis cache helpers.

All operations degrade gracefully when Redis is unavailable.
"""
import json
from typing import Any

from ..extensions import get_redis


class CacheService:
    # TTL constants (seconds)
    PRODUCTS_TTL = 300        # 5 minutes
    PRODUCT_ITEM_TTL = 300
    CART_TTL = 3_600          # 1 hour
    IDEMPOTENCY_TTL = 86_400  # 24 hours

    # -------------------------------------------------------------------------
    # Generic helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def get(key: str) -> Any | None:
        r = get_redis()
        if r is None:
            return None
        raw = r.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    @staticmethod
    def set(key: str, value: Any, ttl: int = 300) -> None:
        r = get_redis()
        if r is None:
            return
        r.setex(key, ttl, json.dumps(value))

    @staticmethod
    def delete(key: str) -> None:
        r = get_redis()
        if r is None:
            return
        r.delete(key)

    @staticmethod
    def delete_pattern(pattern: str) -> None:
        r = get_redis()
        if r is None:
            return
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)

    # -------------------------------------------------------------------------
    # Domain-specific helpers
    # -------------------------------------------------------------------------
    @classmethod
    def get_products(cls, cache_key: str) -> list | None:
        return cls.get(cache_key)

    @classmethod
    def set_products(cls, cache_key: str, data: list) -> None:
        cls.set(cache_key, data, cls.PRODUCTS_TTL)

    @classmethod
    def invalidate_products(cls) -> None:
        cls.delete_pattern("products:*")

    @classmethod
    def get_product(cls, product_id: str) -> dict | None:
        return cls.get(f"product:{product_id}")

    @classmethod
    def set_product(cls, product_id: str, data: dict) -> None:
        cls.set(f"product:{product_id}", data, cls.PRODUCT_ITEM_TTL)

    @classmethod
    def invalidate_product(cls, product_id: str) -> None:
        cls.delete(f"product:{product_id}")
        cls.invalidate_products()

    # -------------------------------------------------------------------------
    # JWT blacklist (used by logout)
    # -------------------------------------------------------------------------
    @staticmethod
    def blacklist_token(jti: str, ttl_seconds: int = 3_600) -> None:
        r = get_redis()
        if r is None:
            return
        r.setex(f"blacklist:{jti}", ttl_seconds, "1")

    # -------------------------------------------------------------------------
    # Idempotency keys (prevent duplicate checkout submissions)
    # -------------------------------------------------------------------------
    @classmethod
    def get_idempotency(cls, key: str) -> dict | None:
        return cls.get(f"idempotency:{key}")

    @classmethod
    def set_idempotency(cls, key: str, order_data: dict) -> None:
        cls.set(f"idempotency:{key}", order_data, cls.IDEMPOTENCY_TTL)
