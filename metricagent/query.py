"""A QuerySpec is the only thing the agent can run. SQL is built from the layer, never from text."""
from dataclasses import dataclass, field
import calendar
import re

MAX_ROWS = 200


class Rejected(Exception):
    """The spec asked for something the layer does not allow. The message is safe to show."""


@dataclass
class QuerySpec:
    metric: str
    group_by: list = field(default_factory=list)
    filters: dict = field(default_factory=dict)      # dimension -> list of allowed values
    start: str | None = None                          # YYYY-MM-DD inclusive
    end: str | None = None
    order: str = "desc"
    limit: int = 20
    store_ids: list | None = None                     # set by access control, never by the planner


def _month_edge(day, last):
    y, m, dd = map(int, day.split("-"))
    return dd == (calendar.monthrange(y, m)[1] if last else 1)


def validate(spec, layer):
    if spec.metric not in layer.metrics:
        raise Rejected(f"'{spec.metric}' is not a defined metric")
    for d in list(spec.group_by) + list(spec.filters):
        if d not in layer.dimensions:
            raise Rejected(f"'{d}' is not a dimension I can group or filter by")
    if len(spec.group_by) > 2:
        raise Rejected("at most two breakdowns at once")
    for d in (spec.start, spec.end):
        if d is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            raise Rejected("dates must look like 2026-03-31")
    if spec.start and spec.end and spec.start > spec.end:
        raise Rejected("the start date is after the end date")
    if spec.order not in ("asc", "desc"):
        raise Rejected("order must be asc or desc")
    if not 1 <= spec.limit <= MAX_ROWS:
        raise Rejected(f"limit must be between 1 and {MAX_ROWS}")
    m = layer.metrics[spec.metric]
    if m.get("special") == "target":
        ok = ("store", "city", "country", "region", "month", "quarter", "year")
        bad = [d for d in spec.group_by if d not in ok] + [d for d in spec.filters if d not in ok + ("channel",)]
        if bad:
            raise Rejected(f"targets exist per store and month, so '{bad[0]}' cannot be used with target attainment")
        for d, last in ((spec.start, False), (spec.end, True)):
            if d and not _month_edge(d, last):
                raise Rejected("targets are set per whole month, so the period must start on the 1st and end on a month's last day")
        if "channel" in spec.group_by:
            raise Rejected("targets exist per store and month, so 'channel' cannot be used with target attainment")


def compile_sql(spec, layer):
    """Return (sql, params). Identifiers come from the layer, values are always bound parameters."""
    validate(spec, layer)
    m = layer.metrics[spec.metric]
    dims = [layer.dimensions[d] for d in spec.group_by]
    joins = {"dim_store": "JOIN dim_store s ON s.store_id = f.store_id",
             "dim_product": "JOIN dim_product p ON p.sku = f.sku",
             "dim_date": "JOIN dim_date d ON d.date = f.date"}
    need = {x["join"] for x in dims if "join" in x} | {layer.dimensions[d]["join"] for d in spec.filters if "join" in layer.dimensions[d]}
    if spec.start or spec.end:
        pass
    where, params = [], []
    if spec.start:
        where.append("f.date >= ?"); params.append(spec.start)
    if spec.end:
        where.append("f.date <= ?"); params.append(spec.end)
    for d, values in spec.filters.items():
        where.append(f"{layer.dimensions[d]['sql']} IN ({','.join('?' * len(values))})"); params += list(values)
    if spec.store_ids is not None:
        where.append(f"f.store_id IN ({','.join('?' * len(spec.store_ids))})"); params += list(spec.store_ids)
    if m.get("special") == "target":
        return _target_sql(spec, layer, dims, where, params)
    sel = ", ".join(f"{x['sql']} AS {n}" for x, n in zip(dims, spec.group_by))
    sql = f"SELECT {sel + ', ' if sel else ''}{m['sql']} AS value FROM fact_sales f " + " ".join(joins[j] for j in sorted(need))
    sql += (" WHERE " + " AND ".join(where)) if where else ""
    if dims:
        sql += " GROUP BY " + ", ".join(spec.group_by)
        sql += f" ORDER BY {'value' if 'month' not in spec.group_by and 'quarter' not in spec.group_by and 'year' not in spec.group_by else spec.group_by[0]} {spec.order.upper()}"
        sql += f" LIMIT {int(spec.limit)}"
    return sql, params


def _target_sql(spec, layer, dims, where, params):
    """Actual and target are summed at store and month first, then rolled up, so a target is never counted twice."""
    sel = ", ".join(f"{x['sql']} AS {n}" for x, n in zip(dims, spec.group_by))
    inner = ("SELECT f.store_id, d.month_label, SUM(f.net_amount_dkk) AS actual FROM fact_sales f "
             "JOIN dim_store s ON s.store_id = f.store_id JOIN dim_date d ON d.date = f.date"
             + ((" WHERE " + " AND ".join(where)) if where else "") + " GROUP BY f.store_id, d.month_label")
    sql = (f"SELECT {sel + ', ' if sel else ''}100.0 * SUM(a.actual) / NULLIF(SUM(t.target_dkk), 0) AS value "
           f"FROM ({inner}) a JOIN fact_target t ON t.store_id = a.store_id AND t.month_label = a.month_label "
           "JOIN dim_store s ON s.store_id = a.store_id "
           "JOIN (SELECT DISTINCT month_label, quarter_label, year FROM dim_date) d ON d.month_label = a.month_label")
    if dims:
        sql += " GROUP BY " + ", ".join(spec.group_by) + f" ORDER BY value {spec.order.upper()} LIMIT {int(spec.limit)}"
    return sql, params
