"""
TTRPG Engine Tools for OpenWebUI
Provides tools for interacting with the TTRPG Game Engine API.
"""

import json
import os
from typing import Any, Optional

import httpx

# ── Configuration ────────────────────────────────────────────────────────────
ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8088")
ENGINE_KEY = os.getenv("ENGINE_KEY", "dev-secret-key")
DEFAULT_CAMPAIGN_ID = os.getenv("DEFAULT_CAMPAIGN_ID", "")

# Map OpenWebUI model names to actor IDs in the campaign
MODEL_TO_ACTOR: dict[str, str] = {
    "gpt-4o": "dm",
    "gpt-4": "player1",
    "llama3": "player2",
}


# ── OpenWebUI Function Class ──────────────────────────────────────────────────

class Tools:
    """TTRPG Engine tools exposed to OpenWebUI."""

    class Valves:
        """
        User-configurable settings (shown in OpenWebUI UI).
        Actor resolution order: actor_id valve -> MODEL_TO_ACTOR (if enabled) -> default_actor_id.
        """
        engine_url: str = ENGINE_URL
        engine_key: str = ENGINE_KEY
        campaign_id: str = DEFAULT_CAMPAIGN_ID
        actor_id: str = ""
        use_model_to_actor_mapping: bool = True
        default_actor_id: str = "human"

    def __init__(self):
        self.valves = self.Valves()

    # ── Private helpers that respect valve overrides ──────────────────────────

    def _h(self) -> dict[str, str]:
        return {"X-ENGINE-KEY": self.valves.engine_key, "Content-Type": "application/json"}

    def _base(self) -> str:
        cid = self.valves.campaign_id or DEFAULT_CAMPAIGN_ID
        if not cid:
            raise ValueError("campaign_id valve is not set")
        return f"{self.valves.engine_url}/v1/campaigns/{cid}"

    def _model_name(self, __model__: Any = None) -> str:
        if isinstance(__model__, dict):
            return str(__model__.get("id") or __model__.get("name") or "")
        if __model__ is not None:
            return str(getattr(__model__, "id", "") or getattr(__model__, "name", "") or "")
        return ""

    def _actor(self, __model__: Any = None) -> str:
        if self.valves.actor_id:
            return self.valves.actor_id
        if self.valves.use_model_to_actor_mapping:
            model_name = self._model_name(__model__)
            if model_name in MODEL_TO_ACTOR:
                return MODEL_TO_ACTOR[model_name]
        return self.valves.default_actor_id or "human"

    def _get(self, path: str, params: dict | None = None) -> str:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{self._base()}{path}",
                    headers=self._h(),
                    params=params or {},
                )
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def _post(self, path: str, body: dict) -> str:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{self._base()}{path}",
                    headers=self._h(),
                    json=body,
                )
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    # ── Tools ─────────────────────────────────────────────────────────────────

    def get_state(self, viewer: str = "", __model__: Any = None) -> str:
        """
        Get the current campaign state visible to the given actor.

        :param viewer: Actor ID of the viewer. Pass an explicit actor ID to filter
            visibility from that actor's perspective. If omitted or empty, defaults
            to the actor ID resolved from MODEL_TO_ACTOR for the current model.
        :return: JSON string with campaign state.
        """
        actor = viewer or self._actor(__model__)
        return self._get("/state", params={"viewer": actor})

    def list_events(self, viewer: str = "", after: str = "", __model__: Any = None) -> str:
        """
        List events visible to the configured actor, optionally after a given event ID.

        :param viewer: Actor ID of the viewer. Defaults to the resolved actor.
        :param after: Event ID to paginate from (optional).
        :return: JSON array of events.
        """
        params: dict[str, str] = {"viewer": viewer or self._actor(__model__)}
        if after:
            params["after"] = after
        return self._get("/events", params=params)

    def log_utterance(self, text: str, visibility: str = "public", __model__: Any = None) -> str:
        """
        Log a spoken utterance as an event in the campaign.

        :param text: The text to log.
        :param visibility: Visibility scope — public, party, dm_only, or private:<actor_id>.
        :return: JSON of the created event.
        """
        body = {
            "actor_id": self._actor(__model__),
            "event_type": "utterance",
            "content": text,
            "visibility": visibility,
        }
        return self._post("/events", body)

    def roll(self, expr: str, reason: str = "", __model__: Any = None) -> str:
        """
        Roll dice using standard notation and log the result.

        :param expr: Dice expression, e.g. '1d20', '2d6+3'.
        :param reason: Reason for the roll, e.g. 'attack roll'.
        :return: JSON roll result with breakdown.
        """
        body = {"expr": expr, "reason": reason, "actor_id": self._actor(__model__)}
        return self._post("/roll", body)

    def mutate(self, mutations: list[dict], __model__: Any = None) -> str:
        """
        Apply state mutations to the campaign (HP changes, inventory, flags, etc.).

        :param mutations: List of mutation objects, each with 'type' and 'payload'.
        :return: JSON summary of applied mutations.
        """
        body = {"actor_id": self._actor(__model__), "mutations": mutations}
        return self._post("/mutate", body)

    def turn_advance(self, __model__: Any = None) -> str:
        """
        Advance the turn to the next actor. May trigger anti-ramble refocus.

        :return: JSON with turn_owner, ai_only_streak, refocus_triggered, and last_event_id.
        """
        return self._post("/turn/advance", {})

    def advance_turn(self, __model__: Any = None) -> str:
        """Backward-compatible alias for turn_advance."""
        return self.turn_advance(__model__)

    def director_next(self, max_events: int = 50, max_memories: int = 30, __model__: Any = None) -> str:
        """
        Get the director package for what should happen next.

        :return: Raw JSON response from the engine.
        """
        return self._post(
            "/director/next",
            {"max_events": max_events, "max_memories": max_memories, "actor_id": self._actor(__model__)},
        )

    def memory_write(self, scope: str, text: str, tags: list[str] | None = None, __model__: Any = None) -> str:
        """
        Write a memory entry to the campaign memory store.

        :param scope: Visibility scope — public, party, private, world, dm_only.
        :param text: Memory content to store.
        :param tags: Optional list of string tags.
        :return: JSON of the created memory entry.
        """
        body = {
            "actor_id": self._actor(__model__),
            "scope": scope,
            "text": text,
            "tags": tags if tags is not None else [],
        }
        return self._post("/memory/write", body)

    def memory_read(self, scope: str = "party", __model__: Any = None) -> str:
        """
        Read memory entries visible to the configured actor.

        :param scope: Optional scope filter — public, party, private, world, dm_only.
        :return: JSON array of memory entries.
        """
        params: dict[str, str] = {"viewer": self._actor(__model__)}
        if scope:
            params["scope"] = scope
        return self._get("/memory/read", params=params)
