import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from auth import verify_engine_key
from db import get_db
from models import Roll
from schemas import RollOut, RollRequest, EventCreate
from services.dice_service import roll_dice
from services.event_service import append_event

router = APIRouter(prefix="/v1/campaigns", tags=["dice"])


@router.post("/{campaign_id}/roll", response_model=RollOut)
def roll(
    campaign_id: str,
    body: RollRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    try:
        result, breakdown = roll_dice(body.expr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    roll_obj = Roll(
        id=uuid.uuid4().hex[:8],
        campaign_id=campaign_id,
        actor_id=body.actor_id,
        expr=body.expr,
        reason=body.reason,
        result=result,
        breakdown=breakdown,
        created_at=datetime.utcnow(),
    )
    db.add(roll_obj)
    db.commit()
    db.refresh(roll_obj)

    # Log as event
    event_create = EventCreate(
        actor_id=body.actor_id,
        event_type="roll",
        content=f"Roll {body.expr} for {body.reason}: {breakdown}",
        visibility="public",
    )
    append_event(db, campaign_id, event_create)

    return RollOut.model_validate(roll_obj)
