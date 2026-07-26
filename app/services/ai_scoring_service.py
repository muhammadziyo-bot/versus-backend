import os
import json
import time
import random
from typing import Dict, List, Optional
from groq import Groq
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.debate import BattleRoom, BattleRound, AIArgumentScore, AIBattleResult, Debate
from app.models.user import User

MAX_SCORE_RETRIES = 3
BASE_RETRY_DELAY = 1
GROQ_TIMEOUT = 20


class AIScoringService:
    """Service for AI-powered debate scoring using Groq"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
    
    def score_argument(self, battle_round_id: int, side: str, argument: str, topic: str, opponent_argument: Optional[str] = None) -> AIArgumentScore:
        """
        Score a single argument using AI with retry logic and timeout
        Only uses provided debate data, no external information
        """
        prompt = self._create_scoring_prompt(argument, topic, side, opponent_argument)
        last_error = None
        
        for attempt in range(MAX_SCORE_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an impartial debate judge. Score arguments ONLY based on the provided content. Do not use external knowledge or hallucinate facts. Be fair and objective."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    timeout=GROQ_TIMEOUT
                )
                
                scoring_data = json.loads(response.choices[0].message.content)
                
                ai_score = AIArgumentScore(
                    battle_round_id=battle_round_id,
                    side=side,
                    score_status="completed",
                    retry_count=attempt,
                    logical_coherence=scoring_data.get("logical_coherence", 5),
                    evidence_quality=scoring_data.get("evidence_quality", 5),
                    clarity=scoring_data.get("clarity", 5),
                    relevance=scoring_data.get("relevance", 5),
                    counter_effectiveness=scoring_data.get("counter_effectiveness", 5),
                    overall_score=scoring_data.get("overall_score", 5),
                    strengths=scoring_data.get("strengths", ""),
                    weaknesses=scoring_data.get("weaknesses", ""),
                    detailed_feedback=scoring_data.get("detailed_feedback", ""),
                    model_used=self.model
                )
                
                self.db.add(ai_score)
                self.db.commit()
                self.db.refresh(ai_score)
                
                return ai_score
                
            except Exception as e:
                last_error = str(e)
                print(f"Error scoring argument (attempt {attempt + 1}/{MAX_SCORE_RETRIES}): {last_error}")
                
                if attempt < MAX_SCORE_RETRIES - 1:
                    delay = BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(delay)
        
        # All retries exhausted — record failure, do NOT silently produce default scores
        print(f"All {MAX_SCORE_RETRIES} attempts failed. Recording failed score status.")
        ai_score = AIArgumentScore(
            battle_round_id=battle_round_id,
            side=side,
            score_status="failed",
            retry_count=MAX_SCORE_RETRIES,
            error_message=last_error,
            overall_score=0,
            strengths="",
            weaknesses="",
            detailed_feedback=f"AI scoring failed after {MAX_SCORE_RETRIES} attempts: {last_error}",
            model_used=self.model
        )
        
        self.db.add(ai_score)
        self.db.commit()
        self.db.refresh(ai_score)
        
        return ai_score
    
    def _create_scoring_prompt(self, argument: str, topic: str, side: str, opponent_argument: Optional[str] = None) -> str:
        """Create a strict prompt for argument scoring"""
        opponent_section = ""
        if opponent_argument:
            opponent_section = f"""
OPPONENT'S ARGUMENT (from this round): {opponent_argument}

