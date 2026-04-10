from functools import lru_cache
from typing import Annotated, Optional
from fastapi import Depends
import logging

# directly use sim_api.py
from ..sim_api import SimulationAPI
from ..cache import CacheManager

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_cache_manager() -> Optional[CacheManager]:
    """Get or create CacheManager instance. Returns None if Redis is unavailable."""
    try:
        cm = CacheManager()
        cm.redis_client.ping()
        return cm
    except Exception as e:
        logger.warning("Redis unavailable, cache disabled: %s", e)
        return None


@lru_cache(maxsize=1)
def get_sim_api() -> SimulationAPI:
    """Get or create SimulationAPI instance, with or without cache."""
    cache_manager = get_cache_manager()
    return SimulationAPI(cache_manager=cache_manager)


SimAPIType = Annotated[SimulationAPI, Depends(get_sim_api)]
CacheManagerType = Annotated[CacheManager, Depends(get_cache_manager)]
