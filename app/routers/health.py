"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """Returns service health status."""
    return {"status": "ok"}
