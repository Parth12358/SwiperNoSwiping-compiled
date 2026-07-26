# TEAMSPLIT — SwipernoSwiping

4 people · 180 minutes · one repo · zero merge conflicts if you respect the directory boundaries.

> **Your individual PRD has the full spec for your slice:**
> - A → [`PRD-A-extension.md`](./PRD-A-extension.md)
> - B → [`PRD-B-modal.md`](./PRD-B-modal.md)
> - C → [`PRD-C-llm.md`](./PRD-C-llm.md)
> - D → [`PRD-D-data.md`](./PRD-D-data.md)
> - Pitch → [`PRD-pitch.md`](./PRD-pitch.md)

---

## Ownership map

Nobody edits a directory they don't own. If you need something changed in someone else's directory, you ask them. This is the whole conflict-avoidance strategy.

| Person | Role | Owns (only these paths) |
|--------|------|-------------------------|
| **A** | Extension / DOM | `extension/content.js`, `extension/detector.js`, `extension/overlay.css`, `extension/manifest.json`, `extension/background.js` |
| **B** | Modal / Frontend | `extension/modal/*` (js, html, css), `extension/popup/*` |
| **C** | Backend / DeepSeek | `server/main.py`, `server/llm.py`, `server/prompts.py`, `server/config.py` |
| **D** | Data / Profile / Demo | `server/db.py`, `server/schema.sql`, `server/stats.py`, `seed.py`, `demo/*`, `README.md` |

**Shared, edited once, at T+0:20, together, then frozen:** `CONTRACT.md` (the JSON shapes from PRD §8).

---

## A — Extension & DOM interception

**Deliverable:** clicking Buy Now on a real product page does nothing except emit a `swiperno:intercept` CustomEvent carrying product context.

1. MV3 manifest, `host_permissions` for the two demo domains, content script at `document_idle`, `"minimum_chrome_version": "114"`.
   **Chrome only** (PRD §7.2). Use `chrome.*` directly — no `browser.*`, no `webextension-polyfill`, no `const api = chrome || browser` shim. Service worker, not a background page. Chrome-only APIs are fair game; don't hedge.
2. `detector.js` — two strategies, in order:
   - known selectors: `#buy-now-button`, `#add-to-cart-button`, `[name=submit.buy-now]`, `[id*=checkout i]`, `[data-testid*=checkout i]`
   - fallback: scan `button, input[type=submit], a[role=button]` for text matching `/buy now|add to cart|place order|proceed to checkout|complete purchase|pay now/i`
3. Overlay: for each match, append a `div` to `document.body`, position from `getBoundingClientRect()` + scroll offsets, `position:absolute; z-index:2147483647; background:transparent; cursor:not-allowed`. Reposition on `scroll` and `resize` inside `requestAnimationFrame`. Re-scan on `MutationObserver` (debounced 300ms).
4. Belt and braces: also register a capture-phase `click` listener on `document` that `preventDefault()` + `stopImmediatePropagation()` on matched targets. The overlay is the spec'd mechanism; the listener catches the frames where the overlay is mid-reposition.
5. Extract product context (title, price → integer cents, image, URL, ≤4KB `innerText` of the nearest product container). Ship a per-site adapter object so Amazon-specific selectors don't leak into the generic path.
6. Expose `window.__swiperno.approve(id)` → removes overlay, calls `.click()` on the original element.
7. `background.js` — thin fetch proxy to `localhost:8000`, so the content script never does cross-origin.

**Done when:** you can `console.log` a correct product object and the button is dead. Hand B the event shape by **T+1:00**.

---

## B — Modal & popup

**Deliverable:** the entire user-facing surface, working against a mock before C's backend exists.

1. Build inside a **shadow DOM** root. Retail CSS will otherwise eat your modal alive.
2. States: `loading` → `question` (transcript + textarea + submit) → `verdict-approved` (green, auto-fires approve after 1.5s) / `verdict-denied` (red, savings counter increments, "Try again in 10 min").
3. Turn counter visible: "2 questions left."
4. **Start against a mock.** Hardcode a fake `interrogate()` that resolves canned JSON after 800ms. Swap to the real endpoint at integration. Do not sit idle waiting for C.
5. Popup: stats panel (`GET /api/stats/1`) + the onboarding form (`PUT /api/profile/1`). Form fields per PRD §9: name, income band, monthly budget, savings goal, goal target, known weakness.
6. P1 if time: joke ad slot at the bottom of the modal, rendering from a static `ads.json` array. No targeting logic, no reading user data — pick at random.

**Done when:** the full flow is clickable end-to-end against the mock by **T+1:30**.

---

## C — Backend & LLM

**Deliverable:** `POST /api/interrogate` returns valid verdict JSON, fast.

