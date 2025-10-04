from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.auth import get_current_user, get_supabase_client
from app.models import SocialAccount

router = APIRouter()

@router.get("/accounts", response_model=List[SocialAccount])
async def get_social_accounts(current_user = Depends(get_current_user)):
    """
    Get all connected social accounts for the current user
    """
    supabase = get_supabase_client()
    
    try:
        response = supabase.table("social_accounts")\
            .select("id, user_id, platform, platform_user_id, username, connected_at")\
            .eq("user_id", current_user.id)\
            .execute()
        
        return response.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch social accounts: {str(e)}")

@router.delete("/accounts/{platform}")
async def disconnect_social_account(
    platform: str,
    current_user = Depends(get_current_user)
):
    """
    Disconnect a social account
    """
    supabase = get_supabase_client()
    
    try:
        # Delete the social account
        response = supabase.table("social_accounts")\
            .delete()\
            .eq("user_id", current_user.id)\
            .eq("platform", platform)\
            .execute()
        
        return {"success": True, "message": f"{platform} disconnected successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect {platform}: {str(e)}")