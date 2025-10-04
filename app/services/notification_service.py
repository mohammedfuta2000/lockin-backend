import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
import base64

# Initialize Firebase from environment variable
if os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'):
    # Railway/Production
    firebase_json = base64.b64decode(os.getenv('FIREBASE_SERVICE_ACCOUNT_BASE64'))
    firebase_dict = json.loads(firebase_json)
    cred = credentials.Certificate(firebase_dict)
else:
    # Local development
    cred_path = os.path.join(os.path.dirname(__file__), '../../firebase-service-account.json')
    cred = credentials.Certificate(cred_path)

firebase_admin.initialize_app(cred)

async def send_goal_notification(user_fcm_token: str, goal_title: str, goal_id: str, preview_text: str):
    """
    Send push notification for goal deadline
    """
    message = messaging.Message(
        notification=messaging.Notification(
            title=f'Goal deadline in 2 hours',
            body=goal_title,
        ),
        data={
            'goal_id': goal_id,
            'preview': preview_text,
            'type': 'goal_deadline'
        },
        token=user_fcm_token,
    )
    
    try:
        response = messaging.send(message)
        print(f"Successfully sent notification: {response}")
        return True
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return False