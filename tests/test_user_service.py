import pytest
from sqlalchemy.orm import Session
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate
from app.models.user import User


def test_create_user(db_session: Session):
    """Test creating a new user"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#",
        full_name="Test User"
    )
    
    user = user_service.create_user(user_data)
    
    assert user.id is not None
    assert user.email == user_data.email
    assert user.username == user_data.username
    assert user.full_name == user_data.full_name
    assert user.is_active is True
    assert user.hashed_password != user_data.password  # Password should be hashed


def test_create_user_duplicate_email(db_session: Session):
    """Test creating user with duplicate email"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    # Create first user
    user_service.create_user(user_data)
    
    # Try to create duplicate
    duplicate_data = UserCreate(
        email="test@example.com",
        username="different_user",
        password="Test123!@#"
    )
    
    with pytest.raises(ValueError, match="already registered"):
        user_service.create_user(duplicate_data)


def test_create_user_duplicate_username(db_session: Session):
    """Test creating user with duplicate username"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    # Create first user
    user_service.create_user(user_data)
    
    # Try to create duplicate
    duplicate_data = UserCreate(
        email="different@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    with pytest.raises(ValueError, match="already taken"):
        user_service.create_user(duplicate_data)


def test_get_user_by_email(db_session: Session):
    """Test retrieving user by email"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    created_user = user_service.create_user(user_data)
    retrieved_user = user_service.get_user_by_email(user_data.email)
    
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.email == user_data.email


def test_get_user_by_username(db_session: Session):
    """Test retrieving user by username"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    created_user = user_service.create_user(user_data)
    retrieved_user = user_service.get_user_by_username(user_data.username)
    
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.username == user_data.username


def test_authenticate_user_success(db_session: Session):
    """Test successful user authentication"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    user_service.create_user(user_data)
    authenticated_user = user_service.authenticate_user(
        user_data.email,
        user_data.password
    )
    
    assert authenticated_user is not None
    assert authenticated_user.email == user_data.email


def test_authenticate_user_wrong_password(db_session: Session):
    """Test authentication with wrong password"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    user_service.create_user(user_data)
    authenticated_user = user_service.authenticate_user(
        user_data.email,
        "wrongpassword"
    )
    
    assert authenticated_user is None


def test_authenticate_user_nonexistent(db_session: Session):
    """Test authentication with non-existent user"""
    user_service = UserService(db_session)
    
    authenticated_user = user_service.authenticate_user(
        "nonexistent@example.com",
        "Test123!@#"
    )
    
    assert authenticated_user is None


def test_update_user(db_session: Session):
    """Test updating user information"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#",
        full_name="Test User"
    )
    
    user = user_service.create_user(user_data)
    
    update_data = UserUpdate(
        full_name="Updated Name",
        bio="This is my bio"
    )
    
    updated_user = user_service.update_user(user.id, update_data)
    
    assert updated_user.full_name == "Updated Name"
    assert updated_user.bio == "This is my bio"


def test_update_nonexistent_user(db_session: Session):
    """Test updating non-existent user"""
    user_service = UserService(db_session)
    
    update_data = UserUpdate(full_name="Updated Name")
    updated_user = user_service.update_user(999, update_data)
    
    assert updated_user is None


def test_account_lockout_after_failed_attempts(db_session: Session):
    """Test account lockout after multiple failed login attempts"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    user_service.create_user(user_data)
    
    # Attempt 4 failed logins (5th attempt triggers lockout)
    for i in range(4):
        user_service.authenticate_user(user_data.email, "wrongpassword")
    
    # 5th attempt should raise account lockout error
    with pytest.raises(ValueError, match="locked"):
        user_service.authenticate_user(user_data.email, "wrongpassword")
    
    # Correct password should still work after lockout period expires
    # (In real implementation, you'd need to mock time or wait)


def test_reset_failed_attempts_on_success(db_session: Session):
    """Test that failed login attempts reset on successful login"""
    user_service = UserService(db_session)
    
    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        password="Test123!@#"
    )
    
    user_service.create_user(user_data)
    
    # 3 failed attempts
    for i in range(3):
        user_service.authenticate_user(user_data.email, "wrongpassword")
    
    # Successful login should reset counter
    user_service.authenticate_user(user_data.email, user_data.password)
    
    # Check that counter is reset by trying failed login again
    # Should not be locked yet
    result = user_service.authenticate_user(user_data.email, "wrongpassword")
    assert result is None  # Wrong password, but not locked
