// SwiperNoSwiping extension config
// Edit locally. Do not commit changes to mock flags.

const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',

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
