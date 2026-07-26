// SwiperNoSwiping — background service worker
// Thin fetch proxy. All API calls from content scripts go through here.
// Fail-open on any error: the extension must never trap a user on a page.

const BACKEND_URL = 'http://localhost:8000';
const TIMEOUT_MS = 8000;

async function proxyFetch(path, options = {}) {
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
