from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/")
async def auth_root():
    return {"message": "Authentication endpoints - To be implemented"}