# TTRPG Game Engine

A lightweight, API-first **Tabletop RPG Game Engine** designed to power AI-assisted campaigns with support for multiple AI players, a human DM or player, dice rolling, event logging, memory management, and anti-ramble turn control.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    OpenWebUI / Voice UI                  │
│         (ttrpg_engine_tools.py — Function plugin)        │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP (X-ENGINE-KEY)
                            ▼
┌──────────────────────────────────────────────────────────┐
│                  TTRPG Game Engine API                   │
│                  FastAPI  •  port 8088                   │
│                                                          │
│  /v1/campaigns      – campaign lifecycle + mutations     │
│  /v1/.../events     – event log with visibility rules    │
│  /v1/.../roll       – dice rolling + event logging       │
│  /v1/.../memory     – scoped memory store                │
│  /v1/.../turn       – turn management + anti-ramble      │
└───────────────────────────┬──────────────────────────────┘
                            │ SQLAlchemy
                            ▼
                     SQLite  (ttrpg.db)
```

---

## Quickstart

### With Docker Compose

```bash
cp .env.example .env
# Edit .env to set ENGINE_KEY and other values
docker compose up --build
```

The API is available at `http://localhost:8088/docs`.

### Local Development

```bash
cd engine
pip install -r requirements.txt
uvicorn app:app --reload --port 8088
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/campaigns` | Create a new campaign with actors |
| `GET` | `/v1/campaigns/{id}/state?viewer={actor}` | Get campaign state |
| `POST` | `/v1/campaigns/{id}/mutate` | Apply state mutations |
| `POST` | `/v1/campaigns/{id}/events` | Append an event |
| `GET` | `/v1/campaigns/{id}/events?viewer={actor}` | List visible events |
| `POST` | `/v1/campaigns/{id}/roll` | Roll dice and log result |
| `POST` | `/v1/campaigns/{id}/memory/write` | Write a memory entry |
| `GET` | `/v1/campaigns/{id}/memory/read?viewer={actor}` | Read memory |
| `POST` | `/v1/campaigns/{id}/turn/advance` | Advance turn |
| `POST` | `/v1/campaigns/{id}/director/next` | Get next actor + filtered context package |

All endpoints require the `X-ENGINE-KEY` header.

---

## Event Visibility Scopes

| Scope | Who can see |
|-------|------------|
| `public` | Everyone |
| `party` | All actors (players + DM) |
| `private:<actor_id>` | Only that actor and the DM |
| `dm_only` | Only the DM actor |

---

## Mutation Types

| Type | Payload | Effect |
|------|---------|--------|
| `hp_set` | `{actor_id, hp}` | Set HP directly |
| `hp_delta` | `{actor_id, delta}` | Add/subtract HP |
| `inventory_add` | `{actor_id, item}` | Add item to inventory |
| `inventory_remove` | `{actor_id, item}` | Remove item from inventory |
| `flag_set` | `{key, value}` | Set a named campaign flag |
| `time_advance` | `{amount, unit}` | Advance in-game time |

---

## Anti-Ramble System

When `AI_ONLY_STREAK_LIMIT` consecutive turns are all taken by AI actors, the engine automatically:

1. Appends a `system_refocus` event visible to all
2. Resets the streak counter to 0
3. Returns `refocus_triggered: true` in the turn advance response

This ensures human players are prompted to participate regularly.

---

## OpenWebUI Setup

1. Copy `openwebui_function/ttrpg_engine_tools.py` into your OpenWebUI **Functions** directory.
2. Set environment variables (or Valves in the UI):
   - `ENGINE_URL` — URL to the running engine (e.g. `http://localhost:8088`)
   - `ENGINE_KEY` — Must match the server's `ENGINE_KEY`
   - `DEFAULT_CAMPAIGN_ID` — The campaign ID to use
   - `actor_id` — The actor this model plays (e.g. `dm`, `player1`)
3. Assign different models as different actors in `MODEL_TO_ACTOR`.
4. Enable voice-to-text in OpenWebUI and use `log_utterance` for spoken input.

---

## AI Runner (local process)

`runner/runner.py` polls `/v1/campaigns/{id}/director/next`, generates actor JSON via an OpenAI-compatible `/chat/completions` endpoint (e.g., Ollama), then writes `say` to `/events` and player `think` to `/memory/write`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENGINE_KEY` | `dev-secret-key` | API authentication key |
| `DATABASE_URL` | `sqlite:///./ttrpg.db` | SQLAlchemy database URL |
| `AI_ONLY_STREAK_LIMIT` | `3` | AI turns before refocus triggers |
| `AI_PLAYER_COOLDOWN_SECONDS` | `30` | Cooldown between AI turns |
| `DM_OMNISCIENT_PRIVATE` | `true` | If false, DM cannot see other actors' private:* content |
| `DEFAULT_CAMPAIGN_ID` | *(empty)* | Default campaign for OpenWebUI tools |

---

## Running Tests

```bash
cd engine
pip install -r requirements.txt
python -m pytest tests/ -v
```
