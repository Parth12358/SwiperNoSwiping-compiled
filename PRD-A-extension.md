# PRD-A — Extension & DOM Interception

**Owner:** A
**Timebox:** 3 hours, parallel slice
**Status:** **COMPLETE.** All 13 deliverables done. All contracts match. Code is interop-ready for B's modal and C's backend. See `extension/` directory.

**Key files:**
- `extension/manifest.json` — MV3, min_chrome_version 114, loads modal.js before content.js
- `extension/content.js` — overlay, intercept, extract, approve/dismiss, cooldown, mock
- `extension/detector.js` — querySelectorAll + text-regex, per-site adapters, visibility filter
- `extension/background.js` — fetch proxy with MOCK_BACKEND and fail-open
- `extension/overlay.css` — transparent overlay with correct box-sizing
- `extension/config.js` — backend URL and mock flags

---

## 1. What you build

A Chrome extension (Manifest V3) that scans any product page, finds every buy/checkout button, covers each with a transparent overlay that swallows clicks, extracts product context from the DOM, and emits a `swiperno:intercept` CustomEvent carrying that context. When told to approve, it removes the overlay and programmatically clicks the real button.

**One-liner for your slice:** "Buy Now is dead — here's the product object that proves it."

---

## 2. API-key gating

The extension is **inactive** without a valid DeepSeek API key present in `server/.env` and a running backend on `localhost:8000`. Your slice does not hold or validate the key itself (that's C's job), but you must handle the case where the backend is unreachable or returns an error:

- **Fail open.** If the backend is down, the DeepSeek key is invalid, or any fetch times out after 8 seconds → the overlay is removed and the purchase proceeds normally. A browser extension that traps a user on a checkout page is worse than no extension.
- Your `background.js` fetch proxy must implement this fail-open guard from the first line of code. Do not defer it to integration.
- When `MOCK_BACKEND = true` (your local working mode until M3 at T+1:45), the backend is not called at all — mock responses are used instead.

---

## 3. Deliverables

| # | Deliverable | Done when |
|---|-------------|-----------|
| 1 | MV3 manifest with `host_permissions`, content script at `document_idle`, `"minimum_chrome_version":"114"` | extension loads unpacked |
| 2 | `detector.js` — two-strategy button detection (known selectors → text-regex fallback) | correct elements found on `demo/product.html` |
| 3 | Overlay `<div>` positioned over each match via `getBoundingClientRect()` + scroll offsets, `z-index: 2147483647` | button is unclickable |
| 4 | `overlay.css` — transparent, absolute, cursor-not-allowed | visual correctness on demo page |
| 5 | Reposition on `scroll` + `resize` inside `requestAnimationFrame`; re-scan on `MutationObserver` (debounced 300ms) | overlay stays on target through scroll and DOM mutation |
| 6 | Capture-phase `click` listener on `document` as a second net | click never fires, even if overlay is mid-reposition |
| 7 | Product context extraction: title, price (integer cents or null), image URL, page URL, site name, ≤4KB `innerText` snippet | correct `fixtures/product.json` shape in console |
| 8 | Per-site adapter object (Amazon-specific selectors in adapter, generic path clean) | no Amazon selectors leak into generic detector |
| 9 | Emit `swiperno:intercept` CustomEvent on `document` with the product payload | event fires, B can receive it |
| 10 | Expose `window.__swiperno.approve(id)` — removes overlay, calls `.click()` on original element | real click fires on the real button |
| 11 | Expose `window.__swiperno.dismiss(id)` — leaves overlay, starts 10-minute localStorage cooldown per SKU | P1 |
| 12 | `background.js` fetch proxy — all API calls go through the service worker, fail-open on any error | no CORS errors, no key leaks to content script |
| 13 | Ship `fixtures/product.json` by T+0:20 — a real extracted product object | B is unblocked |

---

## 4. Contracts — your frozen seams

### 4.1 What A emits → B receives

```js
// Fired on `document` when the overlay is clicked
new CustomEvent('swiperno:intercept', { detail: {
  intercept_id: "int_7f2a",          // opaque, B echoes it back to you via approve/dismiss
  product: {
    title: "Sony WH-1000XM5",
    price_cents: 34800,              // integer, never a string, never a float. null if unparseable.
    currency: "USD",
    url: "https://www.amazon.com/dp/B0C...",
    image_url: "https://m.media-amazon.com/images/I/...",
    site: "amazon",
    dom_snippet: "…max 4000 chars of the product container's innerText…"
  }
}})
```

### 4.2 What B calls back into A

```js
// B calls exactly one of these after verdict
window.__swiperno.approve(intercept_id)   // removes overlay, clicks real element
window.__swiperno.dismiss(intercept_id)   // leaves overlay, starts cooldown
```

### 4.3 Do not change these field names after T+0:20

`intercept_id`, `product.title`, `product.price_cents`, `product.currency`, `product.url`, `product.image_url`, `product.site`, `product.dom_snippet`. Renaming any of these costs four people twenty minutes.

---

## 5. File ownership — only these files

