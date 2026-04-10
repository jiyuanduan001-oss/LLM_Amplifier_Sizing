import asyncio
import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException
from ..schemas import SimRequest, SimResponse
from ..deps import SimAPIType, CacheManagerType
from ...sim_api import SimulationAPI
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulate", tags=["simulate"])


def _detail_500(message: str, exc: Exception = None) -> dict:
    """Build 500 detail with type and full traceback for debugging."""
    detail = {"message": message}
    if exc is not None:
        detail["exception_type"] = type(exc).__name__
        detail["exception_message"] = str(exc)
        detail["traceback"] = traceback.format_exc()
    return detail


@router.post("/", response_model=SimResponse, summary="Run one simulation (sync)")
async def run_simulation(
    req: SimRequest, api: SimAPIType, cache_manager: CacheManagerType
):
    """
    Call SimulationAPI.run(params=...) and return the result.
    Use asyncio.to_thread to execute the synchronous function in the thread pool, avoid blocking.
    """
    # if request set new base_config_path (new circuit), create new SimulationAPI instance, otherwise use the cached instance
    sim_api = api
    if (
        req.base_config_path is not None
        or req.output_dir is not None
        or req.spec_list is not None
    ):
        sim_api = SimulationAPI(
            base_config_path=(
                Path(req.base_config_path) if req.base_config_path else None
            ),
            output_dir=Path(req.output_dir) if req.output_dir else None,
            spec_list=req.spec_list if req.spec_list else None,
            cache_manager=cache_manager,
        )
    try:
        result = await asyncio.to_thread(sim_api.run, params=req.params)
    except Exception as e:
        logger.exception("Simulation failed (500)")
        raise HTTPException(
            status_code=500,
            detail=_detail_500(f"Simulation failed: {e}", e),
        )

    # Expect  api.run to return dict, containing "specs" and "op_region"
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=500,
            detail={
                "message": "SimulationAPI.run returned unexpected format",
                "got_type": type(result).__name__,
                "expected": "dict with keys 'specs' and 'op_region'",
            },
        )
    if "specs" not in result or "op_region" not in result:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "SimulationAPI.run returned unexpected format",
                "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                "expected": "dict with keys 'specs' and 'op_region'",
            },
        )

    return SimResponse(
        specs=result["specs"], op_region=result["op_region"], logs=result.get("logs")
    )


# (Optional) Async submit task interface skeleton, can be enabled in the future by connecting Celery/Queue
@router.post(
    "/submit",
    summary="Submit simulation task (placeholder, for future connection to Celery/Queue)",
)
async def submit_simulation(req: SimRequest):
    # TODO: connect Celery/RQ/Huey etc., put task into queue; return job_id
    return {"status": "queued", "job_id": "placeholder"}


@router.get("/cache_stats", summary="Get cache statistics")
async def get_cache_stats(cache_manager: CacheManagerType):
    """Get cache statistics including hit/miss rates and Redis memory usage."""
    return cache_manager.get_stats()


@router.post("/cache_stats/reset", summary="Reset cache statistics")
async def reset_cache_stats(cache_manager: CacheManagerType):
    """Reset all cache statistics to zero."""
    cache_manager.reset_stats()
    return {"status": "success", "message": "Cache statistics reset"}
