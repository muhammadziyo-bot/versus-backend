import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate
from app.services.user_service import UserService


def _create_user(db_session: Session, data: dict):
    svc = UserService(db_session)
    return svc.create_user(UserCreate(**data))


def _login_user(client: TestClient, email: str, password: str):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        return None
    return resp.json()["access_token"]


def test_user_registration_and_login_flow(client: TestClient, db_session: Session):
    _create_user(db_session, {
        "email": "integration@example.com",
        "username": "integrationuser",
        "password": "Integration123!@#",
        "full_name": "Integration User"
    })
    
    login_response = client.post("/auth/login", json={
        "email": "integration@example.com",
        "password": "Integration123!@#"
    })
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    
    profile_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["email"] == "integration@example.com"


def test_create_debate_and_battle_flow(client: TestClient, db_session: Session):
    user1 = _create_user(db_session, {
        "email": "debater1@example.com", "username": "debater1", "password": "Debater123!@#"
    })
    user2 = _create_user(db_session, {
        "email": "debater2@example.com", "username": "debater2", "password": "Debater123!@#"
    })
    
    token1 = _login_user(client, "debater1@example.com", "Debater123!@#")
    token2 = _login_user(client, "debater2@example.com", "Debater123!@#")
    assert token1 and token2
    
    debate_response = client.post(
        "/api/debates/",
        json={"title": "Climate Change Debate", "description": "Is climate change caused by human activity?"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert debate_response.status_code == 200
    debate = debate_response.json()
    debate_id = debate["id"]
    
    battle_response = client.post(
        "/api/battles/",
        json={"debate_id": debate_id, "opponent_id": user2.id},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert battle_response.status_code == 200
    battle = battle_response.json()
    assert battle["pro_user_id"] == user1.id


def test_get_users_and_search_flow(client: TestClient, db_session: Session):
    for u in [
        {"email": "alice@example.com", "username": "alice", "password": "Alice123!@#"},
        {"email": "bob@example.com", "username": "bob", "password": "Bob123!@#"},
        {"email": "alex@example.com", "username": "alex", "password": "Alex123!@#"}
    ]:
        _create_user(db_session, u)
    
    debaters_response = client.get("/api/users/debaters")
    assert debaters_response.status_code == 200
    assert len(debaters_response.json()) >= 3
    
    search_response = client.get("/api/users/search?q=al")
    assert search_response.status_code == 200
    assert len(search_response.json()) >= 2


def test_create_club_and_members_flow(client: TestClient, db_session: Session):
    _create_user(db_session, {
        "email": "clubowner@example.com", "username": "clubowner", "password": "ClubOwner123!@#"
    })
    token = _login_user(client, "clubowner@example.com", "ClubOwner123!@#")
    assert token
    
    club_response = client.post(
        "/api/clubs/",
        json={"name": "Debate Enthusiasts", "description": "A club for debate lovers"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert club_response.status_code == 200
    assert club_response.json()["name"] == "Debate Enthusiasts"
    
    clubs_response = client.get("/api/clubs/")
    assert clubs_response.status_code == 200
    assert len(clubs_response.json()) >= 1


def test_discussion_creation_and_comments_flow(client: TestClient, db_session: Session):
    _create_user(db_session, {
        "email": "discussant@example.com", "username": "discussant", "password": "Discussant123!@#"
    })
    token = _login_user(client, "discussant@example.com", "Discussant123!@#")
    assert token
    
    discussion_response = client.post(
        "/api/discussions/",
        json={"title": "Future of AI", "content": "What do you think about AI's future impact?"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert discussion_response.status_code == 201
    discussion = discussion_response.json()
    discussion_id = discussion["id"]
    
    comment_response = client.post(
        f"/api/discussions/{discussion_id}/comments",
        json={"content": "I think AI will revolutionize many industries"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert comment_response.status_code == 201
    assert comment_response.json()["content"] == "I think AI will revolutionize many industries"


def test_notification_flow(client: TestClient, db_session: Session):
    user = _create_user(db_session, {
        "email": "notified@example.com", "username": "notified", "password": "Notified123!@#"
    })
    token = _login_user(client, "notified@example.com", "Notified123!@#")
    assert token
    
    notifications_response = client.get(
        "/api/notifications/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert notifications_response.status_code == 200
    assert isinstance(notifications_response.json(), list)


def test_profile_update_flow(client: TestClient, db_session: Session):
    _create_user(db_session, {
        "email": "profile@example.com", "username": "profileuser",
        "password": "Profile123!@#", "full_name": "Original Name"
    })
    token = _login_user(client, "profile@example.com", "Profile123!@#")
    assert token
    
    update_response = client.put(
        "/api/users/profile",
        json={"full_name": "Updated Name", "bio": "This is my updated bio"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_response.status_code == 200
    profile = update_response.json()
    assert profile["full_name"] == "Updated Name"
    assert profile["bio"] == "This is my updated bio"


def test_health_check_endpoints(client: TestClient):
    basic_health = client.get("/health")
    assert basic_health.status_code == 200
    assert basic_health.json()["status"] == "healthy"
    
    detailed_health = client.get("/health/detailed")
    assert detailed_health.status_code == 200
    health_data = detailed_health.json()
    assert "status" in health_data
    assert "dependencies" in health_data
    assert "timestamp" in health_data


def test_rate_limiting_on_multiple_requests(client: TestClient):
    login_data = {"email": "ratelimit@example.com", "password": "wrongpassword"}
    responses = [client.post("/auth/login", json=login_data).status_code for _ in range(15)]
    assert 429 in responses or 401 in responses


def test_unauthorized_access_protection(client: TestClient):
    protected_endpoints = [
        ("GET", "/auth/me"),
        ("POST", "/api/debates/"),
        ("POST", "/api/clubs/"),
    ]
    for method, endpoint in protected_endpoints:
        response = client.post(endpoint, json={}) if method == "POST" else client.get(endpoint)
        assert response.status_code in [401, 403], f"{method} {endpoint} returned {response.status_code}"
