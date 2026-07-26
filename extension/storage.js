// SwiperNoSwiping — client-side data store (chrome.storage.local)
// YOUR data lives HERE, on your machine, as JSON in the extension's storage —
// not on our server. Every interrogation request carries this context with it;
// the hosted backend is stateless and stores nothing.
// Loaded in content scripts (before modal.js) and in the popup.

(function () {
  const PROFILE_KEY = 'swiperno_profile';
  const PURCHASES_KEY = 'swiperno_purchases';
  const MAX_PURCHASES = 100;

  const DEFAULT_PROFILE = {
    display_name: '',
    income_band: '',
    monthly_budget_cents: null,
    savings_goal: '',
    goal_target_cents: null,
    known_weakness: '',
  };

  function storageGet(keys) {
    return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
  }

  function storageSet(obj) {
    return new Promise((resolve) => chrome.storage.local.set(obj, resolve));
  }

  function statsFrom(purchases) {
    let denied = 0;
    let approved = 0;
    let saved = 0;
    const catCounts = {};
    for (const p of purchases) {
      if (p.verdict === 'denied') {
        denied += 1;
        if (typeof p.price_cents === 'number') saved += p.price_cents;
        if (p.category) catCounts[p.category] = (catCounts[p.category] || 0) + 1;
      } else if (p.verdict === 'approved') {
        approved += 1;
      }
    }
    let top = null;
    for (const [cat, n] of Object.entries(catCounts)) {
      if (top === null || n > catCounts[top]) top = cat;
    }
    return { denied_count: denied, approved_count: approved, saved_cents: saved, top_category: top };
  }

  window.__swipernoStore = {
    async getProfile() {
      const data = await storageGet([PROFILE_KEY]);
      return { ...DEFAULT_PROFILE, ...(data[PROFILE_KEY] || {}) };
    },

    async setProfile(fields) {
      const current = await this.getProfile();
      const merged = { ...current };
      for (const key of Object.keys(DEFAULT_PROFILE)) {
        if (key in (fields || {})) merged[key] = fields[key];
      }
      await storageSet({ [PROFILE_KEY]: merged });
      return merged;
    },

    async getPurchases() {
      const data = await storageGet([PURCHASES_KEY]);
      return Array.isArray(data[PURCHASES_KEY]) ? data[PURCHASES_KEY] : [];
    },

    async recordVerdict(entry) {
      const purchases = await this.getPurchases();
      purchases.unshift({
        title: entry.title || 'unknown item',
        price_cents: typeof entry.price_cents === 'number' ? entry.price_cents : null,
        verdict: entry.verdict,
        score: typeof entry.score === 'number' ? entry.score : null,
        category: entry.category || null,
        created_at: entry.created_at || new Date().toISOString(),
      });
      await storageSet({ [PURCHASES_KEY]: purchases.slice(0, MAX_PURCHASES) });
    },

    async getStats() {
      return statsFrom(await this.getPurchases());
    },

    // The payload every interrogation request carries: who you are, what you
    // bought recently, and your running score. Shape matches the backend's
    // context contract (profile / recent / stats).
    async getContext() {
      const [profile, purchases] = await Promise.all([this.getProfile(), this.getPurchases()]);
      return {
        profile,
        recent: purchases.slice(0, 5).map((p) => ({
          title: p.title,
          price_cents: p.price_cents,
          verdict: p.verdict,
          created_at: p.created_at,
        })),
        stats: statsFrom(purchases),
      };
    },
  };
})();
