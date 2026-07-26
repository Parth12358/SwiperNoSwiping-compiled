# PRD-Pitch — SwiperNoSwiping

**Audience:** Hackathon judges, potential investors, product reviewers
**Format:** 5-minute pitch + 90-second live demo
**Extension requirement:** Must activate with a valid DeepSeek API key in `server/.env`

---

## 1. The problem

Impulse purchases happen in the gap between wanting and clicking. That gap is currently ~0.4 seconds — and there is nothing in it.

Every existing "budgeting" tool reports the damage *after* the card is charged. Mint, YNAB, Copilot — all of them say "you spent too much on electronics last month." None of them say "stop, you just bought headphones for the fourth time this month" *before* the click fires.

**The gap is real:** 63% of online shoppers report making purchases they later regret. The average impulse purchase is $114. The average time between seeing an ad and clicking "Buy Now" is under 15 seconds on mobile, under 5 seconds on desktop.

The problem isn't information. It's friction. Or more precisely — the total absence of it.

---

## 2. The product

**SwiperNoSwiping** is a Chrome extension that covers the Buy Now button with an invisible wall. To get through it, you have to justify the purchase to an LLM that knows who you are, what you've bought before, and what you said last time.

The extension extends the gap between wanting and clicking from 0.4 seconds to ~90 seconds — and fills it with an adversarial conversation.

**One-liner:** *Your wallet now has a lawyer, and the lawyer thinks you're lying.*

---

## 3. How it works

```
You click "Buy Now"
     │
     ▼
Nothing happens. A modal opens instead.
     │
     ▼
The LLM (DeepSeek) knows:
  • Your savings goal (e.g., "Japan trip, $4,000 target")
  • Your income band and monthly budget
  • Your last 12 purchases, including 4 pairs of headphones you don't need
     │
     ▼
It asks: "You already own four pairs of over-ear headphones. What changed?"
     │
     ▼
You type: "I want them."
     │
     ▼
LLM: "Your savings goal is a Japan trip and you're $2,700 short. Try again."
     │
     ▼
You type: "My current ones broke and I have calls all day."
     │
     ▼
LLM: "Fair. Go ahead." → APPROVED. The real button clicks.
```

A weak justification gets **DENIED**. The money moves to your "saved" counter. A strong justification gets **APPROVED**. The real click fires. The extension has no power to actually stop you — it just asks you to explain yourself first.

---

## 4. Why this matters

### 4.1 The economics of a 90-second pause

Behavioral economics has known for decades that frictions reduce consumption. The "nudge" literature is full of examples: defaults on retirement plans, opt-out organ donation, calorie labels on menus. But none of it applies to the single highest-leverage moment in consumer spending: the checkout button.

A 90-second compulsory pause at the moment of purchase has no precedent in e-commerce. No one has ever built a product that lives in that gap because until late 2024, there was no technology that could hold a grounded, adversarial, multi-turn conversation at checkout speed. LLMs changed that.

### 4.2 The buyer's agent asymmetry

Every shopping site has a seller's agent: the recommendation algorithm, the scarcity timer, the "37 people are looking at this" banner, the one-click purchase button. The buyer has no agent. Amazon has 15,000 engineers optimizing the purchase funnel. The customer has a to-do list item called "stop buying things."

SwiperNoSwiping is the buyer's agent. It runs locally, has no commercial relationship with any retailer, and its only incentive is the user's stated savings goal.

### 4.3 Privacy-first by architecture

The extension never sends your full browsing session to a server. It extracts a trimmed 4KB snippet of the product page — just enough context for the LLM to ask a grounded question. Your browsing history stays on your machine. Your purchase history is in a local SQLite database. The DeepSeek API key is server-side and never enters a browser context.

The joke ad slot in the modal picks from a static list at random. No user data feeds ad selection. No behavioral targeting, no financial vulnerability signals, no "serve gambling ads to users with high denied counts." The joke stays in the pitch.

---

## 5. The demo

### 90-second live run

