import pytest
from sqlalchemy.orm import Session
from app.services.debate_service import DebateService
from app.models.debate import Debate, BattleRoom
from app.models.user import User


def test_create_battle_room(db_session: Session):
    """Test creating a battle room"""
    debate_service = DebateService(db_session)
    
    # Create test users
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password",
        skill_level="intermediate",
        elo_rating=1200
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password",
        skill_level="intermediate",
        elo_rating=1250
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    # Create a debate topic first
    debate = Debate(
        title="AI Ethics",
        description="Should AI be regulated?",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    # Create battle room
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    assert battle.id is not None
    assert battle.pro_user_id == user1.id
    assert battle.con_user_id == user2.id
    assert battle.status == "waiting"
    assert battle.current_round == 1


def test_start_battle(db_session: Session):
    """Test starting a battle"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    # Start the battle
    started_battle = debate_service.start_battle(battle_room_id=battle.id)
    
    assert started_battle.status == "active"
    assert started_battle.current_round == 1
    assert started_battle.started_at is not None


def test_submit_round_argument(db_session: Session):
    """Test submitting an argument for a round"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    debate_service.start_battle(battle_room_id=battle.id)
    
    # Submit pro argument
    round_obj = debate_service.submit_round_argument(
        battle_room_id=battle.id,
        round_number=1,
        argument="AI should be regulated to ensure safety",
        user_id=user1.id
    )
    
    assert round_obj.pro_argument == "AI should be regulated to ensure safety"
    assert round_obj.round_number == 1


def test_submit_argument_invalid_user(db_session: Session):
    """Test submitting argument from invalid user"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    user3 = User(
        email="user3@example.com",
        username="user3",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.add(user3)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    debate_service.start_battle(battle_room_id=battle.id)
    
    # Try to submit argument from user not in battle
    with pytest.raises(ValueError, match="not part of this battle"):
        debate_service.submit_round_argument(
            battle_room_id=battle.id,
            round_number=1,
            argument="This should fail",
            user_id=user3.id
        )


def test_get_battle_room(db_session: Session):
    """Test retrieving a battle room"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    # Retrieve battle
    retrieved_battle = debate_service.get_battle_room(battle.id)
    
    assert retrieved_battle is not None
    assert retrieved_battle.id == battle.id
    assert retrieved_battle.pro_user_id == user1.id


def test_complete_battle(db_session: Session):
    """Test completing a battle with voting"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    voter = User(
        email="voter@example.com",
        username="voter",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.add(voter)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    debate_service.start_battle(battle_room_id=battle.id)
    
    # Submit arguments for all rounds
    for round_num in range(1, 4):
        debate_service.submit_round_argument(
            battle_room_id=battle.id,
            round_number=round_num,
            argument=f"Pro argument round {round_num}",
            user_id=user1.id
        )
        debate_service.submit_round_argument(
            battle_room_id=battle.id,
            round_number=round_num,
            argument=f"Con argument round {round_num}",
            user_id=user2.id
        )
    
    # Cast vote
    debate_service.cast_vote(
        battle_room_id=battle.id,
        voter_id=voter.id,
        side="pro",
        reasoning="Pro had better arguments",
        confidence=80,
        argument_quality=85,
        clarity=90,
        persuasiveness=75,
        evidence=80
    )
    
    # Complete battle
    debate_service.end_battle(battle_room_id=battle.id)
    completed_battle = debate_service.get_battle_room(battle_room_id=battle.id)
    
    assert completed_battle.status == "completed"
    assert completed_battle.completed_at is not None
    assert completed_battle.winner_side is not None


def test_get_battle_rounds(db_session: Session):
    """Test retrieving battle rounds"""
    debate_service = DebateService(db_session)
    
    # Create test users and battle
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password="hashed_password"
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password="hashed_password"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    
    debate = Debate(
        title="Test Debate",
        description="Test description",
        created_by=user1.id
    )
    db_session.add(debate)
    db_session.commit()
    
    battle = debate_service.create_battle_room(
        debate_id=debate.id,
        pro_user_id=user1.id,
        con_user_id=user2.id
    )
    
    debate_service.start_battle(battle_room_id=battle.id)
    
    # Submit arguments
    debate_service.submit_round_argument(
        battle_room_id=battle.id,
        round_number=1,
        argument="Pro argument",
        user_id=user1.id
    )
    
    # Get rounds
    rounds = debate_service.get_battle_rounds(battle_room_id=battle.id)
    
    assert len(rounds) == 3  # 3 rounds are created by default
    assert rounds[0].round_number == 1
