import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import CASES as OWN
from heldout import CASES as HELD
from fresh import CASES as FRESH
CASES = OWN + HELD + FRESH
from metricagent.access import User
from metricagent.agent import Agent
from metricagent.data import build
from metricagent.planner import RulePlanner
from metricagent.semantic import Layer

db, layer = build(), Layer()
agent = Agent(db, layer, RulePlanner(layer, db))
users = {None: User("admin", "admin"), "odense": User("odense", "store_manager", ("S06",))}


def check(a, exp):
    why = []
    if a.status != exp["status"]:
        return [f"status {a.status}, wanted {exp['status']}"]
    if exp["status"] != "answered":
        return why
    s = a.spec
    if "metric" in exp and s.metric != exp["metric"]: why.append(f"metric {s.metric}")
    if "group_by" in exp and sorted(s.group_by) != sorted(exp["group_by"]): why.append(f"group_by {s.group_by}")
    if "start" in exp and s.start != exp["start"]: why.append(f"start {s.start}")
    if "end" in exp and s.end != exp["end"]: why.append(f"end {s.end}")
    if "filters" in exp and {k: sorted(v) for k, v in s.filters.items()} != {k: sorted(v) for k, v in exp["filters"].items()}:
        why.append(f"filters {s.filters}")
    return why


by, fails = collections.defaultdict(lambda: [0, 0]), []
for cat, q, exp in CASES:
    exp = dict(exp); who = exp.pop("as_", None)
    a = agent.ask(q, users[who])
    why = check(a, exp)
    by[cat][1] += 1
    if not why: by[cat][0] += 1
    else: fails.append((cat, q[:70], "; ".join(why)))
tot = sum(v[1] for v in by.values()); ok = sum(v[0] for v in by.values())
lines = [f"{ok} of {tot} questions handled as expected ({100 * ok // tot}%)", ""]
lines += [f"  {c:<10} {a}/{b}" for c, (a, b) in by.items()]
if fails:
    lines += ["", "Misses:"] + [f"  [{c}] {q!r}: {w}" for c, q, w in fails]
out = "\n".join(lines)
print(out)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.txt"), "w").write(out + "\n")