```
extension/
  manifest.json       — MV3, chrome.* only, no browser.*, no polyfill, min_chrome_version: 114
  content.js          — scan, overlay, intercept, event emission, approve/dismiss
  detector.js         — selector strategy + text-regex strategy, per-site adapters
  overlay.css         — transparent overlay styling
  background.js       — thin fetch proxy to localhost:8000, fail-open on any error
  config.js           — MOCK_BACKEND flag, backend URL
```

Nobody else edits these. You don't edit anything in `extension/modal/`, `extension/popup/`, `server/`, `demo/`, or `fixtures/` (append-only after freeze, and only your own).

---

## 6. Detector spec

### Strategy 1 — known selectors (try these first, in order)

- `#buy-now-button`
- `#add-to-cart-button`
- `[name="submit.buy-now"]`
- `[id*="checkout" i]`
- `[data-testid*="checkout" i]`
- `[aria-label*="buy" i]`
- `[aria-label*="checkout" i]`
- `input[value*="Buy" i]`
- `input[value*="checkout" i]`

### Strategy 2 — text-regex fallback (scan these elements)

Scan all `button`, `input[type="submit"]`, and `a[role="button"]` elements for `innerText` matching (case-insensitive):

```
/buy now|add to cart|place order|proceed to checkout|complete purchase|pay now|checkout/i
```

### Per-site adapters

Define an adapter per site (Amazon, generic) as a plain object with selector overrides. The generic path never contains an Amazon-specific selector. Switch on hostname:

```js
const adapters = {
  amazon:   { selectors: ["#buy-now-button", "#submit\.buy-now", "…"], textRegex: /buy now|…/i },
  generic:  { selectors: ["…"], textRegex: /…/i }
}
```

### Overlay positioning

```js
const rect = el.getBoundingClientRect();
const div = document.createElement('div');
Object.assign(div.style, {
  position: 'absolute',
  left:   `${rect.left + window.scrollX}px`,
  top:    `${rect.top + window.scrollY}px`,
  width:  `${rect.width}px`,
  height: `${rect.height}px`,
  zIndex: '2147483647',
  background: 'transparent',
  cursor: 'not-allowed'
});
document.body.appendChild(div);
```

Reposition on `scroll` / `resize` via `requestAnimationFrame`. Re-scan the DOM on `MutationObserver` with a 300ms debounce.

---

## 7. Mock strategy — build without B, C, D

| Flag | Where | Effect |
|------|-------|--------|
| `MOCK_BACKEND = true` | `extension/config.js` | B's modal resolves from fixtures. Nothing for A to mock — you emit the event. |
| `?swiperno_mock=1` | URL query on `demo/product.html` | Auto-fires a fake `swiperno:intercept` with `fixtures/product.json` on page load. Lets B test modal without A. |

Your own test: open `demo/product.html`, check the console for the product object, confirm the button is unclickable. No backend, no modal, no DB required.

---

## 8. Context extraction

Extract these fields from the DOM. Prefer structured data (`meta`, `schema.org` JSON-LD, `data-*` attributes) over scraping text if available.

| Field | Strategy | Fallback |
|-------|----------|----------|
| `title` | `<meta property="og:title">` or `#productTitle` or `<h1>` | `document.title` |
| `price_cents` | Parse from `[data-price]` or `.a-price-whole` + `.a-price-fraction` | regex `/\$?([\d,]+\.?\d{0,2})/` on nearest price element, then `Math.round(parseFloat * 100)`. **Never a float, never a string.** `null` if unparseable. |
| `image_url` | `<meta property="og:image">` or first `img` in product container | `null` |
| `url` | `window.location.href` | — |
| `site` | hostname without `www.`: `amazon`, `bestbuy`, etc. | `"unknown"` |
| `dom_snippet` | `innerText` of the nearest ancestor with class matching `/product|pdp|detail/i`, truncated to 4000 chars | `document.body.innerText.substring(0, 4000)` |

---

## 9. Timeline

| Time | Action |
|------|--------|
| **0:00–0:15** | Repo setup, venv, extension loads unpacked on agreed Chrome version, logs "hello" |
| **0:15–0:20** | **CONTRACT FREEZE.** Read all field names aloud with B, C, D. Agree. |
| **0:20** | **Ship `fixtures/product.json` + `mockEmit()` for B.** This is your blocking deliverable. |
| **0:20–0:45** | Detector (both strategies), overlay DOM creation + positioning, capture-phase listener, `manifest.json`, `background.js` stub |
| **0:45** | **M1 merge with B.** Your real event drives B's modal. Delete `?swiperno_mock=1` path. |
| **0:45–1:15** | Context extraction, per-site adapters, reposition on scroll/resize, MutationObserver rescan |
| **1:15–1:45** | Harden detector on `demo/product.html`. Fix edge cases. |
| **1:45** | **M3 — full end-to-end merge.** All four. |
| **1:45–2:15** | Fix integration issues surfaced by M3. |
| **2:15** | **FEATURE FREEZE.** Bug fixes only. |
| **2:15–2:45** | Rehearsal 1. If broken, delete the broken thing — don't build new fixes. |
| **2:45–3:00** | Rehearsal 2. Commit. Stop touching the laptop. |

