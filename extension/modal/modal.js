// SwiperNoSwiping — Modal logic
// State machine: loading → question → approved | denied
// Builds against mock fixtures. Swaps to real backend at M3.

(function () {
  let shadowRoot = null;
  let currentInterceptId = null;
  let currentSessionId = null;
  let currentTurn = 0;
  let currentProduct = null;

  // --- Mock interrogate (swap to real at M3) ---

  const MOCK_RESPONSES = {
    turn1: {
      session_id: 'mock_session_001',
      verdict: 'pending',
      reply: "You've bought four pairs of headphones in the last three months. What makes this one different?",
      turn: 1,
      turns_remaining: 2,
      score: null,
      savings_total_cents: 227400,
    },
    turn2_weak: {
      session_id: 'mock_session_001',
      verdict: 'denied',
      reply: "Not good enough. You're $2,700 short of your Japan trip and you already own working headphones.",
      turn: 2,
      turns_remaining: 1,
      score: 25,
      savings_total_cents: 262200,
    },
    turn2_strong: {
      session_id: 'mock_session_001',
      verdict: 'approved',
      reply: 'Fair enough. A broken pair that you need for work is a real reason. Go ahead.',
      turn: 2,
      turns_remaining: 1,
      score: 78,
      savings_total_cents: 227400,
    },
  };

  function isStrongJustification(text) {
    const strongWords = /\b(broke|broken|need|work|calls|meeting|replac|necessar|require)\b/i;
    return strongWords.test(text);
  }

  async function mockInterrogate(product, sessionId, message) {
    await new Promise((r) => setTimeout(r, 800));
    if (!message) return MOCK_RESPONSES.turn1;
    if (isStrongJustification(message)) return MOCK_RESPONSES.turn2_strong;
    return MOCK_RESPONSES.turn2_weak;
  }

  // --- Real API ---

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

    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: 'swiperno:fetch', path: '/api/interrogate', options },
        (response) => {
          if (response && response.ok) {
            resolve(response.data);
          } else {
            reject(new Error(response ? response.error : 'No response'));
          }
        }
      );
    });
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
  }

  // --- Turn handler ---

  async function handleTurn(message) {
    setLoading(true);
    showState('loading');

    try {
      const result = await interrogate(currentProduct, currentSessionId, message);
      currentSessionId = result.session_id;

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
      shadowRoot.host.remove();
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
  });
})();
