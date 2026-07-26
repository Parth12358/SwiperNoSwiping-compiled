// SwiperNoSwiping — button detector
// Two strategies: known selectors first, then text-regex fallback.
// Per-site adapters isolate retailer-specific logic.

const adapters = {
  amazon: {
    selectors: [
      '#buy-now-button',
      '#submit\\.buy-now',
      '#add-to-cart-button',
      '[name="submit.buy-now"]',
      '[id*="checkout" i]',
      '[data-testid*="checkout" i]',
      '[aria-label*="buy" i]',
      '[aria-label*="checkout" i]',
      'input[value*="Buy" i]',
      'input[value*="checkout" i]',
      'input[value*="Proceed" i]',
    ],
    textRegex: /buy now|add to cart|place order|proceed to checkout|complete purchase|pay now|checkout/i,
  },
  bestbuy: {
    selectors: [
      '[class*="add-to-cart" i]',
      '[id*="checkout" i]',
      '[data-testid*="checkout" i]',
      '[data-button-state="ADD_TO_CART"]',
      'button[class*="addToCart" i]',
    ],
    textRegex: /add to cart|checkout|buy now|place order|pre.order/i,
  },
  generic: {
    selectors: [
      '[id*="checkout" i]',
      '[data-testid*="checkout" i]',
      '[aria-label*="buy" i]',
      '[aria-label*="checkout" i]',
      '[aria-label*="cart" i]',
      'input[value*="Buy" i]',
      'input[value*="checkout" i]',
    ],
    textRegex: /buy now|add to cart|place order|proceed to checkout|complete purchase|pay now|checkout/i,
  },
};

function detectSite() {
  const host = window.location.hostname.replace('www.', '');
  if (host.includes('amazon')) return 'amazon';
  if (host.includes('bestbuy')) return 'bestbuy';
  return 'generic';
}

function getAdapter() {
  const site = detectSite();
  return adapters[site] || adapters.generic;
}

function detectBySelectors(selectors) {
  const results = [];
  const seen = new Set();
  for (const sel of selectors) {
    try {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        if (!seen.has(el) && isVisible(el)) {
          results.push(el);
          seen.add(el);
        }
      }
    } catch (_) {
      // invalid selector, skip
    }
  }
  return results;
}

function detectByText(regex) {
  const results = [];
  const candidates = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
  for (const el of candidates) {
    if (regex.test(el.innerText || el.value || '')) {
      results.push(el);
    }
  }
  return results;
}

function isVisible(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
  return true;
}

function detectButtons() {
  const adapter = getAdapter();

  const bySelector = detectBySelectors(adapter.selectors);
  if (bySelector.length > 0) {
    return bySelector;
  }

  return detectByText(adapter.textRegex);
}

// Expose for A's content.js
window.__swipernoDetector = { detectButtons, detectSite, getAdapter };
