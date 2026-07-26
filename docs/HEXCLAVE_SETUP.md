# Hexclave setup (accounts for SwiperNoSwiping)

[Hexclave](https://github.com/hexclave/hexclave) (formerly Stack Auth) is the user-infrastructure
platform behind the site's account form: auth, profiles, teams, analytics. It does **not** host
the site itself — the site is on GitHub Pages; Hexclave provides the user layer.

## One-time setup (needs a human — creates an account)

1. Sign up / log in at **https://app.hexclave.com** and create a project (free tier: 10K auth users).
2. Copy the **Project ID** into `docs/hexclave-config.js`:
   ```js
   window.HEXCLAVE_PROJECT_ID = "proj_...";
   ```
3. The **secret server key** (`HEXCLAVE_SECRET_SERVER_KEY`) goes in `server/.env` ONLY —
   never in the site, never committed. It's needed later for server-side savings sync.
4. Commit + push `docs/hexclave-config.js` — the landing page account form goes live.

## How the site uses it

`docs/index.html` dynamically imports the vanilla SDK (`@hexclave/js`) and initializes
`HexclaveClientApp({ projectId, tokenStore: "cookie" })` when a visitor submits the form.
Until a project ID is set, the form degrades gracefully with a "not connected yet" message.

## Future: savings sync

The backend can verify Hexclave sessions with `HexclaveServerApp` + the secret key, replacing
the hardcoded `user_id = 1`. See https://docs.hexclave.com for the server SDK.
