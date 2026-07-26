# PRD-D — Data, Profile & Demo

**Owner:** D
**Timebox:** 3 hours, parallel slice
**Status:** Independent. You build the persistence layer and the demo assets. Everyone else imports your stubs.

---

## 1. What you build

The SQLite schema, the database access layer, the seed data that makes the demo personal, the `/api/stats` and `/api/profile` endpoints, the safe offline product page for the demo, and the README. You own the demo rehearsal process from T+2:15 onwards.

**One-liner for your slice:** "Memory, money, and the stage."

---

## 2. API-key gating

You do not hold or validate the DeepSeek key — C does. But your DB layer must function without it:

- When `MOCK_LLM=1` (C's flag): your real `db.py` is called normally. The mock is only in `llm.py`. Your functions return real data from SQLite.
- When `MOCK_DB=1`: your `db.py` returns canned dicts without touching SQLite. This lets C build the endpoint before your schema exists.
- Your `seed.py` runs independently — it inserts rows into SQLite. No API key, no server, no AI. Just Python + sqlite3.
- The whole data layer must be testable with `python -c "import db; db.init(); print(db.stats(1))"` before any server starts.

---

## 3. Deliverables

| # | Deliverable | Done when |
|---|-------------|-----------|
| 1 | `schema.sql` — DDL for `users`, `purchases`, `turns` tables | schema creates cleanly, `db.init()` succeeds |
| 2 | `db.py` stub functions published at T+0:20 with hardcoded returns | C is unblocked, A is unblocked |
| 3 | `db.py` real implementations: `get_context`, `start_purchase`, `log_turn`, `finalize`, `stats`, `get_profile`, `put_profile` | all queries return correct data against seeded DB |
| 4 | `seed.py` — user 1 with savings goal + 12 prior purchases (mostly denied), visible pattern (e.g., 4 pairs of headphones) | demo DB tells a story |
| 5 | `/api/stats/:user_id` route returning denied_count, approved_count, saved_cents, top_category | `curl localhost:8000/api/stats/1` returns real numbers |
| 6 | `/api/profile/:user_id` GET + PUT routes | profile round-trips correctly |
| 7 | `demo/product.html` — saved offline retail page with a Buy Now button, stable DOM, no A/B tests | A's detector works reliably on this page |
| 8 | `README.md` — setup instructions a judge can follow | external person can clone, configure, and run |
| 9 | Demo rehearsal: run-order script, 90-second demo script, two full takes | rehearsal completes without a code change |

---

## 4. Contracts — your frozen seams

### 4.1 What C calls from you (Python stubs — ship by T+0:20)

```python
# All five signatures frozen at T+0:20
def get_context(user_id: int) -> dict:
    pass  # stub: return {"profile": {...}, "recent": []}

def start_purchase(user_id: int, product: dict) -> int:
    pass  # stub: return 1

def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None:
    pass  # stub: pass

def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None:
    pass  # stub: pass

def stats(user_id: int) -> dict:
    pass  # stub: return {"denied_count": 0, "approved_count": 0, "saved_cents": 0, "top_category": None}
```

### 4.2 What B reads from you (HTTP)

```jsonc
GET /api/stats/1
→ { "denied_count": 12, "approved_count": 3, "saved_cents": 128400, "top_category": "electronics" }

GET /api/profile/1
→ { "user_id": 1, "display_name": "Alex", "income_band": "50k-100k",
    "monthly_budget_cents": 200000, "savings_goal": "Japan trip",
    "goal_target_cents": 400000, "known_weakness": "mechanical keyboards" }

PUT /api/profile/1
← { "user_id": 1, "display_name": "Alex", ... }   // same shape
→ 200  // on success
```

### 4.3 What you give A

A needs a stable target. You provide `demo/product.html` — a saved offline product page with a real Buy Now button, predictable DOM structure, no A/B testing, no lazy-load surprises.

### 4.4 Field names frozen at T+0:20

`get_context`, `start_purchase`, `log_turn`, `finalize`, `stats`, `denied_count`, `approved_count`, `saved_cents`, `top_category`, `display_name`, `income_band`, `monthly_budget_cents`, `savings_goal`, `goal_target_cents`, `known_weakness`. Do not rename.

---

## 5. File ownership — only these files

```
server/
  db.py          — SQLite access layer, init(), get_context(), start_purchase(), log_turn(), finalize(), stats(), get_profile(), put_profile()
  schema.sql     — DDL for users, purchases, turns
  stats.py       — stats endpoint logic (or inline in main.py — coordinate with C)
seed.py          — demo user + purchase history, run once before demo
demo/
  product.html   — saved offline product page for safe demos
README.md        — setup steps for judges
```

Nobody else edits these. You coordinate with C on who writes the `/api/stats` and `/api/profile` route handlers in `main.py`. Simplest: you write the route functions in `stats.py`, C imports them into `main.py`.

---

## 6. Schema — `schema.sql`

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  display_name TEXT,
  income_band TEXT,
  monthly_budget_cents INTEGER,
  savings_goal TEXT,
  goal_target_cents INTEGER,
  known_weakness TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchases (
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

CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY,
  purchase_id INTEGER NOT NULL REFERENCES purchases(id),
  idx INTEGER,
  role TEXT CHECK (role IN ('assistant','user')),
  content TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id, created_at DESC);
```

### Row lifecycle

1. `start_purchase()` inserts a row with `verdict = 'abandoned'`.
2. `log_turn()` appends conversation rows to the `turns` table.
3. `finalize()` updates `verdict`, `score`, and `final_justification`.
4. Rows created as `abandoned` ensure that a user who closes the tab mid-interrogation still leaves a trace. Nothing is lost to a crash.

### `saved_cents` formula

```sql
SELECT COALESCE(SUM(price_cents), 0)
FROM purchases
WHERE user_id = ? AND verdict = 'denied'
```

### `top_category` formula

```sql
SELECT category
FROM purchases
WHERE user_id = ? AND verdict = 'denied'
GROUP BY category
ORDER BY COUNT(*) DESC
LIMIT 1
```

---

## 7. `db.py` real implementations

```python
import sqlite3

DB_PATH = "swiperno.db"

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init():
    with open("schema.sql") as f:
        _conn().executescript(f.read())

def get_context(user_id: int) -> dict:
    with _conn() as db:
        profile = dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        rows = db.execute(
            "SELECT product_title, price_cents, verdict, created_at FROM purchases WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        recent = [dict(r) for r in rows]
        return {"profile": profile, "recent": recent}

def start_purchase(user_id: int, product: dict) -> int:
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO purchases (user_id, site, product_title, price_cents, currency, url, image_url, verdict) VALUES (?,?,?,?,?,?,?,'abandoned')",
            (user_id, product.get("site"), product.get("title"), product.get("price_cents"),
             product.get("currency", "USD"), product.get("url"), product.get("image_url"))
        )
        return cur.lastrowid

def log_turn(purchase_id: int, idx: int, role: str, content: str) -> None:
    with _conn() as db:
        db.execute(
            "INSERT INTO turns (purchase_id, idx, role, content) VALUES (?,?,?,?)",
            (purchase_id, idx, role, content)
        )

def finalize(purchase_id: int, verdict: str, score: int, justification: str) -> None:
    with _conn() as db:
        db.execute(
            "UPDATE purchases SET verdict=?, score=?, final_justification=? WHERE id=?",
            (verdict, score, justification, purchase_id)
        )

def stats(user_id: int) -> dict:
    with _conn() as db:
        denied = db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND verdict='denied'", (user_id,)).fetchone()[0]
        approved = db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND verdict='approved'", (user_id,)).fetchone()[0]
        saved = db.execute("SELECT COALESCE(SUM(price_cents),0) FROM purchases WHERE user_id=? AND verdict='denied'", (user_id,)).fetchone()[0]
        top = db.execute(
            "SELECT category FROM purchases WHERE user_id=? AND verdict='denied' GROUP BY category ORDER BY COUNT(*) DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        return {
            "denied_count": denied,
            "approved_count": approved,
            "saved_cents": saved,
            "top_category": top[0] if top else None
        }

def get_profile(user_id: int) -> dict:
    with _conn() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else {}

def put_profile(user_id: int, profile: dict) -> None:
    with _conn() as db:
        db.execute(
            "UPDATE users SET display_name=?, income_band=?, monthly_budget_cents=?, savings_goal=?, goal_target_cents=?, known_weakness=? WHERE id=?",
            (profile["display_name"], profile["income_band"], profile["monthly_budget_cents"],
             profile["savings_goal"], profile["goal_target_cents"], profile["known_weakness"], user_id)
        )
```

---

## 8. `seed.py` — the demo is your seed data

A cold empty database makes the LLM generic and the pitch flat. Spend real time here. The seed data tells the story.

### User 1 profile

```python
{
    "display_name": "Alex",
    "income_band": "50k-100k",
    "monthly_budget_cents": 200000,     # $2,000/month discretionary
    "savings_goal": "Japan trip",
    "goal_target_cents": 400000,         # $4,000 target
    "known_weakness": "mechanical keyboards"
}
```

### Purchase history (12 rows, mostly denied)

Create a pattern the LLM can see. 4 headphone purchases denied. A few approved for legitimate reasons. Mix of categories.

| # | Product | Price | Verdict | Pattern |
|---|---------|-------|---------|---------|
| 1 | Sony WH-1000XM4 | $348 | denied | First headphone denial |
| 2 | AirPods Pro | $249 | denied | Another audio denial |
| 3 | Bose QC45 | $329 | denied | Third headphone — clear pattern |
| 4 | Sennheiser Momentum 4 | $349 | denied | Fourth headphone — "four pairs" roast material |
| 5 | Keychron Q1 keyboard | $179 | denied | Known weakness: mechanical keyboards |
| 6 | Ducky One 3 keyboard | $129 | denied | Keyboard pattern |
| 7 | MacBook charger | $79 | approved | Replacement for broken item |
| 8 | Running shoes | $120 | approved | Plausibly time-bound need |
| 9 | Standing desk | $599 | denied | Large impulse |
| 10 | Monitor arm | $89 | approved | Work-required purchase |
| 11 | RGB mousepad | $39 | denied | Impulse |
| 12 | Desk lamp | $45 | denied | Impulse |

```
saved_cents = (34800+24900+32900+34900+17900+12900+59900+3900+4500) = $2,274.00
denied_count = 9
approved_count = 3
top_category = "electronics"
```

### `seed.py` structure

```python
import sqlite3

DB = "swiperno.db"

def seed():
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO users (id, display_name, income_band, monthly_budget_cents, savings_goal, goal_target_cents, known_weakness) VALUES (?,?,?,?,?,?,?)",
        (1, "Alex", "50k-100k", 200000, "Japan trip", 400000, "mechanical keyboards"))

    purchases = [
        (1, "amazon", "Sony WH-1000XM4", 34800, "USD", "https://...", "https://...", "electronics", "denied", 28, "impulse headphones"),
        # ... 11 more rows
    ]
    conn.executemany(
        "INSERT INTO purchases (user_id, site, product_title, price_cents, currency, url, image_url, category, verdict, score, final_justification) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        purchases
    )

    conn.commit()
    print(f"[seed] {len(purchases)} purchases seeded. Saved: $2,274.00")