CRITICAL: Evaluate 'Counter-Effectiveness' based on how well the argument directly addresses 
and refutes the OPPONENT'S ARGUMENT above. Do NOT hallucinate what the opponent said."""

        return f"""Score this debate argument objectively. Use ONLY the information provided below.

DEBATE TOPIC: {topic}
ARGUMENT SIDE: {side.upper()}
ARGUMENT TEXT: {argument}{opponent_section}

Score the argument on these criteria (1-10 scale):
1. Logical Coherence: How well does the argument flow logically?
2. Evidence Quality: How strong is the supporting evidence (only from what's provided)?
3. Clarity: How clear and understandable is the argument?
4. Relevance: How relevant is the argument to the debate topic?
5. Counter-Effectiveness: {("How well does this argument directly address and refute the opponent's argument provided above?" if opponent_argument else "How well does this argument counter potential opposing views?")}

Provide your response as a JSON object with this exact structure:
{{
    "logical_coherence": <1-10>,
    "evidence_quality": <1-10>,
    "clarity": <1-10>,
    "relevance": <1-10>,
    "counter_effectiveness": <1-10>,
    "overall_score": <1-10>,
    "strengths": "<specific strengths based ONLY on the argument>",
    "weaknesses": "<specific weaknesses based ONLY on the argument>",
    "detailed_feedback": "<comprehensive analysis based ONLY on the argument>"
}}

Important: Base your evaluation ENTIRELY on the argument text provided. Do not introduce external facts or knowledge."""
    
    def calculate_battle_result(self, battle_room_id: int) -> AIBattleResult:
        """
        Calculate final battle result from all AI scores
        This runs in background after battle completion
        """
        # Get battle room
        battle_room = self.db.query(BattleRoom).filter(BattleRoom.id == battle_room_id).first()
        if not battle_room:
            raise ValueError("Battle room not found")
        
        # Get debate topic
        debate = self.db.query(Debate).filter(Debate.id == battle_room.debate_id).first()
        topic = debate.title if debate else "Unknown topic"
        
        # Create AI battle result record
        ai_result = AIBattleResult(
            battle_room_id=battle_room_id,
            status="processing",
            processing_started_at=datetime.utcnow(),
            model_used=self.model
        )
        self.db.add(ai_result)
        self.db.commit()
        self.db.refresh(ai_result)
        
        try:
            # Get all battle rounds
            rounds = self.db.query(BattleRound).filter(
                BattleRound.battle_room_id == battle_room_id
            ).order_by(BattleRound.round_number).all()
            
            pro_total = 0
            con_total = 0
            round_breakdown = []
            
            # Calculate scores for each round
            for round_obj in rounds:
                # Get AI scores for this round
                pro_score = self.db.query(AIArgumentScore).filter(
                    AIArgumentScore.battle_round_id == round_obj.id,
                    AIArgumentScore.side == "pro"
                ).first()
                
                con_score = self.db.query(AIArgumentScore).filter(
                    AIArgumentScore.battle_round_id == round_obj.id,
                    AIArgumentScore.side == "con"
                ).first()
                
                # Add to totals (weight later rounds higher)
                # Skip failed scores to avoid counting garbage data
                round_weight = 1.0 + (round_obj.round_number * 0.2)  # Round 1: 1.0, Round 2: 1.2, Round 3: 1.4
                
                pro_valid = pro_score and pro_score.score_status == "completed"
                con_valid = con_score and con_score.score_status == "completed"
                
                if pro_valid:
                    pro_total += pro_score.overall_score * round_weight
                
                if con_valid:
                    con_total += con_score.overall_score * round_weight
                
                # Store round breakdown
                round_breakdown.append({
                    "round_number": round_obj.round_number,
                    "pro_score": pro_score.overall_score if pro_valid else None,
                    "con_score": con_score.overall_score if con_valid else None,
                    "pro_scoring_status": pro_score.score_status if pro_score else "missing",
                    "con_scoring_status": con_score.score_status if con_score else "missing",
                    "pro_strengths": pro_score.strengths if pro_valid else "",
                    "pro_weaknesses": pro_score.weaknesses if pro_valid else "",
                    "con_strengths": con_score.strengths if con_valid else "",
                    "con_weaknesses": con_score.weaknesses if con_valid else ""
                })
            
            # Determine winner
            winner_side = "draw"
            confidence = 5
            
            if pro_total > con_total:
                winner_side = "pro"
                confidence = min(10, 5 + int((pro_total - con_total) / 2))
            elif con_total > pro_total:
                winner_side = "con"
                confidence = min(10, 5 + int((con_total - pro_total) / 2))
            
            # Generate comprehensive analysis
            overall_analysis = self._generate_battle_analysis(
                topic, rounds, round_breakdown, winner_side, pro_total, con_total
            )
            
            # Aggregate strengths and weaknesses
            pro_strengths = self._aggregate_strengths(round_breakdown, "pro")
            pro_weaknesses = self._aggregate_weaknesses(round_breakdown, "pro")
            con_strengths = self._aggregate_strengths(round_breakdown, "con")
            con_weaknesses = self._aggregate_weaknesses(round_breakdown, "con")
            
            # Update AI result
            ai_result.pro_total_score = int(pro_total)
            ai_result.con_total_score = int(con_total)
            ai_result.winner_side = winner_side
            ai_result.confidence = confidence
            ai_result.pro_strengths = pro_strengths
            ai_result.pro_weaknesses = pro_weaknesses
            ai_result.con_strengths = con_strengths
            ai_result.con_weaknesses = con_weaknesses
            ai_result.overall_analysis = overall_analysis
            ai_result.round_breakdown = round_breakdown
            ai_result.status = "completed"
            ai_result.processing_completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(ai_result)
            
            return ai_result
            
        except Exception as e:
            print(f"Error calculating battle result: {e}")
            ai_result.status = "failed"
            ai_result.error_message = str(e)
            ai_result.processing_completed_at = datetime.utcnow()
            self.db.commit()
            raise
    
    def _generate_battle_analysis(self, topic: str, rounds: List[BattleRound], 
                                  round_breakdown: List[Dict], winner_side: str,
                                  pro_total: float, con_total: float) -> str:
        """Generate comprehensive battle analysis using AI"""
        
        # Prepare round summaries for the AI
        round_summaries = []
        for i, round_data in enumerate(round_breakdown):
            round_summaries.append(f"""
Round {round_data['round_number']}:
- Pro Score: {round_data['pro_score']}/10
- Con Score: {round_data['con_score']}/10
- Pro Strengths: {round_data['pro_strengths']}
- Pro Weaknesses: {round_data['pro_weaknesses']}
- Con Strengths: {round_data['con_strengths']}
- Con Weaknesses: {round_data['con_weaknesses']}
""")
        
        prompt = f"""Analyze this debate objectively. Use ONLY the information provided.

DEBATE TOPIC: {topic}
WINNER: {winner_side.upper()}
FINAL SCORES - Pro: {pro_total:.1f}, Con: {con_total:.1f}

ROUND-BY-ROUND DETAILS:
{"".join(round_summaries)}

Provide a comprehensive analysis (200-300 words) covering:
1. Overall debate quality
2. Key turning points
3. Strengths of the winning side
4. Areas where the losing side could improve
5. Notable argumentation patterns

Base your analysis ENTIRELY on the scoring data provided above. Do not introduce external information."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an impartial debate analyst. Analyze debates ONLY based on provided scoring data. Be objective and insightful."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error generating battle analysis: {e}")
            return f"AI analysis generation failed: {str(e)}"
    
    def _aggregate_strengths(self, round_breakdown: List[Dict], side: str) -> str:
        """Aggregate strengths from all rounds for a side"""
        strengths = []
        for round_data in round_breakdown:
            strength = round_data.get(f"{side}_strengths", "")
            if strength and strength not in strengths:
                strengths.append(strength)
        return " | ".join(strengths) if strengths else "No notable strengths identified"
    
    def _aggregate_weaknesses(self, round_breakdown: List[Dict], side: str) -> str:
        """Aggregate weaknesses from all rounds for a side"""
        weaknesses = []
        for round_data in round_breakdown:
            weakness = round_data.get(f"{side}_weaknesses", "")
            if weakness and weakness not in weaknesses:
                weaknesses.append(weakness)
        return " | ".join(weaknesses) if weaknesses else "No notable weaknesses identified"
    
    def calculate_calibration(self, battle_room_id: int) -> dict:
        """Calculate AI vs community score calibration for a battle"""
        from app.models.debate import Vote as BattleVote
        
        votes = self.db.query(BattleVote).filter(BattleVote.battle_room_id == battle_room_id).all()
        rounds = self.db.query(BattleRound).filter(
            BattleRound.battle_room_id == battle_room_id
        ).all()
        
        round_calibrations = []
        for round_obj in rounds:
            ai_scores = self.db.query(AIArgumentScore).filter(
                AIArgumentScore.battle_round_id == round_obj.id
            ).all()
            
            round_data = {"round_number": round_obj.round_number, "sides": []}
            
            for ai_score in ai_scores:
                side_votes = [
                    v for v in votes
                    if v.side == ai_score.side
                ]
                
                side_data = {
                    "side": ai_score.side,
                    "ai_score": ai_score.overall_score,
                    "community_average": None,
                    "score_deviation": None,
                    "calibration_status": ai_score.calibration_status,
                    "vote_count": len(side_votes),
                }
                
                if side_votes:
                    community_avg = sum(
                        (v.argument_quality + v.clarity + v.persuasiveness + v.evidence) / 4
                        for v in side_votes
                    ) / len(side_votes)
                    community_avg_rounded = round(community_avg)
                    
                    ai_score.community_average_score = community_avg_rounded
                    ai_score.score_deviation = ai_score.overall_score - community_avg_rounded
                    ai_score.calibration_status = "calibrated"
                    
                    side_data["community_average"] = community_avg_rounded
                    side_data["score_deviation"] = ai_score.score_deviation
                
                round_data["sides"].append(side_data)
            
            round_calibrations.append(round_data)
        
        self.db.commit()
        return {"rounds": round_calibrations}
    
    def get_battle_result(self, battle_room_id: int) -> Optional[AIBattleResult]:
        """Get AI battle result for a battle room"""
        return self.db.query(AIBattleResult).filter(
            AIBattleResult.battle_room_id == battle_room_id
        ).first()
    
    def get_argument_scores(self, battle_round_id: int) -> List[AIArgumentScore]:
        """Get all AI scores for a specific round"""
        return self.db.query(AIArgumentScore).filter(
            AIArgumentScore.battle_round_id == battle_round_id
        ).all()
