"""Row level access. The user's role is set outside the conversation, so nothing typed in a question can change it."""
from dataclasses import dataclass
from .query import Rejected


@dataclass(frozen=True)
class User:
    name: str
    role: str                    # "admin" sees everything, "store_manager" sees their stores only
    store_ids: tuple = ()


def apply(spec, user, db):
    """Return the spec with the user's stores forced in. Asking for another store is refused, not quietly ignored."""
    if user.role == "admin":
        return spec
    if user.role != "store_manager" or not user.store_ids:
        raise Rejected("this account has no data access")
    if "store" in spec.filters:
        names = {r[0] for r in db.execute(f"SELECT name FROM dim_store WHERE store_id IN ({','.join('?' * len(user.store_ids))})", user.store_ids)}
        outside = [v for v in spec.filters["store"] if v not in names]
        if outside:
            raise Rejected(f"you do not have access to {', '.join(outside)}")
    spec.store_ids = list(user.store_ids)
    return spec
