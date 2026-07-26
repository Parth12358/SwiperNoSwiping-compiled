# PRD-B — Modal & Popup UI

**Owner:** B
**Timebox:** 3 hours, parallel slice
**Status:** **COMPLETE.** All 12 deliverables done. Shadow DOM modal, state machine, mock cycle, popup stats with 10s polling, ad slot, retry pipeline — all implemented.

**Key files:**
- `extension/modal/modal.js` (316 lines) — state machine, fixture-based mock, retry+timeout fetch, ad slot
- `extension/modal/modal.html` — shadow DOM markup with 4 states + ad slot
- `extension/modal/modal.css` — isolated styles with shimmer animations
- `extension/modal/ads.json` — static joke ads (random, no targeting)
- `extension/popup/popup.js` — stats panel with 10s polling, onboarding form
- `extension/popup/popup.html` — popup markup, validation min=1 on cent fields
- `extension/popup/popup.css` — popup styles

---

## 1. What you build

Every pixel the user sees after clicking a blocked Buy button: the interrogation modal inside a shadow DOM root, the chat transcript with turn counter, the approve/denied verdict screens, a stats popup, and an onboarding form. You start against canned JSON fixtures and swap to the real backend at integration.

**One-liner for your slice:** "The extension talks, the user argues, the wallet wins."

---

## 2. API-key gating

The modal's `interrogate()` call goes to `localhost:8000` which requires a valid `DEEPSEEK_API_KEY` in its `.env`. If the key is missing or invalid, C's backend returns an error. Your fetch wrapper must:

- **Fail open on any non-200, timeout >8s, or malformed JSON:** remove the overlay (call `window.__swiperno.approve(intercept_id)`) and let the purchase through.
- A broken backend must never trap a user on a real checkout page.
- During development, you run with `MOCK_BACKEND = true` (or `?swiperno_mock=1` in the URL) — zero dependency on the API key or backend. Swap to real HTTP at M3 (T+1:45).

---

## 3. Deliverables

| # | Deliverable | Done when |
|---|-------------|-----------|
| 1 | Shadow DOM modal root — no retail CSS leakage | modal renders correctly on hostile CSS pages |
| 2 | State machine: `loading` → `question` → `verdict-approved` / `verdict-denied` | all states cycle correctly against mock |
| 3 | Chat transcript with scrollable history, styled assistant vs. user bubbles | full conversation rendered on screen |
| 4 | Textarea + submit button, disabled during `loading` state | input blocked while waiting |
| 5 | Turn counter: "2 questions left" / "last chance" visible to user | counter decrements each turn |
| 6 | `verdict-approved` state: green screen, "Go ahead.", auto-fires `window.__swiperno.approve()` after 1.5s | real click fires, modal closes |
| 7 | `verdict-denied` state: red screen, savings counter increments, "Try again in 10 min" | blocked for cooldown period |
| 8 | Fetch wrapper with 8s timeout, fail-open on any error, retry once | backend outage never blocks the page |
| 9 | Mock `interrogate()` resolving canned JSON from `fixtures/interrogate/*` after 800ms | full flow works without C or any API key |
| 10 | Popup: stats panel reading `GET /api/stats/1` | denied count, approved count, money saved rendered |
| 11 | Popup: onboarding form — `PUT /api/profile/1` — fields: display name, income band, monthly budget, savings goal, goal target, known weakness | profile persists and is read back correctly |
| 12 | P1: Joke ad slot at modal bottom, picking from static `ads.json` at random, no targeting logic | ad renders, no user data touches ad selection |

---

## 4. Contracts — your frozen seams

### 4.1 What A sends to you

```js
// A fires on `document` when overlay is clicked
document.addEventListener('swiperno:intercept', e => {
  const { intercept_id, product } = e.detail;
  // product shape: { title, price_cents, currency, url, image_url, site, dom_snippet }
});
```

### 4.2 What you send to C (HTTP)

