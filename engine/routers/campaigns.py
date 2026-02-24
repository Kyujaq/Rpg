import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from auth import verify_engine_key
from db import get_db
from models import Actor, Campaign, StateKV
from schemas import CampaignCreate, CampaignOut, ActorOut, MutateRequest, StateOut
from services.state_service import get_campaign_state

router = APIRouter(prefix="/v1/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    campaign_id = uuid.uuid4().hex[:8]
    campaign = Campaign(
        id=campaign_id,
        name=body.name,
        created_at=datetime.utcnow(),
        state_json="{}",
        ai_only_streak=0,
        turn_owner="dm",
    )
    db.add(campaign)

    actors = []
    for actor_data in body.actors:
        actor = Actor(
            id=actor_data.id,
            campaign_id=campaign_id,
            name=actor_data.name,
            actor_type=actor_data.actor_type,
            is_ai=actor_data.is_ai,
        )
        db.add(actor)
        actors.append(actor)

    db.commit()
    db.refresh(campaign)

    # Set initial turn_owner to dm actor id if exists
    dm_actor = next((a for a in actors if a.actor_type == "dm"), None)
    if dm_actor:
        campaign.turn_owner = dm_actor.id
        db.commit()
        db.refresh(campaign)

    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        created_at=campaign.created_at,
        turn_owner=campaign.turn_owner,
        ai_only_streak=campaign.ai_only_streak,
        actors=[ActorOut.model_validate(a) for a in actors],
    )


@router.get("/{campaign_id}/state", response_model=StateOut)
def get_state(
    campaign_id: str,
    viewer: str = Query(...),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    try:
        return get_campaign_state(db, campaign_id, viewer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{campaign_id}/mutate")
def mutate_state(
    campaign_id: str,
    body: MutateRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    results = []

    for mutation in body.mutations:
        mut_type = mutation.type
        payload = mutation.payload

        if mut_type == "hp_set":
            actor_id = payload["actor_id"]
            hp = int(payload["hp"])
            _set_kv(db, campaign_id, f"hp:{actor_id}", str(hp))
            results.append({"type": mut_type, "key": f"hp:{actor_id}", "value": hp})

        elif mut_type == "hp_delta":
            actor_id = payload["actor_id"]
            delta = int(payload["delta"])
            current = _get_kv(db, campaign_id, f"hp:{actor_id}", "0")
            new_hp = int(current) + delta
            _set_kv(db, campaign_id, f"hp:{actor_id}", str(new_hp))
            results.append({"type": mut_type, "key": f"hp:{actor_id}", "value": new_hp})

        elif mut_type == "inventory_add":
            actor_id = payload["actor_id"]
            item = payload["item"]
            current = json.loads(_get_kv(db, campaign_id, f"inventory:{actor_id}", "[]"))
            current.append(item)
            _set_kv(db, campaign_id, f"inventory:{actor_id}", json.dumps(current))
            results.append({"type": mut_type, "key": f"inventory:{actor_id}", "value": current})

        elif mut_type == "inventory_remove":
            actor_id = payload["actor_id"]
            item = payload["item"]
            current = json.loads(_get_kv(db, campaign_id, f"inventory:{actor_id}", "[]"))
            if item in current:
                current.remove(item)
            _set_kv(db, campaign_id, f"inventory:{actor_id}", json.dumps(current))
            results.append({"type": mut_type, "key": f"inventory:{actor_id}", "value": current})

        elif mut_type == "flag_set":
            key = payload["key"]
            value = payload["value"]
            _set_kv(db, campaign_id, f"flag:{key}", json.dumps(value))
            results.append({"type": mut_type, "key": f"flag:{key}", "value": value})

        elif mut_type == "time_advance":
            amount = payload["amount"]
            unit = payload["unit"]
            _set_kv(db, campaign_id, "time:current", f"{amount} {unit}")
            results.append({"type": mut_type, "key": "time:current", "value": f"{amount} {unit}"})

        else:
            raise HTTPException(status_code=400, detail=f"Unknown mutation type: {mut_type}")

    db.commit()
    return {"mutations_applied": len(results), "results": results}


def _get_kv(db: Session, campaign_id: str, key: str, default: str = "") -> str:
    row = db.query(StateKV).filter(
        StateKV.campaign_id == campaign_id,
        StateKV.key == key,
    ).first()
    return row.value if row else default


def _set_kv(db: Session, campaign_id: str, key: str, value: str):
    row = db.query(StateKV).filter(
        StateKV.campaign_id == campaign_id,
        StateKV.key == key,
    ).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        row = StateKV(
            id=uuid.uuid4().hex[:8],
            campaign_id=campaign_id,
            key=key,
            value=value,
            updated_at=datetime.utcnow(),
        )
        db.add(row)
