// SwiperNoSwiping — Modal logic
// State machine: loading → question → approved | denied
// Builds against mock fixtures. Swaps to real backend at M3.

(function () {
  let shadowRoot = null;
  let currentInterceptId = null;
  let currentSessionId = null;
  let currentTurn = 0;
  let currentProduct = null;
  let mockResponses = null;   // loaded from fixture files at init
  let ads = [];               // loaded from ads.json at init

  // --- Fixture loading ---

  async function loadFixture(path) {
    const res = await fetch(chrome.runtime.getURL(path));
    return res.json();
  }

  async function initMockResponses() {
    if (mockResponses) return mockResponses;
    const useMock = typeof CONFIG !== 'undefined' && CONFIG.MOCK_BACKEND;
    if (!useMock) return null;
    const [turn1, turn2, approved, denied] = await Promise.all([
      loadFixture('fixtures/interrogate/turn1.json'),
      loadFixture('fixtures/interrogate/turn2.json'),
      loadFixture('fixtures/interrogate/approved.json'),
      loadFixture('fixtures/interrogate/denied.json'),
    ]);
    mockResponses = { turn1, turn2, approved, denied };
    return mockResponses;
  }

  async function initAds() {
    if (ads.length > 0) return ads;
    try {
      const res = await fetch(chrome.runtime.getURL('modal/ads.json'));
      ads = await res.json();
    } catch (_) { /* ads are optional */ }
    return ads;
  }

  // --- Mock interrogate (reads fixture files, supports 3-turn cycle) ---

  function isStrongJustification(text) {
    const strongWords = /\b(broke|broken|need|work|calls|meeting|replac|necessar|require)\b/i;
    return strongWords.test(text);
  }

  async function mockInterrogate(product, sessionId, message) {
    await new Promise((r) => setTimeout(r, 800));
    const m = await initMockResponses();
    if (!m) throw new Error('Mock responses not loaded');

    // Turn 1: no message yet, return pending question
    if (!message) return m.turn1;

    // Turn 2: user answered. If strong, approve. Otherwise, return second pending.
    if (currentTurn <= 1) {
      if (isStrongJustification(message)) return m.approved;
      return m.turn2;
    }

    // Turn 3: final verdict
    if (isStrongJustification(message)) return m.approved;
    return m.denied;
  }

  // --- Real API (with retry and timeout) ---

  const FETCH_TIMEOUT_MS = 8000;

  async function realInterrogate(product, sessionId, message) {
    const options = {
      method: 'POST',
      body: JSON.stringify({
        user_id: 1,
        product,
        session_id: sessionId,
        message: message,
      }),
    };

    let lastError = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            reject(new Error('chrome.runtime.sendMessage timed out'));
          }, FETCH_TIMEOUT_MS);

          chrome.runtime.sendMessage(
            { type: 'swiperno:fetch', path: '/api/interrogate', options },
            (response) => {
              clearTimeout(timer);
              if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
                return;
              }
              resolve(response);
            }
          );
        });

        if (response && response.ok) {
          return response.data;
        }
        throw new Error(response ? response.error : 'No response');
      } catch (err) {
        lastError = err;
        if (attempt === 0) {
          await new Promise((r) => setTimeout(r, 500));
        }
      }
    }
    throw lastError || new Error('Failed after retry');
  }

  async function interrogate(product, sessionId, message) {
    const useMock = typeof CONFIG !== 'undefined' && CONFIG.MOCK_BACKEND;
    if (useMock) {
      return mockInterrogate(product, sessionId, message);
    }
    return realInterrogate(product, sessionId, message);
  }

  // --- State management ---

  function showState(stateName) {
    const root = shadowRoot;
    ['loading', 'question', 'approved', 'denied'].forEach((s) => {
      const el = root.getElementById(`swiperno-state-${s}`);
      if (el) el.style.display = 'none';
    });
    const target = root.getElementById(`swiperno-state-${stateName}`);
    if (target) target.style.display = 'block';
  }

  function addBubble(role, content) {
    const root = shadowRoot;
    const transcript = root.getElementById('swiperno-transcript');
    const div = document.createElement('div');
    div.className = `transcript-bubble ${role}`;
    div.textContent = content;
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;
  }

  function updateTurnCounter(remaining) {
    const root = shadowRoot;
    const counter = root.getElementById('swiperno-turn-counter');
    if (remaining <= 0) {
      counter.textContent = 'Last chance';
    } else if (remaining === 1) {
      counter.textContent = '1 question left';
    } else {
      counter.textContent = `${remaining} questions left`;
    }
  }

  function setLoading(disabled) {
    const root = shadowRoot;
    const input = root.getElementById('swiperno-input');
    const submit = root.getElementById('swiperno-submit');
    if (input) input.disabled = disabled;
    if (submit) submit.disabled = disabled;
  }

  // --- Render verdict ---

  function showApproved(reply, savings) {
    const root = shadowRoot;
    const finalTranscript = root.getElementById('swiperno-transcript-final');
    finalTranscript.innerHTML = '';
    const bubble = document.createElement('div');
    bubble.className = 'transcript-bubble assistant';
    bubble.textContent = reply;
    finalTranscript.appendChild(bubble);

    showState('approved');

    setTimeout(() => {
      if (window.__swiperno && window.__swiperno.approve) {
        window.__swiperno.approve(currentInterceptId);
      }
      if (shadowRoot && shadowRoot.host) {
        shadowRoot.host.remove();
      }
    }, 1500);
  }

  function showDenied(reply, savings) {
    const root = shadowRoot;
    const finalTranscript = root.getElementById('swiperno-transcript-final-denied');
    finalTranscript.innerHTML = '';
    const bubble = document.createElement('div');
    bubble.className = 'transcript-bubble assistant';
    bubble.textContent = reply;
    finalTranscript.appendChild(bubble);

    const savingsEl = root.getElementById('swiperno-savings-counter');
    if (savingsEl && savings) {
      const dollars = (savings / 100).toFixed(2);
      savingsEl.textContent = `You've saved $${dollars} so far.`;
    }

    showState('denied');

    if (window.__swiperno && window.__swiperno.dismiss) {
      window.__swiperno.dismiss(currentInterceptId);
    }

    setTimeout(() => {
      if (shadowRoot && shadowRoot.host) {
        shadowRoot.host.remove();
      }
    }, 5000);
  }

  // --- Turn handler ---

  async function handleTurn(message) {
    setLoading(true);
    showState('loading');

    try {
      const result = await interrogate(currentProduct, currentSessionId, message);
      currentSessionId = result.session_id;
      currentTurn++;

      if (message) {
        addBubble('user', message);
      }
      addBubble('assistant', result.reply);

      if (result.verdict === 'approved') {
        showApproved(result.reply, result.savings_total_cents);
        return;
      }

      if (result.verdict === 'denied') {
        showDenied(result.reply, result.savings_total_cents);
        return;
      }

      updateTurnCounter(result.turns_remaining);
      showState('question');
    } catch (err) {
      console.error('[swiperno:modal] Interrogate failed:', err);
      if (window.__swiperno && window.__swiperno.approve) {
        window.__swiperno.approve(currentInterceptId);
      }
      if (shadowRoot && shadowRoot.host) {
        shadowRoot.host.remove();
      }
    } finally {
      setLoading(false);
    }
  }

  // --- Init ---

  document.addEventListener('swiperno:intercept', async (e) => {
    const { intercept_id, product } = e.detail;
    currentInterceptId = intercept_id;
    currentProduct = product;
    currentSessionId = null;
    currentTurn = 0;

    const host = document.createElement('div');
    host.id = 'swiperno-modal-host';
    document.body.appendChild(host);

    shadowRoot = host.attachShadow({ mode: 'open' });

    const htmlResponse = await fetch(chrome.runtime.getURL('modal/modal.html'));
    const html = await htmlResponse.text();

    const cssResponse = await fetch(chrome.runtime.getURL('modal/modal.css'));
    const css = await cssResponse.text();

    shadowRoot.innerHTML = `<style>${css}</style>${html}`;

    const submitBtn = shadowRoot.getElementById('swiperno-submit');
    const inputEl = shadowRoot.getElementById('swiperno-input');

    submitBtn.addEventListener('click', () => {
      const text = inputEl.value.trim();
      if (!text) return;
      inputEl.value = '';
      handleTurn(text);
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitBtn.click();
      }
    });

    await handleTurn(null);

    // P1: render joke ad slot
    const adList = await initAds();
    if (adList.length > 0) {
      const ad = adList[Math.floor(Math.random() * adList.length)];
      const slot = shadowRoot.getElementById('swiperno-ad-slot');
      const content = shadowRoot.getElementById('swiperno-ad-content');
      if (slot && content) {
        content.textContent = `${ad.headline} — ${ad.sponsor}`;
        slot.style.display = 'block';
      }
    }
  });
})();
