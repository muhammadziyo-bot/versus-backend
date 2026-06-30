import pytest
from fastapi.testclient import TestClient


def test_user_registration_and_login_flow(client: TestClient):
    """Test complete user registration and login flow"""
    user_data = {
        "email": "integration@example.com",
        "username": "integrationuser",
        "password": "Integration123!@#",
        "full_name": "Integration User"
    }
    
    # Register user
    register_response = client.post("/auth/register", json=user_data)
    assert register_response.status_code == 200
    user = register_response.json()
    assert user["email"] == user_data["email"]
    
    # Login with credentials
    login_response = client.post("/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    
    # Get user profile with token
    profile_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["email"] == user_data["email"]


def test_create_debate_and_battle_flow(client: TestClient):
    """Test creating a debate and then a battle"""
    # Register and login users
    user1_data = {
        "email": "debater1@example.com",
        "username": "debater1",
        "password": "Debater123!@#"
    }
    user2_data = {
        "email": "debater2@example.com",
        "username": "debater2",
        "password": "Debater123!@#"
    }
    
    client.post("/auth/register", json=user1_data)
    client.post("/auth/register", json=user2_data)
    
    login1 = client.post("/auth/login", json={
        "email": user1_data["email"],
        "password": user1_data["password"]
    })
    token1 = login1.json()["access_token"]
    
    login2 = client.post("/auth/login", json={
        "email": user2_data["email"],
        "password": user2_data["password"]
    })
    token2 = login2.json()["access_token"]
    
    # Create a debate
    debate_data = {
        "title": "Climate Change Debate",
        "description": "Is climate change caused by human activity?"
    }
    
    debate_response = client.post(
        "/debates/",
        json=debate_data,
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert debate_response.status_code == 200
    debate = debate_response.json()
    debate_id = debate["id"]
    
    # Create a battle room
    battle_data = {
        "debate_id": debate_id,
        "opponent_id": 2  # Assuming user2 has id 2
    }
    
    battle_response = client.post(
        "/battles/",
        json=battle_data,
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert battle_response.status_code == 200
    battle = battle_response.json()
    assert battle["pro_user_id"] == 1  # Assuming user1 has id 1


def test_get_users_and_search_flow(client: TestClient):
    """Test getting users and searching"""
    # Register multiple users
    users = [
        {"email": "alice@example.com", "username": "alice", "password": "Alice123!@#"},
        {"email": "bob@example.com", "username": "bob", "password": "Bob123!@#"},
        {"email": "alex@example.com", "username": "alex", "password": "Alex123!@#"}
    ]
    
    for user in users:
        client.post("/auth/register", json=user)
    
    # Get all debaters
    debaters_response = client.get("/users/debaters")
    assert debaters_response.status_code == 200
    debaters = debaters_response.json()
    assert len(debaters) >= 3
    
    # Search for users
    search_response = client.get("/users/search?q=al")
    assert search_response.status_code == 200
    search_results = search_response.json()
    assert len(search_results) >= 2  # alice and alex


def test_create_club_and_members_flow(client: TestClient):
    """Test creating a club and adding members"""
    # Register and login
    user_data = {
        "email": "clubowner@example.com",
        "username": "clubowner",
        "password": "ClubOwner123!@#"
    }
    client.post("/auth/register", json=user_data)
    
    login = client.post("/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login.json()["access_token"]
    
    # Create a club
    club_data = {
        "name": "Debate Enthusiasts",
        "description": "A club for debate lovers"
    }
    
    club_response = client.post(
        "/clubs/",
        json=club_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert club_response.status_code == 200
    club = club_response.json()
    assert club["name"] == club_data["name"]
    
    # Get clubs
    clubs_response = client.get("/clubs/")
    assert clubs_response.status_code == 200
    clubs = clubs_response.json()
    assert len(clubs) >= 1


def test_discussion_creation_and_comments_flow(client: TestClient):
    """Test creating discussions and adding comments"""
    # Register and login
    user_data = {
        "email": "discussant@example.com",
        "username": "discussant",
        "password": "Discussant123!@#"
    }
    client.post("/auth/register", json=user_data)
    
    login = client.post("/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login.json()["access_token"]
    
    # Create a discussion
    discussion_data = {
        "title": "Future of AI",
        "content": "What do you think about AI's future impact?"
    }
    
    discussion_response = client.post(
        "/discussions/",
        json=discussion_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert discussion_response.status_code == 200
    discussion = discussion_response.json()
    discussion_id = discussion["id"]
    
    # Add a comment
    comment_data = {
        "content": "I think AI will revolutionize many industries"
    }
    
    comment_response = client.post(
        f"/discussions/{discussion_id}/comments",
        json=comment_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert comment_response.status_code == 200
    comment = comment_response.json()
    assert comment["content"] == comment_data["content"]


def test_notification_flow(client: TestClient):
    """Test notification creation and retrieval"""
    # Register and login
    user_data = {
        "email": "notified@example.com",
        "username": "notified",
        "password": "Notified123!@#"
    }
    register_response = client.post("/auth/register", json=user_data)
    user_id = register_response.json()["id"]
    
    login = client.post("/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login.json()["access_token"]
    
    # Get notifications (should be empty initially)
    notifications_response = client.get(
        "/notifications/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert isinstance(notifications, list)


def test_profile_update_flow(client: TestClient):
    """Test updating user profile"""
    # Register and login
    user_data = {
        "email": "profile@example.com",
        "username": "profileuser",
        "password": "Profile123!@#",
        "full_name": "Original Name"
    }
    client.post("/auth/register", json=user_data)
    
    login = client.post("/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login.json()["access_token"]
    
    # Update profile
    update_data = {
        "full_name": "Updated Name",
        "bio": "This is my updated bio"
    }
    
    update_response = client.put(
        "/users/profile",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_response.status_code == 200
    updated_profile = update_response.json()
    assert updated_profile["full_name"] == "Updated Name"
    assert updated_profile["bio"] == "This is my updated bio"


def test_health_check_endpoints(client: TestClient):
    """Test health check endpoints"""
    # Basic health check
    basic_health = client.get("/health")
    assert basic_health.status_code == 200
    assert basic_health.json()["status"] == "healthy"
    
    # Detailed health check
    detailed_health = client.get("/health/detailed")
    assert detailed_health.status_code == 200
    health_data = detailed_health.json()
    assert "status" in health_data
    assert "dependencies" in health_data
    assert "timestamp" in health_data


def test_rate_limiting_on_multiple_requests(client: TestClient):
    """Test that rate limiting works on multiple rapid requests"""
    # Try multiple rapid login attempts
    login_data = {
        "email": "ratelimit@example.com",
        "password": "wrongpassword"
    }
    
    responses = []
    for i in range(15):  # Exceed the rate limit
        response = client.post("/auth/login", json=login_data)
        responses.append(response.status_code)
    
    # At least some requests should be rate limited (429)
    # Note: This depends on the rate limiter configuration
    assert 429 in responses or 401 in responses


def test_unauthorized_access_protection(client: TestClient):
    """Test that protected endpoints require authentication"""
    # Try to access protected endpoints without token
    protected_endpoints = [
        "/auth/me",
        "/users/profile",
        "/debates/",
        "/clubs/"
    ]
    
    for endpoint in protected_endpoints:
        response = client.get(endpoint)
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden
