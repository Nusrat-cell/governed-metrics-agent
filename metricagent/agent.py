"""Question in, answer out. Every step is logged, and every answer says how it was worked out."""
import json
import os
import threading
import time
from dataclasses import dataclass, field

from . import access
from .query import Rejected, compile_sql, validate


@dataclass
class Answer:
    status: str                  # answered, clarify, refused, empty, error
    text: str
    rows: list = field(default_factory=list)
    sql: str = ""
    spec: object = None
    caveats: list = field(default_factory=list)
    options: tuple = ()
    ms: float = 0.0
    detail: str = ""            # the real cause of an error, for the log only


def fmt(value, kind):
    if value is None:
        return "n/a"
    if kind == "dkk":
        return f"{value:,.0f} DKK"
    if kind == "pct":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


class Agent:
    def __init__(self, db, layer, planner, log_path=None):
        self.db, self.layer, self.planner, self.log_path = db, layer, planner, log_path
        self.lock = threading.RLock()              # one connection is shared by every web session

    def ask(self, question, user):
        t0 = time.perf_counter()
        with self.lock:                               # the planner, access check and queries all share one connection
            ans = self._ask(question, user)
        ans.ms = round((time.perf_counter() - t0) * 1000, 1)
        self._log(question, user, ans)
        return ans

    def _ask(self, question, user):
        if not question or not question.strip() or len(question) > 500:
            return Answer("refused", "Ask one question of up to 500 characters.")
        plan = self.planner.plan(question)
        if plan.kind == "refuse":
            return Answer("refused", plan.message)
        if plan.kind == "clarify":
            return Answer("clarify", plan.message, options=plan.options)
        try:
            spec = access.apply(plan.spec, user, self.db)
            validate(spec, self.layer)
            sql, params = compile_sql(spec, self.layer)
        except Rejected as e:
            return Answer("refused", str(e), spec=plan.spec)
        try:
            with self.lock:
                rows = self.db.execute(sql, params).fetchall()
        except Exception as e:                                   # a bug of ours, never shown raw to the user
            return Answer("error", "I could not run that query. It has been logged.", sql=sql, spec=spec, detail=f"{type(e).__name__}: {e}")
        caveats = self._caveats(spec, rows)
        m = self.layer.metrics[spec.metric]
        if not rows or (len(spec.group_by) == 0 and rows[0][-1] is None):
            return Answer("empty", f"No {spec.metric.replace('_', ' ')} data for that selection.", sql=sql, spec=spec, caveats=caveats)
        return Answer("answered", self._say(spec, rows, m), rows, sql, spec, caveats)

    def _say(self, spec, rows, m):
        name = spec.metric.replace("_", " ")
        period = f" from {spec.start} to {spec.end}" if spec.start and spec.end else (f" from {spec.start}" if spec.start else (f" up to {spec.end}" if spec.end else ""))
        scope = "".join(f" in {', '.join(v)}" for v in spec.filters.values())
        if not spec.group_by:
            return f"{name.capitalize()}{scope}{period}: {fmt(rows[0][-1], m['format'])}. ({m['text']}.)"
        lines = [f"{name.capitalize()} by {' and '.join(spec.group_by)}{scope}{period}. ({m['text']}.)"]
        for r in rows:
            lines.append("  " + " / ".join(str(x) for x in r[:-1]) + ": " + fmt(r[-1], m["format"]))
        return "\n".join(lines)

    def _caveats(self, spec, rows):
        out, db = [], self.db
        last = db.execute("SELECT MAX(date) FROM fact_sales").fetchone()[0]
        if spec.end and spec.end > last:
            out.append(f"Data ends on {last}, so the period is incomplete.")
        if spec.metric in ("revenue", "margin", "margin_pct", "aov", "target_attainment"):
            where, p = "", []
            if spec.start: where += " AND f.date >= ?"; p.append(spec.start)
            if spec.end: where += " AND f.date <= ?"; p.append(spec.end)
            if spec.store_ids is not None:
                where += f" AND f.store_id IN ({','.join('?' * len(spec.store_ids))})"; p += spec.store_ids
            with self.lock:
                tot, carried = db.execute("SELECT SUM(f.net_amount_dkk), SUM(CASE WHEN f.fx_carried=1 THEN f.net_amount_dkk ELSE 0 END) "
                                          "FROM fact_sales f WHERE 1=1" + where, p).fetchone()
            if tot and carried / tot > 0.05:
                out.append(f"{100 * carried / tot:.0f}% of this revenue was converted with the last published exchange rate, because weekends have none.")
        if spec.metric in ("revenue", "units", "margin", "orders") and spec.store_ids is None:
            q = db.execute("SELECT SUM(n) FROM quarantine").fetchone()[0]
            out.append(f"{q:,} source lines are in quarantine and not counted.")
        if spec.group_by and spec.limit >= 20 and len(rows) == spec.limit:
            out.append(f"Showing the first {spec.limit} rows. Ask for a higher limit to see more.")
        return out

    def _log(self, question, user, ans):
        if not self.log_path:
            return
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "user": user.name, "role": user.role, "question": question[:500],
               "status": ans.status, "metric": getattr(ans.spec, "metric", None), "ms": ans.ms, "rows": len(ans.rows),
               "reason": ans.text if ans.status in ("refused", "error", "clarify") else "", "detail": ans.detail}
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
