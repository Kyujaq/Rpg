import sys
import os

# Add engine/ directory to sys.path so absolute imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import app
from db import Base, get_db
from auth import verify_engine_key

TEST_DB_URL = "sqlite:///:memory:"

# StaticPool ensures all connections reuse the same in-memory SQLite DB
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def override_verify_engine_key():
    return "test-key"


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[verify_engine_key] = override_verify_engine_key


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def campaign(client):
    resp = client.post(
        "/v1/campaigns",
        json={
            "name": "Test Campaign",
            "actors": [
                {"id": "dm", "name": "DM", "actor_type": "dm", "is_ai": True},
                {"id": "player1", "name": "Player 1", "actor_type": "player", "is_ai": True},
                {"id": "human1", "name": "Human 1", "actor_type": "human", "is_ai": False},
            ],
        },
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200
    return resp.json()
