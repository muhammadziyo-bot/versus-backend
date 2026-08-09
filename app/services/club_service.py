from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.club import Club, ClubDiscussion, club_members
from app.models.user import User
from app.models.debate import BattleRoom
from app.schemas.club import ClubCreate, ClubUpdate, ClubList, ClubResponse, ClubMember, ClubSearchResult

class ClubService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_battles_counts(self, club_ids: list) -> dict:
        """Count active battles for a set of clubs in a single query."""
        if not club_ids:
            return {}

        # Subquery: map club -> member ids
        member_join = (
            self.db.query(
                club_members.c.club_id.label("club_id"),
                club_members.c.user_id.label("user_id"),
            )
            .filter(club_members.c.club_id.in_(club_ids))
            .subquery()
        )

        rows = (
            self.db.query(
                member_join.c.club_id,
                func.count(func.distinct(BattleRoom.id)),
            )
            .join(
                BattleRoom,
                or_(
                    BattleRoom.pro_user_id == member_join.c.user_id,
                    BattleRoom.con_user_id == member_join.c.user_id,
                ),
            )
            .filter(BattleRoom.status.in_(["waiting", "active"]))
            .group_by(member_join.c.club_id)
            .all()
        )

        return {club_id: count for club_id, count in rows}

    def get_clubs(self, skip: int = 0, limit: int = 100, user_id: int = None) -> ClubSearchResult:
        clubs = self.db.query(Club).filter(Club.is_active == True).offset(skip).limit(limit).all()
        total = self.db.query(Club).filter(Club.is_active == True).count()

        club_ids = [club.id for club in clubs]
        result = self._build_club_list_items(clubs, club_ids, user_id)

        return ClubSearchResult(total=total, items=result)

    def search_clubs(self, query: str = None, category: str = None, user_id: int = None,
                     skip: int = 0, limit: int = 100, sort_by: str = "newest") -> ClubSearchResult:
        q = self.db.query(Club).filter(Club.is_active == True)

        if query:
            like = f"%{query.lower()}%"
            q = q.filter(
                or_(
                    func.lower(Club.name).like(like),
                    func.lower(Club.description).like(like),
                    func.lower(Club.category).like(like),
                )
            )

        if category and category != "All":
            q = q.filter(Club.category == category)

        if sort_by == "members":
            member_count_subq = (
                self.db.query(
                    club_members.c.club_id.label("club_id"),
                    func.count(club_members.c.user_id).label("cnt"),
                ).group_by(club_members.c.club_id).subquery()
            )
            q = q.outerjoin(member_count_subq, member_count_subq.c.club_id == Club.id)
            q = q.order_by(member_count_subq.c.cnt.desc(), Club.created_at.desc())
        elif sort_by == "oldest":
            q = q.order_by(Club.created_at.asc())
        else:
            q = q.order_by(Club.created_at.desc())

        total = q.count()
        clubs = q.offset(skip).limit(limit).all()
        club_ids = [club.id for club in clubs]
        items = self._build_club_list_items(clubs, club_ids, user_id)

        return ClubSearchResult(total=total, items=items)

    def _build_club_list_items(self, clubs, club_ids: list, user_id: int = None) -> list:
        if not clubs:
            return []

        # Batch: member counts
        member_counts = dict(
            self.db.query(
                club_members.c.club_id,
                func.count(club_members.c.user_id),
            )
            .filter(club_members.c.club_id.in_(club_ids))
            .group_by(club_members.c.club_id)
            .all()
        )

        # Batch: user memberships
        user_memberships = set()
        if user_id:
            user_memberships = set(
                row[0]
                for row in self.db.query(club_members.c.club_id)
                .filter(
                    club_members.c.club_id.in_(club_ids),
                    club_members.c.user_id == user_id,
                )
                .all()
            )

        # Batch: founders
        founder_ids = {club.founder_id for club in clubs if club.founder_id}
        founder_names = {}
        if founder_ids:
            founder_names = {
                user.id: user.username
                for user in self.db.query(User).filter(User.id.in_(founder_ids)).all()
            }

        # Batch: active battles
        active_battles = self.get_active_battles_counts(club_ids)

        # Batch: discussion counts
        discussion_counts = dict(
            self.db.query(
                ClubDiscussion.club_id,
                func.count(ClubDiscussion.id),
            )
            .filter(ClubDiscussion.club_id.in_(club_ids), ClubDiscussion.is_active == True)
            .group_by(ClubDiscussion.club_id)
            .all()
        )

        result = []
        for club in clubs:
            result.append(ClubList(
                id=club.id,
                name=club.name,
                description=club.description,
                category=club.category,
                badge=club.badge,
                member_count=member_counts.get(club.id, 0),
                active_battles=active_battles.get(club.id, 0),
                discussion_count=discussion_counts.get(club.id, 0),
                is_member=club.id in user_memberships,
                founder=founder_names.get(club.founder_id, "Unknown"),
            ))
        return result

    def get_club(self, club_id: int, user_id: int = None):
        club = self.db.query(Club).filter(Club.id == club_id).first()
        if not club:
            return None

        # Founder name
        founder = None
        if club.founder_id:
            founder = self.db.query(User).filter(User.id == club.founder_id).first()
        founder_name = founder.username if founder else "Unknown"

        # Get members
        members_data = self.db.query(User).join(club_members).filter(
            club_members.c.club_id == club_id
        ).all()

        members = [ClubMember(id=m.id, username=m.username, full_name=m.full_name) for m in members_data]

        # Discussion count
        discussion_count = self.db.query(ClubDiscussion).filter(
            ClubDiscussion.club_id == club_id,
            ClubDiscussion.is_active == True
        ).count()

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
            founder=founder_name,
            founder_id=club.founder_id,
            is_active=club.is_active,
            created_at=club.created_at,
            updated_at=club.updated_at,
            members=members,
            member_count=len(members),
            active_battles=self.get_active_battles_counts([club_id]).get(club_id, 0),
            discussion_count=discussion_count,
            is_member=is_member
        )

    def get_user_clubs(self, user_id: int) -> list:
        club_ids = [
            row[0]
            for row in self.db.query(club_members.c.club_id)
            .filter(club_members.c.user_id == user_id)
            .all()
        ]
        if not club_ids:
            return []
        clubs = self.db.query(Club).filter(Club.id.in_(club_ids)).all()
        return self._build_club_list_items(clubs, club_ids, user_id)

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

    def update_club(self, club_id: int, updates: ClubUpdate, user_id: int):
        club = self.db.query(Club).filter(Club.id == club_id).first()
        if not club:
            return None
        if club.founder_id != user_id:
            raise PermissionError("Only the club founder can edit the club")

        data = updates.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(club, field, value)
        self.db.commit()
        self.db.refresh(club)
        return club

    def delete_club(self, club_id: int, user_id: int):
        club = self.db.query(Club).filter(Club.id == club_id).first()
        if not club:
            return False
        if club.founder_id != user_id:
            raise PermissionError("Only the club founder can delete the club")
        self.db.delete(club)
        self.db.commit()
        return True

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
