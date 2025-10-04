from fastapi import APIRouter, Depends
from datetime import datetime
from app.auth import get_current_user, get_supabase_client

router = APIRouter()

@router.post("/user/fcm-token")
async def update_fcm_token(
    fcm_token: str,
    current_user = Depends(get_current_user)
):
    supabase = get_supabase_client()
    
    supabase.table("user_devices").upsert({
        "user_id": current_user.id,
        "fcm_token": fcm_token,
        "updated_at": datetime.utcnow().isoformat()
    }, on_conflict="user_id").execute()
    
    return {"success": True}