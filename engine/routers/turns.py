from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from auth import verify_engine_key
from db import get_db
from schemas import TurnAdvanceOut
from services.turn_service import advance_turn

router = APIRouter(prefix="/v1/campaigns", tags=["turns"])


@router.post("/{campaign_id}/turn/advance", response_model=TurnAdvanceOut)
def turn_advance(
    campaign_id: str,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    try:
        return advance_turn(db, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
