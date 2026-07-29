from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path
from app.config import settings
from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.api import auth, debates, clubs, users, discussions, battles, websocket_endpoints, matchmaking, notifications, friends, moderation as moderation_api
from app.models import user, debate, club, notification, friend, moderation
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.logging_config import logger
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Note: Database tables should be created via migrations, not on startup
# Commented out to prevent connection issues during deployment
# Base.metadata.create_all(bind=engine)

# Initialize Sentry if DSN is provided
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment="production" if not settings.debug else "development"
    )
    logger.info("Sentry initialized")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Digital Arena API",
    description="Backend for the Digital Arena debate platform",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Run schema migration on startup so the app self-heals if Supabase pooler
# routes to a database instance that missed a migration
@app.on_event("startup")
def run_schema_migration():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false"))
            conn.execute(text("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_muted BOOLEAN DEFAULT false"))
            conn.execute(text("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT false"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS score_status VARCHAR(50) DEFAULT 'pending'"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS error_message TEXT"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS community_average_score INTEGER"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS score_deviation INTEGER"))
            conn.execute(text("ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS calibration_status VARCHAR(50) DEFAULT 'pending'"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS reports (id SERIAL PRIMARY KEY, reporter_id INTEGER REFERENCES app_users(id) NOT NULL, reported_user_id INTEGER REFERENCES app_users(id) NOT NULL, target_type VARCHAR NOT NULL, target_id INTEGER NOT NULL, reason VARCHAR NOT NULL, description TEXT, status VARCHAR DEFAULT 'pending', resolved_by INTEGER REFERENCES app_users(id), resolution VARCHAR, resolution_note TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), resolved_at TIMESTAMP WITH TIME ZONE)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS user_bans (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES app_users(id) NOT NULL, banned_by INTEGER REFERENCES app_users(id) NOT NULL, reason TEXT NOT NULL, ban_type VARCHAR DEFAULT 'mute', is_active BOOLEAN DEFAULT true, expires_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), lifted_at TIMESTAMP WITH TIME ZONE, lifted_by INTEGER REFERENCES app_users(id))"))
            conn.commit()
            logger.info("Startup schema migration completed")
    except Exception as e:
        logger.warning(f"Schema migration check skipped: {e}")

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(debates.router)
app.include_router(clubs.router)
app.include_router(users.router)
app.include_router(discussions.router)
app.include_router(discussions.comments_router)
app.include_router(battles.router)
app.include_router(matchmaking.router)
app.include_router(notifications.router)
app.include_router(friends.router)
app.include_router(moderation_api.router)

# Include WebSocket endpoint
app.websocket("/ws/battle/{battle_room_id}")(websocket_endpoints.websocket_endpoint)

# Mount static files for uploads
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    return {"message": "Digital Arena API is running"}

@app.get("/health")
def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy"}

@app.get("/keep-alive")
def keep_alive():
    """Keep-alive endpoint to prevent Render free tier spin-down"""
    return {"status": "alive", "timestamp": "auto"}

@app.get("/health/detailed")
def detailed_health_check():
    """Detailed health check with dependency status"""
    from app.core.redis_client import redis_client
    import time
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "dependencies": {}
    }
    
    # Check database connection
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status["dependencies"]["database"] = "healthy"
    except Exception as e:
        health_status["dependencies"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis connection
    try:
        redis_healthy = redis_client.ping()
        health_status["dependencies"]["redis"] = "healthy" if redis_healthy else "unhealthy"
        if not redis_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Sentry connection
    try:
        if settings.sentry_dsn:
            health_status["dependencies"]["sentry"] = "configured"
        else:
            health_status["dependencies"]["sentry"] = "not configured"
    except Exception as e:
        health_status["dependencies"]["sentry"] = f"unhealthy: {str(e)}"
    
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
