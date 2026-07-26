# PRD — SwipernoSwiping

**Version:** 0.3 (hackathon — parallel build, DeepSeek-only, Chrome-only)
**Timebox:** 3 hours, 4 engineers
**Status:** Contracts freeze at T+0:20. Nothing in §9 changes after that.

> **What changed from 0.2:** DeepSeek is now the sole AI provider for every AI call in the project, with a single client module and pinned model IDs — see §7.1, and read the deprecation warning in it before anyone writes a fetch call. Chrome-only is now an enforced technical constraint rather than a non-goal — see §7.2.
>
> **What changed in 0.2:** four independent vertical slices, frozen seams, rolling merges. §8 and §9.

---

## 1. Problem

Impulse purchases happen in the gap between wanting and clicking. That gap is currently ~0.4 seconds and there is nothing in it. Every existing "budgeting" tool reports the damage *after* the card is charged.

## 2. Product

A Chrome extension that physically blocks the checkout button on shopping sites and forces the user into a short adversarial conversation with an LLM before it will let the click through. The LLM knows who you are, what you've bought before, and what you said last time.

**One-liner:** Your wallet now has a lawyer, and the lawyer thinks you're lying.

## 3. Goals / Non-goals

**Goals (must be true at demo):**
- G1 — Buy/checkout buttons on a live retail page become unclickable.
- G2 — Clicking the blocked button opens an interrogation modal within 1s.
- G3 — The LLM asks at least one follow-up question grounded in the actual product on the page.
- G4 — A weak justification gets DENIED and the click never fires. A strong justification gets APPROVED and the real click fires.
- G5 — Every attempt is persisted to SQLite and visible in a "money saved" counter.

**Non-goals (explicitly cut):**
- N1 — Any site other than the two demo targets working reliably.
- N2 — Real auth, multi-user, or account sync. One hardcoded `user_id = 1`.
- N3 — **Chrome only.** No Firefox, no Safari, no Edge, no mobile. Not "cross-browser where it's free" — cross-browser compatibility is actively out of scope and code written for it will be rejected. See §7.2.
- N4 — Bypass-proofing. A determined user can open devtools and delete the overlay. Don't care.
- N5 — Real ad targeting. The ad slot ships as a hardcoded list of joke ads with **no** targeting on user data — no behavioral, financial, or vulnerability signals feeding ad selection. The gambling-ads bit stays a joke in the pitch, not a feature in the codebase. (It is also the single fastest way to get the extension pulled from the store and the demo booed.)
- N6 — Chrome Web Store submission. Loads unpacked.
- N7 — Any AI provider other than DeepSeek. No OpenAI, no Anthropic, no Gemini, no local models, no fallback provider. One provider, one client, one key. See §7.1.

## 4. User

One persona. "Someone with a cart open in another tab." Assumes English, desktop Chrome, no configuration beyond a 30-second onboarding form.

## 5. Core flow

```
page loads
  → content script scans DOM for buy-button candidates
  → overlay <div> is drawn on top of each match (transparent, absolute, z-index max)
  → user clicks
  → overlay swallows the click, emits swiperno:intercept
  → modal sends {product context, user profile, purchase history} to backend
  → backend calls DeepSeek → returns interrogator's opening question
  → user types justification (max 3 turns)
  → backend returns verdict: APPROVED | DENIED
      APPROVED → log, remove overlay, programmatically click the real button
      DENIED   → log, show savings counter increment, modal stays closed for 10 min on this SKU
```

## 6. Scope by priority

### P0 — demo is dead without these
| ID | Feature | Owner |
|----|---------|-------|
| P0-1 | Button detection (Amazon + one generic retailer) | A |
| P0-2 | Transparent overlay div + click interception | A |
| P0-3 | Product context extraction (title, price, image, URL) | A |
| P0-4 | Modal UI with chat transcript + input + verdict states | B |
| P0-5 | `POST /api/interrogate` → DeepSeek → verdict JSON | C |
| P0-6 | Interrogator system prompt + scoring rubric | C |
| P0-7 | SQLite schema + write path for every attempt | D |
| P0-8 | Onboarding form → profile row (income band, savings goal, weakness) | D |
| P0-9 | Approve path actually completes the purchase click | A + B |

### P1 — do these if all three merges land by T+2:00
| ID | Feature | Owner |
|----|---------|-------|
| P1-1 | "You have saved $X this week" counter in the extension popup | D |
| P1-2 | History-aware roasting ("this is your fourth pair of headphones") | C + D |
| P1-3 | Modal ad slot with hardcoded joke ads | B |
| P1-4 | Denial cooldown per product (10 min localStorage) | A |

