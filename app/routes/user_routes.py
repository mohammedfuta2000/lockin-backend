from fastapi import APIRouter, Depends, HTTPException
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

@router.delete("/user/account")
async def delete_account(current_user = Depends(get_current_user)):
    supabase = get_supabase_client()
    
    try:
        # Delete in order due to foreign key constraints
        
        # 1. Delete generated posts (references goals)
        supabase.table("generated_posts")\
            .delete()\
            .in_("goal_id", 
                supabase.table("goals")
                    .select("id")
                    .eq("user_id", current_user.id)
                    .execute().data
            )\
            .execute()
        
        # 2. Delete goal_social_selections
        supabase.table("goal_social_selections")\
            .delete()\
            .in_("goal_id",
                supabase.table("goals")
                    .select("id")
                    .eq("user_id", current_user.id)
                    .execute().data
            )\
            .execute()
        
        # 3. Delete goals
        supabase.table("goals")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # 4. Delete social accounts
        supabase.table("social_accounts")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # 5. Delete device tokens
        supabase.table("user_devices")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # 6. Delete user from auth (admin API)
        supabase.auth.admin.delete_user(current_user.id)
        
        return {"success": True, "message": "Account deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")