from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ActorCreate(BaseModel):
    id: str
    name: str
    actor_type: str
    is_ai: bool


class ActorOut(BaseModel):
    id: str
    name: str
    actor_type: str
    is_ai: bool

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    name: str
    actors: List[ActorCreate]


class CampaignOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    turn_owner: str
    ai_only_streak: int
    actors: List[ActorOut]

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    actor_id: str
    event_type: str
    content: str
    visibility: str


class EventOut(BaseModel):
    id: str
    campaign_id: str
    actor_id: str
    event_type: str
    content: str
    visibility: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RollRequest(BaseModel):
    expr: str
    reason: str
    actor_id: str


class RollOut(BaseModel):
    id: str
    campaign_id: str
    actor_id: str
    expr: str
    reason: str
    result: int
    breakdown: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MutationItem(BaseModel):
    type: str
    payload: Dict[str, Any]


class MutateRequest(BaseModel):
    actor_id: str
    mutations: List[MutationItem]


class TurnAdvanceOut(BaseModel):
    turn_owner: str
    ai_only_streak: int
    refocus_triggered: bool
    last_event_id: Optional[str] = None


class MemoryWrite(BaseModel):
    actor_id: str
    scope: str
    text: str
    tags: List[str] = []


class MemoryOut(BaseModel):
    id: str
    campaign_id: str
    actor_id: str
    scope: str
    text: str
    tags: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class StateOut(BaseModel):
    campaign_id: str
    turn_owner: str
    ai_only_streak: int
    actors: List[ActorOut]
    state_kv: Dict[str, str]
    visible_events_count: int


class DirectorNextRequest(BaseModel):
    max_events: int = 50
    max_memories: int = 30


class DirectorMemoriesOut(BaseModel):
    world: List[MemoryOut]
    party: List[MemoryOut]
    private: List[MemoryOut]


class DirectorConstraintsOut(BaseModel):
    must_ask_question: bool
    max_output_sentences: int
    stop_after_act: Optional[bool] = None


class DirectorNextOut(BaseModel):
    should_act: bool
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    reason: str
    viewer_state: Dict[str, Any]
    visible_events: List[EventOut]
    memories: DirectorMemoriesOut
    constraints: DirectorConstraintsOut