### P2 — will not happen, listed so nobody starts them
Streaks, screenshot/vision input, budget enforcement, categories, charts, export, settings page, dark mode.

## 7. Architecture

```
┌──────────────────────────────┐
│ Chrome Extension (MV3)       │
│  content.js  → detect + overlay + extract          │  A
│  modal.js    → shadow-DOM UI                       │  B
│  popup.html  → stats + onboarding                  │  B
│  background.js → fetch proxy to backend            │  A
└────────────┬─────────────────┘
             │ HTTP, JSON
┌────────────▼─────────────────┐
│ Backend (FastAPI)            │
│  main.py / llm.py / prompts  │  C
│  db.py / stats.py / schema   │  D
│  → DeepSeek (sole AI provider)│
│  → SQLite (swiperno.db)      │
└──────────────────────────────┘
```

**Why a backend at all:** the DeepSeek key must not sit in a content script, and `sqlite3` needs a filesystem. Runs on `localhost:8000` for the demo. No deploy.

**DOM payload rule:** send extracted fields plus a **trimmed** snippet (max 4KB of the product container's `innerText`), never `document.body.outerHTML`. Full-page DOM blows the context window, costs latency you don't have, and ships the user's session junk to a third party.

### 7.1 AI provider policy — DeepSeek, everywhere, only

**Every AI call in this project goes to DeepSeek.** No second provider is installed, imported, configured, or kept "as a fallback." If a call to DeepSeek fails, we fail open (§9.5) — we do not reach for another model.

**One client, one chokepoint.** All AI traffic goes through `server/llm.py::complete()`. No other file constructs an AI request. No AI call is ever made from the extension — the key stays server-side, and a content script that talks to an AI API directly is both a key leak and a CORS problem you don't have time for.

**Every AI touchpoint, and they are all DeepSeek:**

| # | Touchpoint | Model | Notes |
|---|-----------|-------|-------|
| 1 | Interrogation turns (the questions) | `deepseek-v4-flash` | latency-critical, user is watching a spinner |
| 2 | Verdict + score (§11 rubric) | `deepseek-v4-flash` | same call as #1, one response, don't split it |
| 3 | Category classification for `purchases.category` | `deepseek-v4-flash` | P1. Batch it into the verdict call rather than a second round-trip |
| 4 | History roast line ("your fourth pair of headphones") | `deepseek-v4-flash` | P1. Also folded into the verdict call — see below |

**Fold, don't chain.** All four touchpoints are one request returning one JSON object. Four sequential DeepSeek calls per turn is 4× the latency for a demo where the user is staring at a loading state. If you find yourself writing a second `await complete()` in one turn, stop.

#### Model IDs — read this before you write a line

> ⚠️ **`deepseek-chat` and `deepseek-reasoner` were deprecated on 2026/07/24 15:59 UTC — yesterday.** Per DeepSeek's docs they return errors with no fallback. Every blog post, Stack Overflow answer, and code-assistant completion you will hit today still uses `deepseek-chat`. If someone pastes that in, the backend 400s and you will lose twenty minutes reading the wrong stack trace.

| Setting | Value |
|---------|-------|
| Base URL | `https://api.deepseek.com` |
| Default model | `deepseek-v4-flash` |
| Escalation model | `deepseek-v4-pro` — only if flash's verdicts are visibly too soft, and only for the final scoring turn |
| SDK | `openai` Python SDK pointed at the DeepSeek base URL. The API is OpenAI-compatible; do not go looking for a DeepSeek-specific SDK. |
| Auth | `DEEPSEEK_API_KEY` as a bearer token, from `server/.env`, never committed |
| Banned | `deepseek-chat`, `deepseek-reasoner` — dead aliases |

**Thinking mode is a parameter now, not a model.** It is enabled with `"thinking": {"type": "enabled"}` plus `reasoning_effort`, not by switching model name. **Leave it off.** Thinking mode blows the 8s timeout and this task does not need chain-of-thought — it needs a fast, slightly mean two-sentence reply.

#### JSON mode — three gotchas that will each cost you 15 minutes

DeepSeek's structured output has documented sharp edges. Handle all three at T+0:20, not at T+2:00:

1. **The word "json" must literally appear in the system or user prompt**, and the docs want a worked example of the target shape in the prompt. Setting `response_format: {"type":"json_object"}` alone is not sufficient.
2. **Set `max_tokens` deliberately.** A truncated response is invalid JSON. Our replies are two sentences — 300 is plenty, and it also caps latency.
3. **JSON mode occasionally returns empty content.** DeepSeek acknowledges this in their docs. So `llm.py` must treat empty content as a failure: one retry, then fail open. Do not let an empty string reach `json.loads()` and surface as a 500 on stage.

Pin the exact model string in one place, `server/config.py`, and have C smoke-test it inside the first 15 minutes (§13). A 400 on the model name is the single most likely way this project is dead at T+2:50 for a reason nobody understands.

### 7.2 Chrome-only — enforced, not aspirational

Chrome is the only target. This is a constraint that *saves* time, so lean on it hard:

- **Manifest V3 only.** Service worker, not a background page.
- **Use the `chrome.*` namespace directly.** Not `browser.*`. No `webextension-polyfill`, no feature detection, no `const api = chrome || browser` shim. Every one of those is a dependency and a build step you don't have 3 hours for.
- **`"minimum_chrome_version": "114"`** in the manifest, so a stale browser fails loudly at load instead of mysteriously at runtime.
- **Chrome-only APIs are fair game.** `chrome.storage.local`, `chrome.scripting`, `chrome.runtime.sendMessage`, `declarativeNetRequest` — use them without hedging.
- **Everyone demos on the same Chrome build.** Agree the version at T+0:05. A per-laptop browser difference discovered at T+2:40 is unrecoverable.
- **The judge's laptop is not a target.** Demo runs on one known machine (D's, per §14).

