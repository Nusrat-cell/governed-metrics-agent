import sys
from metricagent.access import User
from metricagent.agent import Agent
from metricagent.data import build
from metricagent.planner import RulePlanner
from metricagent.semantic import Layer

db, layer = build(), Layer()
agent = Agent(db, layer, RulePlanner(layer, db), log_path="logs/asks.jsonl")
user = User("demo", "admin")
if len(sys.argv) > 1 and sys.argv[1] == "--store":
    user = User("manager", "store_manager", (sys.argv[2],)); sys.argv = sys.argv[:1] + sys.argv[3:]
for q in sys.argv[1:] or [input("Question: ")]:
    a = agent.ask(q, user)
    print(a.text)
    for c in a.caveats: print("  note:", c)
    if a.options: print("  options:", ", ".join(a.options))
