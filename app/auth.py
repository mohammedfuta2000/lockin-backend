from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from config import get_settings

settings = get_settings()
security = HTTPBearer()

# Initialize Supabase client
supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verify JWT token from Supabase and return user
    """
    token = credentials.credentials
    
    try:
        # Verify token with Supabase
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        return user_response.user
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {str(e)}")

def get_supabase_client() -> Client:
    """
    Get Supabase client for database operations
    """
    return supabase

from cryptography.fernet import Fernet

def get_cipher():
    """Get Fernet cipher for encryption/decryption"""
    return Fernet(settings.encryption_key.encode())

def encrypt_token(token: str) -> str:
    """Encrypt OAuth token"""
    cipher = get_cipher()
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt OAuth token"""
    cipher = get_cipher()
    return cipher.decrypt(encrypted_token.encode()).decode()