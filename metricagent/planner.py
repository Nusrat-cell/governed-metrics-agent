"""Turn a question into a QuerySpec, or into a question back, or into a refusal.

RulePlanner works offline. LLMPlanner asks a model for JSON, checks every field, and falls back
to the rules when the reply is unusable. Whatever plans, the spec still goes through validation.
"""
import calendar
import json
import re
from dataclasses import dataclass
from datetime import date

from .query import QuerySpec

TODAY = date(2026, 11, 10)
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


@dataclass
class Plan:
    kind: str                    # spec, clarify or refuse
    spec: QuerySpec | None = None
    message: str = ""
    options: tuple = ()


def month_range(y, m):
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]}"


def parse_time(q, today=TODAY):
    q = q.lower()
    iso = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", q)
    if len(iso) == 2:
        return min(iso), max(iso)
    if len(iso) == 1:
        return iso[0], iso[0]
    if re.search(r"\blast month\b", q):
        y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        return month_range(y, m)
    if re.search(r"\bthis month\b", q):
        return month_range(today.year, today.month)
    if re.search(r"\blast year\b", q):
        return f"{today.year - 1}-01-01", f"{today.year - 1}-12-31"
    if re.search(r"\b(this year|ytd|year to date)\b", q):
        return f"{today.year}-01-01", f"{today.year}-{today.month:02d}-{calendar.monthrange(today.year, today.month)[1]}"
    m = re.search(r"\b(first|second) half(?: of)?\s*(20\d\d)\b|\bh([12])\s*(20\d\d)\b", q)
    if m:
        y = int(m.group(2) or m.group(4)); h = 1 if (m.group(1) == "first" or m.group(3) == "1") else 2
        return month_range(y, 1 if h == 1 else 7)[0], month_range(y, 6 if h == 1 else 12)[1]
    names = "|".join(sorted(MONTHS, key=len, reverse=True))
    m = re.search(r"\b(" + names + r")\s+(?:and|to|through|-)\s+(" + names + r")\s+(20\d\d)\b", q)
    if m:
        a, b, y = MONTHS[m.group(1)], MONTHS[m.group(2)], int(m.group(3))
        if b >= a:
            return month_range(y, a)[0], month_range(y, b)[1]
    m = re.search(r"\bq([1-4])\s*(?:of\s*)?(20\d\d)\b", q)
    if m:
        qn, y = int(m.group(1)), int(m.group(2))
        a, b = (qn - 1) * 3 + 1, qn * 3
        return month_range(y, a)[0], month_range(y, b)[1]
    m = re.search(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\s+(20\d\d)\b", q)
    if m:
        return month_range(int(m.group(2)), MONTHS[m.group(1)])
    m = re.search(r"\b(?:in|for|during|,)?\s*(20\d\d)\b", q)
    if m:
        return f"{m.group(1)}-01-01", f"{m.group(1)}-12-31"
    return None, None


class RulePlanner:
    def __init__(self, layer, db, today=TODAY):
        self.layer, self.db, self.today = layer, db, today
        self.values = {}
        for dim, col, table in (("store", "name", "dim_store"), ("city", "city", "dim_store"), ("country", "country", "dim_store"),
                                ("region", "region", "dim_store"), ("category", "category", "dim_product"), ("brand", "brand", "dim_product")):
            self.values[dim] = [r[0] for r in db.execute(f"SELECT DISTINCT {col} FROM {table}")]
        self.values["channel"] = ["web", "store channel", "in-store", "instore"]

    def plan(self, question):
        q = question.strip()
        low = q.lower()
        if re.search(r"\b(delete|drop|update|insert|alter)\b", low) or re.search(r"\bselect\b.*\bfrom\b", low):
            return Plan("refuse", message="I only answer questions about defined metrics. I cannot run or change SQL.")
        if re.search(r"\b(ignore|forget|disregard)\b.{0,30}\b(rules|instructions|previous|above)\b", low):
            return Plan("refuse", message="I cannot change how I work. Ask a question about a defined metric.")
        if re.search(r"\b(forecast|predict|projection|next (year|month|quarter)|will (be|we))\b", low):
            return Plan("refuse", message="I report what has happened. I do not forecast.")
        bad = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekly|daily|hourly|per week|per day|summer|winter|spring|autumn|weekend|holiday|christmas|yesterday|today|last quarter|this quarter|last week|this week|next)s?\b", low)
        if bad:
            return Plan("refuse", message=f"I cannot filter or group by '{bad.group(1)}'. I can break results down by weekday, month, quarter or year.")
        if re.search(r"[^\x00-\x7f]", low.replace("ø", "").replace("æ", "").replace("å", "")) or re.search(r"\b(quelle|combien|wie viel|cuanto)\b", low):
            return Plan("refuse", message="I only understand English questions.")
        low = re.sub(r"top selling|best selling|best seller", "top units", low)
        low = re.sub(r"\bshops?\b", "stores", low)
        metric = self.layer.find_metric(low)
        if metric is None:
            amb = self.layer.find_ambiguous(low)
            if amb:
                word, opts = amb
                return Plan("clarify", message=f"'{word}' can mean more than one thing here. Which do you mean?", options=tuple(opts))
            return Plan("refuse", message="That is not a metric I have a definition for. Try revenue, units, margin, margin %, orders, average order value or target attainment.")
        group_by = []
        mm = re.search(r"\b(?:by|per|for each|across|split by|broken down by)\s+(.+?)(?:\s+(?:in|for|during|last|this|q[1-4])\b|$|\?)", low)
        if mm:
            for word in re.split(r",|\band\b", mm.group(1)):
                word = word.strip().rstrip("s") if word.strip() not in ("sales", "business") else word.strip()
                dim = {"stor": "store", "shop": "store", "citie": "city", "countrie": "country", "categorie": "category", "month": "month",
                       "quarter": "quarter", "year": "year", "region": "region", "brand": "brand", "product": "product", "product category": "category", "channel": "channel",
                       "city": "city", "store": "store", "country": "country", "category": "category", "weekday": "weekday", "day of week": "weekday"}.get(word)
                if dim and dim not in group_by:
                    group_by.append(dim)
        wh = re.search(r"\b(?:which|what)\s+(?:of\s+(?:our|the)\s+)?(store|stores|city|cities|country|countries|category|categories|brand|brands|product|products|region|regions|channel)\b", low)
        if wh and not group_by:
            group_by.append({"stores": "store", "cities": "city", "countries": "country", "categories": "category", "brands": "brand", "products": "product", "regions": "region"}.get(wh.group(1), wh.group(1)))
            if re.search(r"\b(most|highest|best|top|biggest|largest)\b", low): limit_hint = 5
        top = re.search(r"\b(top|best|highest|bottom|worst|lowest)\s*(\d+)?\b", low)
        order, limit = "desc", 20
        if top:
            order = "asc" if top.group(1) in ("bottom", "worst", "lowest") else "desc"
            limit = int(top.group(2)) if top.group(2) else 5
            if not group_by:
                for dim, pat in (("store", "stores?"), ("product", "products?"), ("category", "categor(?:y|ies)"), ("city", "cit(?:y|ies)"), ("brand", "brands?")):
                    if re.search(rf"\b{pat}\b", low):
                        group_by.append(dim); break
        filters = {}
        for dim, vals in self.values.items():
            hit = [v for v in vals if re.search(rf"\b{re.escape(v.lower())}\b", low)]
            if hit:
                filters[dim] = hit
        if re.search(r"\b(compare|versus|vs\.?)\b", low) and not group_by:
            for dim, hit in filters.items():
                if len(hit) > 1 or dim == "channel":
                    group_by.append(dim); filters.pop(dim); break
        if "channel" in filters:
            filters["channel"] = ["store" if v != "web" else "web" for v in filters["channel"]]
        start, end = parse_time(low, self.today)
        spec = QuerySpec(metric, group_by, filters, start, end, order, limit)
        return Plan("spec", spec)