Nobody writes a compatibility shim "just in case." If someone asks about Firefox during Q&A, the answer is "Chrome first, MV3 ports to Firefox in a week" and you move on.

---

## 8. Parallelization plan

### 8.1 The rule

**Nobody waits for anybody, ever.** Every dependency between two people is replaced by a frozen interface (§9) plus a fixture file checked in at T+0:20. You build against the fixture. The fixture is swapped for the real thing at a merge point. If your slice can't run alone, you built it wrong.

### 8.2 Dependency graph after fixtures

```
        real dependency          replaced by
A ──▶ B  (intercept event)   →   fixtures/product.json  +  mock event emitter
B ──▶ C  (HTTP interrogate)  →   fixtures/interrogate/*.json  +  MOCK_BACKEND flag
C ──▶ D  (db functions)      →   db.py stub returning fixtures  +  MOCK_LLM flag
D ──▶ B  (stats/profile)     →   fixtures/stats.json
A ──▶ D  (nothing)               —
```

After T+0:20 the graph has **no edges**. Four disconnected workstreams.

### 8.3 Stubs land before features

Your **first commit** is not your feature. It is your stub and your fixture, so that the three people downstream of you are unblocked before you've written a line of real logic. This is the highest-leverage 20 minutes in the project.

| Who | Ships by T+0:20 | Unblocks |
|-----|-----------------|----------|
| **A** | `fixtures/product.json` (a real extracted product object) + `mockEmit()` that fires `swiperno:intercept` from the console | B |
| **B** | Nothing — B is downstream of everyone. B starts on UI immediately. | — |
| **C** | `fixtures/interrogate/turn1.json`, `turn2.json`, `approved.json`, `denied.json` — exact response bodies, hand-written, *not* generated from a live DeepSeek call | B |
| **D** | `server/db.py` with all five functions returning hardcoded dicts + `demo/product.html` (saved retail page) | C, A |

`demo/product.html` matters more than it looks: it gives A a stable DOM that doesn't A/B-test itself mid-build, and it's what gets demoed.

### 8.4 Mock switches

Every layer runs with its upstream turned off.

| Flag | Where | Effect |
|------|-------|--------|
| `MOCK_BACKEND = true` | `extension/config.js` | B's modal resolves from `fixtures/interrogate/*` after 800ms. No server needed. |
| `?swiperno_mock=1` | URL on `demo/product.html` | Auto-fires a fake `swiperno:intercept` with `fixtures/product.json` on load. B needs no A. |
| `MOCK_LLM=1` | `server/.env` | `llm.py::complete()` returns canned verdicts with **zero DeepSeek calls**. D, A and B all work with no API key, no latency, no spend. This is the default for everyone except C until M2. |
| `MOCK_DB=1` | `server/.env` | `db.py` returns fixtures instead of touching SQLite. C can build the whole endpoint before the schema exists. |

All four default to **off** in the committed config. Flipping one on is a local edit you never commit.

