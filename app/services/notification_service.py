import httpx
import jwt
import time
import base64
import os

# APNs configuration
APNS_KEY_ID = os.getenv("APNS_KEY_ID")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")
APNS_KEY_BASE64 = os.getenv("APNS_KEY_BASE64")
APNS_BUNDLE_ID = "cloud.lockin.app"

def generate_apns_token():
    """Generate JWT token for APNs authentication"""
    if not APNS_KEY_BASE64:
        raise ValueError("APNS_KEY_BASE64 environment variable not set")
    
    # Decode base64 key
    signing_key = base64.b64decode(APNS_KEY_BASE64).decode('utf-8')
    
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
    Automatically tries production first, falls back to sandbox if BadDeviceToken
    """
    # Try production first (for App Store/TestFlight users)
    success = await _send_to_apns(
        apns_token, 
        goal_title, 
        goal_id, 
        preview_text,
        server="api.push.apple.com"
    )
    
    if not success:
        # If production fails with BadDeviceToken, try sandbox (for development)
        print("Production failed, trying sandbox APNs...")
        success = await _send_to_apns(
            apns_token,
            goal_title,
            goal_id,
            preview_text,
            server="api.sandbox.push.apple.com"
        )
    
    return success

async def _send_to_apns(apns_token: str, goal_title: str, goal_id: str, preview_text: str, server: str):
    """
    Internal function to send to specific APNs server
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
        url = f"https://{server}/3/device/{apns_token}"
        
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
                print(f"Successfully sent notification via {server} to {apns_token[:20]}...")
                return True
            elif response.status_code == 400:
                error_data = response.json()
                if error_data.get("reason") == "BadDeviceToken":
                    print(f"BadDeviceToken on {server}, token may be for other environment")
                    return False
                else:
                    print(f"Failed to send notification on {server}: {response.status_code} - {response.text}")
                    return False
            else:
                print(f"Failed to send notification on {server}: {response.status_code} - {response.text}")
                return False
    
    except Exception as e:
        print(f"Error sending APNs notification to {server}: {e}")
        return False