from fastapi import APIRouter, Depends
from datetime import datetime
from app.auth import get_current_user, get_supabase_client
from pydantic import BaseModel

router = APIRouter()

class APNsTokenRequest(BaseModel):
    apns_token: str

@router.post("/user/apns-token")
async def update_apns_token(
    request: APNsTokenRequest,
    current_user = Depends(get_current_user)
):
    supabase = get_supabase_client()
    
    supabase.table("user_devices").upsert({
        "user_id": current_user.id,
        "apns_token": request.apns_token,
        "platform": "ios",
        "updated_at": datetime.utcnow().isoformat()
    }, on_conflict="user_id").execute()
    
    return {"success": True}

# Keep old endpoint for backwards compatibility during transition
@router.post("/user/fcm-token")
async def update_fcm_token(
    fcm_token: str,
    current_user = Depends(get_current_user)
):
    # Legacy endpoint - does nothing now
    return {"success": True, "message": "FCM deprecated, use APNs"}