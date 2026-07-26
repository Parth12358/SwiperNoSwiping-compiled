"""HTTP layer against the frozen B→C contract (PRD-C §4), MOCK_LLM=1 throughout."""
import pytest
from fastapi.testclient import TestClient

import config
import db
import main

FROZEN_FIELDS = {"session_id", "verdict", "reply", "turn", "turns_remaining", "score", "savings_total_cents"}

PRODUCT = {
    "title": "Sony WH-1000XM5",
    "price_cents": 34800,
    "currency": "USD",
    "url": "https://a.co/x",
    "image_url": "https://x.jpg",
    "site": "amazon",
    "dom_snippet": "Sony WH-1000XM5 $348",
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    with TestClient(main.app) as c:
        yield c


def post(client, session_id=None, message=None, product=PRODUCT, user_id=1):
    return client.post(
        "/api/interrogate",
        json={"user_id": user_id, "product": product, "session_id": session_id, "message": message},
    )


def test_turn1_contract_shape(client):
    r = post(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == FROZEN_FIELDS
    assert body["verdict"] == "pending"
    assert body["turn"] == 1
    assert body["turns_remaining"] == config.MAX_TURNS - 1
    assert body["score"] is None
    assert isinstance(body["session_id"], str) and body["session_id"]
    assert isinstance(body["savings_total_cents"], int)


def test_three_turn_denial_updates_savings(client):
    baseline = db.stats(1)["saved_cents"]
    sid = post(client).json()["session_id"]
    t2 = post(client, session_id=sid, message="I want it").json()
    assert (t2["verdict"], t2["turn"], t2["turns_remaining"]) == ("pending", 2, 1)
    t3 = post(client, session_id=sid, message="just because").json()
    assert t3["verdict"] == "denied"
    assert (t3["turn"], t3["turns_remaining"]) == (3, 0)
    assert isinstance(t3["score"], int)
    assert t3["savings_total_cents"] == baseline + PRODUCT["price_cents"]


def test_session_cleaned_up_after_final_verdict(client):
    sid = post(client).json()["session_id"]
    post(client, session_id=sid, message="I want it")
    post(client, session_id=sid, message="just because")  # denied → session deleted
    r = post(client, session_id=sid).json()  # same id again → brand-new session
    assert r["turn"] == 1
    assert r["session_id"] != sid


def test_strong_answer_approved(client):
    sid = post(client).json()["session_id"]
    r = post(client, session_id=sid, message="my headphones broke and I have work calls").json()
    assert r["verdict"] == "approved"
    assert r["score"] >= config.APPROVE_THRESHOLD


def test_unknown_session_id_starts_fresh(client):
    r = post(client, session_id="s_doesnotexist").json()
    assert r["turn"] == 1
    assert r["verdict"] == "pending"


def test_route_fails_open_when_llm_layer_raises(client, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("total meltdown")

    monkeypatch.setattr(main.llm, "complete", boom)
    r = post(client)
    assert r.status_code == 200  # never a 500 (PRD §9.5)
    body = r.json()
    assert body["verdict"] == "approved"
    assert set(body) == FROZEN_FIELDS


def test_route_fails_open_when_db_raises(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(main.db, "get_context", boom)
    r = post(client)
    assert r.status_code == 200
    assert r.json()["verdict"] == "approved"


def test_malformed_body_is_not_a_500(client):
    r = client.post("/api/interrogate", content='{"user_id":', headers={"Content-Type": "application/json"})
    assert r.status_code < 500  # 422; B's fetch wrapper fails open on any non-200


def test_missing_fields_get_defaults(client):
    r = client.post("/api/interrogate", json={})
    assert r.status_code == 200
    assert r.json()["verdict"] in ("pending", "approved", "denied")


def test_stats_endpoint_shape(client):
    body = client.get("/api/stats/1").json()
    assert {"denied_count", "approved_count", "saved_cents", "top_category"} <= set(body)


def test_profile_roundtrip(client):
    original = client.get("/api/profile/1").json()
    assert original["user_id"] == 1
    updated = client.put("/api/profile/1", json={"savings_goal": "Tokyo trip"}).json()
    assert updated["savings_goal"] == "Tokyo trip"
    assert client.get("/api/profile/1").json()["savings_goal"] == "Tokyo trip"
    client.put("/api/profile/1", json={"savings_goal": original["savings_goal"]})


def test_profile_put_ignores_unknown_and_identity_fields(client):
    before = client.get("/api/profile/1").json()
    after = client.put("/api/profile/1", json={"user_id": 999, "hacker_field": "x"}).json()
    assert after["user_id"] == before["user_id"]
    assert "hacker_field" not in after


def test_turns_remaining_never_negative(client, monkeypatch):
    async def always_pending(*a, **k):
        return {"verdict": "pending", "score": None, "reply": "and?", "category": "electronics", "roast": None}

    monkeypatch.setattr(main.llm, "complete", always_pending)
    sid = post(client).json()["session_id"]
    last = post(client, session_id=sid, message="a")
    last = post(client, session_id=sid, message="b").json()
    # Backend rounds pending → denied on the final turn even if the LLM won't.
    assert last["verdict"] == "denied"
    assert last["turns_remaining"] == 0