### 8.5 Four vertical slices

Each slice has its own demo. At T+1:00 all four people can show their piece working on their own laptop with nothing else running.

| Slice | Standalone demo at T+1:00 |
|-------|---------------------------|
| **A — interception** | Open `demo/product.html`, Buy Now is dead, correct product object in console |
| **B — interrogation UI** | Open `demo/product.html?swiperno_mock=1`, full modal flow to both verdicts, against fixtures |
| **C — verdict engine** | `curl` a product, get a grounded question, then a scored verdict |
| **D — memory** | `python seed.py && curl localhost:8000/api/stats/1` returns a real savings number |

### 8.6 Rolling merges

Three small merges instead of one big one. Each has exactly two people in it; the other two keep building.

| Time | Merge | Who is in it | Who keeps working |
|------|-------|--------------|-------------------|
| **0:45** | **M1 — A→B seam.** A's real event drives B's modal. Delete `?swiperno_mock=1` path. | A, B | C, D |
| **1:15** | **M2 — C→D seam.** C's endpoint writes through D's real `db.py`. Delete `MOCK_DB`. | C, D | A, B |
| **1:45** | **M3 — full.** B points at the live backend. Delete `MOCK_BACKEND`. First end-to-end run. | all four | — |

M1 and M2 run **at the same time**. They touch disjoint directories, so they can't conflict.

If a merge slips 10 minutes, the two people in it keep going and the other two are unaffected. That's the point of splitting it up.

### 8.7 File ownership — no shared files

Nobody edits a path they don't own. Cross-directory changes are requested, not made.

| Person | Owns |
|--------|------|
| **A** | `extension/content.js`, `detector.js`, `overlay.css`, `background.js`, `manifest.json`, `extension/config.js` |
| **B** | `extension/modal/*`, `extension/popup/*` |
| **C** | `server/main.py`, `llm.py`, `prompts.py`, `config.py` (the pinned DeepSeek model string lives here, nowhere else) |
| **D** | `server/db.py`, `schema.sql`, `stats.py`, `seed.py`, `demo/*`, `README.md` |
| shared, frozen T+0:20 | `fixtures/*` — append-only after freeze. Never edit an existing fixture; add a new one. |

**Branching:** four long-lived branches `a-dom`, `b-ui`, `c-llm`, `d-data`, merged to `main` only at M1/M2/M3. No PRs, no review, direct merge. `main` must run at all times.

### 8.8 Parallelism killers — banned

1. **Renaming a §9 field after T+0:20.** Costs 20 minutes across four people. Wrong names ship.
2. **Editing someone else's directory "quickly."** Ask them; they're 30 seconds away.
3. **Waiting for the DeepSeek key.** One person gets it in the first 5 minutes; everyone else runs `MOCK_LLM=1` until then.
4. **Sitting on a broken `main`.** If your merge breaks it, revert your merge, don't debug on `main` while three people are blocked.
5. **Debugging in a group.** One person owns a bug. The other three keep building.
6. **Adding a second AI provider "as a backup."** Two providers means two keys, two response shapes, two prompt formats and two failure modes, in exchange for a fallback that fail-open (§9.5) already covers. Banned by N7.
7. **Writing a cross-browser shim.** Banned by §7.2.

---

## 9. Contracts — all four seams. FROZEN AT T+0:20.

Everything below is agreed once, out loud, by all four people, and then never renegotiated.

### 9.1 Seam A→B — DOM event

A emits on `document`, B listens. Nothing else crosses this boundary.

```js
// A fires this
new CustomEvent('swiperno:intercept', { detail: {
  intercept_id: "int_7f2a",          // opaque, B echoes it back
  product: {
    title: "Sony WH-1000XM5",
    price_cents: 34800,              // integer, never a string, never a float
    currency: "USD",
    url: "https://...",
    image_url: "https://...",
    site: "amazon",
    dom_snippet: "…max 4000 chars…"
  }
}})

// B calls one of these, always exactly one
window.__swiperno.approve(intercept_id)   // removes overlay, clicks the real element
window.__swiperno.dismiss(intercept_id)   // leaves overlay in place, starts cooldown
```

`price_cents` unparseable → send `null`, don't guess. B renders "unknown price" and C's prompt handles it.

### 9.2 Seam B→C — HTTP

