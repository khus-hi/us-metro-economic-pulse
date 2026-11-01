"""Landing raw files.

Every extractor writes exactly what the source returned to
    data/raw/{source}/{run_date}/{name}.{ext}
plus one `_manifest.json` per source and run that records the URL,
parameters (keys redacted), row counts and any series the source said
do not exist. Keeping raw responses untouched means a bad transform can
always be re-run without hitting the APIs again ("replayability").
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import RAW_DIR


def today() -> str:
    return dt.date.today().isoformat()


@dataclass
class Manifest:
    source: str
    run_date: str
    started_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    finished_at: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def dir(self) -> Path:
        return RAW_DIR / self.source / self.run_date

    def write(self, name: str, content: bytes | str | Any, ext: str, *, url: str = "",
              params: dict[str, Any] | None = None, rows: int | None = None) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{name}.{ext}"
        if isinstance(content, bytes):
            path.write_bytes(content)
        elif isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content, indent=1), encoding="utf-8")
        self.files.append({"file": path.name, "url": url, "params": params or {}, "rows": rows})
        return path

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def close(self) -> Path:
        self.finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / "_manifest.json"
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
        return path


def latest_run(source: str) -> Path | None:
    base = RAW_DIR / source
    if not base.exists():
        return None
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    return runs[-1] if runs else None
