import httpx
import jwt
import time
from datetime import datetime, timedelta
import os

# APNs configuration
APNS_KEY_ID = os.getenv("APNS_KEY_ID")  # From Apple Developer Portal
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")  # Your Apple Team ID
APNS_KEY_PATH = os.getenv("APNS_KEY_PATH", "AuthKey.p8")  # Path to your .p8 file
APNS_BUNDLE_ID = "cloud.lockin.app"

# APNs endpoint (use sandbox for development, production for release)
APNS_SERVER = "api.push.apple.com"  # Production
# APNS_SERVER = "api.sandbox.push.apple.com"  # Development/TestFlight

def generate_apns_token():
    """Generate JWT token for APNs authentication"""
    with open(APNS_KEY_PATH, 'r') as f:
        signing_key = f.read()
    
    headers = {
        "alg": "ES256",
        "kid": APNS_KEY_ID
    }
    
    payload = {
        "iss": APNS_TEAM_ID,
        "iat": int(time.time())
    }
    
    token = jwt.encode(payload, signing_key, algorithm="ES256", headers=headers)
    return token

async def send_goal_notification(apns_token: str, goal_title: str, goal_id: str, preview_text: str):
    """
    Send push notification via APNs
    """
    try:
        # Generate JWT auth token
        auth_token = generate_apns_token()
        
        # Prepare notification payload
        payload = {
            "aps": {
                "alert": {
                    "title": "Goal deadline in 2 hours",
                    "body": goal_title,
                    "subtitle": preview_text[:100] if preview_text else ""
                },
                "sound": "default",
                "badge": 1,
                "mutable-content": 1,
                "category": "GOAL_DEADLINE"
            },
            "goal_id": goal_id,
            "type": "goal_deadline"
        }
        
        # APNs HTTP/2 endpoint
        url = f"https://{APNS_SERVER}/3/device/{apns_token}"
        
        headers = {
            "authorization": f"bearer {auth_token}",
            "apns-topic": APNS_BUNDLE_ID,
            "apns-priority": "10",
            "apns-push-type": "alert"
        }
        
        async with httpx.AsyncClient(http2=True) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"Successfully sent notification to {apns_token[:20]}...")
                return True
            else:
                print(f"Failed to send notification: {response.status_code} - {response.text}")
                return False
    
    except Exception as e:
        print(f"Error sending APNs notification: {e}")
        return False