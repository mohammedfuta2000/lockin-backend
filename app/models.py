from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Platform(str, Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    LINKEDIN = "linkedin"

class SocialAccount(BaseModel):
    id: str
    user_id: str
    platform: Platform
    platform_user_id: str
    username: str
    connected_at: datetime
    
class SocialAccountCreate(BaseModel):
    platform: Platform
    platform_user_id: str
    username: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None