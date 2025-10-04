import httpx
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict
from config import get_settings
from app.auth import get_supabase_client, encrypt_token

settings = get_settings()

# In-memory storage for PKCE challenges (use Redis in production)
_pkce_storage: Dict[str, Dict[str, str]] = {}
_state_storage: Dict[str, str] = {}

def generate_code_verifier() -> str:
    """Generate a random code verifier for PKCE"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

def generate_code_challenge(verifier: str) -> str:
    """Generate code challenge from verifier"""
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

def get_authorization_url(user_id: str) -> str:
    """
    Generate Twitter OAuth 2.0 authorization URL with PKCE
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _state_storage[state] = user_id
    
    # Generate PKCE parameters
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Store verifier for later use in callback
    _pkce_storage[state] = {
        'verifier': code_verifier,
        'user_id': user_id
    }
    
    # Build authorization URL
    base_url = "https://twitter.com/i/oauth2/authorize"
    params = {
        "response_type": "code",
        "client_id": settings.twitter_client_id,
        "redirect_uri": settings.twitter_redirect_uri,
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"

async def handle_callback(code: str, state: str, user_id: str):
    """
    Exchange authorization code for access token and store in database
    """
    # Verify state
    if state not in _state_storage or _state_storage[state] != user_id:
        raise Exception("Invalid state - possible CSRF attack")
    
    # Get PKCE verifier
    if state not in _pkce_storage:
        raise Exception("PKCE verifier not found")
    
    pkce_data = _pkce_storage[state]
    code_verifier = pkce_data['verifier']
    
    # Clean up used state and verifier
    del _state_storage[state]
    del _pkce_storage[state]
    
    supabase = get_supabase_client()
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": settings.twitter_client_id,
                "redirect_uri": settings.twitter_redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            auth=(settings.twitter_client_id, settings.twitter_client_secret)
        )
        
        if token_response.status_code != 200:
            raise Exception(f"Token exchange failed: {token_response.text}")
        
        token_data = token_response.json()
    
    # Get user info from Twitter
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={
                "Authorization": f"Bearer {token_data['access_token']}"
            }
        )
        
        if user_response.status_code != 200:
            raise Exception(f"Failed to get Twitter user info: {user_response.text}")
        
        twitter_user = user_response.json()["data"]
    
    # Encrypt tokens
    encrypted_access_token = encrypt_token(token_data["access_token"])
    encrypted_refresh_token = encrypt_token(token_data.get("refresh_token", ""))
    
    # Calculate token expiry (Twitter tokens expire in 2 hours)
    expires_in = token_data.get("expires_in", 7200)
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Prepare data for database
    social_account_data = {
        "user_id": user_id,
        "platform": "twitter",
        "platform_user_id": twitter_user["id"],
        "username": twitter_user["username"],
        "access_token_encrypted": encrypted_access_token,
        "refresh_token_encrypted": encrypted_refresh_token,
        "token_expires_at": token_expires_at.isoformat(),
    }
    
    # Upsert (insert or update if exists)
    response = supabase.table("social_accounts")\
        .upsert(social_account_data, on_conflict="user_id,platform")\
        .execute()
    
    return response.data[0] if response.data else None

async def refresh_access_token(refresh_token_encrypted: str) -> Dict[str, any]:
    """
    Refresh Twitter access token using refresh token
    """
    from app.auth import decrypt_token
    
    refresh_token = decrypt_token(refresh_token_encrypted)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "client_id": settings.twitter_client_id,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            auth=(settings.twitter_client_id, settings.twitter_client_secret)
        )
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        token_data = response.json()
    
    # Return new encrypted tokens
    return {
        "access_token_encrypted": encrypt_token(token_data["access_token"]),
        "refresh_token_encrypted": encrypt_token(token_data.get("refresh_token", refresh_token)),
        "expires_in": token_data.get("expires_in", 7200)
    }