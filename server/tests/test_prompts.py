"""prompts.py — DeepSeek JSON-mode requirements, money rendering, turn rules."""
import config
import prompts

PRODUCT = {
    "title": "Sony WH-1000XM5",
    "price_cents": 34800,
    "currency": "USD",
    "url": "https://a.co/x",
    "image_url": "https://x.jpg",
    "site": "amazon",
    "dom_snippet": "Sony WH-1000XM5 $348",
}
PROFILE = {
    "user_id": 1,
    "display_name": "Kart",
    "monthly_budget_cents": 200000,
    "savings_goal": "Japan trip",
    "goal_target_cents": 400000,
}
RECENT = [{"title": "AirPods", "price_cents": 12800, "verdict": "denied", "created_at": "2026-07-24"}]


def sp(**kw):
    args = dict(product=PRODUCT, profile=PROFILE, recent=RECENT, turn=1, max_turns=3, has_message=False)
    args.update(kw)
    return prompts.system_prompt(**args)


def test_literal_word_json_present():
    # DeepSeek JSON mode hard requirement (PRD-C §7.1).
    assert "json" in sp().lower()


def test_worked_example_present():
    s = sp()
    assert '{"verdict": "pending"' in s
    assert '"category"' in s and '"roast"' in s


def test_money_rendered_in_dollars():
    s = sp()
    assert "$348.00" in s  # product
    assert "$4,000.00" in s  # goal target
    assert "$2,000.00" in s  # monthly budget
    assert "$128.00" in s  # recent purchase


def test_null_price_becomes_unknown():
    p = dict(PRODUCT, price_cents=None)
    s = sp(product=p)
    assert "unknown price" in s
    p = dict(PRODUCT, price_cents="34800")  # string price → don't guess (PRD §9.1)
    assert "unknown price" in sp(product=p)


def test_dom_snippet_trimmed_to_4000():
    p = dict(PRODUCT, dom_snippet="A" * 10000)
    s = sp(product=p)
    assert "A" * 4000 in s
    assert "A" * 4001 not in s


def test_turn_rules():
    assert "opening question" in sp(turn=1, has_message=False)
    assert "FINAL TURN" not in sp(turn=1, has_message=False)
    assert "probe again" in sp(turn=2, has_message=True)
    final = sp(turn=3, has_message=True)
    assert "FINAL TURN" in final and '"pending" is NOT allowed' in final


def test_hard_approve_step_listed_first_with_canonical_categories():
    s = sp()
    assert s.index("STEP 1") < s.index("STEP 2")
    for cat in ("medical", "food", "safety", "work-gear"):
        assert cat in s


def test_rubric_bands_present():
    s = sp()
    for band in ("0-39", "40-69", "70-100"):
        assert band in s


def test_inputs_not_mutated():
    p = dict(PRODUCT)
    prof = dict(PROFILE)
    rec = [dict(RECENT[0])]
    prompts.system_prompt(p, prof, rec, turn=1)
    assert p == PRODUCT and prof == PROFILE and rec == RECENT


def test_default_max_turns_comes_from_config():
    s = prompts.system_prompt(PRODUCT, PROFILE, RECENT, turn=config.MAX_TURNS)
    assert "FINAL TURN" in s