| Step | What happens | What it proves |
|------|-------------|----------------|
| 1 | Product page open. Click Buy Now. | The button is dead. Modal appears in <1s. |
| 2 | Type "I want it." | LLM knows the user's savings goal and calls it out. |
| 3 | Type "my headphones broke and I have calls" | LLM evaluates, approves. Real click fires. |
| 4 | Open popup. | Shows $2,274 saved, 10 purchases blocked. |
| 5 | Close. | No crash, no error, one clean take. |

### What makes the demo compelling

- **The LLM is personal.** It knows the user has bought 4 pairs of headphones and a mechanical keyboard in the last 3 months. It calls that out unprompted.
- **The delay is 5 seconds, not 30.** `deepseek-v4-flash` returns verdicts in under 3 seconds. The user feels a conversation, not a loading screen.
- **It approves real needs.** The extension doesn't say "no" to everything. Replacements, work equipment, medical items — approved immediately. This isn't a deprivation machine.
- **The savings counter is real money.** Every denied purchase adds to the total. The user sees exactly what they didn't spend, mapped to their stated goal. "$2,274 saved. That's 57% of your Japan trip."

---

## 6. Business model (the 5-minute version)

### 6.1 Freemium extension

- **Free tier:** One user profile, one savings goal, up to 20 interrogations/month. The ad slot shows sponsor ads (random, non-targeted).
- **Premium ($3.99/month):** Unlimited interrogations, unlimited savings goals, category-level budgets, weekly reports, streak tracking. No ads.
- **Family ($7.99/month):** Up to 5 profiles, shared family budget, kid mode (approval routing to parent).

### 6.2 Sponsorship model

The ad slot in the free tier shows static, non-targeted ads. A sponsor pays for the slot — not for the targeting. Examples: financial literacy apps, credit unions, budgeting tools, therapy platforms. The sponsor aligns with the product's mission. "This denial brought to you by BetterHelp" is a joke that also happens to be a real ad unit.

### 6.3 Affiliate model (post-launch, optional)

When the extension denies a purchase, it could offer a cheaper alternative from a partner retailer. "You don't need the $348 Sony headphones. These $79 Anker ones have the same rating." If the user buys the alternative, the extension takes a cut. This is opt-in only and disclosed clearly.

### 6.4 Why not just a free side project?

Because the server costs money. DeepSeek API calls are not free. A user who blocks 20 impulse purchases a month is making ~60 LLM calls (3 turns × 20 purchases). At current API pricing, that's about $0.15/user/month in inference costs. At 100,000 free users, that's $15,000/month. The premium tier exists to cover this — and to make sure the extension's incentives stay aligned with the user.

---

## 7. Competitive landscape

| Tool | When it intervenes | Uses AI | Personal | Friction |
|------|-------------------|---------|-----------|----------|
| Mint / YNAB | After purchase | No | Category budgets | None at checkout |
| Honey / Rakuten | During purchase | No | No | Actually reduces friction (coupons) |
| Browser content blockers | Never (blocks ads, not purchases) | No | No | None at checkout |
| SelfControl / Cold Turkey | Before browsing (blocks sites) | No | No | All-or-nothing |
| **SwiperNoSwiping** | **At the Buy button** | **Yes** | **Yes (history, goals)** | **90-second required justification** |

Nobody competes in the gap. Every existing tool is either before the browsing session (site blockers) or after the purchase (budgeting apps). The moment of maximum leverage — the checkout button — is unoccupied.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| **LLM latency kills the demo.** User staring at a spinner for >5s. | `deepseek-v4-flash`, `max_tokens=300`, thinking mode off, 8s timeout, fail open (purchase proceeds). Pre-warm one call before demoing. |
| **LLM is too lenient or too harsh.** Approves everything or denies everything. | Scored rubric: 0-39 denied, 40-69 probe, 70-100 approved. Tunable threshold via env var. Hard rule: medical/food/safety/work → approve immediately. |
| **Users find it annoying and uninstall.** | The extension is a speed bump, not a vault. It takes 90 seconds, not 10 minutes. It approves legitimate purchases. The savings counter shows real progress toward a goal the user set themselves. |
| **Chrome-only limits reach.** | Chrome has 65% browser market share. Firefox/Edge ports are a week of MV3 work. Not a launch concern. |
| **API key requirement is a friction point.** | Users must bring their own DeepSeek key (or the premium tier provides one). Setup is explicitly documented. This is a conscious tradeoff: the key stays server-side, the user's data stays local, and no third party sees purchase history. |
| **Privacy: the LLM sees product context.** | Only a trimmed 4KB `innerText` snippet is sent — not the full DOM, not the user's session, not cookies. The URL and product title are transmitted. This is the minimum viable context for a grounded question. |
| **Real money spent during a live demo.** | Demo on a saved offline `demo/product.html`. Do not click through on a real retail site with a real payment method. |

