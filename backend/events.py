import threading
import time

_lock = threading.Lock()
_events: dict[str, list[dict]] = {}


def emit(job_id: str, phase: str, type_: str, message: str) -> None:
    with _lock:
        _events.setdefault(job_id, []).append(
            {"phase": phase, "type": type_, "message": message, "ts": time.time()}
        )


def since(job_id: str, idx: int) -> list[tuple[int, dict]]:
    with _lock:
        items = _events.get(job_id, [])
        return [(i, items[i]) for i in range(idx, len(items))]


def clear(job_id: str, phase: str) -> None:
    with _lock:
        _events[job_id] = [e for e in _events.get(job_id, []) if e["phase"] != phase]
