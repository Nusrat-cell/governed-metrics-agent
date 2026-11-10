"""A third set, written after the planner was fixed against the second one, and never used for tuning.
It exists to show how much of the second set's score was fitting."""
R = "revenue"
CASES = [
 ("fresh", "what did Gothenburg bring in during Q1 2026", dict(status="answered", metric=R, filters={"city": ["Gothenburg"], "store": ["Gothenburg"]}, start="2026-01-01", end="2026-03-31")),
 ("fresh", "average order size by country for 2025", dict(status="answered", metric="aov", group_by=["country"], start="2025-01-01", end="2025-12-31")),
 ("fresh", "number of orders per month in 2026", dict(status="answered", metric="orders", group_by=["month"], start="2026-01-01", end="2026-12-31")),
 ("fresh", "Which category earns us the highest margin in Norway?", dict(status="answered", metric="margin", group_by=["category"], filters={"country": ["Norway"]})),
 ("fresh", "units of Turntables sold in Q4 2025", dict(status="answered", metric="units", filters={"category": ["Turntables"]}, start="2025-10-01", end="2025-12-31")),
 ("fresh", "how did the webshops do against target last quarter", dict(status="refused")),   # 'last quarter' is not supported, it should say so
 ("fresh", "profit by channel", dict(status="answered", metric="margin", group_by=["channel"])),
 ("fresh", "revenue per store in Sweden, October 2026", dict(status="answered", metric=R, group_by=["store"], filters={"country": ["Sweden"]}, start="2026-10-01", end="2026-10-31")),
 ("fresh", "What's our best performing brand by revenue?", dict(status="answered", metric=R, group_by=["brand"])),
 ("fresh", "orders from Bergen between 2026-01-01 and 2026-01-31", dict(status="answered", metric="orders", filters={"city": ["Bergen"], "store": ["Bergen"]}, start="2026-01-01", end="2026-01-31")),
 ("fresh", "give me everything", dict(status="refused")),
 ("fresh", "margin percent for Skagen in 2026", dict(status="answered", metric="margin_pct", filters={"brand": ["Skagen"]}, start="2026-01-01", end="2026-12-31")),
]