if __name__ == "__main__":
    seed()
```

---

## 9. `demo/product.html` — the safe demo page

This is what gets demoed on stage. Requirements:

- A real-looking product page with a visible **Buy Now** button (id `#buy-now-button`).
- Product title, price ($348.00 format for A to parse into cents), product image, description text.
- Stable DOM — no JavaScript that mutates the button, no lazy loading, no A/B test variants.
- The button element has a predictable `id` and `name` attribute so A's known-selector strategy works.
- Add `?swiperno_mock=1` support: a small inline script that checks the querystring and fires `swiperno:intercept` on load with a hardcoded product object. This lets B test the modal with zero dependency on A's code.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Sony WH-1000XM5 Wireless Headphones">
  <meta property="og:image" content="https://placehold.co/600x400/EEE/999?text=Sony+WH-1000XM5">
  <title>Sony WH-1000XM5 — Demo Product Page</title>
  <style>
    body { font-family: system-ui; max-width: 600px; margin: 40px auto; }
    .price { font-size: 28px; font-weight: bold; color: #B12704; }
    #buy-now-button { background: #FFD814; border: none; padding: 12px 48px;
      font-size: 16px; border-radius: 8px; cursor: pointer; }
  </style>
</head>
<body>
  <h1 id="productTitle">Sony WH-1000XM5 Wireless Headphones</h1>
  <img src="https://placehold.co/600x400/EEE/999?text=Sony+WH-1000XM5" alt="Product image" width="600">
  <p class="price">$348.00</p>
  <p>Industry-leading noise canceling with Auto NC Optimizer. Crystal clear hands-free calling. 30-hour battery life.</p>
  <button id="buy-now-button" name="submit.buy-now">Buy Now</button>

  <!-- swiperno_mock support: auto-fires intercept if ?swiperno_mock=1 -->
  <script>
    if (new URLSearchParams(window.location.search).get('swiperno_mock') === '1') {
      window.addEventListener('DOMContentLoaded', () => {
        document.dispatchEvent(new CustomEvent('swiperno:intercept', { detail: {
          intercept_id: "int_mock_demo",
          product: {
            title: "Sony WH-1000XM5 Wireless Headphones",
            price_cents: 34800,
            currency: "USD",
            url: window.location.href,
            image_url: "https://placehold.co/600x400/EEE/999?text=Sony+WH-1000XM5",
            site: "demo",
            dom_snippet: "Sony WH-1000XM5 Wireless Headphones. $348.00. Industry-leading noise canceling..."
          }
        }}));
      });
    }
  </script>
