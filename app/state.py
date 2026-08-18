"""Production state machine and its JSON-backed store.

Each story moves through a fixed set of states; every transition is timestamped.
The store is a single JSON file (``data/state.json``) — simple, inspectable and
good enough for one channel. Swap for SQLite by re-implementing ``StateStore``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from threading import Lock

from app.config import Settings, get_settings


class ProductionState(str, Enum):
    CANDIDATE = "candidate"
    RESEARCHING = "researching"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SELECTED = "selected"
    SCRIPTED = "scripted"
    ASSETS = "assets"
    RENDERING = "rendering"
    QC_FAILED = "qc_failed"
    READY = "ready"
    UPLOADED = "uploaded"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


#: Legal forward transitions. Rejection and QC failure can happen from most
#: working states; those are allowed explicitly below.
_ALLOWED: dict[ProductionState, set[ProductionState]] = {
    ProductionState.CANDIDATE: {ProductionState.RESEARCHING, ProductionState.REJECTED},
    ProductionState.RESEARCHING: {ProductionState.VERIFIED, ProductionState.REJECTED},
    ProductionState.VERIFIED: {ProductionState.SELECTED, ProductionState.REJECTED},
    ProductionState.SELECTED: {ProductionState.SCRIPTED, ProductionState.REJECTED},
    ProductionState.SCRIPTED: {ProductionState.ASSETS, ProductionState.QC_FAILED},
    ProductionState.ASSETS: {ProductionState.RENDERING, ProductionState.QC_FAILED},
    ProductionState.RENDERING: {ProductionState.READY, ProductionState.QC_FAILED},
    ProductionState.READY: {ProductionState.UPLOADED, ProductionState.QC_FAILED},
    ProductionState.QC_FAILED: {ProductionState.SCRIPTED, ProductionState.REJECTED, ProductionState.ASSETS},
    ProductionState.UPLOADED: {ProductionState.SCHEDULED, ProductionState.PUBLISHED},
    ProductionState.SCHEDULED: {ProductionState.PUBLISHED},
    ProductionState.PUBLISHED: set(),
    ProductionState.REJECTED: set(),
}


class InvalidTransition(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.path = self.settings.data_dir / "state.json"
        self._lock = Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"stories": {}}
        return json.loads(self.path.read_text())

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    def get(self, story_id: str) -> dict | None:
        return self._load()["stories"].get(story_id)

    def all(self) -> dict[str, dict]:
        return self._load()["stories"]

    def current_state(self, story_id: str) -> ProductionState | None:
        rec = self.get(story_id)
        if not rec:
            return None
        return ProductionState(rec["state"])

    def create(self, story_id: str, *, meta: dict | None = None) -> dict:
        with self._lock:
            data = self._load()
            if story_id in data["stories"]:
                return data["stories"][story_id]
            rec = {
                "story_id": story_id,
                "state": ProductionState.CANDIDATE.value,
                "meta": meta or {},
                "history": [{"state": ProductionState.CANDIDATE.value, "at": _now()}],
            }
            data["stories"][story_id] = rec
            self._save(data)
            return rec

    def transition(self, story_id: str, to: ProductionState, *, note: str = "") -> dict:
        with self._lock:
            data = self._load()
            rec = data["stories"].get(story_id)
            if rec is None:
                rec = {
                    "story_id": story_id,
                    "state": ProductionState.CANDIDATE.value,
                    "meta": {},
                    "history": [{"state": ProductionState.CANDIDATE.value, "at": _now()}],
                }
                data["stories"][story_id] = rec
            frm = ProductionState(rec["state"])
            if to != frm and to not in _ALLOWED.get(frm, set()):
                raise InvalidTransition(f"{story_id}: {frm.value} -> {to.value} not allowed")
            rec["state"] = to.value
            rec["history"].append({"state": to.value, "at": _now(), "note": note})
            self._save(data)
            return rec

    def set_meta(self, story_id: str, **kwargs) -> None:
        with self._lock:
            data = self._load()
            rec = data["stories"].setdefault(
                story_id,
                {"story_id": story_id, "state": ProductionState.CANDIDATE.value, "meta": {}, "history": []},
            )
            rec["meta"].update(kwargs)
            self._save(data)

    def in_state(self, state: ProductionState) -> list[str]:
        return [sid for sid, rec in self.all().items() if rec["state"] == state.value]
