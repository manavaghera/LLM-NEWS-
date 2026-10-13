"""Coordinate cached AI generation and publish complete JSON files atomically."""
import json
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path


_registry_lock = threading.Lock()
_pending = {}


@contextmanager
def generation_lock(path: Path):
    """Only one thread generates a cache entry; remove idle locks after the last waiter."""
    key = str(path.resolve())
    with _registry_lock:
        lock, users = _pending.get(key, (threading.Lock(), 0))
        _pending[key] = (lock, users + 1)
    try:
        with lock:
            yield
    finally:
        with _registry_lock:
            _, users = _pending[key]
            if users == 1:
                del _pending[key]
            else:
                _pending[key] = (lock, users - 1)


def write_json(path: Path, value) -> None:
    """Leave the previous cache intact if serialization or writing fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        partial.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
