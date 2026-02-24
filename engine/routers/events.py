from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from auth import verify_engine_key
from db import get_db
from schemas import EventCreate, EventOut
from services.event_service import append_event, list_events

router = APIRouter(prefix="/v1/campaigns", tags=["events"])


@router.post("/{campaign_id}/events", response_model=EventOut)
def create_event(
    campaign_id: str,
    body: EventCreate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    event = append_event(db, campaign_id, body)
    return EventOut.model_validate(event)


@router.get("/{campaign_id}/events", response_model=List[EventOut])
def get_events(
    campaign_id: str,
    viewer: str = Query(...),
    after: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    events = list_events(db, campaign_id, viewer, after)
    return [EventOut.model_validate(e) for e in events]
