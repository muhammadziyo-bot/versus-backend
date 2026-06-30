from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.club import ClubDiscussion, Club, ClubComment
from app.models.user import User
from app.models.vote import DiscussionVote, CommentVote
from app.schemas.discussion import DiscussionList, DiscussionCreate, DiscussionDetail, CommentCreate, Comment
from typing import List, Optional

class DiscussionService:
    def __init__(self, db: Session):
        self.db = db

    def get_discussions(self, skip: int = 0, limit: int = 100, user_id: int = None) -> List[DiscussionList]:
        discussions = self.db.query(ClubDiscussion).join(User).outerjoin(Club).order_by(
            ClubDiscussion.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Get user's votes if user_id is provided
        user_votes = {}
        if user_id:
            votes = self.db.query(DiscussionVote).filter(
                DiscussionVote.user_id == user_id
            ).all()
            user_votes = {vote.discussion_id: vote.vote_type for vote in votes}
        
        result = []
        for discussion in discussions:
            # Count comments (replies)
            reply_count = self.db.query(ClubComment).filter(
                ClubComment.discussion_id == discussion.id
            ).count()
            
            # Determine if hot (recent activity)
            is_hot = reply_count > 20  # Simple hot logic
            
            discussion_list = DiscussionList(
                id=discussion.id,
                title=discussion.title,
                category=discussion.club.category if discussion.club else None,
                author=discussion.author.full_name or discussion.author.username,
                author_id=discussion.author_id,
                club_id=discussion.club_id,
                club_name=discussion.club.name if discussion.club else None,
                replies=reply_count,
                views=discussion.views if hasattr(discussion, 'views') else 0,
                last_activity=discussion.updated_at,
                is_pinned=False,  # Default to False since field doesn't exist
                is_hot=is_hot,
                tags=[],  # Tags feature not yet implemented
                upvotes=discussion.upvotes,
                downvotes=discussion.downvotes,
                user_vote=user_votes.get(discussion.id)
            )
            result.append(discussion_list)
        return result

    def get_stats(self) -> dict:
        total_discussions = self.db.query(ClubDiscussion).count()
        total_replies = self.db.query(ClubComment).count()
        
        # Active discussions (with recent activity)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        active_discussions = self.db.query(ClubDiscussion).filter(
            ClubDiscussion.updated_at >= recent_cutoff
        ).count()
        
        return {
            "total_discussions": total_discussions,
            "total_replies": total_replies,
            "active_discussions": active_discussions
        }

    def create_discussion(self, discussion: DiscussionCreate, author_id: int) -> DiscussionDetail:
        new_discussion = ClubDiscussion(
            title=discussion.title,
            content=discussion.content,
            author_id=author_id,
            club_id=discussion.club_id,
            upvotes=0,
            downvotes=0
        )
        self.db.add(new_discussion)
        self.db.commit()
        self.db.refresh(new_discussion)
        
        return self.get_discussion_by_id(new_discussion.id)

    def get_discussion_by_id(self, discussion_id: int, user_id: int = None) -> Optional[DiscussionDetail]:
        discussion = self.db.query(ClubDiscussion).filter(
            ClubDiscussion.id == discussion_id
        ).first()
        
        if not discussion:
            return None
        
        # Increment view count
        if hasattr(discussion, 'views'):
            discussion.views += 1
            self.db.commit()
        
        # Get all comments for this discussion
        comments = self.db.query(ClubComment).filter(
            ClubComment.discussion_id == discussion_id,
            ClubComment.parent_id.is_(None)
        ).all()
        
        # Get user's comment votes if user_id is provided
        user_comment_votes = {}
        if user_id:
            comment_votes = self.db.query(CommentVote).filter(
                CommentVote.user_id == user_id
            ).all()
            user_comment_votes = {vote.comment_id: vote.vote_type for vote in comment_votes}
        
        # Build comment tree
        comment_tree = [self._build_comment_tree(comment, user_comment_votes) for comment in comments]
        
        # Get user's vote for this discussion
        user_vote = None
        if user_id:
            discussion_vote = self.db.query(DiscussionVote).filter(
                DiscussionVote.user_id == user_id,
                DiscussionVote.discussion_id == discussion_id
            ).first()
            if discussion_vote:
                user_vote = discussion_vote.vote_type
        
        return DiscussionDetail(
            id=discussion.id,
            title=discussion.title,
            content=discussion.content,
            author=discussion.author.full_name or discussion.author.username,
            author_id=discussion.author_id,
            club_id=discussion.club_id,
            club_name=discussion.club.name if discussion.club else None,
            upvotes=discussion.upvotes,
            downvotes=discussion.downvotes,
            user_vote=user_vote,
            created_at=discussion.created_at,
            updated_at=discussion.updated_at,
            tags=[],
            comments=comment_tree
        )

    def _build_comment_tree(self, comment: ClubComment, user_comment_votes: dict = None) -> Comment:
        # Get replies
        replies = self.db.query(ClubComment).filter(
            ClubComment.parent_id == comment.id
        ).all()
        
        return Comment(
            id=comment.id,
            content=comment.content,
            author=comment.author.full_name or comment.author.username,
            author_id=comment.author_id,
            discussion_id=comment.discussion_id,
            parent_id=comment.parent_id,
            upvotes=comment.upvotes,
            downvotes=comment.downvotes,
            created_at=comment.created_at,
            user_vote=user_comment_votes.get(comment.id) if user_comment_votes else None,
            replies=[self._build_comment_tree(reply, user_comment_votes) for reply in replies]
        )

    def create_comment(self, discussion_id: int, comment: CommentCreate, author_id: int) -> Comment:
        new_comment = ClubComment(
            content=comment.content,
            author_id=author_id,
            discussion_id=discussion_id,
            parent_id=comment.parent_id,
            upvotes=0,
            downvotes=0
        )
        self.db.add(new_comment)
        self.db.commit()
        self.db.refresh(new_comment)
        
        return self._build_comment_tree(new_comment)

    def vote_discussion(self, discussion_id: int, vote_type: str, user_id: int = None) -> Optional[DiscussionDetail]:
        discussion = self.db.query(ClubDiscussion).filter(
            ClubDiscussion.id == discussion_id
        ).first()
        
        if not discussion:
            return None
        
        if user_id is None:
            # Legacy behavior: just increment (shouldn't be used)
            if vote_type == 'up':
                discussion.upvotes += 1
            elif vote_type == 'down':
                discussion.downvotes += 1
        else:
            # Check if user has already voted
            existing_vote = self.db.query(DiscussionVote).filter(
                DiscussionVote.user_id == user_id,
                DiscussionVote.discussion_id == discussion_id
            ).first()
            
            if existing_vote:
                if existing_vote.vote_type == vote_type:
                    # Remove vote (toggle off)
                    self.db.delete(existing_vote)
                    if vote_type == 'up':
                        discussion.upvotes = max(0, discussion.upvotes - 1)
                    elif vote_type == 'down':
                        discussion.downvotes = max(0, discussion.downvotes - 1)
                else:
                    # Change vote
                    existing_vote.vote_type = vote_type
                    if vote_type == 'up':
                        discussion.upvotes += 1
                        discussion.downvotes = max(0, discussion.downvotes - 1)
                    elif vote_type == 'down':
                        discussion.downvotes += 1
                        discussion.upvotes = max(0, discussion.upvotes - 1)
            else:
                # New vote
                new_vote = DiscussionVote(
                    user_id=user_id,
                    discussion_id=discussion_id,
                    vote_type=vote_type
                )
                self.db.add(new_vote)
                if vote_type == 'up':
                    discussion.upvotes += 1
                elif vote_type == 'down':
                    discussion.downvotes += 1
        
        self.db.commit()
        self.db.refresh(discussion)
        
        return self.get_discussion_by_id(discussion_id, user_id)

    def vote_comment(self, comment_id: int, vote_type: str, user_id: int = None) -> Optional[Comment]:
        comment = self.db.query(ClubComment).filter(
            ClubComment.id == comment_id
        ).first()
        
        if not comment:
            return None
        
        if user_id is None:
            # Legacy behavior: just increment (shouldn't be used)
            if vote_type == 'up':
                comment.upvotes += 1
            elif vote_type == 'down':
                comment.downvotes += 1
        else:
            # Check if user has already voted
            existing_vote = self.db.query(CommentVote).filter(
                CommentVote.user_id == user_id,
                CommentVote.comment_id == comment_id
            ).first()
            
            if existing_vote:
                if existing_vote.vote_type == vote_type:
                    # Remove vote (toggle off)
                    self.db.delete(existing_vote)
                    if vote_type == 'up':
                        comment.upvotes = max(0, comment.upvotes - 1)
                    elif vote_type == 'down':
                        comment.downvotes = max(0, comment.downvotes - 1)
                else:
                    # Change vote
                    existing_vote.vote_type = vote_type
                    if vote_type == 'up':
                        comment.upvotes += 1
                        comment.downvotes = max(0, comment.downvotes - 1)
                    elif vote_type == 'down':
                        comment.downvotes += 1
                        comment.upvotes = max(0, comment.upvotes - 1)
            else:
                # New vote
                new_vote = CommentVote(
                    user_id=user_id,
                    comment_id=comment_id,
                    vote_type=vote_type
                )
                self.db.add(new_vote)
                if vote_type == 'up':
                    comment.upvotes += 1
                elif vote_type == 'down':
                    comment.downvotes += 1
        
        self.db.commit()
        self.db.refresh(comment)
        
        # Get user votes for the response
        user_comment_votes = {}
        if user_id:
            comment_votes = self.db.query(CommentVote).filter(
                CommentVote.user_id == user_id
            ).all()
            user_comment_votes = {vote.comment_id: vote.vote_type for vote in comment_votes}
        
        return self._build_comment_tree(comment, user_comment_votes)
