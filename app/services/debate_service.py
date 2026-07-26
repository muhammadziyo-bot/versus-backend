from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
import asyncio
from app.models.debate import Debate, Argument, BattleRoom, Vote, BattleRound, EloHistory
from app.models.user import User
from app.schemas.debate import DebateCreate, DebateList, DebateResponse

ELO_K_FACTOR = 32
ELO_SCALE = 400


def _calculate_elo_updates(rating_a: int, rating_b: int, score_a: float) -> tuple[int, int]:
    """
    Calculate Elo rating updates using the standard Arpad Elo formula.
    
    Args:
        rating_a: Current rating of player A
        rating_b: Current rating of player B
        score_a: Actual score for player A (1.0 = win, 0.5 = draw, 0.0 = loss)
    
    Returns:
        Tuple of (new_rating_a, new_rating_b)
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / ELO_SCALE))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / ELO_SCALE))
    score_b = 1.0 - score_a
    new_a = round(rating_a + ELO_K_FACTOR * (score_a - expected_a))
    new_b = round(rating_b + ELO_K_FACTOR * (score_b - expected_b))
    return max(0, new_a), max(0, new_b)


class DebateService:
    def __init__(self, db: Session):
        self.db = db

    def get_debates(self, skip: int = 0, limit: int = 100):
        debates = self.db.query(Debate).offset(skip).limit(limit).all()
        result = []
        for debate in debates:
            pro_count = self.db.query(Argument).filter(
                Argument.debate_id == debate.id,
                Argument.side == "pro"
            ).count()
            con_count = self.db.query(Argument).filter(
                Argument.debate_id == debate.id,
                Argument.side == "con"
            ).count()
            
            debate_list = DebateList(
                id=debate.id,
                title=debate.title,
                description=debate.description,
                category=debate.category,
                status=debate.status,
                created_at=debate.created_at,
                pro_count=pro_count,
                con_count=con_count,
                total_arguments=pro_count + con_count
            )
            result.append(debate_list)
        return result

    def get_debate(self, debate_id: int):
        debate = self.db.query(Debate).filter(Debate.id == debate_id).first()
        if not debate:
            return None
        
        arguments = self.db.query(Argument).filter(Argument.debate_id == debate_id).all()
        pro_count = len([arg for arg in arguments if arg.side == "pro"])
        con_count = len([arg for arg in arguments if arg.side == "con"])
        
        return DebateResponse(
            id=debate.id,
            title=debate.title,
            description=debate.description,
            category=debate.category,
            status=debate.status,
            created_by=debate.created_by,
            created_at=debate.created_at,
            updated_at=debate.updated_at,
            arguments=arguments,
            pro_count=pro_count,
            con_count=con_count,
            total_arguments=pro_count + con_count
        )

    def create_debate(self, debate: DebateCreate, created_by: int):
        debate_data = debate.dict()
        debate_data['created_by'] = created_by
        db_debate = Debate(**debate_data)
        self.db.add(db_debate)
        self.db.commit()
        self.db.refresh(db_debate)
        
        # Return in DebateList format for consistency
        return DebateList(
            id=db_debate.id,
            title=db_debate.title,
            description=db_debate.description,
            category=db_debate.category,
            status=db_debate.status,
            created_at=db_debate.created_at,
            pro_count=0,
            con_count=0,
            total_arguments=0
        )

    def get_stats(self):
        total_debates = self.db.query(Debate).count()
        active_debates = self.db.query(Debate).filter(Debate.status == "active").count()
        total_arguments = self.db.query(Argument).count()
        
        return {
            "total_debates": total_debates,
            "active_debates": active_debates,
            "total_arguments": total_arguments
        }

    # ========== BATTLE SYSTEM METHODS ==========
    
    def create_battle_room(self, debate_id: int, pro_user_id: int, con_user_id: int) -> BattleRoom:
        """Create a new battle room - pro_user_id is the creator, con_user_id is the opponent"""
        print(f"=== CREATING BATTLE ROOM ===")
        print(f"Debate ID: {debate_id}")
        print(f"Pro User ID: {pro_user_id} (type: {type(pro_user_id)})")
        print(f"Con User ID: {con_user_id} (type: {type(con_user_id)})")
        
        battle_room = BattleRoom(
            debate_id=debate_id,
            pro_user_id=int(pro_user_id),
            con_user_id=int(con_user_id),
            status="waiting"
        )
        
        self.db.add(battle_room)
        self.db.commit()
        self.db.refresh(battle_room)
        
        print(f"Battle Room Created with ID: {battle_room.id}")
        print(f"Stored Pro User ID: {battle_room.pro_user_id} (type: {type(battle_room.pro_user_id)})")
        print(f"Stored Con User ID: {battle_room.con_user_id} (type: {type(battle_room.con_user_id)})")
        print(f"============================")
        
        # Create battle rounds
        for round_num in range(1, 4):  # 3 rounds
            battle_round = BattleRound(
                battle_room_id=battle_room.id,
                round_number=round_num,
                status="waiting"
            )
            self.db.add(battle_round)
        
        self.db.commit()
        return battle_room
    
    def select_battle_side(self, battle_room_id: int, user_id: int, side: str) -> BattleRoom:
        """Select a side for the battle (pro or con) - only available when both users are in room but sides not assigned"""
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room:
            raise ValueError("Battle room not found")
        
        # Verify user is part of this battle
        if user_id not in [battle_room.pro_user_id, battle_room.con_user_id]:
            raise ValueError("User is not part of this battle")
        
        # Check if battle is still in waiting state
        if battle_room.status != "waiting":
            raise ValueError("Battle has already started, cannot change sides")
        
        # For now, sides are already assigned during battle creation
        # This method is a placeholder for future side selection functionality
        # Currently, the creator is always pro and opponent is always con
        return battle_room
    
    def start_battle(self, battle_room_id: int) -> BattleRoom:
        """Start a battle"""
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room:
            raise ValueError("Battle room not found")
        
        print(f"=== STARTING BATTLE ===")
        print(f"Battle Room ID: {battle_room_id}")
        print(f"Current Status: {battle_room.status}")
        print(f"Pro User ID: {battle_room.pro_user_id}")
        print(f"Con User ID: {battle_room.con_user_id}")
        
        if battle_room.status != "waiting":
            raise ValueError("Battle is not in waiting state")
        
        # Update battle room
        battle_room.status = "active"
        battle_room.started_at = datetime.utcnow()
        battle_room.round_started_at = datetime.utcnow()
        battle_room.round_ends_at = datetime.utcnow() + timedelta(seconds=battle_room.round_time_limit)
        
        # Update first round
        first_round = self.db.query(BattleRound).filter(
            and_(
                BattleRound.battle_room_id == battle_room_id,
                BattleRound.round_number == 1
            )
        ).first()
        
        if first_round:
            first_round.status = "active"
            first_round.started_at = datetime.utcnow()
            print(f"Activated Round 1 with ID: {first_round.id}")
        else:
            print(f"ERROR: Round 1 not found for battle room {battle_room_id}")
            # Check what rounds exist
            all_rounds = self.db.query(BattleRound).filter(
                BattleRound.battle_room_id == battle_room_id
            ).all()
            print(f"Existing rounds: {[(r.id, r.round_number, r.status) for r in all_rounds]}")
        
        self.db.commit()
        self.db.refresh(battle_room)
        
        print(f"Battle started successfully")
        print(f"======================")
        
        return battle_room
    
    def submit_round_argument(self, battle_room_id: int, round_number: int, argument: str, user_id: int) -> BattleRound:
        """Submit an argument for a specific round"""
        # Get battle room
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room:
            raise ValueError("Battle room not found")
        
        # Verify user is part of this battle
        if user_id not in [battle_room.pro_user_id, battle_room.con_user_id]:
            raise ValueError("User is not part of this battle")
        
        # Get the round
        round_obj = self.db.query(BattleRound).filter(
            and_(
                BattleRound.battle_room_id == battle_room_id,
                BattleRound.round_number == round_number
            )
        ).first()
        
        if not round_obj:
            raise ValueError("Round not found")
        
        # Enforce sequential submission: Pro must submit before Con
        if user_id == battle_room.con_user_id and not round_obj.pro_argument:
            raise ValueError("Pro must submit their argument first")
        
        # Check if user already submitted their argument for this round
        if user_id == battle_room.pro_user_id and round_obj.pro_argument:
            raise ValueError("You have already submitted your argument for this round")
        if user_id == battle_room.con_user_id and round_obj.con_argument:
            raise ValueError("You have already submitted your argument for this round")
        
        # Determine which side the user is on and submit argument
        side = None
        if user_id == battle_room.pro_user_id:
            round_obj.pro_argument = argument
            round_obj.pro_submitted_at = datetime.utcnow()
            side = "pro"
        else:
            round_obj.con_argument = argument
            round_obj.con_submitted_at = datetime.utcnow()
            side = "con"
        
        # Check if both arguments are submitted
        if round_obj.pro_argument and round_obj.con_argument:
            round_obj.status = "completed"
            round_obj.completed_at = datetime.utcnow()
            
            # Trigger AI scoring for both arguments in background
            self._trigger_ai_scoring(battle_room_id, round_obj.id)
            
            # Auto-advance to next round or end battle
            self._advance_round_or_end_battle(battle_room_id)
        
        self.db.commit()
        self.db.refresh(round_obj)
        return round_obj
    
    def _advance_round_or_end_battle(self, battle_room_id: int):
        """Advance to next round or end the battle"""
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        
        if battle_room.current_round < battle_room.max_rounds:
            # Advance to next round
            next_round_num = battle_room.current_round + 1
            battle_room.current_round = next_round_num
            battle_room.round_started_at = datetime.utcnow()
            battle_room.round_ends_at = datetime.utcnow() + timedelta(seconds=battle_room.round_time_limit)
            
            # Update next round status
            next_round = self.db.query(BattleRound).filter(
                and_(
                    BattleRound.battle_room_id == battle_room_id,
                    BattleRound.round_number == next_round_num
                )
            ).first()
            
            if next_round:
                next_round.status = "active"
                next_round.started_at = datetime.utcnow()
        else:
            # End the battle and trigger AI result calculation
            self.end_battle(battle_room_id)
            # Trigger AI result calculation in background
            self._trigger_ai_result_calculation(battle_room_id)
    
    def end_battle(self, battle_room_id: int):
        """End a battle and determine winner"""
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room:
            raise ValueError("Battle room not found")
        
        # Calculate winner based on votes
        votes = self.db.query(Vote).filter(Vote.battle_room_id == battle_room_id).all()
        
        if votes:
            pro_votes = len([v for v in votes if v.side == "pro"])
            con_votes = len([v for v in votes if v.side == "con"])
            
            if pro_votes > con_votes:
                battle_room.winner_side = "pro"
                battle_room.winner_user_id = battle_room.pro_user_id
            elif con_votes > pro_votes:
                battle_room.winner_side = "con"
                battle_room.winner_user_id = battle_room.con_user_id
            else:
                battle_room.winner_side = "draw"
                battle_room.winner_user_id = None
        else:
            # No votes - determine based on argument completion
            completed_rounds = self.db.query(BattleRound).filter(
                and_(
                    BattleRound.battle_room_id == battle_room_id,
                    BattleRound.status == "completed"
                )
            ).count()
            
            if completed_rounds >= 2:  # At least 2 rounds completed
                battle_room.winner_side = "draw"
                battle_room.winner_user_id = None
            else:
                battle_room.winner_side = "draw"
                battle_room.winner_user_id = None
        
        battle_room.status = "completed"
        battle_room.completed_at = datetime.utcnow()
        
        # Update ELO ratings using proper Arpad Elo formula
        pro_user = self.db.query(User).filter(User.id == battle_room.pro_user_id).first()
        con_user = self.db.query(User).filter(User.id == battle_room.con_user_id).first()
        
        if pro_user and con_user:
            pro_old = pro_user.elo_rating or 400
            con_old = con_user.elo_rating or 400
            
            if battle_room.winner_side == "pro":
                pro_new, con_new = _calculate_elo_updates(pro_old, con_old, score_a=1.0)
                pro_change = pro_new - pro_old
                con_change = con_new - con_old
            elif battle_room.winner_side == "con":
                con_new, pro_new = _calculate_elo_updates(con_old, pro_old, score_a=1.0)
                pro_change = pro_new - pro_old
                con_change = con_new - con_old
            else:
                # Draw: both get 0.5 score
                pro_new, con_new = _calculate_elo_updates(pro_old, con_old, score_a=0.5)
                pro_change = pro_new - pro_old
                con_change = con_new - con_old
            
            pro_user.elo_rating = pro_new
            con_user.elo_rating = con_new
            
            # Create ELO history entries for both participants
            self.db.add(EloHistory(
                user_id=battle_room.pro_user_id,
                battle_room_id=battle_room_id,
                old_elo=pro_old,
                new_elo=pro_new,
                elo_change=pro_change
            ))
            self.db.add(EloHistory(
                user_id=battle_room.con_user_id,
                battle_room_id=battle_room_id,
                old_elo=con_old,
                new_elo=con_new,
                elo_change=con_change
            ))
        
        self.db.commit()
    
    def get_user_battles(self, user_id: int, status: str = None) -> list:
        """Get battles for a specific user"""
        query = self.db.query(BattleRoom).filter(
            or_(BattleRoom.pro_user_id == user_id, BattleRoom.con_user_id == user_id)
        )
        
        if status:
            query = query.filter(BattleRoom.status == status)
        
        return query.order_by(BattleRoom.created_at.desc()).all()
    
    def get_battle_room(self, battle_room_id: int) -> BattleRoom:
        """Get a specific battle room"""
        return self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
    
    def cast_vote(self, battle_room_id: int, voter_id: int, side: str, reasoning: str = None, 
                  confidence: int = 5, argument_quality: int = 5, clarity: int = 5, 
                  persuasiveness: int = 5, evidence: int = 5) -> Vote:
        """Cast a vote for a battle"""
        # Check if battle is completed
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room or battle_room.status != "completed":
            raise ValueError("Battle is not completed yet")
        
        # Check if user already voted
        existing_vote = self.db.query(Vote).filter(
            and_(
                Vote.battle_room_id == battle_room_id,
                Vote.voter_id == voter_id
            )
        ).first()
        
        if existing_vote:
            raise ValueError("User has already voted for this battle")
        
        # Create vote
        vote = Vote(
            battle_room_id=battle_room_id,
            voter_id=voter_id,
            side=side,
            reasoning=reasoning,
            confidence=confidence,
            argument_quality=argument_quality,
            clarity=clarity,
            persuasiveness=persuasiveness,
            evidence=evidence
        )
        
        self.db.add(vote)
        self.db.commit()
        self.db.refresh(vote)
        
        # Recalculate battle winner
        self.end_battle(battle_room_id)
        
        return vote
    
    def get_battle_rounds(self, battle_room_id: int) -> list:
        """Get all rounds for a battle"""
        return self.db.query(BattleRound).filter(
            BattleRound.battle_room_id == battle_room_id
        ).order_by(BattleRound.round_number).all()
    
    def get_battle_votes(self, battle_room_id: int) -> list:
        """Get all votes for a battle"""
        return self.db.query(Vote).filter(Vote.battle_room_id == battle_room_id).all()
    
    def _trigger_ai_scoring(self, battle_room_id: int, round_id: int):
        """Trigger AI scoring for a completed round in background"""
        try:
            from app.services.ai_scoring_service import AIScoringService
            
            def score_arguments():
                # Create new DB session for background task
                from app.database import SessionLocal
                db = SessionLocal()
                try:
                    ai_service = AIScoringService(db)
                    
                    # Get round and battle room
                    round_obj = self.db.query(BattleRound).filter(BattleRound.id == round_id).first()
                    battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
                    debate = self.db.query(Debate).filter(Debate.id == battle_room.debate_id).first()
                    
                    if round_obj and battle_room and debate:
                        # Score pro argument with con's argument as opponent context
                        if round_obj.pro_argument:
                            ai_service.score_argument(
                                round_id, "pro", round_obj.pro_argument, debate.title,
                                opponent_argument=round_obj.con_argument
                            )
                        
                        # Score con argument with pro's argument as opponent context
                        if round_obj.con_argument:
                            ai_service.score_argument(
                                round_id, "con", round_obj.con_argument, debate.title,
                                opponent_argument=round_obj.pro_argument
                            )
                finally:
                    db.close()
            
            # Run in background thread
            import threading
            thread = threading.Thread(target=score_arguments)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            print(f"Error triggering AI scoring: {e}")
    
    def _trigger_ai_result_calculation(self, battle_room_id: int):
        """Trigger AI result calculation in background with delay"""
        try:
            from app.services.ai_scoring_service import AIScoringService
            
            def calculate_delayed_result():
                # Wait 60-90 seconds before calculating results
                import time
                import random
                delay = random.uniform(60, 90)
                time.sleep(delay)
                
                # Create new DB session for background task
                from app.database import SessionLocal
                db = SessionLocal()
                try:
                    ai_service = AIScoringService(db)
                    ai_service.calculate_battle_result(battle_room_id)
                finally:
                    db.close()
            
            # Run in background thread
            import threading
            thread = threading.Thread(target=calculate_delayed_result)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            print(f"Error triggering AI result calculation: {e}")
