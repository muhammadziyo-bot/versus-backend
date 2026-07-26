from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_current_admin_user
from app.models.user import User
from app.models.moderation import Report, UserBan
from app.models.club import ClubDiscussion, ClubComment
from app.models.debate import Argument, Debate

router = APIRouter(prefix="/api/moderation", tags=["moderation"])


class ReportCreate(BaseModel):
    reported_user_id: int
    target_type: str
    target_id: int
    reason: str
    description: Optional[str] = None


class ReportResolve(BaseModel):
    resolution: str
    resolution_note: Optional[str] = None


class UserBanCreate(BaseModel):
    ban_type: str = "mute"
    reason: str
    expires_at: Optional[datetime] = None


class ReportResponse(BaseModel):
    id: int
    reporter_id: int
    reported_user_id: int
    target_type: str
    target_id: int
    reason: str
    description: Optional[str] = None
    status: str
    resolution: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("/report", status_code=status.HTTP_201_CREATED)
def create_report(
    report_data: ReportCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    reported_user = db.query(User).filter(User.id == report_data.reported_user_id).first()
    if not reported_user:
        raise HTTPException(status_code=404, detail="Reported user not found")

    if reported_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    report = Report(
        reporter_id=current_user.id,
        reported_user_id=report_data.reported_user_id,
        target_type=report_data.target_type,
        target_id=report_data.target_id,
        reason=report_data.reason,
        description=report_data.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {"message": "Report submitted", "report_id": report.id}


@router.get("/reports", response_model=List[ReportResponse])
def list_reports(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter)
    reports = query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()
    return reports


@router.post("/reports/{report_id}/resolve")
def resolve_report(
    report_id: int,
    resolve_data: ReportResolve,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = "resolved"
    report.resolution = resolve_data.resolution
    report.resolution_note = resolve_data.resolution_note
    report.resolved_by = current_user.id
    report.resolved_at = datetime.utcnow()

    db.commit()
    return {"message": "Report resolved", "report_id": report.id, "resolution": resolve_data.resolution}


@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: int,
    ban_data: UserBanCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot ban an admin")

    if ban_data.ban_type not in ("mute", "ban"):
        raise HTTPException(status_code=400, detail="ban_type must be 'mute' or 'ban'")

    user_ban = UserBan(
        user_id=user_id,
        banned_by=current_user.id,
        reason=ban_data.reason,
        ban_type=ban_data.ban_type,
        expires_at=ban_data.expires_at,
    )
    db.add(user_ban)

    if ban_data.ban_type == "mute":
        target_user.is_muted = True
        action = "muted"
    else:
        target_user.is_banned = True
        action = "suspended"

    db.commit()
    return {"message": f"User {action}", "user_id": user_id, "ban_type": ban_data.ban_type}


@router.post("/users/{user_id}/unban")
def unban_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    active_ban = db.query(UserBan).filter(
        UserBan.user_id == user_id,
        UserBan.is_active == True
    ).first()

    if not active_ban:
        raise HTTPException(status_code=400, detail="No active ban found for this user")

    active_ban.is_active = False
    active_ban.lifted_at = datetime.utcnow()
    active_ban.lifted_by = current_user.id

    target_user.is_muted = False
    target_user.is_banned = False

    db.commit()
    return {"message": "User unbanned", "user_id": user_id}
