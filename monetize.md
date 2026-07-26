# Monetize — SwiperNoSwiping

## Strategy

**API-key-gated Chrome extension.** Users buy a subscription via a landing page (powered by HexClave Payments + Stripe), receive an API key (HexClave API Keys app), enter it into the extension to activate it. The backend validates keys on every request via HexClave's REST API.

```
User lands on page → Hexclave Auth (sign up / sign in)
        ↓
User clicks "Subscribe" → Hexclave Payments → Stripe Checkout
        ↓
User has active subscription → User creates API key (Hexclave API Keys app)
        ↓
User copies key → pastes into extension popup → stored in chrome.storage.local
        ↓
Extension sends X-API-Key header on every request → Backend validates against Hexclave
```

---

## HexClave Apps Required

| App | Purpose |
|-----|---------|
| **Auth** | User sign-up/sign-in on the landing page |
| **Payments** | Stripe checkout for subscription (handled by HexClave, no stripe SDK needed) |
| **API Keys** | Generate per-user API keys; validate them server-side |

Enable all three in the Hexclave dashboard or via `hexclave.config.ts`.

---

## Integration Points

### 1. Landing Page (NEW)

A simple page + a `hexclave/client.tsx` to handle auth and payments. There is no Next.js or React in this project, so the landing page can be a vanilla HTML page that redirects through HexClave's hosted pages for auth, then hits the REST API for checkout and key creation.

**Flow (vanilla, no framework):**

1. User visits landing page → redirected to HexClave hosted sign-in if not authenticated
2. After sign-in, redirected back to landing page with `code` query param → exchange for session
3. Landing page uses HexClave REST API to call `POST /api/v1/user-checkout-sessions` to get Stripe checkout URL
4. User completes Stripe checkout → redirected back
5. Landing page calls `POST /api/v1/user-api-keys` to generate API key
6. API key displayed to user

**Files to create:**
- `landing/index.html` — Subscription landing page
- `landing/landing.js` — Vanilla JS glue for auth redirect, checkout, key creation
- `landing/landing.css` — Styling

### 2. Backend — API Key Validation (MODIFY)

The FastAPI server must validate the API key on every request. HexClave provides a validation endpoint.

**New middleware in `server/main.py`:**

```python
from fastapi import Request, HTTPException
import os
import requests

HEXCLAVE_PROJECT_ID = os.environ["HEXCLAVE_PROJECT_ID"]
HEXCLAVE_SECRET_SERVER_KEY = os.environ["HEXCLAVE_SECRET_SERVER_KEY"]

async def validate_api_key(request: Request):
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(401, "Missing X-API-Key header")

    resp = requests.post(
        "https://api.hexclave.com/api/v1/user-api-keys/check",
        headers={
            "X-Hexclave-Access-Type": "server",
            "X-Hexclave-Project-Id": HEXCLAVE_PROJECT_ID,
            "X-Hexclave-Secret-Server-Key": HEXCLAVE_SECRET_SERVER_KEY,
            "Content-Type": "application/json",
        },
        json={"key": api_key},
        timeout=10,
    )

    if resp.status_code != 200:
        raise HTTPException(401, "Invalid API key")

    result = resp.json()
    request.state.user_id = result["user_id"]  # map to internal user
```

Apply this to existing routes: `POST /api/interrogate`, `GET /api/stats/{user_id}`, `GET /api/profile/{user_id}`, `PUT /api/profile/{user_id}`.

**New env vars in `server/.env.example`:**
```
HEXCLAVE_PROJECT_ID=
HEXCLAVE_SECRET_SERVER_KEY=
```

### 3. Backend — Profile Mapping (MODIFY)

Currently `user_id` is hardcoded to `1`. Instead, the HexClave user ID from the validated API key should be used. Add a `hexclave_user_id` column to the `users` table, or use the Hexclave user ID directly as the primary key.

**`server/schema.sql` — add column:**
```sql
ALTER TABLE users ADD COLUMN hexclave_user_id TEXT UNIQUE;
```

**`server/db.py` — new stub:**
```python
def get_or_create_user(hexclave_user_id: str) -> int:
    """Look up local user by HexClave ID, create if not exists."""
    pass
```

### 4. Extension — API Key Storage & Sending (MODIFY)

