import json
import os
import time
from urllib import request


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

    _engine_post("/turn/advance", {})


def run_once(max_steps: int = 2) -> int:
    acted = 0
    for _ in range(max_steps):
        director = _engine_post(
            "/director/next",
            {"max_events": RUNNER_MAX_EVENTS, "max_memories": RUNNER_MAX_MEMORIES},
        )
        if not director.get("should_act"):
            break
        role = director.get("actor_role")
        actor_id = director.get("actor_id")
        if not actor_id:
            break

        if acted == 1 and role != "player":
            break

        output = _call_model(actor_id, role, director)
        _apply_actor_output(actor_id, role, output)
        acted += 1

        if acted == 1 and role != "dm":
            break
    return acted


def main():
    if not CAMPAIGN_ID:
        raise ValueError("CAMPAIGN_ID is required")
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[runner] error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