```jsonc
// POST /api/interrogate
{
  "user_id": 1,
  "product": { /* pass through exactly as received from A — do not reshape */ },
  "session_id": null,       // null on first turn, echo C's value on subsequent turns
  "message": null           // null on first turn, user's typed justification after
}

// 200 — you receive
{
  "session_id": "b1f3…",
  "verdict": "pending",     // "pending" | "approved" | "denied"
  "reply": "You already own two pairs of over-ears. What changed?",
  "turn": 1,
  "turns_remaining": 2,
  "score": null,            // 0-100 once verdict is final, null while pending
  "savings_total_cents": 128400
}
```

### 4.3 What you call back on A

```js
window.__swiperno.approve(intercept_id)   // on APPROVED
window.__swiperno.dismiss(intercept_id)   // on DENIED
```

### 4.4 What you read from D

```jsonc
// GET /api/stats/1
{ "denied_count": 12, "approved_count": 3, "saved_cents": 128400, "top_category": "electronics" }

// GET /api/profile/1  →  read the current profile
// PUT /api/profile/1  →  save onboarding form data
{ "user_id": 1, "display_name": "…", "income_band": "…", "monthly_budget_cents": 200000,
  "savings_goal": "Japan trip", "goal_target_cents": 400000, "known_weakness": "mechanical keyboards" }
```

### 4.5 Field names frozen at T+0:20

Do not rename any of these. Do not reshape `product`. Pass it through byte-for-byte from A to C.

---

## 5. File ownership — only these files

```
extension/
  modal/
    modal.html          — modal markup inside shadow DOM
    modal.css           — modal styles (isolated by shadow DOM)
    modal.js            — state machine, chat rendering, verdict display, A→B→C wiring
    ads.json            — static joke ad array (P1, random selection, no targeting)
  popup/
    popup.html          — extension popup (toolbar icon click)
    popup.css           — popup styles
    popup.js            — stats fetch, onboarding form submit/read
```

