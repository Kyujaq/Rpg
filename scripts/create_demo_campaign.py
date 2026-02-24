#!/usr/bin/env python3
"""
Create a demo campaign with a DM, an AI player, and a human actor.

Usage:
    python scripts/create_demo_campaign.py

Environment variables:
    ENGINE_URL  - base URL of the engine  (default: http://localhost:8088)
    ENGINE_KEY  - API key                  (default: dev-secret-key)

Prints the campaign ID on success so you can copy it into your valves.
"""

import json
import os
import sys
from urllib import request
from urllib.error import HTTPError, URLError

ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8088")
ENGINE_KEY = os.getenv("ENGINE_KEY", "dev-secret-key")

CAMPAIGN_PAYLOAD = {
    "name": "Demo Campaign",
    "actors": [
        {"id": "dm", "name": "Dungeon Master", "actor_type": "dm", "is_ai": True},
        {"id": "player1", "name": "Player 1", "actor_type": "player", "is_ai": True},
        {"id": "human", "name": "Human", "actor_type": "human", "is_ai": False},
    ],
}


def create_campaign() -> str:
    url = f"{ENGINE_URL}/v1/campaigns"
    data = json.dumps(CAMPAIGN_PAYLOAD).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-ENGINE-KEY": ENGINE_KEY,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["id"]
    except HTTPError as exc:
        print(f"[error] HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except URLError as exc:
        print(f"[error] Could not connect to engine at {ENGINE_URL}: {exc.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    campaign_id = create_campaign()
    print(campaign_id)
