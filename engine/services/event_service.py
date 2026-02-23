import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from models import Actor, Event
from schemas import EventCreate


def is_visible(event: Event, viewer_actor_id: str, viewer_is_dm: bool) -> bool:
    vis = event.visibility

    if vis == "public":
        return True
    elif vis == "party":
        return True  # visible to all actors including dm
    elif vis == "dm_only":
        return viewer_is_dm
    elif vis.startswith("private:"):
        target_actor_id = vis.split(":", 1)[1]
        return viewer_actor_id == target_actor_id or viewer_is_dm

    return False


def append_event(db: Session, campaign_id: str, event_create: EventCreate) -> Event:
    event = Event(
        id=uuid.uuid4().hex[:8],
        campaign_id=campaign_id,
        actor_id=event_create.actor_id,
        event_type=event_create.event_type,
        content=event_create.content,
        visibility=event_create.visibility,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    campaign_id: str,
    viewer_actor_id: str,
    after_event_id: Optional[str] = None,
) -> List[Event]:
    viewer_actor = db.query(Actor).filter(
        Actor.id == viewer_actor_id,
        Actor.campaign_id == campaign_id,
    ).first()

    viewer_is_dm = viewer_actor is not None and viewer_actor.actor_type == "dm"

    query = db.query(Event).filter(Event.campaign_id == campaign_id).order_by(Event.created_at)

    if after_event_id:
        after_event = db.query(Event).filter(Event.id == after_event_id).first()
        if after_event:
            query = query.filter(Event.created_at > after_event.created_at)

    all_events = query.all()

    return [e for e in all_events if is_visible(e, viewer_actor_id, viewer_is_dm)]
