from fastapi import APIRouter, Depends, Body, HTTPException
from datetime import datetime
from app.auth import get_current_user, get_supabase_client
from pydantic import BaseModel
from typing import Dict

router = APIRouter()

class APNsTokenRequest(BaseModel):
    apns_token: str

@router.post("/user/apns-token")
async def update_apns_token(
    request: Dict = Body(...),
    current_user = Depends(get_current_user)
):
    supabase = get_supabase_client()
    
    apns_token = request.get("apns_token")
    if not apns_token:
        return {"success": False, "error": "apns_token required"}
    
    supabase.table("user_devices").upsert({
        "user_id": current_user.id,
        "apns_token": apns_token,
        "platform": "ios",
        "updated_at": datetime.utcnow().isoformat()
    }, on_conflict="user_id").execute()
    
    return {"success": True}

@router.delete("/user/account")
async def delete_account(current_user = Depends(get_current_user)):
    supabase = get_supabase_client()
    
    try:
        # Get all goal IDs for this user first
        goals_response = supabase.table("goals")\
            .select("id")\
            .eq("user_id", current_user.id)\
            .execute()
        
        goal_ids = [goal['id'] for goal in goals_response.data]
        
        if goal_ids:
            # Delete generated posts for these goals
            supabase.table("generated_posts")\
                .delete()\
                .in_("goal_id", goal_ids)\
                .execute()
            
            # Delete goal_social_selections
            supabase.table("goal_social_selections")\
                .delete()\
                .in_("goal_id", goal_ids)\
                .execute()
        
        # Delete goals
        supabase.table("goals")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # Delete social accounts
        supabase.table("social_accounts")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # Delete device tokens
        supabase.table("user_devices")\
            .delete()\
            .eq("user_id", current_user.id)\
            .execute()
        
        # Delete user from auth
        supabase.auth.admin.delete_user(current_user.id)
        
        return {"success": True, "message": "Account deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting account: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

# Keep old endpoint for backwards compatibility during transition
@router.post("/user/fcm-token")
async def update_fcm_token(
    fcm_token: str,
    current_user = Depends(get_current_user)
):
    # Legacy endpoint - does nothing now
    return {"success": True, "message": "FCM deprecated, use APNs"}