import json
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.routes import oauth_routes, social_routes, goal_routes, user_routes
from app.jobs.deadline_checker import run_scheduler
from app.jobs.auto_poster import run_auto_poster  # NEW
from config import get_settings

settings = get_settings()

# Background tasks
scheduler_task = None
auto_poster_task = None  # NEW

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start both background jobs
    global scheduler_task, auto_poster_task
    
    scheduler_task = asyncio.create_task(run_scheduler())
    print("✅ Deadline checker started")
    
    auto_poster_task = asyncio.create_task(run_auto_poster())  # NEW
    print("✅ Auto-poster started")  # NEW
    
    yield
    
    # Shutdown: Cancel both tasks
    if scheduler_task:
        scheduler_task.cancel()
        print("✅ Deadline checker stopped")
    
    if auto_poster_task:  # NEW
        auto_poster_task.cancel()  # NEW
        print("✅ Auto-poster stopped")  # NEW

app = FastAPI(
    title="lockin API",
    description="Backend API for lockin accountability app",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(oauth_routes.router, prefix="/oauth", tags=["oauth"])
app.include_router(social_routes.router, prefix="/social", tags=["social"])
app.include_router(goal_routes.router, prefix="/goals", tags=["goals"])
app.include_router(user_routes.router, prefix="/api", tags=["user"])

@app.get("/")
async def root():
    return {"message": "lockin API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/.well-known/apple-app-site-association")
async def apple_app_site_association():
    """
    Serve Apple App Site Association file for Universal Links
    """
    aasa_content = {
        "applinks": {
            "apps": [],
            "details": [
                {
                    "appID": "GWF28Z9MW3.cloud.lockin.app", 
                    "paths": [
                        "/oauth/callback",
                        "/oauth/*",
                        "*"
                    ]
                }
            ]
        }
    }
    
    return Response(
        content=json.dumps(aasa_content),
        media_type="application/json"
    )
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
    
    
