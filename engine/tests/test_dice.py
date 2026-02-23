import pytest
from services.dice_service import roll_dice, parse_dice_expr


def test_1d20_in_range():
    for _ in range(20):
        result, breakdown = roll_dice("1d20")
        assert 1 <= result <= 20, f"1d20 result {result} out of range"


def test_2d6_plus_3_in_range():
    for _ in range(20):
        result, breakdown = roll_dice("2d6+3")
        assert 5 <= result <= 15, f"2d6+3 result {result} out of range"


def test_d6_no_count_in_range():
    for _ in range(20):
        result, breakdown = roll_dice("d6")
        assert 1 <= result <= 6, f"d6 result {result} out of range"


def test_invalid_expr_raises():
    with pytest.raises(ValueError):
        parse_dice_expr("invalid")


def test_invalid_expr_in_roll_raises():
    with pytest.raises(ValueError):
        roll_dice("notadice")


def test_roll_logged_as_event(client, campaign):
    cid = campaign["id"]
    resp = client.post(
        f"/v1/campaigns/{cid}/roll",
        json={"expr": "1d20", "reason": "attack", "actor_id": "player1"},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expr"] == "1d20"
    assert data["reason"] == "attack"

    # Check that an event was created
    events = client.get(
        f"/v1/campaigns/{cid}/events",
        params={"viewer": "player1"},
        headers={"X-ENGINE-KEY": "test-key"},
    ).json()
    assert any(e["event_type"] == "roll" for e in events)


def test_roll_breakdown_contains_result(client, campaign):
    cid = campaign["id"]
    resp = client.post(
        f"/v1/campaigns/{cid}/roll",
        json={"expr": "1d6", "reason": "test", "actor_id": "dm"},
        headers={"X-ENGINE-KEY": "test-key"},
    )
    data = resp.json()
    result_str = str(data["result"])
    assert result_str in data["breakdown"]
