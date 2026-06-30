from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.club import Club, club_members
from app.models.user import User
from app.models.debate import BattleRoom
from app.schemas.club import ClubCreate, ClubList, ClubResponse, ClubMember

class ClubService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_battles_count(self, club_id: int) -> int:
        """Count active battles involving club members"""
        # Get all club member IDs
        member_ids = [row[0] for row in self.db.query(club_members.c.user_id).filter(
            club_members.c.club_id == club_id
        ).all()]
        
        if not member_ids:
            return 0
        
        # Count active battles where club members are participants
        active_battles_count = self.db.query(BattleRoom).filter(
            BattleRoom.status.in_(["waiting", "active"]),
            (BattleRoom.pro_user_id.in_(member_ids)) | (BattleRoom.con_user_id.in_(member_ids))
        ).count()
        
        return active_battles_count

    def get_clubs(self, skip: int = 0, limit: int = 100, user_id: int = None):
        clubs = self.db.query(Club).offset(skip).limit(limit).all()
        result = []
        for club in clubs:
            member_count = self.db.query(club_members).filter(
                club_members.c.club_id == club.id
            ).count()
            
            # Check if current user is a member
            is_member = False
            if user_id:
                is_member = self.db.query(club_members).filter(
                    club_members.c.club_id == club.id,
                    club_members.c.user_id == user_id
                ).first() is not None
            
            # Get founder name
            founder = self.db.query(User).filter(User.id == club.founder_id).first()
            founder_name = founder.username if founder else "Unknown"
            
            club_list = ClubList(
                id=club.id,
                name=club.name,
                description=club.description,
                category=club.category,
                badge=club.badge,
                member_count=member_count,
                active_battles=self.get_active_battles_count(club.id),
                is_member=is_member,
                founder=founder_name
            )
            result.append(club_list)
        return result

    def get_club(self, club_id: int, user_id: int = None):
        club = self.db.query(Club).filter(Club.id == club_id).first()
        if not club:
            return None
        
        # Get members
        members_data = self.db.query(User).join(club_members).filter(
            club_members.c.club_id == club_id
        ).all()
        
        members = [ClubMember(id=m.id, username=m.username, full_name=m.full_name) for m in members_data]
        
        # Check if current user is a member
        is_member = False
        if user_id:
            is_member = self.db.query(club_members).filter(
                club_members.c.club_id == club_id,
                club_members.c.user_id == user_id
            ).first() is not None
        
        return ClubResponse(
            id=club.id,
            name=club.name,
            description=club.description,
            category=club.category,
            badge=club.badge,
            founder_id=club.founder_id,
            is_active=club.is_active,
            created_at=club.created_at,
            updated_at=club.updated_at,
            members=members,
            member_count=len(members),
            active_battles=self.get_active_battles_count(club_id),
            is_member=is_member
        )

    def create_club(self, club: ClubCreate, founder_id: int):
        db_club = Club(**club.dict(), founder_id=founder_id)
        self.db.add(db_club)
        self.db.commit()
        self.db.refresh(db_club)
        
        # Add founder as member and admin
        self.db.execute(
            club_members.insert().values(
                club_id=db_club.id,
                user_id=founder_id,
                is_admin=True
            )
        )
        self.db.commit()
        
        return db_club

    def get_stats(self):
        total_clubs = self.db.query(Club).count()
        active_clubs = self.db.query(Club).filter(Club.is_active == True).count()
        
        # Get total members across all clubs
        total_members = self.db.query(club_members).distinct().count()
        
        return {
            "total_clubs": total_clubs,
            "active_clubs": active_clubs,
            "total_members": total_members
        }