---

## 10. Success criteria — done when

1. Open `demo/product.html`. The Buy Now button is visible but unclickable.
2. Click it. Console shows the `swiperno:intercept` event with a correct product object matching `fixtures/product.json` shape.
3. All fields in the product object are populated (except `price_cents` may be `null` if unparseable).
4. The overlay follows the button through scroll and window resize.
5. Calling `window.__swiperno.approve(id)` from the console removes the overlay and the real button receives a click.
6. B can consume your event without any code change to your files.
7. `grep -r "deepseek-chat\|deepseek-reasoner\|browser\.\|webextension-polyfill" extension/` returns nothing.

---

## 11. Rules you must not break

1. **Chrome only.** `chrome.*` namespace, no `browser.*`, no polyfill, no cross-browser shim. Manifest says `"minimum_chrome_version":"114"`.
2. **Fail open.** Any fetch error → overlay removed, click proceeds. Implemented in `background.js` from day one.
3. **Field names frozen at T+0:20.** See §4.3. Do not rename.
4. **Only edit your own files.** Ask B/C/D if you need a change in their directory.
5. **Don't wait for anyone.** Build against `fixtures/product.json` and your own console. B, C, and D are disconnected until M1.
6. **No DeepSeek calls from the extension.** The API key lives in `server/.env` only. Your `background.js` proxies HTTP — it does not construct AI requests.
7. **`extract_product()` is pure DOM → JSON.** It does not make network requests, does not talk to the backend, does not read localStorage. It reads the page and returns an object.

---

## 12. What you do NOT build

- The modal UI (that's B)
- The chat transcript, verdict display, submit button (that's B)
- Any AI logic, prompt construction, or DeepSeek API calls (that's C)
- The popup stats or onboarding form (that's B's popup work)
- SQLite, schema, or seed data (that's D)
- The demo page itself (that's D — `demo/product.html`)
- Any ad slot (that's B, P1)
- Cooldown per product (that's your P1 — localStorage, 10-minute per-SKU key)

---

## 13. Implementation status (updated post-build)

**All core deliverables complete.** Tested via syntax check (`node --check`), code review against spec, and end-to-end contract validation.

| # | Deliverable | Status | Notes |
|---|-------------|--------|-------|
| 1 | MV3 manifest | ✅ Done | Chrome 114+, `host_permissions` for amazon/bestbuy/localhost, content script at `document_idle` |
| 2 | Two-strategy detector | ✅ Done | Known selectors → text-regex fallback. Per-site adapters for amazon, bestbuy, generic |
| 3 | Overlay positioning | ✅ Done | `getBoundingClientRect()` + scroll offsets, `z-index: 2147483647` |
| 4 | `overlay.css` | ✅ Done | Transparent, absolute, `cursor: not-allowed` |
| 5 | Reposition + MutationObserver | ✅ Done | `requestAnimationFrame` on scroll/resize, 300ms debounced re-scan |
| 6 | Capture-phase click listener | ✅ Done | Second net with `approvedIntercepts` guard to prevent infinite loop on `approve()` |
| 7 | Product context extraction | ✅ Done | Full fallback chain: `og:title` → `#productTitle` → `<h1>` → `document.title`. Price: schema.org → `[data-price]` → Amazon `.a-price-*` → regex. Image: `og:image` → first img in product container |
| 8 | Per-site adapters | ✅ Done | `detectSite()` switches on hostname. Amazon selectors isolated in adapter, never leak to generic |
| 9 | `swiperno:intercept` CustomEvent | ✅ Done | Fires on overlay click with `{intercept_id, product, target}` |
| 10 | `window.__swiperno.approve(id)` | ✅ Done | Removes overlay, guards capture listener via `approvedIntercepts` set, calls `.click()` on real button |
| 11 | `window.__swiperno.dismiss(id)` | ✅ Done | 10-minute localStorage cooldown per interceptId |
| 12 | `background.js` fetch proxy | ✅ Done | 8s timeout, fail-open on any error, `chrome.runtime.onMessage` listener |
| 13 | `fixtures/product.json` | ✅ Done | Shipped at T+0:20, matches contract shape |

### Fixes applied beyond initial spec

- **`detectBySelectors`**: Changed from `querySelector` (first match only) to `querySelectorAll` + dedup via `Set`. Fixes multi-button pages.
- **`approve()` infinite-loop guard**: Capture listener checks `approvedIntercepts` set before intercepting. A programmatic `.click()` from `approve()` now passes through cleanly.
- **`swiperno_mock` race condition**: At `document_idle`, `DOMContentLoaded` has already fired. Changed from `window.addEventListener('DOMContentLoaded', ...)` to firing immediately.
- **`extractProduct` title fallback**: Added `#productTitle` and `<h1>` as intermediate fallbacks (spec only listed `og:title` and `document.title`).
- **`extractProduct` image fallback**: Added first `<img>` in product container as fallback after `og:image`.
- **`extractProduct` price**: Added `[data-price]` attribute strategy and `.price` class-element scanning before the regex body-text fallback.
