import json
import uuid
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from models import Actor, ActorCursor, Campaign, Event
from schemas import (
    DirectorConstraintsOut,
    DirectorMemoriesOut,
    DirectorNextOut,
    DirectorNextRequest,
    EventOut,
    MemoryOut,
)
from services.event_service import list_events
from services.memory_service import read_memory
from services.state_service import get_campaign_state


def _to_memory_out(memory) -> MemoryOut:
    tags = json.loads(memory.tags) if isinstance(memory.tags, str) else memory.tags
    return MemoryOut(
        id=memory.id,
        campaign_id=memory.campaign_id,
        actor_id=memory.actor_id,
        scope=memory.scope,
        text=memory.text,
        tags=tags,
        created_at=memory.created_at,
    )


def _empty_response(reason: str) -> DirectorNextOut:
    return DirectorNextOut(
        should_act=False,
        reason=reason,
        viewer_state={},
        visible_events=[],
        memories=DirectorMemoriesOut(world=[], party=[], private=[]),
        constraints=DirectorConstraintsOut(must_ask_question=False, max_output_sentences=6),
    )


def _latest_dm_utterance(db: Session, campaign_id: str) -> Optional[Event]:
    dm_actor_ids = [
        a.id
        for a in db.query(Actor).filter(
            Actor.campaign_id == campaign_id,
            Actor.actor_type == "dm",
        ).all()
    ]
    if not dm_actor_ids:
        return None
    return (
        db.query(Event)
        .filter(Event.campaign_id == campaign_id, Event.actor_id.in_(dm_actor_ids))
        .order_by(Event.created_at.desc())
        .first()
    )


def _is_directly_addressed(db: Session, campaign_id: str, actor: Actor) -> bool:
    last_dm = _latest_dm_utterance(db, campaign_id)
    if not last_dm:
        return False
    content = (last_dm.content or "").lower()
    return f"@{actor.id}".lower() in content or (actor.name or "").lower() in content


def _recent_ai_only_streak(db: Session, campaign_id: str, limit: int = 3) -> int:
    events = (
        db.query(Event)
        .filter(Event.campaign_id == campaign_id)
        .order_by(Event.created_at.desc())
        .limit(limit)
        .all()
    )
    streak = 0
    for event in events:
        event_actor = db.query(Actor).filter(
            Actor.campaign_id == campaign_id,
            Actor.id == event.actor_id,
        ).first()
        if event_actor and event_actor.is_ai:
            streak += 1
        else:
            break
    return streak


def _last_event(db: Session, campaign_id: str) -> Optional[Event]:
    return (
        db.query(Event)
        .filter(Event.campaign_id == campaign_id)
        .order_by(Event.created_at.desc())
        .first()
    )


def _get_cursor(db: Session, campaign_id: str, actor_id: str) -> ActorCursor:
    cursor = db.query(ActorCursor).filter(
        ActorCursor.campaign_id == campaign_id,
        ActorCursor.actor_id == actor_id,
    ).first()
    if cursor:
        return cursor

    cursor = ActorCursor(
        id=uuid.uuid4().hex,
        campaign_id=campaign_id,
        actor_id=actor_id,
        last_seen_event_id=None,
    )
    db.add(cursor)
    db.commit()
    db.refresh(cursor)
    return cursor


def next_director_context(db: Session, campaign_id: str, body: DirectorNextRequest) -> DirectorNextOut:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise ValueError(f"Campaign not found: {campaign_id}")

    actor = db.query(Actor).filter(
        Actor.campaign_id == campaign_id,
        Actor.id == campaign.turn_owner,
    ).first()
    if actor is None:
        return _empty_response("no_turn_owner")

    recent_events = (
        db.query(Event)
        .filter(Event.campaign_id == campaign_id)
        .order_by(Event.created_at.desc())
        .limit(6)
        .all()
    )
    has_human_input = any(
        db.query(Actor).filter(
            Actor.campaign_id == campaign_id,
            Actor.id == e.actor_id,
            Actor.is_ai.is_(False),
        ).first()
        for e in recent_events
    )

    if actor.actor_type == "player" and actor.is_ai and not has_human_input and not _is_directly_addressed(db, campaign_id, actor):
        return _empty_response("await_human_input")

    cursor = _get_cursor(db, campaign_id, actor.id)
    visible_events = list_events(
        db,
        campaign_id,
        actor.id,
        after_event_id=cursor.last_seen_event_id,
    )[:body.max_events]

    if visible_events:
        cursor.last_seen_event_id = visible_events[-1].id
        db.commit()

    all_memories = read_memory(db, campaign_id, actor.id)
    grouped: Dict[str, List[MemoryOut]] = {"world": [], "party": [], "private": []}
    for mem in all_memories:
        mem_out = _to_memory_out(mem)
        if mem.scope in ("world", "public"):
            if len(grouped["world"]) < body.max_memories:
                grouped["world"].append(mem_out)
        elif mem.scope == "party":
            if len(grouped["party"]) < body.max_memories:
                grouped["party"].append(mem_out)
        elif mem.scope == "private":
            if len(grouped["private"]) < body.max_memories:
                grouped["private"].append(mem_out)

    last_event = _last_event(db, campaign_id)
    must_refocus = (
        campaign.ai_only_streak >= 3
        or _recent_ai_only_streak(db, campaign_id, limit=3) >= 3
        or (last_event is not None and last_event.event_type == "system_refocus")
    )
    return DirectorNextOut(
        should_act=True,
        actor_id=actor.id,
        actor_role=actor.actor_type,
        reason="refocus" if must_refocus else "turn_owner",
        viewer_state=get_campaign_state(db, campaign_id, actor.id).model_dump(),
        visible_events=[EventOut.model_validate(e) for e in visible_events],
        memories=DirectorMemoriesOut(
            world=grouped["world"],
            party=grouped["party"],
            private=grouped["private"],
        ),
        constraints=DirectorConstraintsOut(must_ask_question=must_refocus, max_output_sentences=6),
    )
