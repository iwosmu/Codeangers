import hashlib
import json
from typing import Any

# OWNER E. In-memory, dies with the process, and that is fine for 24 hours.
# It exists so a rate limit during the demo cannot change what the judges see.

_store: dict[str, Any] = {}


def key(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:32]


def get(k: str) -> Any | None:
    return _store.get(k)


def put(k: str, value: Any) -> Any:
    _store[k] = value
    return value


def clear() -> None:
    _store.clear()
