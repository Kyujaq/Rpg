from sqlalchemy.orm import Session
from models import Actor, Campaign, Event, StateKV
from schemas import ActorOut, StateOut
from services.event_service import is_visible


def get_campaign_state(db: Session, campaign_id: str, viewer_actor_id: str) -> StateOut:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if campaign is None:
        raise ValueError(f"Campaign not found: {campaign_id}")

    actors = db.query(Actor).filter(Actor.campaign_id == campaign_id).all()

    viewer_actor = next((a for a in actors if a.id == viewer_actor_id), None)
    viewer_is_dm = viewer_actor is not None and viewer_actor.actor_type == "dm"

    kv_rows = db.query(StateKV).filter(StateKV.campaign_id == campaign_id).all()
    state_kv = {row.key: row.value for row in kv_rows}

    all_events = db.query(Event).filter(Event.campaign_id == campaign_id).all()
    visible_count = sum(1 for e in all_events if is_visible(e, viewer_actor_id, viewer_is_dm))

    return StateOut(
        campaign_id=campaign_id,
        turn_owner=campaign.turn_owner,
        ai_only_streak=campaign.ai_only_streak,
        actors=[ActorOut.model_validate(a) for a in actors],
        state_kv=state_kv,
        visible_events_count=visible_count,
    )
