import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.debate import Debate
from app.services.debate_service import DebateService
from app.core.security import create_access_token


def _setup_battle(db_session: Session):
    user1 = User(
        email="p1@test.com", username="player1",
        hashed_password="x", elo_rating=400
    )
    user2 = User(
        email="p2@test.com", username="player2",
        hashed_password="x", elo_rating=400
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    debate = Debate(title="Test Topic", description="desc", created_by=user1.id)
    db_session.add(debate)
    db_session.commit()

    svc = DebateService(db_session)
    battle = svc.create_battle_room(debate_id=debate.id, pro_user_id=user1.id, con_user_id=user2.id)

    token1 = create_access_token(data={"sub": user1.email})
    token2 = create_access_token(data={"sub": user2.email})
    return token1, token2, battle.id


def _drain_until(ws, expected_type, max_attempts=5):
    for _ in range(max_attempts):
        msg = ws.receive_json()
        if msg["type"] == expected_type:
            return msg
    raise AssertionError(f"Expected {expected_type} but not found in {max_attempts} messages")


def test_websocket_connect_and_receive_state(client: TestClient, db_session: Session):
    token1, _, battle_id = _setup_battle(db_session)
    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws:
        data = ws.receive_json()
        assert data["type"] == "battle_state"
        assert data["data"]["battle"]["id"] == battle_id
        assert data["data"]["battle"]["status"] == "waiting"
        assert len(data["data"]["rounds"]) == 3


def test_websocket_requires_auth(client: TestClient, db_session: Session):
    _, _, battle_id = _setup_battle(db_session)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/battle/{battle_id}?token=invalid_token"):
            pass


def test_websocket_heartbeat(client: TestClient, db_session: Session):
    token1, _, battle_id = _setup_battle(db_session)
    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws:
        ws.receive_json()
        ws.send_json({"type": "heartbeat"})
        resp = ws.receive_json()
        assert resp["type"] == "heartbeat_response"


def test_websocket_chat(client: TestClient, db_session: Session):
    token1, token2, battle_id = _setup_battle(db_session)
    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/battle/{battle_id}?token={token2}") as ws2:
            ws2.receive_json()
            ws1.send_json({"type": "chat", "data": {"message": "Hello!"}})
            msg = _drain_until(ws2, "chat")
            assert msg["data"]["message"] == "Hello!"
            assert msg["data"]["username"] == "player1"


def test_websocket_battle_start(client: TestClient, db_session: Session):
    token1, token2, battle_id = _setup_battle(db_session)
    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/battle/{battle_id}?token={token2}") as ws2:
            ws2.receive_json()
            ws1.send_json({"type": "start_battle"})
            event1 = _drain_until(ws1, "battle_started")
            event2 = _drain_until(ws2, "battle_started")
            assert event1["data"]["battle_id"] == battle_id
            assert event1["data"]["current_round"] == 1


def test_websocket_argument_submission(client: TestClient, db_session: Session):
    token1, token2, battle_id = _setup_battle(db_session)
    svc = DebateService(db_session)
    svc.start_battle(battle_id)

    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/battle/{battle_id}?token={token2}") as ws2:
            ws2.receive_json()
            ws1.send_json({
                "type": "submit_argument",
                "data": {"round_number": 1, "argument": "Pro argument"}
            })
            event = _drain_until(ws2, "argument_submitted")
            assert event["data"]["round_number"] == 1
            assert event["data"]["side"] == "pro"


def test_websocket_argument_order_enforced(client: TestClient, db_session: Session):
    token1, token2, battle_id = _setup_battle(db_session)
    svc = DebateService(db_session)
    svc.start_battle(battle_id)

    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token2}") as ws2:
        ws2.receive_json()
        ws2.send_json({
            "type": "submit_argument",
            "data": {"round_number": 1, "argument": "Con jumps first"}
        })
        resp = ws2.receive_json()
        assert resp["type"] == "error"
        assert "Pro must submit" in resp["data"]["message"]


def test_websocket_round_completion(client: TestClient, db_session: Session):
    token1, token2, battle_id = _setup_battle(db_session)
    svc = DebateService(db_session)
    svc.start_battle(battle_id)

    with client.websocket_connect(f"/ws/battle/{battle_id}?token={token1}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/battle/{battle_id}?token={token2}") as ws2:
            ws2.receive_json()
            ws1.send_json({
                "type": "submit_argument",
                "data": {"round_number": 1, "argument": "Pro"}
            })
            ws2.send_json({
                "type": "submit_argument",
                "data": {"round_number": 1, "argument": "Con"}
            })
            round_completed = _drain_until(ws1, "round_completed")
            assert round_completed["data"]["round_number"] == 1
            assert round_completed["data"]["next_round"] == 2
