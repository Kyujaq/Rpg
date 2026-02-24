# TTRPG Engine — Copilot Instructions

## Overview

This repository implements a **TTRPG (Tabletop Role-Playing Game) Game Engine** as a REST API.
It is designed to orchestrate AI-assisted campaigns where multiple AI language models act as players
or the Dungeon Master, with optional human participation.

---

## Architecture

```
engine/
  app.py            – FastAPI application entry point
  config.py         – Settings via pydantic-settings
  db.py             – SQLAlchemy engine + session factory
  models.py         – ORM table definitions
  schemas.py        – Pydantic request/response schemas
  auth.py           – X-ENGINE-KEY header authentication

  services/
    dice_service.py   – Dice expression parser and roller
    event_service.py  – Event append/list with visibility filtering
    state_service.py  – Campaign state aggregation
    turn_service.py   – Turn rotation + anti-ramble logic
    memory_service.py – Scoped memory read/write

  routers/
    campaigns.py      – Campaign CRUD + state mutations
    events.py         – Event log endpoints
    dice.py           – Dice roll endpoint
    memory.py         – Memory endpoints
    turns.py          – Turn advance endpoint

  tests/
    conftest.py       – Shared fixtures (in-memory DB, TestClient)
    test_visibility.py
    test_dice.py
    test_turns.py

openwebui_function/
  ttrpg_engine_tools.py  – OpenWebUI plugin with 8 tool methods
```

---

## Key Concepts

### Campaigns
A campaign is the top-level container. It holds actors, events, rolls, memories, and state KV pairs.

### Actors
Each participant is an Actor with:
- `actor_type`: `dm` | `player` | `human`
- `is_ai`: `true` for AI-controlled, `false` for human-controlled

### Events
Events are immutable log entries. Each event has a **visibility scope**:
- `public` — visible to everyone
- `party` — visible to all party members and DM
- `private:<actor_id>` — visible only to that actor and the DM
- `dm_only` — visible only to the DM

### Turns
Turns rotate through actors in order: DM → players → humans → DM.
The engine tracks `ai_only_streak` — consecutive turns where the last event was from an AI actor.
When the streak hits `AI_ONLY_STREAK_LIMIT`, a `system_refocus` event is injected and the streak resets.

### Memory
The memory store is separate from events. Memories have scopes:
- `world` / `public` / `party` — visible to all
- `private` — visible only to writer and DM
- `dm_only` — visible only to DM

### State KV
Arbitrary key-value pairs per campaign for tracking HP, inventory, flags, and time.

---

## How AI Players Should Interact

1. **Start of turn**: Call `get_state(viewer=<actor_id>)` to get current game state.
2. **Read context**: Call `list_events(after=<last_seen_event_id>)` for new events.
3. **Take action**: Call `log_utterance(text=<speech>, visibility=<scope>)` to speak.
4. **Roll dice**: Call `roll(expr=<dice>, reason=<why>)` when needed.
5. **Update state**: Call `mutate(mutations=[...])` for HP changes, items, flags.
6. **Record memories**: Call `memory_write(scope=<scope>, text=<text>)` for important facts.
7. **End turn**: Call `advance_turn()` to pass to the next actor.

---

## Contributing

- All source files use **absolute imports** (not relative), since the engine directory is added to `sys.path`.
- Tests run from `engine/` directory: `python -m pytest tests/ -v`
- The `conftest.py` inserts the engine directory into `sys.path` and overrides dependencies for in-memory testing.
- Add new mutation types in `routers/campaigns.py` in the `mutate_state` function.
- Add new event types by simply using them in event `event_type` field — no enum enforcement.

---

## Running Locally

```bash
cd engine
pip install -r requirements.txt
uvicorn app:app --reload --port 8088
```

## Running Tests

```bash
cd engine
python -m pytest tests/ -v
```

## Docker

```bash
docker compose up --build
```
