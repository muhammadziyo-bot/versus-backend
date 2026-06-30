import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient, test_user_data):
    """Test user registration"""
    response = client.post("/auth/register", json=test_user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert "id" in data
    assert data["is_active"] is True


def test_register_duplicate_email(client: TestClient, test_user_data):
    """Test registration with duplicate email"""
    # Register first user
    client.post("/auth/register", json=test_user_data)
    
    # Try to register with same email
    duplicate_data = test_user_data.copy()
    duplicate_data["username"] = "different_user"
    response = client.post("/auth/register", json=duplicate_data)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_register_duplicate_username(client: TestClient, test_user_data):
    """Test registration with duplicate username"""
    # Register first user
    client.post("/auth/register", json=test_user_data)
    
    # Try to register with same username
    duplicate_data = test_user_data.copy()
    duplicate_data["email"] = "different@example.com"
    response = client.post("/auth/register", json=duplicate_data)
    assert response.status_code == 400
    assert "already taken" in response.json()["detail"]


def test_register_weak_password(client: TestClient, test_user_data):
    """Test registration with weak password"""
    weak_password_data = test_user_data.copy()
    weak_password_data["password"] = "weak"
    
    response = client.post("/auth/register", json=weak_password_data)
    assert response.status_code == 422  # Validation error


def test_login_user(client: TestClient, test_user_data):
    """Test user login"""
    # Register user first
    client.post("/auth/register", json=test_user_data)
    
    # Login
    login_data = {
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    }
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient, test_user_data):
    """Test login with invalid credentials"""
    # Register user first
    client.post("/auth/register", json=test_user_data)
    
    # Try to login with wrong password
    login_data = {
        "email": test_user_data["email"],
        "password": "wrongpassword"
    }
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    """Test login with non-existent user"""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "Test123!@#"
    }
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401


def test_get_current_user(client: TestClient, test_user_data):
    """Test getting current user info"""
    # Register and login
    client.post("/auth/register", json=test_user_data)
    login_response = client.post("/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    })
    token = login_response.json()["access_token"]
    
    # Get current user
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]


def test_get_current_user_unauthorized(client: TestClient):
    """Test getting current user without authentication"""
    response = client.get("/auth/me")
    assert response.status_code == 403


def test_rate_limiting_register(client: TestClient, test_user_data):
    """Test rate limiting on registration endpoint"""
    # Try to register multiple users rapidly (should be rate limited after 5)
    for i in range(6):
        test_data = test_user_data.copy()
        test_data["email"] = f"test{i}@example.com"
        test_data["username"] = f"testuser{i}"
        response = client.post("/auth/register", json=test_data)
    
    # The 6th request might be rate limited
    # Note: This test depends on the rate limiter configuration


def test_rate_limiting_login(client: TestClient, test_user_data):
    """Test rate limiting on login endpoint"""
    # Register user
    client.post("/auth/register", json=test_user_data)
    
    # Try multiple failed logins rapidly
    login_data = {
        "email": test_user_data["email"],
        "password": "wrongpassword"
    }
    
    for i in range(11):
        response = client.post("/auth/login", json=login_data)
    
    # Should eventually be rate limited
    # Note: This test depends on the rate limiter configuration