1. FastAPI (or Express — decide in the first 5 minutes, don't debate it for 20). CORS wide open, it's localhost.
2. Session state in a module-level dict keyed by `session_id`. Not Redis. Not a table. A dict.
3. `llm.py` — the **only** file in the project that talks to an AI. DeepSeek is the sole provider (PRD §7.1, N7); no second provider, not even as a fallback.
   - Model: **`deepseek-v4-flash`**, pinned in `config.py`. ⚠️ **`deepseek-chat` and `deepseek-reasoner` died 2026/07/24 15:59 UTC** — every tutorial and autocomplete will hand you one of them and you'll get a 400. Curl the model name and confirm a 200 in your first 15 minutes, before writing anything else.
   - Base URL `https://api.deepseek.com`, OpenAI-compatible — use the `openai` SDK pointed at it. There is no DeepSeek-specific SDK to find.
   - Thinking mode **off**. It's a parameter now (`"thinking": {"type":"enabled"}`), not a model, and it blows the 8s budget.
   - `response_format: {"type":"json_object"}`, `temperature: 0.8`, `max_tokens: 300`, 8s timeout, one retry, then fail open with `{"verdict":"approved","reply":"Backend's down. Enjoy your thing."}`
   - Three DeepSeek JSON gotchas, handle all three now: the literal word **json** plus a worked example must appear in the prompt; `max_tokens` must be set or the JSON truncates; **JSON mode sometimes returns empty content** — treat empty as a failure and retry, never `json.loads("")`.
4. `prompts.py` — system prompt implements PRD §10: two-sentence max, skeptical-friend tone, the 0–39/40–69/70–100 rubric, hard-approve carve-out for medical/food/safety/work-required items.
5. Inject into the prompt: the user profile row and the last 5 purchases (D gives you `get_context(user_id)`). This is what makes it feel personal — prioritize wiring it over prompt polish.
   **One DeepSeek call per turn**, returning reply + verdict + score + (P1) category + roast line in a single JSON object. Four chained calls is 4× the latency while the user watches a spinner.
6. Call `db.log_turn()` and `db.finalize()` on every turn. You call D's functions; you never touch `db.py`.

**Done when:** `deepseek-v4-flash` returns 200 by **T+0:15**; `curl` a fake product and get a sane question back by **T+1:00**; verdict logic closed by **T+1:30**.

---

## D — Data, profile, demo

**Deliverable:** persistence, the savings number, and the thing that actually gets demoed.

1. `schema.sql` from PRD §9. Ship it in the first 20 minutes — C is blocked on your function signatures, so publish them immediately even as stubs:
   ```python
   def get_context(user_id) -> dict        # profile + last 5 purchases
   def start_purchase(user_id, product) -> int
   def log_turn(purchase_id, idx, role, content) -> None
   def finalize(purchase_id, verdict, score, justification) -> None
   def stats(user_id) -> dict
   ```
2. `seed.py` — a realistic user 1 with a savings goal and ~12 prior purchases, mostly denied, with a visible pattern (four pairs of headphones). **This seed data is the demo.** A cold empty DB makes the LLM generic and the pitch flat. Spend real time here.
3. `/api/stats/1` and `/api/profile/1` endpoints (coordinate with C on where they live — simplest is you write the route functions, C imports them).
4. From **T+2:15** you stop coding and own the demo: saved offline copy of the product page in `demo/`, the run-order script, the 90-second script from PRD §12, and rehearsing it twice.
5. `README.md` — setup steps that a judge could follow.

**Done when:** seeded DB + working stats by **T+1:15**; rehearsed demo by **T+2:45**.

---

## Timeline

| Time | Everyone |
|------|----------|
| **0:00–0:15** | Repo, directories, `npm`/`venv`, DeepSeek key in `server/.env`, extension loads unpacked and logs "hello" on a product page. Everyone confirms this before writing features. |
| **0:15–0:20** | **Contract freeze.** All four read PRD §8 aloud, write `CONTRACT.md`, agree field names. Nobody renames a field after this. |
| **0:20–1:30** | Heads-down parallel build. A→detector+overlay, B→modal against mock, C→endpoint+prompt, D→schema+seed+stats. |
| **1:30–1:45** | **Integration 1.** B drops the mock, points at C. A fires the real event into B's modal. First end-to-end attempt. Expect it to fail; that's what this slot is for. |
| **1:45–2:15** | Fix integration. C tunes the prompt against real seeded history. A hardens the detector on the actual demo page. |
| **2:15–2:30** | **Feature freeze.** Only bug fixes and P1-1 (savings counter). No new files. |
| **2:30–2:45** | Full-take rehearsal. Anything that breaks gets removed, not fixed. |
| **2:45–3:00** | Second full take. Commit. Stop touching the laptop. |

---

## Rules

1. **Fail open, always.** Any error anywhere → overlay comes off, purchase goes through. Never trap a judge on a checkout page.
2. **Mock first, integrate second.** B and C both build against fixtures. Nobody waits on anybody before T+1:30.
3. **The contract is frozen at T+0:20.** A field rename at T+2:00 costs 20 minutes across four people.
4. **Feature freeze at T+2:15 is real.** The most common way a 3-hour hackathon project dies is someone adding a feature at T+2:40.
5. **Don't demo with a real payment method.** Use the offline page in `demo/`.
6. **No ad targeting on user data.** The joke lives in the pitch. The code picks from a static list at random.
7. **DeepSeek is the only AI provider, `deepseek-v4-flash` is the only model string.** Not `deepseek-chat` — it's deprecated as of yesterday and returns errors.
8. **Chrome only.** Nobody writes a compatibility shim "just in case."

Before each merge: `grep -r "deepseek-chat\|deepseek-reasoner\|browser\.\|webextension-polyfill" .` should return nothing.
