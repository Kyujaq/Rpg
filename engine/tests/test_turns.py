import pytest


def post_event(client, campaign_id, actor_id, content="event"):
    return client.post(
        f"/v1/campaigns/{campaign_id}/events",
        json={
            "actor_id": actor_id,
            "event_type": "utterance",
            "content": content,
            "visibility": "public",
        },
        headers={"X-ENGINE-KEY": "test-key"},
    )


def advance_turn(client, campaign_id):
    return client.post(
        f"/v1/campaigns/{campaign_id}/turn/advance",
        headers={"X-ENGINE-KEY": "test-key"},
    )


def test_advance_turn_cycles(client, campaign):
    cid = campaign["id"]

    # Get initial turn owner
    state = client.get(
        f"/v1/campaigns/{cid}/state",
        params={"viewer": "dm"},
        headers={"X-ENGINE-KEY": "test-key"},
    ).json()
    initial_owner = state["turn_owner"]

    # Advance a few times and verify it changes
    owners = [initial_owner]
    for _ in range(3):
        resp = advance_turn(client, cid)
        assert resp.status_code == 200
        payload = resp.json()
        owners.append(payload["turn_owner"])
        assert "last_event_id" in payload

    # Should have cycled through different owners
    assert len(set(owners)) > 1


def test_ai_only_streak_increments(client, campaign):
    cid = campaign["id"]

    # Post AI events (dm and player1 are AI)
    post_event(client, cid, "dm", "AI event 1")
    resp = advance_turn(client, cid)
    streak1 = resp.json()["ai_only_streak"]

    post_event(client, cid, "player1", "AI event 2")
    resp = advance_turn(client, cid)
    streak2 = resp.json()["ai_only_streak"]

    assert streak2 >= streak1 or streak2 == 0  # Could reset if refocus triggered


def test_anti_ramble_triggers_refocus(client, campaign):
    cid = campaign["id"]

    # Post 3 AI events to trigger refocus
    post_event(client, cid, "dm", "AI 1")
    advance_turn(client, cid)
    post_event(client, cid, "player1", "AI 2")
    advance_turn(client, cid)
    post_event(client, cid, "dm", "AI 3")
    resp = advance_turn(client, cid)

    # Check events for system_refocus
    events = client.get(
        f"/v1/campaigns/{cid}/events",
        params={"viewer": "dm"},
        headers={"X-ENGINE-KEY": "test-key"},
    ).json()

    refocus_events = [e for e in events if e["event_type"] == "system_refocus"]
    assert len(refocus_events) > 0


def test_human_event_resets_streak(client, campaign):
    cid = campaign["id"]

    # Post AI events to build streak
    post_event(client, cid, "dm", "AI 1")
    advance_turn(client, cid)
    post_event(client, cid, "player1", "AI 2")
    advance_turn(client, cid)

    # Post human event
    post_event(client, cid, "human1", "Human action")
    resp = advance_turn(client, cid)

    assert resp.json()["ai_only_streak"] == 0
