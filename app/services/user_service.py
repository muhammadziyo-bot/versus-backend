from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserList
from app.core.security import get_password_hash, verify_password
from typing import Optional, List

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_create: UserCreate) -> User:
        print(f"=== CREATING USER ===")
        print(f"Email: {user_create.email}")
        print(f"Username: {user_create.username}")
        
        # Check if user already exists
        existing_email = self.get_user_by_email(user_create.email)
        if existing_email:
            print(f"Email already registered with ID: {existing_email.id}")
            raise ValueError("Email already registered")
        
        existing_username = self.get_user_by_username(user_create.username)
        if existing_username:
            print(f"Username already taken with ID: {existing_username.id}")
            raise ValueError("Username already taken")
        
        # Create new user
        hashed_password = get_password_hash(user_create.password)
        db_user = User(
            email=user_create.email,
            username=user_create.username,
            full_name=user_create.full_name,
            hashed_password=hashed_password,
            bio=user_create.bio,
            avatar_url=user_create.avatar_url
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        print(f"User created with ID: {db_user.id}")
        print(f"===================")
        
        return db_user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise ValueError(f"Account is locked until {user.locked_until}. Please try again later.")
        
        # Check if lockout period has expired
        if user.locked_until and user.locked_until <= datetime.utcnow():
            user.failed_login_attempts = 0
            user.locked_until = None
            self.db.commit()
        
        if not verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                self.db.commit()
                raise ValueError("Too many failed login attempts. Account locked for 30 minutes.")
            
            self.db.commit()
            return None
        
        # Reset failed login attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()
        return user
    
    def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        for field, value in user_update.dict(exclude_unset=True).items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_stats(self, user_id: int) -> dict:
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        
        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "elo_rating": user.elo_rating or 400,
            "created_at": user.created_at
        }
    
    def get_top_debaters(self, skip: int = 0, limit: int = 50) -> List[UserList]:
        # Get all users sorted by ELO rating (highest first)
        users = self.db.query(User).order_by(
            (User.elo_rating or 400).desc()
        ).offset(skip).limit(limit).all()
        
        result = []
        for user in users:
            user_list = UserList(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                elo_rating=user.elo_rating or 400
            )
            result.append(user_list)
        return result
    
    def get_stats(self) -> dict:
        from app.models.debate import BattleRoom
        
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(
            User.elo_rating > 400
        ).count()
        total_battles = self.db.query(BattleRoom).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_battles": total_battles
        }
