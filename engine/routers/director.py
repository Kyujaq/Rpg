from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from auth import verify_engine_key
from db import get_db
from schemas import DirectorNextOut, DirectorNextRequest
from services.director_service import next_director_context

router = APIRouter(prefix="/v1/campaigns", tags=["director"])


@router.post("/{campaign_id}/director/next", response_model=DirectorNextOut)
def director_next(
    campaign_id: str,
    body: DirectorNextRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    try:
        return next_director_context(db, campaign_id, body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
