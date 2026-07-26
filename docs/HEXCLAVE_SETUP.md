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
