from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    state_json = Column(String, default="{}")
    ai_only_streak = Column(Integer, default=0)
    turn_owner = Column(String, default="dm")
    floor_lock = Column(String, nullable=True)
    floor_lock_at = Column(DateTime, nullable=True)


class Actor(Base):
    __tablename__ = "actors"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    name = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)  # dm/player/human
    is_ai = Column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    actor_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    visibility = Column(String, nullable=False)  # public/party/private:<actor_id>/dm_only
    created_at = Column(DateTime, default=datetime.utcnow)


class Roll(Base):
    __tablename__ = "rolls"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    actor_id = Column(String, nullable=False)
    expr = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    result = Column(Integer, nullable=False)
    breakdown = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    actor_id = Column(String, nullable=False)
    scope = Column(String, nullable=False)  # public/party/private/world/dm_only
    text = Column(String, nullable=False)
    tags = Column(String, default="[]")  # JSON list
    created_at = Column(DateTime, default=datetime.utcnow)


class StateKV(Base):
    __tablename__ = "state_kv"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