**`extension/background.js`:**
- On startup, read API key from `chrome.storage.local`
- Attach `X-API-Key` header to all proxied fetch requests
- If key is missing, return error (don't fail-open — extension is inactive)

**`extension/popup/popup.js`:**
- Attach `X-API-Key` header to direct fetch calls

### 5. Extension — Activation Flow (MODIFY)

**`extension/popup/popup.html` / `popup.js`:**
- If no API key is stored, show activation form (text input + "Activate" button)
- On submit, call `POST https://api.hexclave.com/api/v1/user-api-keys/check` directly from popup to verify the key locally
- If valid, save to `chrome.storage.local` and proceed to normal popup
- If invalid, show error toast

**`extension/manifest.json`:**
- Add `https://api.hexclave.com/*` to `host_permissions` (for key validation from popup)
- Update `BACKEND_URL` references if deploying server (not just localhost)

**`extension/config.js`:**
- `BACKEND_URL` should accept deployed URL (set at build time or via env)
- Add `HEXCLAVE_PROJECT_ID` for popup-side validation

---

## User Flow (Step by Step)

```
1. Install extension → click toolbar icon → popup shows "Activate" screen
2. Popup has: [API Key input] [Activate button] + link "Don't have a key?"
3. Link opens landing page in new tab
4. Landing page: "SwiperNoSwiping — $5/month" → Sign up with Google/GitHub/email (Hexclave)
5. Subscribe via Stripe checkout (Hexclave handles everything)
6. After purchase: "Your API Key: swp_live_xxxxxxxxxxxx" + "Copy" button
7. User copies key, pastes into extension popup, clicks "Activate"
8. Extension verifies key, stores it, switches to normal stats/profile view
9. All subsequent API calls include X-API-Key → backend validates every time
```

---

## Hackathon Quick-Start Checklist

**Before hackathon:**
- [ ] Create HexClave account at [hexclave.com](https://hexclave.com)
- [ ] Create project, enable Apps: Auth, Payments, API Keys
- [ ] Create Stripe account, connect it in HexClave Payments settings
- [ ] Define product in Payments: "SwiperNoSwiping" subscription, customer type `user`, e.g. $5/month
- [ ] Enable test mode in Payments (test card: `4242 4242 4242 4242`)
- [ ] Set up Auth providers (Google, GitHub, or email)

**During hackathon:**
- [ ] Write `landing/index.html` + `landing/landing.js` — auth redirect, checkout flow, key display
- [ ] Add API key validation middleware to `server/main.py`
- [ ] Add `hexclave_user_id` to schema + `get_or_create_user` to `db.py`
- [ ] Update `extension/background.js` to attach `X-API-Key` header
- [ ] Add activation form to `extension/popup/popup.html` + `popup.js`
- [ ] Update `extension/config.js` `BACKEND_URL` to deployed server
- [ ] Deploy server (Render/Railway) with `HEXCLAVE_PROJECT_ID` + `HEXCLAVE_SECRET_SERVER_KEY` env vars
- [ ] Deploy landing page (same server at `/`, or separate static host)

**Demo flow for judges:**
```
1. Open installed extension → activation screen
2. Click "Get a key" → landing page opens
3. Sign up → subscribe (test mode, no charge) → copy key
4. Paste into extension → activate → works
5. Visit Amazon → try to buy something → extension blocks it → LLM interrogates
```

---

## HexClave REST API Reference (Relevant Endpoints)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/user-api-keys` | POST | client (user access token) | Create API key for current user |
| `/api/v1/user-api-keys/check` | POST | server (secret key) | Validate an API key, returns user_id |
| `/api/v1/user-checkout-sessions` | POST | client (user access token) | Create Stripe checkout URL for a product |
| Various auth endpoints | — | — | Handled by HexClave hosted pages or SDK |

---

## Architecture Decisions

| Decision | Why |
|----------|-----|
| HexClave handles auth, not us | No user DB to manage. HexClave gives us sign-up, session management, OAuth providers for free. |
| HexClave handles Stripe, not us | No Stripe SDK integration. Product definition, checkout, webhooks — all handled. |
| HexClave handles API keys, not us | HexClave generates, stores, validates, and monitors API keys for exposure. No custom key table needed. |
| Use REST API (not SDK) on landing page | This project has no Node.js/React. Vanilla JS + HexClave REST API = no build step, no framework lock-in. |
| Validate on backend via REST API | The server is Python FastAPI. No JS SDK available. HexClave's REST API is SDK-equivalent. |
| Popup validates key locally (not through our backend) | Avoids chicken-and-egg (need a key to validate a key). HexClave's `/check` endpoint is the source of truth. |

---

## Idea: Channel3 for Smarter-Alternative Recommendations

[trychannel3.com](https://trychannel3.com/) — an "agentic commerce" product API: 100M+ products, real-time pricing, deep metadata, built for AI agents to search and recommend. Free tier to start; docs at [docs.trychannel3.com](https://docs.trychannel3.com).

**The idea:** wire their entire product API into the interrogation flow. Right now the agent only blocks a purchase. With Channel3 it can also *replace* it — when someone is about to buy something needlessly expensive or dumb, the agent researches the real catalog and automatically recommends something that actually fits their needs, cheaper.

```
User hits "Buy" on a $400 espresso machine
        ↓
Extension detects purchase → modal opens → LLM interrogates
        ↓
LLM extracts the ACTUAL need ("I drink one coffee a day")
        ↓
Query Channel3 API with that need + a sane price ceiling
        ↓
Modal shows: "You don't need this. Here are 3 that do the job for $60."
        ↓
User buys the smart thing instead of nothing (or nothing at all — both are wins)
```

**Why it fits:**

| | |
|---|---|
| Turns a nag into a helper | The extension stops being pure friction — it saves money *and* still gets you the thing |
| Real data, not LLM hallucination | Channel3 returns live products and prices, so recommendations are actually buyable |
| Second revenue line | Their built-in monetization (affiliate on redirected purchases) means the extension can earn on the *alternative* it recommends — subscription + commission, not just subscription |
| Cheap to demo | Free API tier, one HTTP call from `server/llm.py` after the interrogation step |
