// SwiperNoSwiping extension config
// Edit locally. Do not commit changes to mock flags.

const CONFIG = {
  BACKEND_URL: 'http://localhost:8000',

  // Development switches — all default to false.
  // Flip locally, never commit.
  MOCK_BACKEND: false,
  MOCK_PRODUCT: false,
};

if (typeof window !== 'undefined') {
  window.__SWIPERNO_CONFIG = CONFIG;
}
