// SwiperNoSwiping — content script
// 1. Scan for buy buttons on page load and DOM mutation
// 2. Cover each with a transparent overlay
// 3. Emit swiperno:intercept on overlay click
// 4. Listen for swiperno_mock query param for standalone testing

(function () {
  let overlays = [];
  let observedButtons = new WeakSet();
  let approvedIntercepts = new Set();    // interceptIds that are mid-approve — let clicks through

  // --- Overlay creation ---

  function createOverlay(button) {
    const rect = button.getBoundingClientRect();
    const interceptId = 'int_' + Math.random().toString(36).substring(2, 10);

    const div = document.createElement('div');
    div.className = 'swiperno-overlay';
    div.style.left = `${rect.left + window.scrollX}px`;
    div.style.top = `${rect.top + window.scrollY}px`;
    div.style.width = `${rect.width}px`;
    div.style.height = `${rect.height}px`;

    div.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const product = extractProduct(button);

      document.dispatchEvent(new CustomEvent('swiperno:intercept', {
        detail: { intercept_id: interceptId, product, target: button },
      }));
    });

    document.body.appendChild(div);
    overlays.push({ div, button, interceptId });
    observedButtons.add(button);
  }

  // --- Reposition on scroll/resize ---

  let rafId = null;
  function repositionAll() {
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      for (const { div, button } of overlays) {
        if (!document.body.contains(button)) continue;
        const rect = button.getBoundingClientRect();
        div.style.left = `${rect.left + window.scrollX}px`;
        div.style.top = `${rect.top + window.scrollY}px`;
        div.style.width = `${rect.width}px`;
        div.style.height = `${rect.height}px`;
      }
      rafId = null;
    });
  }

  window.addEventListener('scroll', repositionAll, { passive: true });
  window.addEventListener('resize', repositionAll, { passive: true });

  // --- Scan the DOM ---

  function scanAndOverlay() {
    const buttons = window.__swipernoDetector.detectButtons();
    for (const btn of buttons) {
      if (!observedButtons.has(btn)) {
        createOverlay(btn);
      }
    }
  }

  // --- MutationObserver for dynamic content ---

  let mutationTimer = null;
  const observer = new MutationObserver(() => {
    if (mutationTimer) clearTimeout(mutationTimer);
    mutationTimer = setTimeout(scanAndOverlay, 300);
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // --- Product context extraction ---

  function extractProduct(button) {
    const site = window.__swipernoDetector.detectSite();

    // Title: og:title → #productTitle → h1 → document.title
    let title = null;
    const metaTitle = document.querySelector('meta[property="og:title"]');
    if (metaTitle) title = metaTitle.getAttribute('content');
    if (!title) {
      const productTitleEl = document.querySelector('#productTitle');
      if (productTitleEl) title = productTitleEl.innerText.trim();
    }
    if (!title) {
      const h1 = document.querySelector('h1');
      if (h1) title = h1.innerText.trim();
    }
    if (!title) title = document.title;

    const priceCents = extractPrice();

    // Image: og:image → first img in product container → null
    let imageUrl = null;
    const metaImage = document.querySelector('meta[property="og:image"]');
    if (metaImage) imageUrl = metaImage.getAttribute('content');
    if (!imageUrl) {
      const container = button.closest('[class*="product" i], [id*="product" i], [class*="detail" i], [class*="pdp" i]');
      if (container) {
        const firstImg = container.querySelector('img');
        if (firstImg) imageUrl = firstImg.src;
      }
    }

    const snippet = extractSnippet(button);

    return {
      title: title || null,
      price_cents: priceCents,
      currency: 'USD',
      url: window.location.href,
      image_url: imageUrl,
      site,
      dom_snippet: snippet,
    };
  }

  function extractPrice() {
    // Try schema.org microdata
    const meta = document.querySelector('[itemprop="price"]');
    if (meta && meta.getAttribute('content')) {
      const val = parseFloat(meta.getAttribute('content'));
      if (!isNaN(val)) return Math.round(val * 100);
    }

    // Try data-price attribute
    const dataPrice = document.querySelector('[data-price]');
    if (dataPrice) {
      const val = parseFloat(dataPrice.getAttribute('data-price'));
      if (!isNaN(val)) return Math.round(val * 100);
    }

    // Try Amazon-style .a-price-whole + .a-price-fraction
    const whole = document.querySelector('.a-price-whole');
    const fraction = document.querySelector('.a-price-fraction');
    if (whole) {
      const w = parseInt(whole.innerText.replace(/[^0-9]/g, ''), 10);
      const f = fraction ? parseInt(fraction.innerText.replace(/[^0-9]/g, ''), 10) : 0;
      if (!isNaN(w)) return w * 100 + f;
    }

    // Try regex match on a price element near the button or in body
    const priceEls = document.querySelectorAll('.price, [class*="price" i], [id*="price" i]');
    for (const el of priceEls) {
      const match = el.innerText.match(/\$?([\d,]+\.?\d{0,2})/);
      if (match) {
        const cents = Math.round(parseFloat(match[1].replace(/,/g, '')) * 100);
        if (!isNaN(cents) && cents > 0) return cents;
      }
    }

    // Last resort: scan body text
    const text = document.body.innerText;
    const match = text.match(/\$(\d{1,3}(?:,\d{3})*\.?\d{0,2})/);
    if (match) {
      return Math.round(parseFloat(match[1].replace(/,/g, '')) * 100);
    }

    return null;
  }

  function extractSnippet(button) {
    const productContainer = button.closest('[class*="product" i], [class*="pdp" i], [id*="product" i], [class*="detail" i]');
    if (productContainer) {
      return productContainer.innerText.substring(0, 4000);
    }
    return document.body.innerText.substring(0, 4000);
  }

  // --- Capture-phase click listener (second net) ---

  document.addEventListener('click', (e) => {
    const button = e.target.closest('button, input[type="submit"], a[role="button"]');
    if (!button) return;

    // Check if this button is mid-approve — let it through
    const overlay = overlays.find((o) => o.button === button);
    if (overlay && approvedIntercepts.has(overlay.interceptId)) {
      approvedIntercepts.delete(overlay.interceptId);
      return; // let the click through
    }

    const adapter = window.__swipernoDetector.getAdapter();
    const text = button.innerText || button.value || '';
    if (adapter.textRegex.test(text) && !observedButtons.has(button)) {
      // Missed by the overlay — intercept anyway
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const product = extractProduct(button);
      const interceptId = 'int_' + Math.random().toString(36).substring(2, 10);

      document.dispatchEvent(new CustomEvent('swiperno:intercept', {
        detail: { intercept_id: interceptId, product, target: button },
      }));
    }
  }, true);

  // --- swiperno_mock support ---
  // At document_idle, DOMContentLoaded has already fired — fire immediately.

  if (new URLSearchParams(window.location.search).get('swiperno_mock') === '1') {
    document.dispatchEvent(new CustomEvent('swiperno:intercept', {
      detail: {
        intercept_id: 'int_mock_demo',
        product: {
          title: 'Sony WH-1000XM5 Wireless Headphones',
          price_cents: 34800,
          currency: 'USD',
          url: window.location.href,
          image_url: 'https://placehold.co/600x400/EEE/999?text=Sony+WH-1000XM5',
          site: 'demo',
          dom_snippet: 'Sony WH-1000XM5 Wireless Headphones. $348.00. Industry-leading noise canceling...',
        },
        target: null,
      },
    }));
  }

  // --- A's external API for B ---

  window.__swiperno = {
    approve(interceptId) {
      const overlay = overlays.find((o) => o.interceptId === interceptId);
      if (!overlay) {
        console.warn('[swiperno] approve: no overlay found for', interceptId);
        return;
      }

      // Mark as approved so the capture listener lets this click through
      approvedIntercepts.add(interceptId);

      // Remove the overlay
      overlay.div.remove();
      overlays = overlays.filter((o) => o !== overlay);

      // Programmatically click the real button — capture listener sees the flag and passes
      overlay.button.click();
    },

    dismiss(interceptId) {
      // 10-minute localStorage cooldown keyed by interceptId
      const cooldownKey = `swiperno:cooldown:${interceptId}`;
      localStorage.setItem(cooldownKey, Date.now().toString());

      // Also mark the overlay so it stays but shows "cooldown" state
      const overlay = overlays.find((o) => o.interceptId === interceptId);
      if (overlay) {
        overlay.div.style.cursor = 'not-allowed';
      }
    },
  };

  // --- Initial scan ---

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scanAndOverlay);
  } else {
    scanAndOverlay();
  }
})();
