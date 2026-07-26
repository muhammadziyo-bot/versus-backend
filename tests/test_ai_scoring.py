import pytest
import json
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.debate import Debate, BattleRoom, BattleRound, AIArgumentScore, AIBattleResult
from app.services.debate_service import DebateService
from app.services.ai_scoring_service import AIScoringService, MAX_SCORE_RETRIES


MOCK_SCORE_RESPONSE = json.dumps({
    "logical_coherence": 8,
    "evidence_quality": 7,
    "clarity": 9,
    "relevance": 8,
    "counter_effectiveness": 6,
    "overall_score": 8,
    "strengths": "Clear logical flow with good use of evidence",
    "weaknesses": "Could better address counter-arguments",
    "detailed_feedback": "The argument presents a coherent position with supporting reasoning."
})


def _setup_battle_with_rounds(db_session: Session):
    user1 = User(email="u1@t.com", username="u1", hashed_password="x")
    user2 = User(email="u2@t.com", username="u2", hashed_password="x")
    db_session.add_all([user1, user2])
    db_session.commit()

    debate = Debate(title="Test Debate", description="desc", created_by=user1.id)
    db_session.add(debate)
    db_session.commit()

    svc = DebateService(db_session)
    battle = svc.create_battle_room(debate.id, user1.id, user2.id)
    db_session.refresh(battle)

    round_obj = db_session.query(BattleRound).filter(
        BattleRound.battle_room_id == battle.id,
        BattleRound.round_number == 1
    ).first()
    round_obj.pro_argument = "Pro says this"
    round_obj.con_argument = "Con says that"
    round_obj.status = "completed"
    db_session.commit()

    return db_session, battle.id, round_obj.id


@patch("app.services.ai_scoring_service.Groq")
def test_score_argument_success(mock_groq_class, db_session: Session):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_SCORE_RESPONSE
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_class.return_value = mock_client

    _, battle_id, round_id = _setup_battle_with_rounds(db_session)
    service = AIScoringService(db_session)
    result = service.score_argument(round_id, "pro", "Pro says this", "Test Debate")

    assert result.score_status == "completed"
    assert result.overall_score == 8
    assert result.logical_coherence == 8
    assert result.side == "pro"
    assert result.battle_round_id == round_id
    assert result.retry_count == 0


@patch("app.services.ai_scoring_service.Groq")
def test_score_argument_retry_then_succeed(mock_groq_class, db_session: Session):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_SCORE_RESPONSE

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Groq temporary error")
        return mock_response

    mock_client.chat.completions.create.side_effect = side_effect
    mock_groq_class.return_value = mock_client

    _, _, round_id = _setup_battle_with_rounds(db_session)
    service = AIScoringService(db_session)
    result = service.score_argument(round_id, "con", "Con says that", "Test Debate")

    assert result.score_status == "completed"
    assert result.retry_count == 2


@patch("app.services.ai_scoring_service.Groq")
def test_score_argument_all_retries_fail(mock_groq_class, db_session: Session):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Groq persistent failure")
    mock_groq_class.return_value = mock_client

    _, _, round_id = _setup_battle_with_rounds(db_session)
    service = AIScoringService(db_session)
    result = service.score_argument(round_id, "pro", "Pro says this", "Test Debate")

    assert result.score_status == "failed"
    assert result.retry_count == MAX_SCORE_RETRIES
    assert result.overall_score == 0
    assert "Groq persistent failure" in result.error_message


@patch("app.services.ai_scoring_service.Groq")
def test_scoring_prompt_includes_opponent(mock_groq_class, db_session: Session):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_SCORE_RESPONSE
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_class.return_value = mock_client

    _, _, round_id = _setup_battle_with_rounds(db_session)
    service = AIScoringService(db_session)

    result = service.score_argument(
        round_id, "pro", "Pro says this", "Test Debate",
        opponent_argument="Con says that"
    )

    assert result.score_status == "completed"
    call_args = mock_client.chat.completions.create.call_args
    prompt_content = call_args[1]["messages"][1]["content"]
    assert "OPPONENT'S ARGUMENT" in prompt_content
    assert "Con says that" in prompt_content


@patch("app.services.ai_scoring_service.Groq")
def test_calculate_battle_result_skips_failed_scores(mock_groq_class, db_session: Session):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_SCORE_RESPONSE
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_class.return_value = mock_client

    _, battle_id, round_id = _setup_battle_with_rounds(db_session)

    service = AIScoringService(db_session)
    service.score_argument(round_id, "pro", "Pro says this", "Test Debate")

    failed_score = AIArgumentScore(
        battle_round_id=round_id, side="con", score_status="failed",
        retry_count=3, error_message="fail", overall_score=0
    )
    db_session.add(failed_score)
    db_session.commit()

    result = service.calculate_battle_result(battle_id)
    assert result.status == "completed"
    assert result.pro_total_score > 0
    assert result.con_total_score == 0


@patch("app.services.ai_scoring_service.Groq")
def test_calculate_calibration(mock_groq_class, db_session: Session):
    from app.models.debate import Vote

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = MOCK_SCORE_RESPONSE
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_class.return_value = mock_client

    _, battle_id, round_id = _setup_battle_with_rounds(db_session)

    service = AIScoringService(db_session)
    service.score_argument(round_id, "pro", "Pro says this", "Test Debate")

    vote = Vote(
        battle_room_id=battle_id, voter_id=1, side="pro",
        argument_quality=7, clarity=8, persuasiveness=7, evidence=6
    )
    db_session.add(vote)
    db_session.commit()

    calibration = service.calculate_calibration(battle_id)
    assert "rounds" in calibration
    assert len(calibration["rounds"]) >= 1
    sides = calibration["rounds"][0]["sides"]
    pro_side = next((s for s in sides if s["side"] == "pro"), None)
    assert pro_side is not None
    assert pro_side["community_average"] is not None
    assert pro_side["vote_count"] > 0
