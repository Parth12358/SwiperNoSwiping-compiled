# Hexclave setup (accounts for SwiperNoSwiping)

[Hexclave](https://github.com/hexclave/hexclave) (formerly Stack Auth) is the user-infrastructure
platform behind the site's account form: auth, profiles, teams, analytics. It does **not** host
the site itself — the site is on GitHub Pages; Hexclave provides the user layer.

## Status: CONNECTED (cloud setup)

- Project ID `2a0a2d75-5c4f-43c5-bb6c-d6638c494fb8` and API URL
  `https://api.stack-auth.com` are live in `docs/hexclave-config.js` (public values)
  and mirrored in `server/.env` / `server/.env.example`.
- The landing-page form initializes `@hexclave/js@1.0.67` (version-pinned via esm.sh)
  with `tokenStore: "cookie"` and `urls: { default: { type: "hosted" } }`, then calls
  `redirectToSignUp()` — visitors land on Hexclave's hosted sign-up pages.

## Remaining human step

Paste the **secret server key** from the Hexclave dashboard into `server/.env`:
```
HEXCLAVE_SECRET_SERVER_KEY=...
```
Server-side ONLY — never in the site, never committed. It unlocks server-side
session verification (`HexclaveServerApp` / REST) for per-user savings sync.

## Dashboard checklist (human steps — the code is already live)

All at https://app.hexclave.com → project **SwiperNoSwiping**:

1. **Trusted domains** (makes hosted auth redirects work — dashboard-only setting):
   *Domain & Handlers* → add BOTH:
   - `https://parth12358.github.io`
   - `https://swipernoswiping-production.up.railway.app`
   Keep "allow localhost callbacks" on.
2. **Enable Payments**: *Apps* → **Payments** → Enable. Payments run on **Stripe
   Connect** (US businesses; identity/bank onboarding) — do the Stripe steps
   yourself, and turn on **test mode** so hackathon purchases are free.
3. **Create the product** (*Payments → Products & Items*):
   | Field | Value |
   |---|---|
   | Product ID | `lawyer_retainer` |
   | Display name | `Retain the Lawyer — Pro` |
   | Customer type | `user` |
   | Price | one-time, USD `5.00` (no interval) |

The site already handles every state: signed-out → hosted sign-up/sign-in;
signed-in → shows the user + "Retain the lawyer — $5" (checkout via
`user.createCheckoutUrl`); already-purchased → PRO badge; payments not yet
enabled → friendly "warming up" message instead of an error.

## Optional: Hexclave MCP for AI agents

To give coding agents live access to Hexclave docs/APIs, register their MCP server
yourself (agent config is a you-decision, not something setup scripts should touch):
```
claude mcp add --transport http hexclave https://mcp.hexclave.com/mcp
```

## How the site uses it

`docs/index.html` dynamically imports the vanilla SDK (`@hexclave/js`) and initializes
`HexclaveClientApp({ projectId, tokenStore: "cookie" })` when a visitor submits the form.
Until a project ID is set, the form degrades gracefully with a "not connected yet" message.

## Future: savings sync

The backend can verify Hexclave sessions with `HexclaveServerApp` + the secret key, replacing
the hardcoded `user_id = 1`. See https://docs.hexclave.com for the server SDK.
