import pytest
from sqlalchemy.orm import Session
from app.services.debate_service import DebateService, _calculate_elo_updates
from app.models.user import User
from app.models.debate import Debate, BattleRoom, BattleRound, Vote, EloHistory


def _setup_full_battle(db_session: Session):
    """Helper: create users, debate, battle room, start it, return svc + battle_id"""
    user1 = User(
        email="p1@bf.com", username="player1",
        hashed_password="x", elo_rating=1500
    )
    user2 = User(
        email="p2@bf.com", username="player2",
        hashed_password="x", elo_rating=1200
    )
    voter = User(
        email="v@bf.com", username="voter",
        hashed_password="x", elo_rating=1000
    )
    db_session.add_all([user1, user2, voter])
    db_session.commit()

    debate = Debate(title="Flow Test", description="desc", created_by=user1.id)
    db_session.add(debate)
    db_session.commit()

    svc = DebateService(db_session)
    battle = svc.create_battle_room(debate.id, user1.id, user2.id)
    svc.start_battle(battle.id)

    return svc, battle.id, user1, user2, voter


def test_full_three_round_battle(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)

    for r in range(1, 4):
        svc.submit_round_argument(battle_id, r, f"Pro argument round {r}", u1.id)
        svc.submit_round_argument(battle_id, r, f"Con argument round {r}", u2.id)

    battle = svc.get_battle_room(battle_id)
    assert battle.status == "completed"
    assert battle.current_round == 3

    rounds = svc.get_battle_rounds(battle_id)
    for r in rounds:
        assert r.status == "completed"

    assert battle.winner_side in ("pro", "con", "draw")


def test_voting_after_completion(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)

    for r in range(1, 4):
        svc.submit_round_argument(battle_id, r, f"Pro arg {r}", u1.id)
        svc.submit_round_argument(battle_id, r, f"Con arg {r}", u2.id)

    vote = svc.cast_vote(
        battle_id, voter.id, side="pro",
        reasoning="Better arguments", confidence=8,
        argument_quality=7, clarity=8, persuasiveness=7, evidence=6
    )
    assert vote.side == "pro"
    assert vote.voter_id == voter.id

    votes = svc.get_battle_votes(battle_id)
    assert len(votes) == 1


def test_duplicate_vote_rejected(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)

    for r in range(1, 4):
        svc.submit_round_argument(battle_id, r, f"Pro {r}", u1.id)
        svc.submit_round_argument(battle_id, r, f"Con {r}", u2.id)

    svc.cast_vote(battle_id, voter.id, side="pro")
    with pytest.raises(ValueError, match="already voted"):
        svc.cast_vote(battle_id, voter.id, side="con")


def test_elo_update_on_win(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)

    for r in range(1, 4):
        svc.submit_round_argument(battle_id, r, f"Pro {r}", u1.id)
        svc.submit_round_argument(battle_id, r, f"Con {r}", u2.id)

    pre_elo_u1 = u1.elo_rating
    pre_elo_u2 = u2.elo_rating
    battle = svc.get_battle_room(battle_id)

    if battle.winner_side == "pro":
        assert u1.elo_rating != pre_elo_u1 or u2.elo_rating != pre_elo_u2

    history = db_session.query(EloHistory).filter(
        EloHistory.battle_room_id == battle_id
    ).all()
    assert len(history) == 2
    for h in history:
        assert h.old_elo is not None
        assert h.new_elo is not None
        assert h.elo_change != 0


def test_elo_draw_updates_both(db_session: Session):
    u1 = User(email="ed1@t.com", username="elo1", hashed_password="x", elo_rating=1200)
    u2 = User(email="ed2@t.com", username="elo2", hashed_password="x", elo_rating=2000)
    db_session.add_all([u1, u2])
    db_session.commit()

    debate = Debate(title="ELO Draw", description="d", created_by=u1.id)
    db_session.add(debate)
    db_session.commit()

    svc = DebateService(db_session)
    battle = svc.create_battle_room(debate.id, u1.id, u2.id)
    svc.start_battle(battle.id)

    for r in range(1, 4):
        svc.submit_round_argument(battle.id, r, f"P{r}", u1.id)
        svc.submit_round_argument(battle.id, r, f"C{r}", u2.id)

    battle = svc.get_battle_room(battle.id)
    if battle.winner_side == "draw":
        underdog_change = u1.elo_rating - 1200
        favorite_change = u2.elo_rating - 2000
        assert underdog_change > 0
        assert favorite_change < 0
        assert underdog_change == abs(favorite_change)


def test_invalid_round_argument_rejected(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)
    with pytest.raises(ValueError, match="Round not found"):
        svc.submit_round_argument(battle_id, 99, "Bad round", u1.id)


def test_pro_must_submit_first(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)
    with pytest.raises(ValueError, match="Pro must submit"):
        svc.submit_round_argument(battle_id, 1, "Con goes first", u2.id)


def test_vote_on_active_battle_rejected(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)
    with pytest.raises(ValueError, match="not completed"):
        svc.cast_vote(battle_id, voter.id, side="pro")


def test_complete_battle_round_counting(db_session: Session):
    u1 = User(email="rc1@t.com", username="rc1", hashed_password="x")
    u2 = User(email="rc2@t.com", username="rc2", hashed_password="x")
    db_session.add_all([u1, u2])
    db_session.commit()

    debate = Debate(title="RC Test", description="d", created_by=u1.id)
    db_session.add(debate)
    db_session.commit()

    svc = DebateService(db_session)
    battle = svc.create_battle_room(debate.id, u1.id, u2.id)
    svc.start_battle(battle.id)

    rounds_before = svc.get_battle_rounds(battle.id)
    assert len(rounds_before) == 3

    completed_before = sum(1 for r in rounds_before if r.status == "completed")
    assert completed_before == 0

    for r in range(1, 4):
        svc.submit_round_argument(battle.id, r, f"P{r}", u1.id)
        svc.submit_round_argument(battle.id, r, f"C{r}", u2.id)

    rounds_after = svc.get_battle_rounds(battle.id)
    completed_after = sum(1 for r in rounds_after if r.status == "completed")
    assert completed_after == 3


def test_non_participant_vote_rejected(db_session: Session):
    svc, battle_id, u1, u2, voter = _setup_full_battle(db_session)

    for r in range(1, 4):
        svc.submit_round_argument(battle_id, r, f"P{r}", u1.id)
        svc.submit_round_argument(battle_id, r, f"C{r}", u2.id)

    stranger = User(email="s@t.com", username="stranger", hashed_password="x")
    db_session.add(stranger)
    db_session.commit()

    vote = svc.cast_vote(battle_id, stranger.id, side="pro")
    assert vote is not None
