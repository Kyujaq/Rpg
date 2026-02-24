import argparse
import json
import os
import re
import time
from urllib import request
from urllib.error import HTTPError, URLError


ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8088")
ENGINE_KEY = os.getenv("ENGINE_KEY", "dev-secret-key")
CAMPAIGN_ID = os.getenv("CAMPAIGN_ID", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
DM_MODEL = os.getenv("DM_MODEL", "llama3")
PLAYER_MODEL = os.getenv("PLAYER_MODEL", "llama3")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "1.0"))
RUNNER_MAX_EVENTS = int(os.getenv("RUNNER_MAX_EVENTS", "50"))
RUNNER_MAX_MEMORIES = int(os.getenv("RUNNER_MAX_MEMORIES", "30"))
MAX_AUTO_TURNS_PER_TICK = int(os.getenv("MAX_AUTO_TURNS_PER_TICK", "2"))
MAX_MODEL_JSON_RETRIES = 2
DM_REFOCUS_ASK_FALLBACK = "What do you do next?"


def _post_json(url: str, body: dict, headers: dict | None = None) -> dict:
    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _engine_post(path: str, body: dict) -> dict:
    return _post_json(
        f"{ENGINE_URL}/v1/campaigns/{CAMPAIGN_ID}{path}",
        body,
        headers={"X-ENGINE-KEY": ENGINE_KEY},
    )


def _schema_for_role(actor_role: str) -> dict:
    if actor_role == "dm":
        return {
            "name": "dm_response",
            "schema": {
                "type": "object",
                "properties": {
                    "say": {"type": "string"},
                    "state_updates": {"type": "array"},
                    "ask": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["say", "state_updates", "ask", "notes"],
            },
        }
    return {
        "name": "player_response",
        "schema": {
            "type": "object",
            "properties": {
                "say": {"type": "string"},
                "think": {"type": "string"},
                "intent": {"type": "object"},
                "ask": {"type": "string"},
            },
            "required": ["say", "think", "intent", "ask"],
        },
    }


def _call_model(actor_id: str, actor_role: str, director_payload: dict) -> dict:
    model = DM_MODEL if actor_role == "dm" else PLAYER_MODEL
    system_prompt = (
        f"You are actor '{actor_id}' with role '{actor_role}'. "
        "Return only valid JSON matching the provided schema."
    )
    completion = _post_json(
        f"{OPENAI_BASE_URL}/chat/completions",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(director_payload)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": _schema_for_role(actor_role),
            },
        },
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
    )
    content = completion["choices"][0]["message"]["content"]
    return json.loads(content)


def _shorten_text(text: str, max_sentences: int = 2) -> str:
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]
    return ". ".join(parts[:max_sentences]) + ("." if parts else "")


def _enforce_dm_constraints(model_output: dict, director_payload: dict) -> dict:
    constraints = director_payload.get("constraints") or {}
    if not constraints.get("must_ask_question"):
        return model_output

    output = dict(model_output)
    output["say"] = _shorten_text((output.get("say") or "").strip(), max_sentences=2)
    ask = (output.get("ask") or "").strip()
    output["ask"] = ask if (ask and ask.endswith("?")) else DM_REFOCUS_ASK_FALLBACK
    return output


def _log_runner_error(message: str):
    _engine_post(
        "/events",
        {
            "actor_id": "system",
            "event_type": "runner_error",
            "content": message,
            "visibility": "public",
        },
    )


def _last_visible_event_actor_id(director_payload: dict) -> str:
    visible_events = director_payload.get("visible_events") or []
    if not visible_events:
        return ""
    return str(visible_events[-1].get("actor_id") or "")


def _is_actor_ai(actor_id: str, director_payload: dict) -> bool:
    actors = (director_payload.get("viewer_state") or {}).get("actors") or []
    return any(a.get("id") == actor_id and a.get("is_ai") for a in actors)


def _apply_actor_output(actor_id: str, actor_role: str, model_output: dict):
    say = (model_output.get("say") or "").strip()
    if say:
        _engine_post(
            "/events",
            {
                "actor_id": actor_id,
                "event_type": "utterance",
                "content": say,
                "visibility": "party",
            },
        )

    if actor_role != "dm":
        think = (model_output.get("think") or "").strip()
        if think:
            _engine_post(
                "/memory/write",
                {
                    "actor_id": actor_id,
                    "scope": "private",
                    "text": think,
                    "tags": [],
                },
            )
    else:
        state_updates = model_output.get("state_updates") or []
        if state_updates:
            _engine_post("/mutate", {"actor_id": actor_id, "mutations": state_updates})

    # Always advance to prevent actor stalls when model returns empty fields.
    _engine_post("/turn/advance", {})


def tick() -> int:
    """Run one bounded automation tick and return how many actors acted."""
    acted = 0
    for _ in range(MAX_AUTO_TURNS_PER_TICK):
        director = _engine_post(
            "/director/next",
            {"max_events": RUNNER_MAX_EVENTS, "max_memories": RUNNER_MAX_MEMORIES},
        )
        if not director.get("should_act"):
            reason = director.get("reason", "unknown")
            print(f"[runner] stopped: should_act=false reason={reason}")
            break
        actor_id = director.get("actor_id")
        role = director.get("actor_role")
        if not actor_id:
            print("[runner] stopped: no actor_id in director response")
            break

        if (
            _is_actor_ai(actor_id, director)
            and _is_actor_ai(_last_visible_event_actor_id(director), director)
            and director.get("reason") != "turn_owner"
        ):
            print(f"[runner] stopped: ai-to-ai safety guard triggered for actor '{actor_id}'")
            break

        output = None
        for attempt in range(MAX_MODEL_JSON_RETRIES):
            try:
                output = _call_model(actor_id, role, director)
                break
            except json.JSONDecodeError:
                if attempt == MAX_MODEL_JSON_RETRIES - 1:
                    _log_runner_error(f"[runner] invalid JSON from model for actor '{actor_id}'")
                    return acted
            except (KeyError, HTTPError, URLError):
                if attempt == MAX_MODEL_JSON_RETRIES - 1:
                    _log_runner_error(f"[runner] model call failed for actor '{actor_id}'")
                    return acted

        if output is None:
            return acted
        if role == "dm":
            output = _enforce_dm_constraints(output, director)

        _apply_actor_output(actor_id, role, output)
        print(f"[runner] actor '{actor_id}' acted (role={role})")
        acted += 1
    return acted


def main():
    parser = argparse.ArgumentParser(description="TTRPG Engine Runner")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one bounded tick and exit.",
    )
    mode_group.add_argument(
        "--watch",
        action="store_true",
        help="Poll continuously and tick when needed (default behaviour).",
    )
    args = parser.parse_args()

    if not CAMPAIGN_ID:
        raise ValueError("CAMPAIGN_ID is required")

    if args.once:
        try:
            acted = tick()
            print(f"[runner] tick complete: {acted} actor(s) acted")
        except Exception as exc:
            print(f"[runner] error: {exc}")
        return

    # --watch or default: continuous polling loop
    while True:
        try:
            tick()
        except Exception as exc:
            print(f"[runner] error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