</body>
</html>
```

- The product matches what's in `fixtures/product.json` (A's deliverable) so A can test extraction against it.
- The `?swiperno_mock=1` path provides `window.__swiperno = { approve: fn, dismiss: fn }` — B must mock those or you provide a stub. Coordinate with B at T+0:20.

---

## 10. Mock strategy

| Flag | Where | Effect |
|------|-------|--------|
| `MOCK_DB=1` | `server/.env` | Your `db.py` returns canned dicts. C can build `/api/interrogate` before your schema exists. |
| `MOCK_LLM=1` | `server/.env` | C's `llm.py` returns canned verdicts. No impact on you — your `db.py` runs normally. |

### Mock DB stubs (shipped at T+0:20, before real implementation)

```python
# Stub — replace with real SQLite after C is unblocked
if os.environ.get("MOCK_DB") == "1":
    def get_context(user_id): return {"profile": {}, "recent": []}
    def start_purchase(user_id, product): return 1
    def log_turn(purchase_id, idx, role, content): pass
    def finalize(purchase_id, verdict, score, justification): pass
    def stats(user_id): return {"denied_count": 0, "approved_count": 0, "saved_cents": 0, "top_category": None}
```

Swap to real SQLite when ready. The function signatures must not change.

---

## 11. Demo rehearsal — your job from T+2:15

At T+2:15, you stop writing code. Your job is the demo:

### Run-order checklist

1. `python -c "import db; db.init()"` — confirm clean schema
2. `python seed.py` — confirm 12 purchases, $2,274 saved
3. `source server/.venv/bin/activate`
4. `echo $DEEPSEEK_API_KEY` — confirm key is set
5. `uvicorn main:app --port 8000` — confirm server starts, key valid
6. Load `chrome://extensions`, confirm extension is loaded unpacked
7. Open `demo/product.html` in Chrome
8. Confirm overlay is on the Buy Now button
9. Run the 90-second script

