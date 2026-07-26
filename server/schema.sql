CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  display_name TEXT,
  income_band TEXT,
  monthly_budget_cents INTEGER,
  savings_goal TEXT,
  goal_target_cents INTEGER,
  known_weakness TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  site TEXT,
  product_title TEXT,
  price_cents INTEGER,
  currency TEXT DEFAULT 'USD',
  url TEXT,
  image_url TEXT,
  category TEXT,
  verdict TEXT CHECK (verdict IN ('approved','denied','abandoned')),
  score INTEGER,
  final_justification TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS turns (
  id INTEGER PRIMARY KEY,
  purchase_id INTEGER NOT NULL REFERENCES purchases(id),
  idx INTEGER,
  role TEXT CHECK (role IN ('assistant','user')),
  content TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id, created_at DESC);
