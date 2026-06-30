from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.debate import DebateCreate, DebateResponse, DebateList
from app.services.debate_service import DebateService
from app.core.dependencies import get_current_active_user
from app.models.user import User
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/debates", tags=["debates"])
limiter = Limiter(key_func=get_remote_address)

@router.get("/", response_model=List[DebateList])
@limiter.limit("60/minute")
def get_debates(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    debate_service = DebateService(db)
    return debate_service.get_debates(skip=skip, limit=limit)

@router.get("/{debate_id}", response_model=DebateResponse)
@limiter.limit("60/minute")
def get_debate(request: Request, debate_id: int, db: Session = Depends(get_db)):
    debate_service = DebateService(db)
    debate = debate_service.get_debate(debate_id)
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debate not found"
        )
    return debate

@router.post("/", response_model=DebateList)
@limiter.limit("10/minute")
def create_debate(
    request: Request,
    debate: DebateCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    debate_service = DebateService(db)
    return debate_service.create_debate(debate, created_by=current_user.id)

@router.get("/stats/overview")
@limiter.limit("30/minute")
def get_debate_stats(request: Request, db: Session = Depends(get_db)):
    debate_service = DebateService(db)
    return debate_service.get_stats()
