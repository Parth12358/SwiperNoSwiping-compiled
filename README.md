# SwipernoSwiping

> Your wallet now has a lawyer, and the lawyer thinks you're lying.

A Chrome extension that covers the **Buy Now** button with an invisible wall. To get through it, you have to justify the purchase to an LLM that has read your budget, your savings goal, and the last twelve things you bought.

Weak excuse → **DENIED**, and the money moves to your "saved" counter.
Real reason → **APPROVED**, and the click goes through untouched.

Built in 3 hours.

---

## How it works

```
product page
   │
   ├─ content.js scans the DOM for buy / checkout / add-to-cart buttons
   ├─ a transparent <div> is drawn on top of each one — the click never lands
   │
   ▼  you click anyway
modal opens
   │
   ├─ product context (title, price, trimmed DOM snippet) → backend
   ├─ backend adds your profile + last 5 purchases from SQLite
   ├─ DeepSeek plays skeptical friend, max 3 questions
   │
   ▼
verdict
   ├─ APPROVED → overlay removed, real button clicked for you
   └─ DENIED   → logged, price added to savings total, 10-minute cooldown on that item
```

---

## Stack

| Layer | Choice |
|-------|--------|
| Extension | **Chrome only** — MV3, vanilla JS, `chrome.*` namespace, shadow-DOM modal |
| Backend | FastAPI on `localhost:8000` |
| AI | **DeepSeek, everywhere** — `deepseek-v4-flash`, JSON mode, one client module |
| DB | SQLite (`swiperno.db`) |

The backend exists for two reasons: the DeepSeek key must not sit in a content script, and SQLite needs a filesystem.

**DeepSeek is the sole AI provider.** Every AI call in the project — the interrogator's questions, the verdict, the scoring, the category tag, the roast line — goes through `server/llm.py` to DeepSeek. There is no second provider and no fallback model; if DeepSeek is unreachable the extension fails open (see below).

**Chrome only, deliberately.** No `browser.*`, no `webextension-polyfill`, no cross-browser shims. Requires Chrome 114+.

---

## Setup

**Requirements:** Python 3.10+, Chrome 114+, a [DeepSeek API key](https://platform.deepseek.com/api_keys).

### 1. Backend

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

echo "DEEPSEEK_API_KEY=sk-..." > .env

python -c "import db; db.init()"   # creates swiperno.db from schema.sql
python ../seed.py                  # seeds user 1 + purchase history

uvicorn main:app --reload --port 8000
```

Sanity check the DB:

```bash
curl localhost:8000/api/stats/1
# {"denied_count":12,"approved_count":3,"saved_cents":128400,"top_category":"electronics"}
```

Sanity check DeepSeek:

```bash
curl https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}]}'
```

> ⚠️ **Use `deepseek-v4-flash`, not `deepseek-chat`.** The `deepseek-chat` and `deepseek-reasoner` aliases were deprecated on 2026-07-24 15:59 UTC and now return errors with no fallback. Most tutorials and code-assistant suggestions still use them. The model string is pinned in `server/config.py` — change it there, nowhere else.

### 2. Extension

1. `chrome://extensions`
2. Toggle **Developer mode** on
3. **Load unpacked** → select the `extension/` directory
4. Open the extension popup and fill in the onboarding form (budget, savings goal, known weakness)

### 3. Try it

Open any supported product page and click Buy Now. Nothing happens. That's the feature.

Or use the offline demo page, which is safer and doesn't involve a real card:

```bash
open demo/product.html
```

---

## Config

`server/.env`

| Key | Default | Notes |
|-----|---------|-------|
| `DEEPSEEK_API_KEY` | — | required, server-side only, never in the extension |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | escalate to `deepseek-v4-pro` only if verdicts are too soft |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible; use the `openai` SDK against it |
| `MAX_TURNS` | `3` | questions before the verdict is forced |
| `APPROVE_THRESHOLD` | `70` | score 0–100 needed to pass |
| `LLM_TIMEOUT_S` | `8` | after this, fails open |
| `MOCK_LLM` | `0` | `1` runs the whole app with canned verdicts and zero DeepSeek calls |

---

## API

```jsonc
POST /api/interrogate
{ "user_id": 1,
  "product": { "title": "...", "price_cents": 34800, "url": "...", "dom_snippet": "..." },
  "session_id": null,
  "message": null }

→ { "session_id": "b1f3…", "verdict": "pending",
    "reply": "You already own two pairs of over-ears. What changed?",
    "turn": 1, "turns_remaining": 2, "score": null,
    "savings_total_cents": 128400 }
```

`verdict` is one of `pending` · `approved` · `denied`.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/interrogate` | start or continue an interrogation |
| `GET /api/stats/:user_id` | denied count, approved count, money saved |
| `GET \| PUT /api/profile/:user_id` | onboarding profile |

---

## Fail open

If the backend is down, DeepSeek times out, or the JSON comes back malformed or empty, the overlay is removed and the purchase goes through. A shopping extension that can trap you on a checkout page is worse than no extension.

There is deliberately no fallback provider. Fail-open covers the same failures without a second key, a second response shape, and a second set of bugs.

The interrogator is also prompted to approve immediately, skipping remaining turns, when an item is plausibly medical, food, safety, or work-required.

---

## Layout

```
extension/
  manifest.json
  content.js          # scan, overlay, intercept
  detector.js         # selector + text-regex strategies, per-site adapters
  background.js       # fetch proxy (keeps the content script same-origin)
  modal/              # shadow-DOM interrogation UI
  popup/              # stats + onboarding form
server/
  main.py             # routes
  llm.py              # DeepSeek client, JSON mode, timeout, fail-open
  prompts.py          # interrogator persona + scoring rubric
  db.py               # SQLite access layer
  schema.sql
  stats.py
seed.py               # demo user + purchase history
demo/product.html     # offline page for safe demos
```

---

## Known limits

- Two retailers detected reliably. Everything else falls back to text matching and is a coin flip.
- Anyone can open devtools and delete the overlay. It's a speed bump, not a vault.
- Single hardcoded user (`user_id = 1`). No auth, no sync.
- Chrome 114+ only, by design. MV3 would port to Firefox in about a week; nobody has done it.
- DeepSeek only. If DeepSeek is down, the extension is a no-op (which is the safe direction).
- Session state is an in-memory dict. Restart the server and open interrogations vanish.

---

## About the ads

The pitch includes an ad slot in the modal. It renders from a static `ads.json` and picks at random — **no user data feeds ad selection**, ever. Serving targeted ads against someone's spending weaknesses is the exact thing this project is making fun of, and building it for real would be both harmful and a fast way to get pulled from the store. The joke stays in the deck.

---

## Docs

- [`PRD.md`](./PRD.md) — master overview: scope, contracts, data model, risks, demo script
- [`TEAMSPLIT.md`](./TEAMSPLIT.md) — ownership map and the 3-hour timeline
- [`PRD-A-extension.md`](./PRD-A-extension.md) — Engineer A: Extension & DOM interception
- [`PRD-B-modal.md`](./PRD-B-modal.md) — Engineer B: Modal UI & Popup
- [`PRD-C-llm.md`](./PRD-C-llm.md) — Engineer C: Backend & DeepSeek LLM
- [`PRD-D-data.md`](./PRD-D-data.md) — Engineer D: Data, Profile & Demo
- [`PRD-pitch.md`](./PRD-pitch.md) — Pitch deck: sell this extension to judges/investors
