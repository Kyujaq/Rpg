from config import settings


def create_campaign(client, actors):
    resp = client.post(
        "/v1/campaigns",
        json={"name": "Director Test", "actors": actors},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def post_event(client, campaign_id, actor_id, visibility, content):
    resp = client.post(
        f"/v1/campaigns/{campaign_id}/events",
        json={
            "actor_id": actor_id,
            "event_type": "utterance",
            "content": content,
            "visibility": visibility,
        },
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200


def write_memory(client, campaign_id, actor_id, scope, text):
    resp = client.post(
        f"/v1/campaigns/{campaign_id}/memory/write",
        json={"actor_id": actor_id, "scope": scope, "text": text, "tags": []},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200


def director_next(client, campaign_id, max_events=50, max_memories=30):
    resp = client.post(
        f"/v1/campaigns/{campaign_id}/director/next",
        json={"max_events": max_events, "max_memories": max_memories},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200
    return resp.json()


def test_director_cursor_advances(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "public", "event 1")
    post_event(client, cid, "player1", "public", "event 2")

    first = director_next(client, cid)
    assert first["actor_id"] == "dm"
    assert [e["content"] for e in first["visible_events"]] == ["event 1", "event 2"]

    second = director_next(client, cid)
    assert second["visible_events"] == []

    post_event(client, cid, "human1", "public", "event 3")
    third = director_next(client, cid)
    assert [e["content"] for e in third["visible_events"]] == ["event 3"]


def test_director_filters_private_context_for_player(client):
    cid = create_campaign(
        client,
        [
            {"id": "dm", "name": "DM", "actor_type": "dm", "is_ai": True},
            {"id": "player1", "name": "Player 1", "actor_type": "player", "is_ai": True},
            {"id": "player2", "name": "Player 2", "actor_type": "player", "is_ai": True},
        ],
    )
    # Move turn from dm -> player1 so player1 is selected by director.
    resp = client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})
    assert resp.status_code == 200
    assert resp.json()["turn_owner"] == "player1"

    post_event(client, cid, "player2", "private:player2", "player2 secret")
    post_event(client, cid, "player2", "party", "player2 party")
    post_event(client, cid, "dm", "party", "@player1, react to this.")
    write_memory(client, cid, "player2", "private", "player2 private memory")
    write_memory(client, cid, "player2", "party", "player2 party memory")

    data = director_next(client, cid)
    contents = [e["content"] for e in data["visible_events"]]
    assert "player2 secret" not in contents
    assert "player2 party" in contents
    assert all(m["actor_id"] != "player2" for m in data["memories"]["private"])
    assert any(m["text"] == "player2 party memory" for m in data["memories"]["party"])


def test_director_dm_non_omniscient_private_filter(client, campaign, monkeypatch):
    cid = campaign["id"]
    monkeypatch.setattr(settings, "DM_OMNISCIENT_PRIVATE", False)

    post_event(client, cid, "player1", "private:player1", "hidden from dm")
    write_memory(client, cid, "player1", "private", "hidden memory from dm")

    data = director_next(client, cid)
    assert all(e["content"] != "hidden from dm" for e in data["visible_events"])
    assert all(m["text"] != "hidden memory from dm" for m in data["memories"]["private"])


def test_director_refocus_constraints_when_ai_streak_high(client, campaign):
    cid = campaign["id"]
    post_event(client, cid, "dm", "public", "AI 1")
    client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})
    post_event(client, cid, "player1", "public", "AI 2")
    client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})
    post_event(client, cid, "dm", "public", "AI 3")
    client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})

    data = director_next(client, cid)
    assert data["reason"] == "refocus"
    assert data["constraints"]["must_ask_question"] is True


def test_director_blocks_ai_player_without_human_or_direct_address(client):
    cid = create_campaign(
        client,
        [
            {"id": "dm", "name": "Dungeon Master", "actor_type": "dm", "is_ai": True},
            {"id": "player1", "name": "Player One", "actor_type": "player", "is_ai": True},
            {"id": "human", "name": "Human", "actor_type": "human", "is_ai": False},
        ],
    )
    resp = client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})
    assert resp.status_code == 200
    if resp.json()["turn_owner"] != "player1":
        resp = client.post(f"/v1/campaigns/{cid}/turn/advance", headers={"X-ENGINE-KEY": "test-key"})
        assert resp.status_code == 200
    assert resp.json()["turn_owner"] == "player1"

    blocked = director_next(client, cid)
    assert blocked["should_act"] is False

    post_event(client, cid, "dm", "party", "@player1 what do you do?")
    allowed = director_next(client, cid)
    assert allowed["should_act"] is True
