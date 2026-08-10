from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from app.database import get_db
from app.schemas.user import UserCreate, UserLogin, Token, User
from app.services.user_service import UserService
from app.core.security import create_access_token
from app.core.dependencies import get_current_active_user
from app.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)

@router.post("/register", response_model=User)
@limiter.limit("5/minute")
def register(request: Request, user_create: UserCreate, db: Session = Depends(get_db)):
    user_service = UserService(db)
    try:
        user = user_service.create_user(user_create)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, user_login: UserLogin, db: Session = Depends(get_db)):
    print(f"=== LOGIN ATTEMPT ===")
    print(f"Email: {user_login.email}")
    
    user_service = UserService(db)
    try:
        user = user_service.authenticate_user(user_login.email, user_login.password)
    except ValueError as e:
        print(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user:
        print(f"Authentication failed for email: {user_login.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"User authenticated: {user.username} (ID: {user.id})")
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Mark user as online
    if not user.is_online:
        user.is_online = True
        db.commit()
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    print(f"Token created for user ID: {user.id}")
    print(f"===================")
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    print(f"=== GET CURRENT USER INFO ===")
    print(f"User ID: {current_user.id}")
    print(f"Username: {current_user.username}")
    print(f"Email: {current_user.email}")
    print(f"==============================")
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "elo_rating": current_user.elo_rating or 400,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_online": current_user.is_online
    }

@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    """Get all users (for debugging)"""
    from app.models.user import User
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "created_at": user.created_at
        }
        for user in users
    ]

@router.post("/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_active_user)):
    """Refresh access token"""
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": current_user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Logout - mark user as offline"""
    if current_user.is_online:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.commit()
    return {"message": "Successfully logged out"}
