"""
TTRPG Engine Tools for OpenWebUI
Provides tools for interacting with the TTRPG Game Engine API.
"""

import json
import os
from typing import Any, Callable, Optional

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {"X-ENGINE-KEY": ENGINE_KEY, "Content-Type": "application/json"}


def _campaign_id() -> str:
    cid = DEFAULT_CAMPAIGN_ID
    if not cid:
        raise ValueError("DEFAULT_CAMPAIGN_ID is not set")
    return cid


def _actor_id(model: str) -> str:
    return MODEL_TO_ACTOR.get(model, "dm")


def _get(path: str, params: dict | None = None) -> str:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{ENGINE_URL}{path}", headers=_headers(), params=params or {})
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _post(path: str, body: dict) -> str:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{ENGINE_URL}{path}", headers=_headers(), json=body)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── OpenWebUI Function Class ──────────────────────────────────────────────────

class Tools:
    """TTRPG Engine tools exposed to OpenWebUI."""

    class Valves:
        """User-configurable settings (shown in OpenWebUI UI)."""
        engine_url: str = ENGINE_URL
        engine_key: str = ENGINE_KEY
        campaign_id: str = DEFAULT_CAMPAIGN_ID
        actor_id: str = "dm"

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

    def _actor(self) -> str:
        return self.valves.actor_id or "dm"

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

    def get_state(self, viewer: str = "") -> str:
        """
        Get the current campaign state visible to the given actor.

        :param viewer: Actor ID of the viewer (defaults to the configured actor).
        :return: JSON string with campaign state.
        """
        actor = viewer or self._actor()
        return self._get("/state", params={"viewer": actor})

    def list_events(self, after: str = "") -> str:
        """
        List events visible to the configured actor, optionally after a given event ID.

        :param after: Event ID to paginate from (optional).
        :return: JSON array of events.
        """
        params: dict[str, str] = {"viewer": self._actor()}
        if after:
            params["after"] = after
        return self._get("/events", params=params)

    def log_utterance(self, text: str, visibility: str = "public") -> str:
        """
        Log a spoken utterance as an event in the campaign.

        :param text: The text to log.
        :param visibility: Visibility scope — public, party, dm_only, or private:<actor_id>.
        :return: JSON of the created event.
        """
        body = {
            "actor_id": self._actor(),
            "event_type": "utterance",
            "content": text,
            "visibility": visibility,
        }
        return self._post("/events", body)

    def roll(self, expr: str, reason: str) -> str:
        """
        Roll dice using standard notation and log the result.

        :param expr: Dice expression, e.g. '1d20', '2d6+3'.
        :param reason: Reason for the roll, e.g. 'attack roll'.
        :return: JSON roll result with breakdown.
        """
        body = {"expr": expr, "reason": reason, "actor_id": self._actor()}
        return self._post("/roll", body)

    def mutate(self, mutations: list) -> str:
        """
        Apply state mutations to the campaign (HP changes, inventory, flags, etc.).

        :param mutations: List of mutation objects, each with 'type' and 'payload'.
        :return: JSON summary of applied mutations.
        """
        body = {"actor_id": self._actor(), "mutations": mutations}
        return self._post("/mutate", body)

    def advance_turn(self) -> str:
        """
        Advance the turn to the next actor. May trigger anti-ramble refocus.

        :return: JSON with new turn_owner, ai_only_streak, and refocus_triggered.
        """
        return self._post("/turn/advance", {})

    def memory_write(self, scope: str, text: str, tags: list[str] | None = None) -> str:
        """
        Write a memory entry to the campaign memory store.

        :param scope: Visibility scope — public, party, private, world, dm_only.
        :param text: Memory content to store.
        :param tags: Optional list of string tags.
        :return: JSON of the created memory entry.
        """
        body = {
            "actor_id": self._actor(),
            "scope": scope,
            "text": text,
            "tags": tags or [],
        }
        return self._post("/memory/write", body)

    def memory_read(self, scope: str = "") -> str:
        """
        Read memory entries visible to the configured actor.

        :param scope: Optional scope filter — public, party, private, world, dm_only.
        :return: JSON array of memory entries.
        """
        params: dict[str, str] = {"viewer": self._actor()}
        if scope:
            params["scope"] = scope
        return self._get("/memory/read", params=params)
