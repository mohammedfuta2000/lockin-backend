import asyncio
from datetime import datetime, timedelta
import httpx
from app.auth import get_supabase_client, decrypt_token
from app.oauth.token_refresh import refresh_twitter_token

async def post_to_platform(post, account):
    """
    Post content to a specific platform
    Returns (success: bool, error_message: str or None)
    """
    platform = account['platform']
    content = post['edited_content'] or post['content']
    
    try:
        if platform == 'twitter':
            access_token = decrypt_token(account['access_token_encrypted'])
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.twitter.com/2/tweets",
                    json={"text": content},
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                # Handle token expiry
                if response.status_code == 401:
                    print(f"Twitter token expired, refreshing...")
                    access_token = await refresh_twitter_token(account['id'])
                    
                    response = await client.post(
                        "https://api.twitter.com/2/tweets",
                        json={"text": content},
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                
                if response.status_code == 201:
                    return True, None
                else:
                    return False, f"Status {response.status_code}: {response.text}"
        
        elif platform == 'linkedin':
            access_token = decrypt_token(account['access_token_encrypted'])
            
            async with httpx.AsyncClient() as client:
                linkedin_payload = {
                    "author": f"urn:li:person:{account['platform_user_id']}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": content},
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
                }
                
                response = await client.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    json=linkedin_payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Restli-Protocol-Version": "2.0.0",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in [200, 201]:
                    return True, None
                else:
                    return False, f"Status {response.status_code}: {response.text}"
        
        else:
            return False, f"Unsupported platform: {platform}"
    
    except Exception as e:
        return False, str(e)

async def auto_post_expired_goals():
    """
    Find goals past deadline and auto-post them
    """
    supabase = get_supabase_client()
    
    # Find goals past deadline that haven't been completed
    now = datetime.utcnow()
    
    goals_response = supabase.table("goals")\
        .select("*")\
        .eq("completed", False)\
        .lte("deadline", now.isoformat())\
        .execute()
    
    goals = goals_response.data
    
    if not goals:
        return
    
    print(f"🤖 Found {len(goals)} expired goals to auto-post")
    
    for goal in goals:
        print(f"📝 Auto-posting goal: {goal['title']} (ID: {goal['id']})")
        
        # Get all posts for this goal
        posts_response = supabase.table("generated_posts")\
            .select("*, social_accounts(*)")\
            .eq("goal_id", goal["id"])\
            .execute()
        
        posts = posts_response.data
        
        if not posts:
            print(f"⚠️  No posts found for goal {goal['id']}, marking as completed anyway")
            supabase.table("goals")\
                .update({
                    "completed": True,
                    "completed_at": now.isoformat()
                })\
                .eq("id", goal["id"])\
                .execute()
            continue
        
        # Track results
        all_success = True
        results = []
        
        for post in posts:
            # Skip if already posted
            if post.get('posted_at'):
                print(f"  ℹ️  Post {post['id']} already posted, skipping")
                continue
            
            account = post['social_accounts']
            platform = account['platform']
            
            success, error = await post_to_platform(post, account)
            
            if success:
                print(f"  ✅ Posted to {platform}")
                # Mark post as posted
                supabase.table("generated_posts")\
                    .update({"posted_at": now.isoformat()})\
                    .eq("id", post['id'])\
                    .execute()
                results.append({"platform": platform, "success": True})
            else:
                print(f"  ❌ Failed to post to {platform}: {error}")
                all_success = False
                results.append({"platform": platform, "success": False, "error": error})
        
        # Mark goal as completed regardless of posting success
        # (This is the "lockin" - deadline means completion, no exceptions)
        supabase.table("goals")\
            .update({
                "completed": True,
                "completed_at": now.isoformat()
            })\
            .eq("id", goal["id"])\
            .execute()
        
        status = "✅ fully posted" if all_success else "⚠️  partially posted"
        print(f"  Goal {goal['id']} marked as completed ({status})")

async def run_auto_poster():
    """
    Run auto-poster every minute
    """
    print("🚀 Auto-poster started, checking every minute...")
    while True:
        try:
            await auto_post_expired_goals()
        except Exception as e:
            print(f"❌ Error in auto-poster: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait 1 minute
        await asyncio.sleep(60)
