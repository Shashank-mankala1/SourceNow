from fastapi import APIRouter


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health():
    return {"ok": True, "service": "civicsense", "version": "0.1.0"}