"""Project artifact storage helpers.

Each production lives under ``projects/<story_id>/`` with self-describing JSON
artifacts. These helpers centralise read/write so paths stay consistent and
every write is atomic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


class ProjectStore:
    def __init__(self, story_id: str, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.story_id = story_id
        self.root: Path = self.settings.project_dir(story_id)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "assets").mkdir(exist_ok=True)
        (self.root / "scenes").mkdir(exist_ok=True)
        (self.root / "audio").mkdir(exist_ok=True)

    def path(self, name: str) -> Path:
        return self.root / name

    def write_json(self, name: str, data: Any) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        if hasattr(data, "model_dump"):
            payload = data.model_dump()
        else:
            payload = data
        tmp.write_text(json.dumps(payload, indent=2, default=_default))
        tmp.replace(p)
        return p

    def read_json(self, name: str) -> Any:
        p = self.root / name
        if not p.exists():
            return None
        return json.loads(p.read_text())

    def exists(self, name: str) -> bool:
        return (self.root / name).exists()

    def write_text(self, name: str, text: str) -> Path:
        p = self.root / name
        p.write_text(text)
        return p


def _default(o: Any) -> Any:
    if hasattr(o, "model_dump"):
        return o.model_dump()
    if hasattr(o, "value"):  # Enum
        return o.value
    return str(o)
