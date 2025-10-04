import httpx
import secrets
from datetime import datetime, timedelta
from config import get_settings
from app.auth import get_supabase_client, encrypt_token

settings = get_settings()
_state_storage = {}

def get_authorization_url(user_id: str) -> str:
    """
    Generate LinkedIn OAuth authorization URL
    """
    state = secrets.token_urlsafe(32)
    _state_storage[state] = user_id
    
    base_url = "https://www.linkedin.com/oauth/v2/authorization"
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": "openid profile email w_member_social"
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"

async def handle_callback(code: str, state: str, user_id: str):
    """
    Exchange authorization code for access token
    """
    # Verify state
    if state not in _state_storage or _state_storage[state] != user_id:
        raise Exception("Invalid state")
    
    del _state_storage[state]
    
    supabase = get_supabase_client()
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if token_response.status_code != 200:
            raise Exception(f"Token exchange failed: {token_response.text}")
        
        token_data = token_response.json()
    
    # Get user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        
        if user_response.status_code != 200:
            raise Exception(f"Failed to get user info: {user_response.text}")
        
        linkedin_user = user_response.json()
    
    # Encrypt tokens
    encrypted_access_token = encrypt_token(token_data["access_token"])
    encrypted_refresh_token = encrypt_token(token_data.get("refresh_token", ""))
    
    # LinkedIn tokens expire in 60 days
    expires_in = token_data.get("expires_in", 5184000)
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    social_account_data = {
        "user_id": user_id,
        "platform": "linkedin",
        "platform_user_id": linkedin_user["sub"],
        "username": linkedin_user.get("name", linkedin_user.get("email", "Unknown")),
        "access_token_encrypted": encrypted_access_token,
        "refresh_token_encrypted": encrypted_refresh_token,
        "token_expires_at": token_expires_at.isoformat(),
    }
    
    response = supabase.table("social_accounts")\
        .upsert(social_account_data, on_conflict="user_id,platform")\
        .execute()
    
    return response.data[0] if response.data else None