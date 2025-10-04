from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user, get_supabase_client
from app.oauth import linkedin, twitter
from app.models import OAuthCallbackRequest

router = APIRouter()

# Twitter OAuth
@router.get("/twitter/connect")
async def twitter_connect(current_user = Depends(get_current_user)):
    """
    Get Twitter OAuth authorization URL
    """
    try:
        auth_url = twitter.get_authorization_url(current_user.id)
        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate Twitter OAuth: {str(e)}")

@router.get("/twitter/callback")
async def twitter_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Handle Twitter OAuth callback
    Note: This endpoint is called by Twitter's redirect, not directly by Flutter
    """
    try:
        # We can't verify JWT here since Twitter redirects to this endpoint
        # Instead, we'll use the state to get user_id
        # The state was stored in twitter.get_authorization_url()
        
        # For now, return success HTML that will trigger deep link
        html_content = f"""
        <html>
            <head>
                <title>Connecting Twitter...</title>
            </head>
            <body>
                <h2>Authorization successful!</h2>
                <p>Redirecting back to app...</p>
                <script>
                    // Trigger deep link
                    window.location.href = 'lockin://oauth/callback?code={code}&state={state}&platform=twitter';
                    
                    // Fallback message after 2 seconds
                    setTimeout(function() {{
                        document.body.innerHTML = '<h3>Please return to the app</h3><p>If the app did not open automatically, please open it manually.</p>';
                    }}, 2000);
                </script>
            </body>
        </html>
        """
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twitter OAuth callback failed: {str(e)}")

@router.post("/twitter/complete")
async def twitter_complete(
    code: str,
    state: str,
    current_user = Depends(get_current_user)
):
    """
    Complete Twitter OAuth flow
    Called by Flutter after receiving deep link
    """
    try:
        social_account = await twitter.handle_callback(
            code=code,
            state=state,
            user_id=current_user.id
        )
        return {"success": True, "account": social_account}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twitter OAuth completion failed: {str(e)}")
    

# LinkedIn OAuth
@router.get("/linkedin/connect")
async def linkedin_connect(current_user = Depends(get_current_user)):
    """
    Get LinkedIn OAuth authorization URL
    """
    try:
        auth_url = linkedin.get_authorization_url(current_user.id)
        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate LinkedIn OAuth: {str(e)}")

@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Handle LinkedIn OAuth callback
    """
    try:
        html_content = f"""
        <html>
            <head><title>Connecting LinkedIn...</title></head>
            <body>
                <h2>Authorization successful!</h2>
                <p>Redirecting back to app...</p>
                <script>
                    window.location.href = 'lockin://oauth/callback?code={code}&state={state}&platform=linkedin';
                    setTimeout(function() {{
                        document.body.innerHTML = '<h3>Please return to the app</h3>';
                    }}, 2000);
                </script>
            </body>
        </html>
        """
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LinkedIn OAuth callback failed: {str(e)}")

@router.post("/linkedin/complete")
async def linkedin_complete(
    code: str,
    state: str,
    current_user = Depends(get_current_user)
):
    """
    Complete LinkedIn OAuth flow
    """
    try:
        social_account = await linkedin.handle_callback(
            code=code,
            state=state,
            user_id=current_user.id
        )
        return {"success": True, "account": social_account}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LinkedIn completion failed: {str(e)}")
    
    
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