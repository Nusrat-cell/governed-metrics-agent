"""Summarise logs/asks.jsonl: what people ask, what gets refused, how long it takes."""
import collections, json, sys

path = sys.argv[1] if len(sys.argv) > 1 else "logs/asks.jsonl"
recs = [json.loads(l) for l in open(path, encoding="utf-8")]
st = collections.Counter(r["status"] for r in recs)
ms = sorted(r["ms"] for r in recs)
print(f"{len(recs)} questions. " + ", ".join(f"{k} {v}" for k, v in st.most_common()))
print(f"time: median {ms[len(ms) // 2]} ms, slowest {ms[-1]} ms")
print("metrics asked about:", ", ".join(f"{k} {v}" for k, v in collections.Counter(r["metric"] for r in recs if r["metric"]).most_common()))
why = collections.Counter(r["reason"] for r in recs if r["status"] in ("refused", "clarify"))
if why:
    print("most common reasons for not answering:")
    for k, v in why.most_common(5):
        print(f"  {v}x {k[:90]}")
