import httpx
from datetime import datetime
from app.auth import get_supabase_client, decrypt_token, encrypt_token
from config import get_settings

settings = get_settings()

async def refresh_twitter_token(social_account_id: str):
    """
    Refresh Twitter access token using refresh token
    """
    supabase = get_supabase_client()
    
    # Get account
    account_response = supabase.table("social_accounts")\
        .select("*")\
        .eq("id", social_account_id)\
        .single()\
        .execute()
    
    account = account_response.data
    refresh_token = decrypt_token(account['refresh_token_encrypted'])
    
    # Refresh token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "client_id": settings.twitter_client_id,
            },
            auth=(settings.twitter_client_id, settings.twitter_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        token_data = response.json()
    
    # Update tokens in database
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 7200))
    
    supabase.table("social_accounts")\
        .update({
            "access_token_encrypted": encrypt_token(token_data['access_token']),
            "refresh_token_encrypted": encrypt_token(token_data.get('refresh_token', refresh_token)),
            "token_expires_at": expires_at.isoformat()
        })\
        .eq("id", social_account_id)\
        .execute()
    
    return token_data['access_token']