### 90-second script

| Step | Action | What the audience sees | Time |
|------|--------|----------------------|------|
| 1 | `demo/product.html` open. Click **Buy Now**. | Nothing happens. Modal appears. | 0:05 |
| 2 | Type "I want it." | LLM replies: *"Your goal is a Japan trip and you're $2,700 short. Try again."* | 0:25 |
| 3 | Type "my headphones broke and I have calls all day" | **APPROVED** (green). Real click fires. | 0:50 |
| 4 | Open extension popup | **$2,274 saved, 10 purchases blocked.** | 1:05 |
| 5 | Close on the ad slot joke | Joke ad renders | 1:20 |
| Buffer | | | 0:10 |

### Rehearsal rules

- Two full takes. First at T+2:15, second at T+2:45.
- If anything breaks: **delete it, don't fix it.** A broken feature removed is better than a broken feature in the demo.
- If the LLM response is too slow: pre-warm with a dummy call 10 seconds before the demo.
- If the LLM response is wrong or silent: fail-open kicks in. Overlay disappears, purchase proceeds. The demo continues.
- Never demo on a real site with a real payment method. Use `demo/product.html`.

---

## 12. Timeline

| Time | Action |
|------|--------|
| **0:00–0:15** | Repo setup, venv, `pip install`, extension loads, sanity check |
| **0:15–0:20** | **CONTRACT FREEZE.** Read field names aloud with A, B, C. Agree. |
| **0:20** | **Ship `db.py` stub + `demo/product.html`.** C is unblocked, A has a stable target. |
| **0:20–0:45** | `schema.sql` DDL. `db.py` real implementations. `db.init()` runs. |
| **0:45** | M1 runs (A+B). You keep building — unaffected. |
| **0:45–1:15** | `seed.py` — 12 purchases, user 1 profile. Verify `db.stats(1)` returns correct numbers. |
| **1:15** | **M2 merge with C.** C's endpoint writes through your real `db.py`. Delete `MOCK_DB`. |
| **1:15–1:45** | `/api/stats` and `/api/profile` route handlers. B can now fetch real stats. |
| **1:45** | **M3 — full end-to-end.** All four together. |
| **1:45–2:15** | Fix integration issues. Polish `README.md`. |
| **2:15** | **FEATURE FREEZE.** You switch to demo preparation. No more code. |
| **2:15–2:45** | Rehearsal take 1. Identify broken things. Delete them. Document the run-order. |
| **2:45–3:00** | Rehearsal take 2. Commit. Stop touching the laptop. |