```jsonc
// POST /api/interrogate
{
  "user_id": 1,
  "product": { /* exactly the product object from 9.1, passed through untouched */ },
  "session_id": null,          // null on first turn, echoed value after
  "message": null              // null on first turn, else the user's justification
}

// 200
{
  "session_id": "b1f3…",
  "verdict": "pending",        // "pending" | "approved" | "denied"
  "reply": "You already own two pairs of over-ears. What changed?",
  "turn": 1,
  "turns_remaining": 2,
  "score": null,               // 0-100 once verdict is final, null while pending
  "savings_total_cents": 128400
}
```

B passes `product` through byte-for-byte. B does not reshape, rename, or enrich it. This is what makes 9.1 and 9.2 one contract instead of two.

### 9.3 Seam C→D — Python

D publishes these signatures at T+0:20 as stubs. C imports them and never opens `db.py`.

```python
def get_context(user_id: int) -> dict:
    """{'profile': {...}, 'recent': [{'title','price_cents','verdict','created_at'}, ...]}
       'recent' is the last 5, newest first. Empty list if none."""

def start_purchase(user_id: int, product: dict) -> int:
    """Insert with verdict='abandoned'. Returns purchase_id."""

def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None: ...

def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None: ...

def stats(user_id: int) -> dict:
    """{'denied_count','approved_count','saved_cents','top_category'}"""
```

Rows are created as `abandoned` and updated on verdict, so a user who closes the tab mid-interrogation still leaves a trace and nothing is lost to a crash.

### 9.4 Seam D→B — HTTP

```jsonc
GET /api/stats/1
{ "denied_count": 12, "approved_count": 3, "saved_cents": 128400, "top_category": "electronics" }

GET | PUT /api/profile/1
{ "user_id": 1, "display_name": "…", "income_band": "…", "monthly_budget_cents": 200000,
  "savings_goal": "Japan trip", "goal_target_cents": 400000, "known_weakness": "mechanical keyboards" }
```

### 9.5 Error contract — applies to every seam

Any non-200, any timeout >8s, any malformed JSON → the extension **fails open**: overlay removed, purchase proceeds. A broken hackathon backend must never trap a judge on a real checkout page. B implements this once, in the fetch wrapper, on day one — not as a fix later.

---