class LLMPlanner:
    SYSTEM = ("You turn a business question into a JSON query spec. Reply with one line of JSON only: "
              '{"metric": "...", "group_by": [...], "filters": {"dimension": ["value"]}, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", '
              '"order": "asc|desc", "limit": 20} or {"clarify": "question"} or {"refuse": "reason"}. '
              "Use only the metrics and dimensions you are given. Never write SQL.")

    def __init__(self, llm, layer, db, fallback=None):
        self.llm, self.layer = llm, layer
        self.fallback = fallback or RulePlanner(layer, db)
        self.bad_replies = 0

    def _prompt(self, question):
        return (f"Metrics: {', '.join(self.layer.metrics)}\nDimensions: {', '.join(self.layer.dimensions)}\n"
                f"Question: {question}")

    def plan(self, question):
        try:
            msg = json.loads(self.llm(self.SYSTEM, self._prompt(question)))
        except Exception:
            msg = None
        if not isinstance(msg, dict):
            self.bad_replies += 1
            return self.fallback.plan(question)
        if "refuse" in msg:
            return Plan("refuse", message=str(msg["refuse"])[:200])
        if "clarify" in msg:
            return Plan("clarify", message=str(msg["clarify"])[:200])
        allowed = {"metric", "group_by", "filters", "start", "end", "order", "limit"}
        if set(msg) - allowed or not isinstance(msg.get("metric"), str) or msg["metric"] not in self.layer.metrics:
            self.bad_replies += 1                    # an unknown key such as "sql" is a reason not to trust the reply at all
            return self.fallback.plan(question)
        try:
            spec = QuerySpec(msg["metric"], list(msg.get("group_by", [])), dict(msg.get("filters", {})), msg.get("start"),
                             msg.get("end"), msg.get("order", "desc"), int(msg.get("limit", 20)))
        except (TypeError, ValueError):
            self.bad_replies += 1
            return self.fallback.plan(question)
        return Plan("spec", spec)
