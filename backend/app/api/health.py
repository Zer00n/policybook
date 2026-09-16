from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "policybook",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
