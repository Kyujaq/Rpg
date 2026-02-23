import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from auth import verify_engine_key
from db import get_db
from schemas import MemoryOut, MemoryWrite
from services.memory_service import read_memory, write_memory

router = APIRouter(prefix="/v1/campaigns", tags=["memory"])


@router.post("/{campaign_id}/memory/write", response_model=MemoryOut)
def write_mem(
    campaign_id: str,
    body: MemoryWrite,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    memory = write_memory(db, campaign_id, body)
    return _to_memory_out(memory)


@router.get("/{campaign_id}/memory/read", response_model=List[MemoryOut])
def read_mem(
    campaign_id: str,
    viewer: str = Query(...),
    scope: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _key: str = Depends(verify_engine_key),
):
    memories = read_memory(db, campaign_id, viewer, scope)
    return [_to_memory_out(m) for m in memories]


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
