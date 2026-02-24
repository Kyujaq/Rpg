import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from config import settings
from models import Actor, Campaign, Event
from schemas import TurnAdvanceOut


def advance_turn(db: Session, campaign_id: str) -> TurnAdvanceOut:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise ValueError(f"Campaign not found: {campaign_id}")

    actors = db.query(Actor).filter(Actor.campaign_id == campaign_id).order_by(Actor.id).all()

    if not actors:
        raise ValueError("No actors in campaign")

    # Determine actor order: dm first, then players, then humans
    dm_actors = [a for a in actors if a.actor_type == "dm"]
    other_actors = [a for a in actors if a.actor_type != "dm"]
    ordered_actors = dm_actors + other_actors

    actor_ids = [a.id for a in ordered_actors]

    current_owner = campaign.turn_owner

    # Find next actor
    if current_owner in actor_ids:
        current_idx = actor_ids.index(current_owner)
        next_idx = (current_idx + 1) % len(actor_ids)
    else:
        next_idx = 0

    next_owner_id = actor_ids[next_idx]
    next_actor = next(a for a in ordered_actors if a.id == next_owner_id)

    # Update ai_only_streak based on last event
    last_event = (
        db.query(Event)
        .filter(Event.campaign_id == campaign_id)
        .order_by(Event.created_at.desc())
        .first()
    )

    refocus_triggered = False
    streak = campaign.ai_only_streak

    if last_event:
        last_actor = db.query(Actor).filter(Actor.id == last_event.actor_id).first()
        if last_actor and last_actor.is_ai:
            streak += 1
        else:
            streak = 0

    if streak >= settings.AI_ONLY_STREAK_LIMIT:
        refocus_triggered = True
        streak = 0
        # Append system_refocus event
        refocus_event = Event(
            id=uuid.uuid4().hex[:8],
            campaign_id=campaign_id,
            actor_id="system",
            event_type="system_refocus",
            content="[SYSTEM] Anti-ramble triggered: Human player, please take action.",
            visibility="public",
            created_at=datetime.utcnow(),
        )
        db.add(refocus_event)

    campaign.turn_owner = next_owner_id
    campaign.ai_only_streak = streak
    campaign.floor_lock = next_owner_id
    campaign.floor_lock_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    return TurnAdvanceOut(
        turn_owner=next_owner_id,
        ai_only_streak=streak,
        refocus_triggered=refocus_triggered,
        last_event_id=last_event.id if last_event else None,
    )
