import pytest


def post_event(client, campaign_id, actor_id, visibility, content="test"):
    return client.post(
        f"/v1/campaigns/{campaign_id}/events",
        json={
            "actor_id": actor_id,
            "event_type": "utterance",
            "content": content,
            "visibility": visibility,
        },
        headers={"X-ENGINE-KEY": "test-key"},
    )


def get_events(client, campaign_id, viewer):
    resp = client.get(
        f"/v1/campaigns/{campaign_id}/events",
        params={"viewer": viewer},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200
    return resp.json()


def test_public_event_visible_to_all(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "public", "Public message")

    for viewer in ["dm", "player1", "human1"]:
        events = get_events(client, cid, viewer)
        assert any(e["content"] == "Public message" for e in events), f"{viewer} should see public event"


def test_party_event_visible_to_all(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "player1", "party", "Party message")

    for viewer in ["dm", "player1", "human1"]:
        events = get_events(client, cid, viewer)
        assert any(e["content"] == "Party message" for e in events), f"{viewer} should see party event"


def test_private_event_visible_to_owner_and_dm(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "player1", "private:player1", "Private to player1")

    # Owner can see
    events = get_events(client, cid, "player1")
    assert any(e["content"] == "Private to player1" for e in events)

    # DM can see
    events = get_events(client, cid, "dm")
    assert any(e["content"] == "Private to player1" for e in events)

    # Other player cannot see
    events = get_events(client, cid, "human1")
    assert not any(e["content"] == "Private to player1" for e in events)


def test_dm_only_event_visible_only_to_dm(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "dm_only", "DM secret")

    # DM can see
    events = get_events(client, cid, "dm")
    assert any(e["content"] == "DM secret" for e in events)

    # Others cannot see
    for viewer in ["player1", "human1"]:
        events = get_events(client, cid, viewer)
        assert not any(e["content"] == "DM secret" for e in events), f"{viewer} should not see dm_only"


def test_player1_cannot_see_private_player2(client, campaign):
    cid = campaign["id"]
    # Use human1 as "player2" for private event
    post_event(client, cid, "human1", "private:human1", "Human1 private")

    events = get_events(client, cid, "player1")
    assert not any(e["content"] == "Human1 private" for e in events)


def test_player1_cannot_see_dm_only(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "dm_only", "DM only content")

    events = get_events(client, cid, "player1")
    assert not any(e["content"] == "DM only content" for e in events)


def test_dm_can_see_all_events(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "public", "Public")
    post_event(client, cid, "player1", "party", "Party")
    post_event(client, cid, "player1", "private:player1", "Private")
    post_event(client, cid, "dm", "dm_only", "DM only")

    events = get_events(client, cid, "dm")
    contents = [e["content"] for e in events]
    assert "Public" in contents
    assert "Party" in contents
    assert "Private" in contents
    assert "DM only" in contents
