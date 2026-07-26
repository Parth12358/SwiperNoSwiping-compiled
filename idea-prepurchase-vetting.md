# Idea: Pre-Purchase Vetting (Compatibility + Negative Reviews)

Right now the agent argues about *whether you should want it*. This idea adds a second axis: **is this thing actually going to work for you?** Two checks, both run before the modal renders its verdict.

---

## Check 1 — Does it work with what you already own?

We already store every purchase we've seen in the `purchases` table (`product_title`, `category`, `url`, `price_cents`). That's a free inventory of the user's stuff. Before approving a buy, the agent cross-references the new product against it.

**What it catches:**

- Ecosystem mismatch — Apple Watch when the profile shows an Android phone
- Wrong standard/fit — DDR5 RAM for a DDR4 board, 27" monitor arm rated for 15 lbs holding a 22 lb display, Lightning cables after a USB-C phone
- Redundancy — third pair of noise-cancelling headphones bought in eight months
- Orphaned accessory — a lens for a camera body they sold, film for a discontinued format

**Output the LLM should get:** a short list of relevant prior purchases (same or adjacent category, last ~12–24 months) injected into the interrogation prompt, so it can open with *"You bought the XM4s in March. What's wrong with them?"* instead of a generic challenge.

## Check 2 — What do the angry reviews say?

Star ratings are useless — everything is 4.3. The signal is in the 1★ and 2★ reviews, and in what people say six months in. The agent should go read those specifically and surface the **failure modes**, not the average.

**What we want back:**

- The recurring complaint, not the one-off — *"headband cracks at the hinge, ~50 reviews, mostly around month 8"*
- Deal-breakers relative to *this* user's stated need — if they said "for the gym," pull the sweat-damage reviews
- Post-honeymoon reviews — filter/weight toward reviews written well after purchase date
- Known incompatibilities reviewers hit, which also feeds Check 1

**Sources:** retailer review sections (already partly in the DOM the extension scrapes), plus Reddit/forum threads for anything technical. Channel3 (see `monetize.md`) gives structured product data and can supply the alternative to recommend once we've decided the original is a bad buy.

---

## How it slots into the existing flow

```
Extension detects Buy click
        ↓
Scrape product (title, price, DOM snippet)  ← already built
        ↓
┌─────────────────────┬──────────────────────────┐
│ Check 1: compat     │ Check 2: negative reviews│   ← NEW, run in parallel
│ vs purchases table  │ scrape + summarize       │
└─────────────────────┴──────────────────────────┘
        ↓
Both results injected into build_prompt() alongside profile + history
        ↓
LLM interrogates with actual ammunition:
  "You already own something that does this."
  "43 reviewers say the hinge snaps around month 8."
        ↓
Verdict → if denied, hand off to Channel3 for a better fit
```

---

## What it touches

| File | Change |
|---|---|
| `server/prompts.py` | `build_prompt()` gains `owned` and `review_signals` args; system prompt told to lead with concrete evidence over generic guilt |
| `server/db.py` | New `get_related_purchases(user_id, category, months)` — pull prior buys in the same/adjacent category |
| `server/llm.py` | New review-summarization call: reviews in → structured failure modes out |
| `server/schema.sql` | Optional `review_signals` cache table keyed by product URL, so we don't re-scrape the same product per user |
| `extension/detector.js` | Also scrape the review section of the product page, not just title/price |
| `extension/modal/modal.js` | Render the evidence — "3 recurring complaints" chip, "you already own X" chip |

---

## Why this is the stronger half of the product

Blocking a purchase is easy and annoying. **Being right about *why*** is the thing people would actually pay for and keep installed. A generic "do you really need this?" gets dismissed in one click. "You own the previous model and the top complaint on this one is a hinge that snaps" does not — and it's the same modal, just fed real data.

It also gives the demo a much better beat than pure friction: the agent isn't nagging, it's doing the twenty minutes of research the user was about to skip.

---

## Open questions

- Scrape reviews client-side (extension already has the page, no CORS problems) or server-side (cacheable across users, but needs to fetch the page itself)? Client-side is faster to build; server-side scales better.
- How aggressive is the compat check before it gets annoying? A false "you already own this" is worse than saying nothing.
- Category taxonomy — `purchases.category` is currently free text. Needs to be normalized for cross-referencing to work at all.
- Latency budget: the modal has to feel instant. Reviews may need to stream in after the first interrogation turn rather than block it.