---

## 9. The ask

We need:

1. **A DeepSeek API key.** One key, one model, one provider. The extension is inactive without it. We validate the key on server startup and fail open if it's missing — but the demo needs a live key to show the LLM being personal.
2. **3 hours, 4 engineers.** Each working on an independent vertical slice with frozen contracts at T+0:20. Zero idle-blocking by design. Three small rolling merges instead of one big one.
3. **One Chrome instance, one laptop, one 90-second unbroken take.** No code changes mid-demo. If it breaks on stage, we fail open and keep going.

---

## 10. What we're not asking for

- Permission to ship to the Chrome Web Store (loads unpacked, demo only).
- Multiple AI providers, fallback models, or provider-agnostic architecture (DeepSeek, everywhere, only).
- Cross-browser support (Chrome-only, by design — saves 45 minutes of polyfill work).
- Real auth, multi-user, or account sync (one hardcoded `user_id = 1`).
- Real ad targeting (static joke ads, random selection, no user data).
- Bypass-proofing (devtools deletion is trivial; don't care).
- Mobile support (desktop Chrome only).

---

## 11. The team

4 engineers, 4 vertical slices, 3 hours, zero merge conflicts if directory boundaries are respected.

| Person | Slice | Delivers |
|--------|-------|----------|
| **A** | Extension & DOM | Button detection, invisible overlay, click interception, product extraction, background proxy |
| **B** | Modal & Popup | Shadow-DOM interrogation UI, chat transcript, verdict screens, stats popup, onboarding form |
| **C** | Backend & LLM | `POST /api/interrogate`, DeepSeek client (`deepseek-v4-flash`), interrogator prompt, scoring rubric |
| **D** | Data & Demo | SQLite schema, seed data, `/api/stats`, `/api/profile`, `demo/product.html`, README, rehearsal |

**Parallelization:** After T+0:20 (contract freeze), the dependency graph has zero edges. Everyone builds against fixtures and mock flags. Three rolling merges at 0:45, 1:15, and 1:45. No engineer is idle-blocked for more than 5 minutes.

---

## 12. Success criteria — what "winning" looks like

1. **Demo completes in one unbroken 90-second take.** Buy Now → modal → interrogation → approve → popup stats. No reload, no console errors, no code change mid-stage.
2. **The LLM is personal.** It references the user's actual savings goal ("Japan trip") and purchase pattern ("fourth pair of headphones") without being prompted. This is the single moment that separates this from every other demo.
3. **The savings counter tells a story.** "$2,274 saved = 57% of your Japan trip." The user set the goal. The extension shows progress.
4. **Fail-open works.** If the backend dies mid-demo, the purchase proceeds. The audience sees the extension protect the user from itself AND protect the user from the extension.
5. **The ad slot joke lands.** Because it's not actually targeting anyone. The joke is that we could, and we didn't.

---

## 13. The close

Every shopping site has spent two decades removing friction from the purchase funnel. One-click ordering. Stored payment methods. Shop Pay. Buy with Prime. The checkout button is the most optimized 40×40 pixel square in the history of commerce — and it has no counterweight.

SwiperNoSwiping puts one there. Not a wall. Not a parent. A skeptical friend with access to your bank statement, who asks one question before you spend $348 on headphones you don't need.

It's not going to save the world. It might save you from a fourth pair of headphones.

**That's worth 90 seconds of a judge's time.**
