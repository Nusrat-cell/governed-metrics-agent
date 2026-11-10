"""Written after the planner was finished, in the way a colleague would actually phrase things.
Not used for tuning. The score on these is the honest one."""
R = "revenue"
CASES = [
 ("heldout", "How much did we take in over the summer of 2026?", dict(status="refused")),                # summer is not defined, so a guess would be wrong
 ("heldout", "Which of our shops sold the most headphones last month?", dict(status="answered", metric="units", group_by=["store"], filters={"category": ["Headphones"]}, start="2026-10-01", end="2026-10-31")),
 ("heldout", "compare web and store revenue for 2026", dict(status="answered", metric=R, group_by=["channel"], start="2026-01-01", end="2026-12-31")),
 ("heldout", "Revenue, split by country, Q2 2026", dict(status="answered", metric=R, group_by=["country"], start="2026-04-01", end="2026-06-30")),
 ("heldout", "what's the AOV in Sweden", dict(status="answered", metric="aov", filters={"country": ["Sweden"]})),
 ("heldout", "are we hitting target in Norway this year", dict(status="answered", metric="target_attainment", filters={"country": ["Norway"]}, start="2026-01-01", end="2026-11-30")),
 ("heldout", "margin % per category, 2025", dict(status="answered", metric="margin_pct", group_by=["category"], start="2025-01-01", end="2025-12-31")),
 ("heldout", "how many baskets did Oslo do in November 2025", dict(status="answered", metric="orders", filters={"city": ["Oslo"], "store": ["Oslo"]}, start="2025-11-01", end="2025-11-30")),
 ("heldout", "which brand makes us the most profit", dict(status="answered", metric="margin", group_by=["brand"])),
 ("heldout", "revenue on Saturdays", dict(status="refused")),                        # no weekday filter exists, it should say so and not ignore it
 ("heldout", "give me the revenue figure for the first half of 2026", dict(status="answered", metric=R, start="2026-01-01", end="2026-06-30")),
 ("heldout", "sales vs last year", dict(status="clarify")),
 ("heldout", "revenue Copenhagen Central Q4 2025", dict(status="answered", metric=R, filters={"store": ["Copenhagen Central"], "city": ["Copenhagen"]}, start="2025-10-01", end="2025-12-31")),
 ("heldout", "tell me about the Halden speakers", dict(status="refused")),
 ("heldout", "Quelle est la marge en 2025 ?", dict(status="refused")),                # French: not supported, should not guess
 ("heldout", "revenue by store for April and May 2026", dict(status="answered", metric=R, group_by=["store"], start="2026-04-01", end="2026-05-31")),
 ("heldout", "weekly revenue", dict(status="refused")),                               # no week grain
 ("heldout", "units sold per product category in Denmark during 2026", dict(status="answered", metric="units", group_by=["category"], filters={"country": ["Denmark"]}, start="2026-01-01", end="2026-12-31")),
 ("heldout", "top selling product", dict(status="answered", metric="units", group_by=["product"])),
 ("heldout", "how are the Aarhus stores doing against plan", dict(status="answered", metric="target_attainment", filters={"city": ["Aarhus"]})),
]
