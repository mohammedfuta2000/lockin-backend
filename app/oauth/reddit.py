import httpx
import secrets
from datetime import datetime, timedelta
from config import get_settings
from app.auth import get_supabase_client, encrypt_token

settings = get_settings()
_state_storage = {}

def get_authorization_url(user_id: str) -> str:
    """
    Generate Reddit OAuth authorization URL
    """
    state = secrets.token_urlsafe(32)
    _state_storage[state] = user_id
    
    base_url = "https://www.reddit.com/api/v1/authorize"
    params = {
        "client_id": settings.reddit_client_id,
        "response_type": "code",
        "state": state,
        "redirect_uri": settings.reddit_redirect_uri,
        "duration": "permanent",
        "scope": "identity submit"
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"

async def handle_callback(code: str, user_id: str):
    """
    Exchange authorization code for access token
    """
    # Implementation similar to Twitter
    # We'll complete this in the detailed OAuth guide
    pass