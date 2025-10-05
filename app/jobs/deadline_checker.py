import asyncio
from datetime import datetime, timedelta
from app.auth import get_supabase_client
from app.services.notification_service import send_goal_notification

async def check_deadlines():
    """
    Check for goals hitting 2-hour deadline and send notifications
    """
    supabase = get_supabase_client()
    
    # Calculate time window (2 hours from now, +/- 1 minute)
    now = datetime.utcnow()
    target_time = now + timedelta(hours=2)
    window_start = target_time - timedelta(minutes=1)
    window_end = target_time + timedelta(minutes=1)
    
    # Find goals in the window that haven't been notified
    goals_response = supabase.table("goals")\
        .select("*")\
        .eq("completed", False)\
        .eq("notification_sent", False)\
        .gte("deadline", window_start.isoformat())\
        .lte("deadline", window_end.isoformat())\
        .execute()
    
    goals = goals_response.data
    
    print(f"Found {len(goals)} goals hitting deadline in 2 hours")
    
    for goal in goals:
        # Get user's APNs token
        device_response = supabase.table("user_devices")\
            .select("apns_token")\
            .eq("user_id", goal["user_id"])\
            .single()\
            .execute()
        
        if not device_response.data or not device_response.data.get("apns_token"):
            print(f"No APNs token for user {goal['user_id']}, skipping")
            continue
        
        apns_token = device_response.data["apns_token"]
        
        # Get first generated post for preview
        posts_response = supabase.table("generated_posts")\
            .select("content, edited_content")\
            .eq("goal_id", goal["id"])\
            .limit(1)\
            .execute()
        
        preview = ""
        if posts_response.data:
            post = posts_response.data[0]
            preview = (post["edited_content"] or post["content"])[:100]
        
        # Send notification
        success = await send_goal_notification(
            apns_token,
            goal["title"],
            goal["id"],
            preview
        )
        
        if success:
            # Mark as notified
            supabase.table("goals")\
                .update({"notification_sent": True})\
                .eq("id", goal["id"])\
                .execute()

async def run_scheduler():
    """
    Run deadline checker every minute
    """
    print("Scheduler running, checking deadlines every minute...")
    while True:
        try:
            await check_deadlines()
        except Exception as e:
            print(f"Error in deadline checker: {e}")
        
        # Wait 1 minute
        await asyncio.sleep(60)