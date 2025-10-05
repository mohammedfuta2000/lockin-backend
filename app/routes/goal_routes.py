import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import List
from datetime import datetime, timedelta

import httpx
from app.auth import get_current_user, get_supabase_client
from pydantic import BaseModel
from openai import OpenAI
from config import get_settings
from app.auth import decrypt_token

settings = get_settings()
router = APIRouter()

# Use settings instead of os.getenv
client = OpenAI(api_key=settings.openai_api_key)

class GoalCreate(BaseModel):
    title: str
    description: str
    deadline: datetime
    selected_social_account_ids: List[str]

class Goal(BaseModel):
    id: str
    title: str
    description: str
    deadline: datetime
    completed: bool
    created_at: datetime

async def generate_posts_background(goal_id: str, user_id: str):
    """
    Background task to generate AI posts after goal creation
    """
    supabase = get_supabase_client()
    
    try:
        # Get goal with social selections
        goal_response = supabase.table("goals")\
            .select("*, goal_social_selections(social_accounts(id, platform, username))")\
            .eq("id", goal_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        goal = goal_response.data
        
        # Generate posts for each platform
        for selection in goal['goal_social_selections']:
            account = selection['social_accounts']
            platform = account['platform']
            
            # Generate with AI
            prompt = f"""Generate a celebratory social media post for {platform} announcing completion of this goal:

Title: {goal['title']}
Description: {goal['description']}

Requirements for {platform}:
- Authentic and personal tone
- 1-3 sentences
- Include relevant emoji
- No generic corporate speak
{"- Keep under 280 characters" if platform == "twitter" else ""}
"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            
            content = response.choices[0].message.content
            
            # Store in database
            supabase.table("generated_posts").insert({
                "goal_id": goal_id,
                "social_account_id": account['id'],
                "content": content,
            }).execute()
        
        print(f"Successfully generated posts for goal {goal_id}")
    
    except Exception as e:
        print(f"Failed to generate posts for goal {goal_id}: {e}")

@router.post("/goals")
async def create_goal(
    goal_data: GoalCreate,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    supabase = get_supabase_client()
    
    # Insert goal
    goal_response = supabase.table("goals").insert({
        "user_id": current_user.id,
        "title": goal_data.title,
        "description": goal_data.description,
        "deadline": goal_data.deadline.isoformat(),
    }).execute()
    
    goal = goal_response.data[0]
    
    # Link selected social accounts
    selections = [
        {"goal_id": goal["id"], "social_account_id": acc_id}
        for acc_id in goal_data.selected_social_account_ids
    ]
    
    supabase.table("goal_social_selections").insert(selections).execute()
    
    # Queue background task to generate posts
    background_tasks.add_task(generate_posts_background, goal["id"], current_user.id)
    
    return {"success": True, "goal": goal}

@router.get("/goals")
async def get_goals(current_user = Depends(get_current_user)):
    supabase = get_supabase_client()
    
    # Get goals
    goals_response = supabase.table("goals")\
        .select("*")\
        .eq("user_id", current_user.id)\
        .eq("completed", False)\
        .order("deadline")\
        .execute()
    
    goals = goals_response.data
    
    # For each goal, get its social selections
    for goal in goals:
        selections_response = supabase.table("goal_social_selections")\
            .select("*, social_accounts(platform, username)")\
            .eq("goal_id", goal["id"])\
            .execute()
        
        goal["goal_social_selections"] = selections_response.data
    
    return goals


@router.get("/goals/{goal_id}/posts")
async def get_goal_posts(
    goal_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get generated posts for a goal
    """
    supabase = get_supabase_client()
    
    # Verify goal belongs to user
    goal_response = supabase.table("goals")\
        .select("id")\
        .eq("id", goal_id)\
        .eq("user_id", current_user.id)\
        .single()\
        .execute()
    
    if not goal_response.data:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Get posts with social account info
    posts_response = supabase.table("generated_posts")\
        .select("*, social_accounts(platform, username)")\
        .eq("goal_id", goal_id)\
        .execute()
    
    return posts_response.data

@router.post("/goals/{goal_id}/generate-posts")
async def generate_posts(
    goal_id: str,
    current_user = Depends(get_current_user)
):
    supabase = get_supabase_client()
    
    # Get goal
    goal_response = supabase.table("goals")\
        .select("*, goal_social_selections(social_accounts(id, platform, username))")\
        .eq("id", goal_id)\
        .eq("user_id", current_user.id)\
        .single()\
        .execute()
    
    goal = goal_response.data
    
    # Generate posts for each platform
    generated = []
    for selection in goal['goal_social_selections']:
        account = selection['social_accounts']
        platform = account['platform']
        
        # Generate with AI
        prompt = f"""Generate a celebratory social media post for {platform} announcing completion of this goal:

Title: {goal['title']}
Description: {goal['description']}

Requirements for {platform}:
- Authentic and personal tone
- 1-3 sentences
- Include relevant emoji
- No generic corporate speak
{"- Keep under 280 characters" if platform == "twitter" else ""}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        content = response.choices[0].message.content
        
        # Store in database
        post_response = supabase.table("generated_posts").insert({
            "goal_id": goal_id,
            "social_account_id": account['id'],
            "content": content,
        }).execute()
        
        generated.append(post_response.data[0])
    
    return {"posts": generated}



@router.patch("/posts/{post_id}")
async def update_post(
    post_id: str,
    edited_content: str,
    current_user = Depends(get_current_user)
):
    """
    Update edited content of a generated post
    """
    supabase = get_supabase_client()
    
    # Verify post belongs to user's goal
    post_response = supabase.table("generated_posts")\
        .select("goal_id")\
        .eq("id", post_id)\
        .single()\
        .execute()
    
    if not post_response.data:
        raise HTTPException(status_code=404, detail="Post not found")
    
    goal_response = supabase.table("goals")\
        .select("id")\
        .eq("id", post_response.data["goal_id"])\
        .eq("user_id", current_user.id)\
        .single()\
        .execute()
    
    if not goal_response.data:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Update the post
    response = supabase.table("generated_posts")\
        .update({"edited_content": edited_content})\
        .eq("id", post_id)\
        .execute()
    
    return {"success": True, "post": response.data[0]}



from app.auth import decrypt_token
from app.oauth.token_refresh import refresh_twitter_token

@router.post("/goals/{goal_id}/post-now")
async def post_now(
    goal_id: str,
    current_user = Depends(get_current_user)
):
    """
    Post all generated posts for a goal and mark as completed
    """
    supabase = get_supabase_client()
    
    # Get goal and verify ownership
    goal_response = supabase.table("goals")\
        .select("id, title")\
        .eq("id", goal_id)\
        .eq("user_id", current_user.id)\
        .single()\
        .execute()
    
    if not goal_response.data:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Get all posts for this goal
    posts_response = supabase.table("generated_posts")\
        .select("*, social_accounts(*)")\
        .eq("goal_id", goal_id)\
        .execute()
    
    posts = posts_response.data
    results = []
    
    for post in posts:
        account = post['social_accounts']
        platform = account['platform']
        content = post['edited_content'] or post['content']
        
        print(f"DEBUG: Processing post for platform: {platform}")
        
        try:
            if platform == 'twitter':
                print(f"DEBUG: Decrypting Twitter token...")
                access_token = decrypt_token(account['access_token_encrypted'])
                print(f"DEBUG: Token decrypted, posting to Twitter...")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.twitter.com/2/tweets",
                        json={"text": content},
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    
                    print(f"DEBUG: Twitter response: {response.status_code}")
                    print(f"DEBUG: Twitter response body: {response.text}")
                    
                    # If 401, try refreshing token once
                    if response.status_code == 401:
                        print(f"Twitter 401, refreshing token...")
                        access_token = await refresh_twitter_token(account['id'])
                        
                        # Retry with new token
                        response = await client.post(
                            "https://api.twitter.com/2/tweets",
                            json={"text": content},
                            headers={"Authorization": f"Bearer {access_token}"}
                        )
                        print(f"DEBUG: Twitter retry response: {response.status_code}")
                        print(f"DEBUG: Twitter retry body: {response.text}")
                    
                    if response.status_code == 201:
                        results.append({"platform": platform, "success": True})
                        print(f"✓ Twitter post successful")
                    else:
                        print(f"✗ Twitter post failed: {response.status_code} - {response.text}")
                        results.append({"platform": platform, "success": False, "error": response.text})
            
            elif platform == 'linkedin':
                print(f"DEBUG: Posting to LinkedIn...")
                access_token = decrypt_token(account['access_token_encrypted'])
                print(f"DEBUG: LinkedIn token decrypted")
                
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
                    
                    print(f"DEBUG: LinkedIn payload: {linkedin_payload}")
                    
                    response = await client.post(
                        "https://api.linkedin.com/v2/ugcPosts",
                        json=linkedin_payload,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "X-Restli-Protocol-Version": "2.0.0",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    print(f"DEBUG: LinkedIn response status: {response.status_code}")
                    print(f"DEBUG: LinkedIn response body: {response.text}")
                    
                    if response.status_code in [200, 201]:
                        results.append({"platform": platform, "success": True})
                        print(f"✓ LinkedIn post successful")
                    else:
                        print(f"✗ LinkedIn post failed: {response.status_code} - {response.text}")
                        results.append({"platform": platform, "success": False, "error": response.text})
            
            # Mark post as posted
            supabase.table("generated_posts")\
                .update({"posted_at": datetime.utcnow().isoformat()})\
                .eq("id", post['id'])\
                .execute()
        
        except Exception as e:
            print(f"✗ Exception posting to {platform}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({"platform": platform, "success": False, "error": str(e)})
            
    # Mark goal as completed
    supabase.table("goals")\
        .update({
            "completed": True,
            "completed_at": datetime.utcnow().isoformat()
        })\
        .eq("id", goal_id)\
        .execute()
    
    updated_goal = supabase.table("goals")\
    .select("*")\
    .eq("id", goal_id)\
    .single()\
    .execute()

    return {
        "success": True, 
        "results": results,
        "completed_goal": updated_goal.data  # Add this
    }

# Add this endpoint to goal_routes.py

@router.post("/goals/{goal_id}/postpone")
async def postpone_goal(
    goal_id: str,
    minutes: int,
    current_user = Depends(get_current_user)
):
    """
    Postpone a goal's deadline by specified minutes (max 120 total)
    """
    supabase = get_supabase_client()
    
    # Validate minutes
    if minutes <= 0 or minutes > 120:
        raise HTTPException(
            status_code=400,
            detail="Postponement must be between 1 and 120 minutes"
        )
    
    # Get goal and verify ownership
    goal_response = supabase.table("goals")\
        .select("*")\
        .eq("id", goal_id)\
        .eq("user_id", current_user.id)\
        .single()\
        .execute()
    
    if not goal_response.data:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    goal = goal_response.data
    
    # Check if goal is already completed
    if goal['completed']:
        raise HTTPException(
            status_code=400,
            detail="Cannot postpone a completed goal"
        )
    
    # Check if deadline has already passed
    deadline = datetime.fromisoformat(goal['deadline'].replace('Z', '+00:00'))
    if deadline < datetime.utcnow().replace(tzinfo=deadline.tzinfo):
        raise HTTPException(
            status_code=400,
            detail="Cannot postpone a goal past its deadline"
        )
    
    # Check total postponed time
    total_postponed = goal.get('total_postponed_minutes', 0)
    if total_postponed + minutes > 120:
        remaining = 120 - total_postponed
        raise HTTPException(
            status_code=400,
            detail=f"Cannot postpone. Maximum 2 hours total. You have {remaining} minutes remaining."
        )
    
    # Calculate new deadline
    new_deadline = deadline + timedelta(minutes=minutes)
    
    # Update goal
    response = supabase.table("goals")\
        .update({
            "deadline": new_deadline.isoformat(),
            "total_postponed_minutes": total_postponed + minutes,
            # Reset notification flag so they get notified again at T-2h
            "notification_sent": False
        })\
        .eq("id", goal_id)\
        .execute()
    
    return {
        "success": True,
        "goal": response.data[0],
        "postponed_by_minutes": minutes,
        "total_postponed_minutes": total_postponed + minutes,
        "remaining_postpone_minutes": 120 - (total_postponed + minutes),
        "new_deadline": new_deadline.isoformat()
    }
    
@router.get("/goals/history")
async def get_completed_goals(current_user = Depends(get_current_user)):
    """
    Get completed goals with their posts
    """
    supabase = get_supabase_client()
    
    goals_response = supabase.table("goals")\
        .select("*, goal_social_selections(social_accounts(platform, username))")\
        .eq("user_id", current_user.id)\
        .eq("completed", True)\
        .order("completed_at", desc=True)\
        .execute()
    
    return goals_response.data