Nobody else edits these. You don't edit files in `extension/` root (A's), `server/` (C's and D's), or `demo/` (D's).

---

## 6. Modal state machine

```
                   ┌─────────┐
                   │ loading │  ← skeleton spinner, textarea disabled
                   └────┬────┘
                        │ response received
                   ┌────▼────┐
    ┌──────────────│ question │──────────────┐
    │ turns > 1    └────┬────┘  turns = 1    │
    │ user types        │       user types   │
    │ "submit"          │       "submit"     │
    │                   │                    │
    │              ┌────▼────┐               │
    └──────────────│ loading │───────────────┘
                   └────┬────┘
                        │
              ┌─────────┴─────────┐
              │                   │
         ┌────▼────┐        ┌────▼─────┐
         │approved │        │  denied   │
         │ (green) │        │  (red)   │
         └─────────┘        └──────────┘
         auto-fire           savings +1
         approve()           cooldown 10min
         after 1.5s
```

### State details

| State | Visual | User action | Auto-behavior |
|-------|--------|-------------|---------------|
| `loading` | Skeleton shimmer / spinner, "Just a moment…" | None — textarea disabled | Calls `interrogate()`. Shows for max 8s then fails open. |
| `question` | Chat transcript (scrollable), assistant bubble with latest reply, "N questions left" badge, textarea + Submit | Types justification, clicks Submit | Calls `interrogate()` with `message` = user text |
| `verdict-approved` | Green screen, "Go ahead.", transcript visible | None | After 1.5s: calls `window.__swiperno.approve(intercept_id)`, closes modal |
| `verdict-denied` | Red screen, "Denied.", "You saved $X", "Try again in 10 min", transcript visible | None | Calls `window.__swiperno.dismiss(intercept_id)`, modal closes, cooldown starts |

### Loading skeleton

A `<div>` with a subtle CSS shimmer animation. Two gray bars mimicking text lines. No text, no emoji. This renders for at most 8 seconds, then the error path fires (fail open).

---

## 7. Chat transcript

Render each exchange as a set of bubbles:

```
┌──────────────────────────────────────────┐
│  [assistant] Why do you need this?       │  ← left-aligned, light gray bg
│                                          │
│                    [user] I want it. ────│  ← right-aligned, blue bg
│                                          │
│  [assistant] You said your goal is a     │
│  Japan trip and you're $2,700 short.     │  ← left-aligned
│  What changed?                           │
│                                          │
│  ── 2 questions left ──                  │  ← centered badge
│  ┌──────────────────────────┐           │
│  │ Type your justification…  │           │  ← textarea
│  └──────────────────────────┘           │
│     [Submit]                             │  ← button
└──────────────────────────────────────────┘
```

- Assistant bubbles: `text-align: left`, light gray background, rounded left corners
- User bubbles: `text-align: right`, accent background (blue), rounded right corners
- Transcript container: `overflow-y: auto`, max-height ~50vh, scrolls to bottom on new message
- Turn counter badge: centered between transcript and input

---

## 8. Mock strategy — build without A, C, D

| Flag | Where | Effect |
|------|-------|--------|
| `?swiperno_mock=1` | URL query on `demo/product.html` | Auto-fires `swiperno:intercept` with `fixtures/product.json` on page load. No A needed. |
| `MOCK_BACKEND = true` | `extension/config.js` (or your modal source) | `interrogate()` resolves from `fixtures/interrogate/turn1.json`, `turn2.json`, `approved.json`, `denied.json` after 800ms delay. No C, no API key, no server. |

### Canned fixture responses (C ships these by T+0:20)

```
fixtures/interrogate/
  turn1.json       → { verdict: "pending", reply: "Why do you need this?", turn: 1, turns_remaining: 2, ... }
  turn2.json       → { verdict: "pending", reply: "That's weak. Try again.", turn: 2, turns_remaining: 1, ... }
  approved.json    → { verdict: "approved", reply: "Fair. Go ahead.", score: 82, ... }
  denied.json      → { verdict: "denied", reply: "Denied. Save for Japan.", score: 28, ... }
```

Your mock `interrogate()` cycles through these:
- First call → `turn1.json`
- Second call (with a weak message like "idk") → `denied.json`
- Second call (with a strong message like "my current one is broken") → `approved.json`

Implement this logic so your demo with `?swiperno_mock=1` shows BOTH verdict outcomes cleanly.

---

## 9. Fetch wrapper spec

Every API call goes through one wrapper. This is where fail-open lives.

```js
async function apiFetch(path, body = null) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);

  try {
    const res = await fetch(`http://localhost:8000${path}`, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });
    clearTimeout(timer);

    if (!res.ok) {
      // fail open on any non-200
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    if (!data || (typeof data === 'string' && data.trim() === '')) {
      // empty content → fail open
      throw new Error('Empty response');
    }
    return data;
  } catch (err) {
    clearTimeout(timer);
    // FAIL OPEN: remove overlay, let purchase through
    window.__swiperno && window.__swiperno.approve && window.__swiperno.approve(currentInterceptId);
    throw err;
  }
}
```

**Rules:**
- No other `fetch()` call exists in modal code.
- `apiFetch` is the single chokepoint for fail-open.
- 8s timeout, one retry, then fail open. No second retry.

---

## 10. Popup

### Stats panel

Extension toolbar icon → popup.html shows:

```
┌─────────────────────────┐
│  SwipernoSwiping        │
│                         │
│  DENIED  12 times       │
│  APPROVED  3 times      │
│  SAVED   $1,284.00      │
│  Top category: Electronics│
│                         │
│  [Edit Profile]         │
└─────────────────────────┘
```

- Fetches `GET /api/stats/1` on popup open.
- Handles loading and error states (show "—" on error, not a crash).
- Updates live if the popup stays open during a denial (poll every 10s).

### Onboarding form

Click "[Edit Profile]" → form with fields mapping to D's `/api/profile/1`:

| Label | Field | Type |
|-------|-------|------|
| Display name | `display_name` | text |
| Income band | `income_band` | select: `under_50k`, `50k_100k`, `100k_200k`, `over_200k` |
| Monthly budget | `monthly_budget_cents` | number (display as $, submit as cents) |
| Savings goal | `savings_goal` | text (e.g. "Japan trip") |
| Goal target | `goal_target_cents` | number (display as $, submit as cents) |
| Known weakness | `known_weakness` | text (e.g. "mechanical keyboards") |

- On submit: `PUT /api/profile/1` with the form data.
- On load: `GET /api/profile/1` to prefill.
- Validation: all fields required. `monthly_budget_cents` and `goal_target_cents` must be positive integers.
- Success: green toast "Profile saved." Error: red toast with the server message.

---

## 11. Timeline

| Time | Action |
|------|--------|
| **0:00–0:15** | Repo setup, extension loads, CI runs green |
| **0:15–0:20** | **CONTRACT FREEZE.** Read field names aloud with A, C, D. Agree. |
| **0:20** | A and C ship their fixtures. You start immediately on UI — no downstream wait. |
| **0:20–0:45** | Modal shell: shadow DOM, state machine skeleton, `loading` state, HTML/CSS structure |
| **0:45** | **M1 merge with A.** A's real event drives your modal. Delete `?swiperno_mock=1`. |
| **0:45–1:15** | Chat transcript rendering, user input, state transitions, verdict screens, mock `interrogate()` wired to fixtures |
| **1:15–1:45** | Popup: stats panel + onboarding form against D's stubs, fetch wrapper with fail-open |
| **1:45** | **M3 — full end-to-end.** Drop `MOCK_BACKEND`, point at real C. First live run. |
| **1:45–2:15** | Fix integration: pass `product` through unmodified, handle real verdict JSON, wire approve/dismiss calls |
| **2:15** | **FEATURE FREEZE.** Bug fixes and P1 ad slot only. |
| **2:15–2:45** | Rehearsal 1. Delete broken things. |
| **2:45–3:00** | Rehearsal 2. Commit. Stop. |

---

## 12. Success criteria — done when

1. Open `demo/product.html?swiperno_mock=1`. Modal appears on click. Full flow: loading → question → verdict (both approve and deny paths) against canned fixtures. No backend, no API key required.
2. Chat transcript renders with correct styling, scrollable, and all assistant/user bubbles visible.
3. Turn counter decrements correctly (3 → 2 → 1 → final verdict).
4. `verdict-approved` fires `window.__swiperno.approve()` automatically after 1.5s.
5. `verdict-denied` shows correct savings counter increment.
6. Textarea is disabled during `loading` state, re-enabled during `question` state.
7. Popup shows real stats from D's endpoint after integration.
8. Onboarding form save/load round-trips correctly.
9. Fail-open: kill the backend server. Click Buy Now. The purchase proceeds (overlay removed within 8s). No error screen, no dead page.
10. `grep -r "deepseek-chat\|deepseek-reasoner\|browser\.\|webextension-polyfill" extension/modal/ extension/popup/` returns nothing.

---

## 13. Rules you must not break

1. **Shadow DOM.** The modal is inside a shadow root attached to a container `div` you inject into the page. Retail CSS is hostile — do not rely on `all: initial` or luck.
2. **Fail open.** Any fetch error → `window.__swiperno.approve()` immediately. Implemented in `apiFetch()` from day one. Never trap a user.
3. **Pass `product` through unmodified.** Do not rename, reshape, or enrich the `product` object from A. B→C is a pass-through.
4. **Chrome only.** `chrome.storage.local`, `chrome.runtime.sendMessage`, one fetch domain (`localhost:8000`). No polyfills.
5. **Only edit your own files.** Ask A/C/D for cross-directory changes.
6. **Start against mocks.** Build against `fixtures/interrogate/*`. Wait for nobody.
7. **Ad slot: no targeting.** If you build the P1 ad slot, pick from `ads.json` at random. Do not read purchase history, profile, or any user data for ad selection. This is a joke feature — keep it harmless.

---

## 14. What you do NOT build

- The overlay or button detection (that's A)
- `content.js`, `detector.js`, `background.js`, `manifest.json` (that's A)
- Any AI logic or DeepSeek calls (that's C)
- The `POST /api/interrogate` endpoint (that's C)
- SQLite, schema, seed data, `/api/stats` endpoint logic, `/api/profile` endpoint logic (that's D)
- The `demo/product.html` page (that's D)