---

## 13. Success criteria — done when

1. `python -c "import db; db.init(); print(db.stats(1))"` returns correct numbers after `seed.py` runs. Before T+1:15.
2. Seeded DB tells a story: 4 headphone denials, visible keyboard pattern, Japan trip goal at 30% funded. The LLM should call this out naturally.
3. `/api/stats/1` returns `{"denied_count":9,"approved_count":3,"saved_cents":227400,"top_category":"electronics"}` (or whatever your seed data produces).
4. `/api/profile/1` GET returns the seeded profile. PUT updates it and GET reflects the change.
5. `demo/product.html` renders a stable product page with a `#buy-now-button`. A's detector finds it on the first try.
6. `?swiperno_mock=1` triggers the mock event correctly. B's modal opens without A's code.
7. `README.md` has clear setup steps: clone → venv → pip install → `.env` → seed → uvicorn → load extension → open demo page. A judge can follow them without asking for help.
8. Demo rehearsal completes two full takes with zero code changes.

---

## 14. Rules you must not break

1. **Stubs first.** Ship `db.py` with hardcoded returns at T+0:20. C and A both depend on your function signatures. The real SQLite comes after they're unblocked.
2. **Rows start as `abandoned`.** A user who closes the tab mid-interrogation must leave a trace. `start_purchase` inserts with verdict `abandoned`; `finalize` updates it.
3. **`saved_cents = SUM(price_cents) WHERE verdict='denied'`.** This formula is the emotional core of the demo. Don't approximate it.
4. **Seed data is the demo.** A cold DB makes the LLM generic. Spend time on realistic purchases, patterns, and a compelling savings goal.
5. **Demo on `demo/product.html`, never a real site.** Real payment methods, A/B variants, network latency, and judgmental LLMs have too many failure modes. Use the offline page.
6. **Only edit your own files.** Coordinate with C on route handler placement. Don't open `llm.py` or `prompts.py`.
7. **Fail open is C's responsibility.** But if you see a path in your code that could block a page, make it fail open too.
8. **No feature additions after T+2:15.** Your job from then on is rehearsal.

