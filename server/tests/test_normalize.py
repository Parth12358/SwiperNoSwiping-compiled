"""main._normalize — the contract-safety layer between the LLM and the response."""
import config
import main


def n(raw, final=False):
    return main._normalize(raw, final_turn=final)


def test_passthrough_pending():
    r = n({"verdict": "pending", "score": None, "reply": "Why?", "category": "electronics"})
    assert r == {"verdict": "pending", "score": None, "reply": "Why?"}


def test_final_turn_pending_rounds_down_to_denied():
    r = n({"verdict": "pending", "score": None, "reply": "hm", "category": "electronics"}, final=True)
    assert r["verdict"] == "denied"
    assert isinstance(r["score"], int) and r["score"] < 40


def test_garbage_verdict_without_score_fails_open():
    r = n({"verdict": "banana", "score": None, "reply": ""})
    assert r["verdict"] == "approved"
    assert r["reply"]


def test_garbage_verdict_with_score_derives_verdict():
    assert n({"verdict": None, "score": 85, "reply": "ok"})["verdict"] == "approved"
    assert n({"verdict": "??", "score": 50, "reply": "ok"})["verdict"] == "pending"
    assert n({"verdict": "??", "score": 10, "reply": "ok"})["verdict"] == "denied"


def test_threshold_gates_final_verdicts():
    below = config.APPROVE_THRESHOLD - 1
    assert n({"verdict": "approved", "score": below, "reply": "ok", "category": "electronics"})["verdict"] == "denied"
    assert n({"verdict": "denied", "score": config.APPROVE_THRESHOLD, "reply": "ok", "category": "electronics"})["verdict"] == "approved"


def test_approved_without_score_stays_approved():
    assert n({"verdict": "approved", "score": None, "reply": "go"})["verdict"] == "approved"


def test_score_coercion():
    assert n({"verdict": "denied", "score": 20.7, "reply": "no", "category": "x"})["score"] == 20
    assert n({"verdict": "approved", "score": True, "reply": "go"})["score"] is None  # bools are not scores
    assert n({"verdict": "approved", "score": "90", "reply": "go"})["score"] is None


def test_blank_reply_gets_fallback():
    assert n({"verdict": "pending", "score": None, "reply": "   "})["reply"]
    assert n({"verdict": "pending", "score": None, "reply": None})["reply"]


def test_hard_approve_category_net():
    for cat in ("medical", "health", "food", "groceries", "safety", "work-gear", "MEDICAL", " Food "):
        r = n({"verdict": "pending", "score": None, "reply": "why?", "category": cat})
        assert (r["verdict"], r["score"]) == ("approved", 100), cat


def test_hard_approve_keeps_llm_reply_only_when_it_already_approved():
    r = n({"verdict": "approved", "score": 100, "reply": "Health first. Go.", "category": "medical"})
    assert r["reply"] == "Health first. Go."
    # LLM probed anyway → its question would read absurd next to an approval; use canned reply.
    r = n({"verdict": "pending", "score": None, "reply": "But why though?", "category": "medical"})
    assert r["reply"] != "But why though?"


def test_normal_categories_not_hard_approved():
    r = n({"verdict": "pending", "score": None, "reply": "why?", "category": "electronics"})
    assert r["verdict"] == "pending"
