// SwiperNoSwiping — background service worker
// Thin fetch proxy. All API calls from content scripts go through here.
// Fail-open on any error: the extension must never trap a user on a page.

const MOCK_BACKEND = false;  // Flip to true for local dev without server
// Hosted hackathon brain (stateless). Self-hosters: http://localhost:8000.
const BACKEND_URL = 'https://swipernoswiping-production.up.railway.app';
const TIMEOUT_MS = 8000;

async function proxyFetch(path, options = {}) {
  if (MOCK_BACKEND) {
    return {
      ok: true,
      data: {
        session_id: 'mock_bg_session',
        verdict: 'pending',
        reply: 'You already own two pairs of over-ears. What changed?',
        turn: 1,
        turns_remaining: 2,
        score: null,
        savings_total_cents: 227400,
      }
    };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    clearTimeout(timer);

    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}`);
    }

    const data = await res.json();

    if (!data || (typeof data === 'string' && data.trim() === '')) {
      throw new Error('Empty response from backend');
    }

    return { ok: true, data };
  } catch (err) {
    clearTimeout(timer);
    console.warn('[swiperno:background] Fetch failed (failing open):', err.message);
    return { ok: false, error: err.message };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'swiperno:fetch') {
    proxyFetch(message.path, message.options).then(sendResponse);
    return true; // keep channel open for async response
  }
});

// First-run onboarding: open the profile form in a tab so the lawyer knows
// who she's defending before the first interrogation.
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.tabs.create({ url: chrome.runtime.getURL('popup/popup.html?welcome=1') });
  }
});