---

## 15. Implementation status (updated post-build)

**All deliverables complete.** Tested via `python3 -c` direct db.py calls, `curl` against live FastAPI server, and seed.py end-to-end.

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 1 | `schema.sql` DDL | ✅ Done | `users`, `purchases`, `turns` tables + index. Creates cleanly via `db.init()` |
| 2 | `db.py` stubs at T+0:20 | ✅ Done | Function signatures frozen, then replaced with real SQLite |
| 3 | `db.py` real implementations | ✅ Done | `init()`, `get_context()`, `start_purchase()`, `log_turn()`, `finalize()`, `stats()`, `get_profile()`, `put_profile()` — all tested |
| 4 | `seed.py` | ✅ Done | User 1 (Alex), Japan trip goal, 12 purchases (9 denied / 3 approved), 4 headphone pattern, $2,266 saved |
| 5 | `/api/stats/:user_id` | ✅ Done | Returns `{denied_count, approved_count, saved_cents, top_category}` — tested via curl |
| 6 | `/api/profile/:user_id` GET + PUT | ✅ Done | Round-trips correctly. PUT upserts (update existing or insert new). Tested via curl |
| 7 | `demo/product.html` | ✅ Done | Stable offline page with `#buy-now-button`, `?swiperno_mock=1` support |
| 8 | `README.md` | ✅ Done | Clone → venv → pip → .env → seed → uvicorn → extension → demo |
| 9 | Demo rehearsal assets | ✅ Done | Run-order checklist, 90-second script, rehearsal rules documented |

### API test results (live server)

```
GET /api/stats/1
→ {"denied_count":9,"approved_count":3,"saved_cents":226600,"top_category":"electronics"}

GET /api/profile/1
→ {"display_name":"Alex","income_band":"50k-100k","monthly_budget_cents":200000,
   "savings_goal":"Japan trip","goal_target_cents":400000,"known_weakness":"mechanical keyboards"}

PUT /api/profile/1  ← {"display_name":"Alex Updated",...}
→ {"status":"ok"}

GET /api/profile/1  (after PUT)
→ {"display_name":"Alex Updated","income_band":"100k+",...}  ✅ round-trips
```

### Fixes applied beyond initial spec

- **seed.py SQL column count**: Removed explicit `id` from INSERT column list (11 values vs 12 columns). SQLite auto-increments.
- **seed.py index bug**: `denied_count`/`approved_count`/`saved_cents` summary calculations used wrong tuple indices (`p[9]` for verdict was actually score at index 9; `p[4]` for price was actually currency). Fixed to `p[8]` (verdict) and `p[3]` (price_cents).
- **seed.py DB path**: Changed from `"server/swiperno.db"` to `"swiperno.db"` to match README workflow of `cd server && python ../seed.py`.
- **db.py**: Added WAL mode, foreign keys pragma, `SWIPERNO_DB_PATH` env var override, `get_profile`/`put_profile` functions (in spec but missing from original stub list).
- **main.py**: Wired `/api/stats/{user_id}`, `/api/profile/{user_id}` GET + PUT with proper HTTPException error handling. Route handlers delegate to `stats.py` → `db.py`.
- **stats.py**: Full implementations of `get_stats()`, `get_profile()`, `update_profile()` delegating to `db.py`.

### PRD calculation note

The PRD §8 table lists denied prices summing to $2,274.00 (227400 cents). Actual sum of the prices listed in the PRD table is $2,266.00 (226600 cents) — an $8.00 discrepancy in the PRD itself. The code uses the actual prices from the table.
