from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str
    
    # Encryption
    encryption_key: str
    
    # OAuth - Twitter
    twitter_client_id: str = ""
    twitter_client_secret: str = ""
    twitter_redirect_uri: str = ""
    
    # OAuth - Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_redirect_uri: str = ""
    
    # OAuth - LinkedIn
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = ""
    
    # App
    frontend_url: str = "lockin://oauth/callback"  # Flutter deep link
    
    # OpenAI
    openai_api_key: str = ""
    
    # Railway auto-detects PORT, default to 8000 for local dev
    port: int = int(os.getenv("PORT", "8000"))
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()