## 10. Data model

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  display_name TEXT,
  income_band TEXT,
  monthly_budget_cents INTEGER,
  savings_goal TEXT,
  goal_target_cents INTEGER,
  known_weakness TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE purchases (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  site TEXT,
  product_title TEXT,
  price_cents INTEGER,
  currency TEXT DEFAULT 'USD',
  url TEXT,
  image_url TEXT,
  category TEXT,
  verdict TEXT CHECK (verdict IN ('approved','denied','abandoned')),
  score INTEGER,
  final_justification TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE turns (
  id INTEGER PRIMARY KEY,
  purchase_id INTEGER NOT NULL REFERENCES purchases(id),
  idx INTEGER,
  role TEXT CHECK (role IN ('assistant','user')),
  content TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_purchases_user ON purchases(user_id, created_at DESC);
```

`saved_cents = SELECT COALESCE(SUM(price_cents),0) FROM purchases WHERE user_id=? AND verdict='denied'`

## 11. Interrogator spec

Runs on `deepseek-v4-flash` via `llm.py::complete()`. Thinking mode off. See §7.1 for the model-ID warning and the three JSON-mode gotchas — this section assumes they're already handled.

**Persona:** a skeptical but fair friend who has seen your bank statement. Short. Never more than two sentences per turn. Never lectures.

**One call per turn** returns everything: the reply, the verdict, the score, and (P1) the category and roast line. Do not make a second DeepSeek call to classify or to roast.

**Call shape:**

```python
complete(
    model=config.DEEPSEEK_MODEL,          # "deepseek-v4-flash"
    messages=[system, *history, user],
    response_format={"type": "json_object"},
    max_tokens=300,                        # two sentences; also caps latency
    temperature=0.8,
    timeout=8,
)
```

The system prompt must contain the literal word **json** and a worked example of the output object — DeepSeek's JSON mode requires both. Empty content counts as a failure: one retry, then fail open.

**Rubric returned as strict JSON** (`{"verdict","score","reply"}`):
- 0–39 → denied. Pure want-framing, vague "I deserve it", contradicts stated savings goal.
- 40–69 → probe again (max 3 turns total, then round down to denied).
- 70–100 → approved. Concrete need, replacement of a broken item, already budgeted, time-bound external cause.

**Hard rule in the prompt:** approve immediately and skip remaining turns if the item is plausibly medical, food, safety, or work-required. Nobody's demo survives the extension blocking someone's insulin.

## 12. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Amazon DOM shifts / A-B test variant | High | Two-strategy detector: ID selectors first, then text-regex over all `button`/`input[type=submit]`/`a[role=button]`. `demo/product.html` is the stable target of record. |
| Overlay misaligns on scroll or sticky headers | High | Reposition on `scroll`/`resize` via rAF, plus a capture-phase `click` listener as a second net. |
| **`deepseek-chat` pasted from a tutorial → hard 400** | **High** | Alias died 2026/07/24. Model string pinned in `config.py` only; C smoke-tests it in the first 15 min (§13). Grep for `deepseek-chat` before every merge. |
| DeepSeek JSON mode returns empty content | Med | Documented DeepSeek behaviour. `llm.py` treats empty as failure → one retry → fail open. Never `json.loads("")`. |
| DeepSeek latency > 5s kills the demo | Med | `deepseek-v4-flash`, thinking mode off, `max_tokens=300`, 8s timeout, skeleton loader, fail open. Pre-warm one call before demoing. |
| Someone adds a second provider or a browser shim | Low | Banned by N7 and §7.2. Costs more than it saves at this timebox. |
| CORS from content script | Med | All fetches go through the background service worker; `host_permissions` set in manifest. |
| Real money spent during a live demo | Med | Demo on `demo/product.html`. Do not click through on stage with a real card. |
| One person's slice slips and stalls the other three | Med | §8 — fixtures, mock flags, disjoint directories, three small merges instead of one. |
| Merge conflicts | Low, once §8.7 holds | Four branches, four directories, no shared files except append-only `fixtures/`. |

## 13. Timeline

| Time | A | B | C | D |
|------|---|---|---|---|
| **0:00–0:15** | repo, venv, `DEEPSEEK_API_KEY` in `.env`, extension loads unpacked in an agreed Chrome version, everyone gets "hello" on a page. **C curls `deepseek-v4-flash` and confirms a 200 before anything else is built.** | ← | ← | ← |
| **0:15–0:20** | **CONTRACT FREEZE.** All four read §9 aloud and agree field names. | ← | ← | ← |
| **0:20** | ship `fixtures/product.json` + `mockEmit()` | — | ship `fixtures/interrogate/*` | ship `db.py` stub + `demo/product.html` |
| **0:20–0:45** | detector + overlay (`chrome.*` direct, MV3 SW) | modal shell, states, fetch wrapper w/ fail-open | `config.py` + `llm.py` (DeepSeek client, retry, empty-content guard), `MOCK_LLM` | `schema.sql`, real `db.py` |
| **0:45** | **M1 — A→B** | **M1** | (keeps building) | (keeps building) |
| **0:45–1:15** | context extraction, per-site adapters | verdict states, approve path | prompt + rubric, JSON-mode wiring (word "json" + example in prompt), real `deepseek-v4-flash` call | `seed.py` — 12 realistic prior purchases |
| **1:15** | (keeps building) | (keeps building) | **M2 — C→D** | **M2** |
| **1:15–1:45** | harden detector on demo page | popup: stats + onboarding | history injection into prompt | `/api/stats`, `/api/profile` |
| **1:45** | **M3 — full end-to-end.** All four. | | | |
| **1:45–2:15** | fix integration. C tunes prompt against real seeded history. | | | |
| **2:15** | **FEATURE FREEZE.** Bug fixes and P1-1 only. No new files. | | | |
| **2:15–2:45** | rehearsal take 1. Anything broken gets deleted, not fixed. | | | D drives |
| **2:45–3:00** | rehearsal take 2, commit, stop touching the laptop. | | | |

## 14. Demo script (90 seconds)

1. `demo/product.html` open. Click **Buy Now**. Nothing happens — modal appears.
2. Type "I want it." → LLM: *"Your goal is a Japan trip and you're $2,700 short. Try again."*
3. Type "my headphones broke and I have calls all day" → **APPROVED**, real click fires.
4. Open popup: **$1,284 saved, 12 purchases blocked.**
5. Close on the ad slot joke.

## 15. Success criteria

Ship-blocking: G1–G5 all demonstrated in one unbroken take, on one Chrome instance, without a code change mid-demo.
Process: all three merges (M1, M2, M3) land on time, and no engineer is idle-blocked for more than 5 minutes at any point.
Hygiene: `grep -r "deepseek-chat\|deepseek-reasoner\|browser\.\|webextension-polyfill" .` returns nothing at freeze.
