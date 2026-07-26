"""Seed the database with a demo user and purchase history."""
import sqlite3

DB = "server/swiperno.db"

def seed():
    conn = sqlite3.connect(DB)
    
    conn.execute("""
        INSERT OR REPLACE INTO users (id, display_name, income_band, monthly_budget_cents, savings_goal, goal_target_cents, known_weakness)
        VALUES (?,?,?,?,?,?,?)
    """, (1, "Alex", "50k-100k", 200000, "Japan trip", 400000, "mechanical keyboards"))
    
    purchases = [
        (1, "amazon", "Sony WH-1000XM4", 34800, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 28, "impulse"),
        (1, "amazon", "AirPods Pro", 24900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 32, "impulse audio"),
        (1, "amazon", "Bose QC45", 32900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 35, "third pair"),
        (1, "amazon", "Sennheiser Momentum 4", 34900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 30, "fourth pair"),
        (1, "amazon", "Keychron Q1 keyboard", 17900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 25, "keyboard weakness"),
        (1, "amazon", "Ducky One 3 keyboard", 12900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 22, "another keyboard"),
        (1, "amazon", "MacBook USB-C charger", 7900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "approved", 85, "replacement"),
        (1, "amazon", "Nike running shoes", 12000, "USD", "https://amazon.com/", "https://placehold.co/200", "clothing", "approved", 75, "fitness need"),
        (1, "bestbuy", "Standing desk 60in", 59900, "USD", "https://bestbuy.com/", "https://placehold.co/200", "furniture", "denied", 38, "impulse furniture"),
        (1, "amazon", "Monitor arm", 8900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "approved", 90, "work ergonomics"),
        (1, "amazon", "RGB gaming mousepad", 3900, "USD", "https://amazon.com/", "https://placehold.co/200", "electronics", "denied", 15, "impulse rgb"),
        (1, "amazon", "LED desk lamp", 4500, "USD", "https://amazon.com/", "https://placehold.co/200", "home", "denied", 20, "impulse home"),
    ]
    
    conn.executemany("""
        INSERT OR REPLACE INTO purchases (id, user_id, site, product_title, price_cents, currency, url, image_url, category, verdict, score, final_justification)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, purchases)
    
    conn.commit()
    
    denied_count = sum(1 for p in purchases if p[9] == "denied")
    saved_cents = sum(p[4] for p in purchases if p[9] == "denied")
    approved_count = sum(1 for p in purchases if p[9] == "approved")
    
    print(f"[seed] {len(purchases)} purchases seeded")
    print(f"[seed]   denied: {denied_count}, approved: {approved_count}")
    print(f"[seed]   saved: ${saved_cents / 100:.2f}")

if __name__ == "__main__":
    seed()
