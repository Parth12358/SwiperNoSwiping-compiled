// SwiperNoSwiping — content script
// 1. Scan for buy buttons on page load and DOM mutation
// 2. Cover each with a transparent overlay
// 3. Emit swiperno:intercept on overlay click
// 4. Listen for swiperno_mock query param for standalone testing

(function () {
  let overlays = [];
  let observedButtons = new WeakSet();
  // interceptId -> { div|null, button }. Both the overlay path and the
  // capture-phase fallback register here so approve() can always resolve
  // the real button to click.
  const interceptMap = new Map();

  // Denial cooldown per page. 0 = off (no lockout; the overlay just stays and
  // the user can argue again immediately). Set COOLDOWN_MINUTES in config.js.
  const COOLDOWN_MS =
    ((window.__SWIPERNO_CONFIG && window.__SWIPERNO_CONFIG.COOLDOWN_MINUTES) || 0) * 60 * 1000;

  // --- Overlay creation ---

  function createOverlay(button) {
    const rect = button.getBoundingClientRect();
    const div = document.createElement('div');
    div.className = 'swiperno-overlay';
    div.style.left = `${rect.left + window.scrollX}px`;
    div.style.top = `${rect.top + window.scrollY}px`;
    div.style.width = `${rect.width}px`;
    div.style.height = `${rect.height}px`;

    const interceptId = 'int_' + Math.random().toString(36).substring(2, 10);
    interceptMap.set(interceptId, { div, button });

    div.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const product = extractProduct(button);

      document.dispatchEvent(new CustomEvent('swiperno:intercept', {
        detail: { intercept_id: interceptId, product },
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
      if (observedButtons.has(btn)) continue;
      if (COOLDOWN_MS > 0) {
        const cooldownKey = 'swiperno:cooldown:' + btoa(window.location.href).substring(0, 32);
        const cooldown = localStorage.getItem(cooldownKey);
        if (cooldown && (Date.now() - parseInt(cooldown, 10) < COOLDOWN_MS)) continue;
      }
      try {
        createOverlay(btn);
      } catch (err) {
        // One bad button must not kill protection for the rest of the page.
        console.warn('[swiperno] overlay failed for a button:', err);
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
    const metaTitle = document.querySelector('meta[property="og:title"]');
    const productTitleEl = document.querySelector('#productTitle');
    const h1 = document.querySelector('h1');
    const title = metaTitle
      ? metaTitle.getAttribute('content')
      : (productTitleEl ? productTitleEl.innerText : null)
      || (h1 ? h1.innerText : null)
      || document.title;

    const priceCents = extractPrice(button);
    let imageUrl = null;
    const metaImage = document.querySelector('meta[property="og:image"]');
    if (metaImage) imageUrl = metaImage.getAttribute('content');
    if (!imageUrl) {
      const productContainer = document.querySelector('[class*="product" i], [class*="pdp" i], [id*="product" i]');
      if (productContainer) {
        const img = productContainer.querySelector('img');
        if (img) imageUrl = img.src;
      }
    }

    const snippet = extractSnippet(button);

    return {
      title,
      price_cents: priceCents,
      currency: 'USD',
      url: window.location.href,
      image_url: imageUrl,
      site,
      dom_snippet: snippet,
    };
  }

  function _parseMoney(text) {
    if (!text) return null;
    const m = String(text).match(/(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)/);
    if (!m) return null;
    const val = parseFloat(m[1].replace(/,/g, ''));
    return isNaN(val) ? null : Math.round(val * 100);
  }

  function extractPrice(button) {
    // PRD §9.1: unparseable -> null, never guess. A wrong price poisons the
    // whole interrogation (the AI argues about the wrong number), so every
    // lookup is scoped to the BUYBOX / product container — never the cart
    // rail, sponsored carousels, or the page-wide first "$X".

    // 1. Amazon's canonical current price: buybox .a-offscreen holds the full
    //    "$49.99" string. :not(.a-text-price) skips struck-through list prices.
    const amazonBuybox = [
      '#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen',
      '#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen',
      '#apex_desktop .a-price:not(.a-text-price) .a-offscreen',
      '#price_inside_buybox',
    ];
    for (const sel of amazonBuybox) {
      const cents = _parseMoney(document.querySelector(sel)?.textContent);
      if (cents !== null) return cents;
    }

    // 2. The clicked button's own product container (works on any retailer).
    const container = button && button.closest(
      '#buybox, [id*="buybox" i], [class*="buybox" i], [class*="product" i], [class*="pdp" i], [id*="product" i], [class*="detail" i]'
    );
    if (container) {
      const cents =
        _parseMoney(container.querySelector('.a-price:not(.a-text-price) .a-offscreen')?.textContent) ??
        _parseMoney(container.querySelector('[itemprop="price"]')?.getAttribute('content')) ??
        _parseMoney(container.querySelector('[data-price]')?.dataset.price) ??
        (() => {
          const whole = container.querySelector('.a-price:not(.a-text-price) .a-price-whole');
          if (!whole) return null;
          const frac = container.querySelector('.a-price:not(.a-text-price) .a-price-fraction');
          const w = parseInt(whole.textContent.replace(/[^0-9]/g, ''), 10);
          const f = frac ? parseInt(frac.textContent.replace(/[^0-9]/g, ''), 10) : 0;
          return isNaN(w) ? null : w * 100 + (isNaN(f) ? 0 : f);
        })() ??
        _parseMoney((container.innerText.match(/\$(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)/) || [])[1]);
      if (cents !== null) return cents;
    }

    // 3. Page-level structured data only (meta tags are per-product, unlike
    //    the first .a-price-whole in the DOM, which is often the cart rail).
    const cents =
      _parseMoney(document.querySelector('meta[property="product:price:amount"]')?.getAttribute('content')) ??
      _parseMoney(document.querySelector('meta[property="og:price:amount"]')?.getAttribute('content')) ??
      _parseMoney(document.querySelector('[itemprop="price"]')?.getAttribute('content'));
    if (cents !== null) return cents;

    // No confident price -> null. Backend renders "unknown price" and the AI
    // asks instead of arguing about a number that belongs to the cart rail.
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

    const adapter = window.__swipernoDetector.getAdapter();
    const text = button.innerText || button.value || '';
    if (adapter.textRegex.test(text) && !observedButtons.has(button)) {
      // Missed by the overlay — intercept anyway
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const product = extractProduct(button);
      const interceptId = 'int_' + Math.random().toString(36).substring(2, 10);
      // Register so approve(interceptId) can click the real button later.
      interceptMap.set(interceptId, { div: null, button });

      document.dispatchEvent(new CustomEvent('swiperno:intercept', {
        detail: { intercept_id: interceptId, product },
      }));
    }
  }, true);

  // --- swiperno_mock support ---

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
      },
    }));
  }

  // --- A's external API for B ---

  window.__swiperno = {
    approve(interceptId) {
      const entry = interceptMap.get(interceptId);
      if (!entry) return;
      if (entry.div) {
        entry.div.remove();
        const idx = overlays.findIndex((o) => o.interceptId === interceptId);
        if (idx !== -1) overlays.splice(idx, 1);
      }
      interceptMap.delete(interceptId);
      entry.button.click();
    },

    dismiss(interceptId) {
      // Denied: the overlay STAYS so the button remains blocked (PRD §9.1).
      // Clicking again reopens the interrogation — no lockout unless a
      // cooldown is configured in config.js.
      if (COOLDOWN_MS > 0) {
        const cooldownKey = 'swiperno:cooldown:' + btoa(window.location.href).substring(0, 32);
        localStorage.setItem(cooldownKey, Date.now().toString());
      }
    },
  };

  // --- Initial scan ---

  scanAndOverlay();
})();
