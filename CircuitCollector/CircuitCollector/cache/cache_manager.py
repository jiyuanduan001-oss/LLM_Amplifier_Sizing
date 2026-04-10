"""
Cache Manager implementing Redis (hot cache) + SQLite (cold storage) architecture.
"""

from __future__ import annotations
import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
import redis
from redis.lock import Lock
from CircuitCollector.utils.path import PROJECT_ROOT


class CacheManager:
    """
    Two-tier cache manager: Redis (hot) + SQLite (cold).

    Features:
    - Redis: Hot cache with automatic LRU eviction
    - SQLite: Full persistence storage
    - Canonical key generation (SHA256)
    - Distributed locking to prevent duplicate simulations
    - Automatic fallback: Redis → SQLite → Simulation
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        sqlite_path: Optional[Path] = None,
        lock_timeout: int = 30,
        lock_blocking_timeout: int = 10,
    ):
        """
        Initialize CacheManager.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            sqlite_path: Path to SQLite database file
            lock_timeout: Lock timeout in seconds
            lock_blocking_timeout: Blocking timeout for acquiring lock
        """
        # Redis connection
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
        )

        # SQLite database
        if sqlite_path is None:
            db_dir = PROJECT_ROOT / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            sqlite_path = db_dir / "cache.db"
        self.sqlite_path = Path(sqlite_path)
        self._init_sqlite()

        # Lock configuration
        self.lock_timeout = lock_timeout
        self.lock_blocking_timeout = lock_blocking_timeout

        # Statistics
        self.stats = {
            "redis_hit": 0,
            "redis_miss": 0,
            "sqlite_hit": 0,
            "sqlite_miss": 0,
            "set_count": 0,
        }

    def _init_sqlite(self):
        """Initialize SQLite database."""
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        # Tables are created on-demand per circuit

    def _get_table_name(self, circuit: str) -> str:
        """
        Generate a valid SQL table name from circuit path.

        Args:
            circuit: Base config path (e.g., "config/skywater/opamp/tsm.toml")

        Returns:
            Valid SQL table name (e.g., "skywater_opamp_tsm")
        """
        # Remove file extension
        circuit_path = circuit.rsplit(".", 1)[0] if "." in circuit else circuit

        # Split by path separator and filter out empty parts
        parts = [p for p in circuit_path.split("/") if p]

        # Skip common prefixes like "config"
        if parts and parts[0] in ["config"]:
            parts = parts[1:]

        # Join remaining parts with underscore
        table_name = "_".join(parts)

        # Remove any invalid characters and ensure it starts with a letter
        table_name = "".join(c if c.isalnum() or c == "_" else "_" for c in table_name)

        # Ensure it starts with a letter or underscore
        if table_name and not (table_name[0].isalpha() or table_name[0] == "_"):
            table_name = "_" + table_name

        return table_name

    def _ensure_table(self, circuit: str):
        """
        Ensure the table for the given circuit exists.

        Args:
            circuit: Base config path
        """
        table_name = self._get_table_name(circuit)
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()
        conn.close()

    def _generate_key(self, circuit: str, params: Dict[str, Any]) -> str:
        """
        Generate canonical cache key.

        Args:
            circuit: Base config path (e.g., "config/skywater/opamp/tsm.toml")
            params: Simulation parameters

        Returns:
            SHA256 hash of circuit + canonical params JSON
        """
        # Canonical params: sort keys for consistent ordering
        canonical_params = json.dumps(params, sort_keys=True)

        # Combine circuit and params
        key_string = f"{circuit}|{canonical_params}"

        # SHA256 hash
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()

        return key_hash

    def _get_lock(self, key: str) -> Lock:
        """Get a distributed lock for the given key."""
        lock_key = f"lock:{key}"
        return self.redis_client.lock(
            lock_key,
            timeout=self.lock_timeout,
            blocking_timeout=self.lock_blocking_timeout,
        )

    def get(
        self, circuit: str, params: Dict[str, Any], count_stats: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result.

        Priority: Redis → SQLite → None

        Args:
            circuit: Base config path
            params: Simulation parameters
            count_stats: Whether to count statistics (default: True)

        Returns:
            Cached result dict or None if not found
        """
        key = self._generate_key(circuit, params)

        # Try Redis first
        try:
            redis_value = self.redis_client.get(key)
            if redis_value is not None:
                if count_stats:
                    self.stats["redis_hit"] += 1
                return json.loads(redis_value)
        except Exception:
            pass  # Redis unavailable, fall through to SQLite

        if count_stats:
            self.stats["redis_miss"] += 1

        # Try SQLite (use circuit-specific table)
        table_name = self._get_table_name(circuit)
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        # Check if table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            (table_name,),
        )
        if cursor.fetchone():
            cursor.execute(f"SELECT value FROM {table_name} WHERE key = ?", (key,))
            row = cursor.fetchone()
        else:
            row = None
        conn.close()

        if row is not None:
            # Re-warm Redis cache
            value = json.loads(row[0])
            try:
                self.redis_client.set(key, row[0])
            except Exception:
                pass  # Redis unavailable, skip re-warming
            if count_stats:
                self.stats["sqlite_hit"] += 1
            return value

        if count_stats:
            self.stats["sqlite_miss"] += 1
        return None

    def set(
        self,
        circuit: str,
        params: Dict[str, Any],
        value: Dict[str, Any],
    ) -> None:
        """
        Set cache value in both Redis and SQLite.

        Args:
            circuit: Base config path
            params: Simulation parameters
            value: Result to cache (should include circuit, params, specs, op_region, logs)
        """
        key = self._generate_key(circuit, params)
        json_value = json.dumps(value)

        # Write to Redis
        try:
            self.redis_client.set(key, json_value)
        except Exception:
            pass  # Redis unavailable, skip

        # Write to SQLite (INSERT OR REPLACE) - use circuit-specific table
        self._ensure_table(circuit)
        table_name = self._get_table_name(circuit)
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT OR REPLACE INTO {table_name} (key, value) VALUES (?, ?)",
            (key, json_value),
        )
        conn.commit()
        conn.close()

        self.stats["set_count"] += 1

    def get_with_lock(
        self, circuit: str, params: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[Lock]]:
        """
        Get cached result with distributed lock.

        Returns:
            Tuple of (cached_value, lock). If cache hit, lock is None.
            If cache miss, returns (None, lock) where lock must be released after simulation.
        """
        # Try to get from cache first
        cached = self.get(circuit, params)
        if cached is not None:
            return cached, None

        # Cache miss: acquire distributed lock (requires Redis)
        try:
            key = self._generate_key(circuit, params)
            lock = self._get_lock(key)

            # Actually acquire the lock (blocking with timeout)
            acquired = lock.acquire(
                blocking=True, blocking_timeout=self.lock_blocking_timeout
            )
            if not acquired:
                # Failed to acquire lock, return None (caller should handle)
                return None, None

            # Try cache again after acquiring lock (another worker might have written it)
            # Don't count stats for the second check to avoid double counting
            cached = self.get(circuit, params, count_stats=False)
            if cached is not None:
                # Cache hit after acquiring lock: release lock and return
                try:
                    lock.release()
                except Exception:
                    pass
                return cached, None
        except Exception:
            # Redis unavailable for locking, proceed without lock
            return None, None

        # Still miss: return lock for caller to hold during simulation
        return None, lock

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_info = self.redis_client.info("memory")
            redis_memory = redis_info.get("used_memory_human", "N/A")
            redis_key_count = self.redis_client.dbsize()
        except Exception:
            redis_memory = "N/A"
            redis_key_count = 0

        return {
            **self.stats,
            "redis_memory": redis_memory,
            "redis_key_count": redis_key_count,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        self.stats = {
            "redis_hit": 0,
            "redis_miss": 0,
            "sqlite_hit": 0,
            "sqlite_miss": 0,
            "set_count": 0,
        }
