"""Router exposing basic system endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/status")
async def get_status() -> dict[str, str]:
    """Return a minimal status payload."""
    return {"status": "online"}
