from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Debate(Base):
    __tablename__ = "debates"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)
    status = Column(String, default="active")  # active, completed, cancelled
    created_by = Column(Integer, ForeignKey("app_users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="debates")
    arguments = relationship("Argument", back_populates="debate")
    battle_rooms = relationship("BattleRoom", back_populates="debate")

class Argument(Base):
    __tablename__ = "arguments"
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    side = Column(String, nullable=False)  # pro, con
    author_id = Column(Integer, ForeignKey("app_users.id"))
    debate_id = Column(Integer, ForeignKey("debates.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    author = relationship("User")
    debate = relationship("Debate", back_populates="arguments")

class BattleRoom(Base):
    __tablename__ = "battle_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    debate_id = Column(Integer, ForeignKey("debates.id"))
    pro_user_id = Column(Integer, ForeignKey("app_users.id"))
    con_user_id = Column(Integer, ForeignKey("app_users.id"))
    status = Column(String, default="waiting")  # waiting, active, completed
    current_round = Column(Integer, default=1)
    max_rounds = Column(Integer, default=3)
    round_time_limit = Column(Integer, default=300)  # seconds
    
    # Enhanced battle timing
    started_at = Column(DateTime(timezone=True))
    round_started_at = Column(DateTime(timezone=True))
    round_ends_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Battle results
    winner_side = Column(String)  # "pro", "con", "draw"
    winner_user_id = Column(Integer, ForeignKey("app_users.id"))
    
    # Relationships
    debate = relationship("Debate", back_populates="battle_rooms")
    pro_user = relationship("User", foreign_keys=[pro_user_id])
    con_user = relationship("User", foreign_keys=[con_user_id])
    votes = relationship("Vote", back_populates="battle_room")

class Vote(Base):
    __tablename__ = "votes"
    
    id = Column(Integer, primary_key=True, index=True)
    battle_room_id = Column(Integer, ForeignKey("battle_rooms.id"))
    voter_id = Column(Integer, ForeignKey("app_users.id"))
    side = Column(String, nullable=False)  # pro, con
    
    # Enhanced voting criteria
    reasoning = Column(Text)
    confidence = Column(Integer, default=5)  # 1-10 scale
    argument_quality = Column(Integer, default=5)  # 1-10
    clarity = Column(Integer, default=5)  # 1-10
    persuasiveness = Column(Integer, default=5)  # 1-10
    evidence = Column(Integer, default=5)  # 1-10
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    battle_room = relationship("BattleRoom", back_populates="votes")
    voter = relationship("User")

class BattleRound(Base):
    __tablename__ = "battle_rounds"
    
    id = Column(Integer, primary_key=True, index=True)
    battle_room_id = Column(Integer, ForeignKey("battle_rooms.id"))
    round_number = Column(Integer, nullable=False)
    status = Column(String, default="waiting")  # waiting, active, completed
    
    # Round arguments
    pro_argument = Column(Text)
    con_argument = Column(Text)
    pro_submitted_at = Column(DateTime(timezone=True))
    con_submitted_at = Column(DateTime(timezone=True))
    
    # Round timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    battle_room = relationship("BattleRoom")

class EloHistory(Base):
    __tablename__ = "elo_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    battle_room_id = Column(Integer, ForeignKey("battle_rooms.id"), nullable=True)
    old_elo = Column(Integer, nullable=False)
    new_elo = Column(Integer, nullable=False)
    elo_change = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    battle_room = relationship("BattleRoom")

class AIArgumentScore(Base):
    __tablename__ = "ai_argument_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    battle_round_id = Column(Integer, ForeignKey("battle_rounds.id"), nullable=False)
    side = Column(String, nullable=False)  # "pro" or "con"
    
    # AI scoring criteria (1-10 scale)
    logical_coherence = Column(Integer, default=5)
    evidence_quality = Column(Integer, default=5)
    clarity = Column(Integer, default=5)
    relevance = Column(Integer, default=5)
    counter_effectiveness = Column(Integer, default=5)
    
    # Overall score and analysis
    overall_score = Column(Integer, default=5)
    strengths = Column(Text)  # AI-generated strengths
    weaknesses = Column(Text)  # AI-generated weaknesses
    detailed_feedback = Column(Text)  # Comprehensive AI analysis
    
    # Metadata
    model_used = Column(String)  # Which AI model scored this
    scored_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    battle_round = relationship("BattleRound")

class AIBattleResult(Base):
    __tablename__ = "ai_battle_results"
    
    id = Column(Integer, primary_key=True, index=True)
    battle_room_id = Column(Integer, ForeignKey("battle_rooms.id"), nullable=False)
    
    # Final scores
    pro_total_score = Column(Integer, default=0)
    con_total_score = Column(Integer, default=0)
    winner_side = Column(String)  # "pro", "con", "draw"
    confidence = Column(Integer, default=5)  # AI's confidence in the decision (1-10)
    
    # Detailed breakdown
    pro_strengths = Column(Text)
    pro_weaknesses = Column(Text)
    con_strengths = Column(Text)
    con_weaknesses = Column(Text)
    overall_analysis = Column(Text)  # Comprehensive battle analysis
    
    # Round-by-round breakdown
    round_breakdown = Column(JSON)  # Store detailed round analysis
    
    # Processing status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Metadata
    model_used = Column(String)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    battle_room = relationship("BattleRoom")
