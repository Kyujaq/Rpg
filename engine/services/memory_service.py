import json
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from config import settings
from models import Actor, Memory
from schemas import MemoryWrite


def write_memory(db: Session, campaign_id: str, memory_write: MemoryWrite) -> Memory:
    memory = Memory(
        id=uuid.uuid4().hex[:8],
        campaign_id=campaign_id,
        actor_id=memory_write.actor_id,
        scope=memory_write.scope,
        text=memory_write.text,
        tags=json.dumps(memory_write.tags),
        created_at=datetime.utcnow(),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def read_memory(
    db: Session,
    campaign_id: str,
    viewer_actor_id: str,
    scope: Optional[str] = None,
    dm_omniscient_private: Optional[bool] = None,
) -> List[Memory]:
    if dm_omniscient_private is None:
        dm_omniscient_private = settings.DM_OMNISCIENT_PRIVATE
    viewer_actor = db.query(Actor).filter(
        Actor.id == viewer_actor_id,
        Actor.campaign_id == campaign_id,
    ).first()

    viewer_is_dm = viewer_actor is not None and viewer_actor.actor_type == "dm"

    query = db.query(Memory).filter(Memory.campaign_id == campaign_id)

    if scope:
        query = query.filter(Memory.scope == scope)

    all_memories = query.order_by(Memory.created_at).all()

    result = []
    for mem in all_memories:
        if mem.scope in ("world", "public", "party"):
            result.append(mem)
        elif mem.scope == "dm_only":
            if viewer_is_dm:
                result.append(mem)
        elif mem.scope == "private":
            if mem.actor_id == viewer_actor_id:
                result.append(mem)
            elif viewer_is_dm and dm_omniscient_private:
                result.append(mem)

    return result
