// SwiperNoSwiping extension config
// Edit locally. Do not commit changes to mock flags.

const CONFIG = {
  // Hosted hackathon brain (stateless — stores nothing). Self-hosters:
  // point this back at http://localhost:8000.
  BACKEND_URL: 'https://swipernoswiping-production.up.railway.app',

  // Minutes a denied product's page stays locked out. 0 = no lockout: the
  // overlay stays up and the user can re-argue immediately.
  COOLDOWN_MINUTES: 0,

  // Development switches — all default to false.
  // Flip locally, never commit.
  MOCK_BACKEND: false,
  MOCK_PRODUCT: false,
};

if (typeof window !== 'undefined') {
  window.__SWIPERNO_CONFIG = CONFIG;
}
