"""Small shared constants and file utilities for the live Assist runtime."""
from __future__ import annotations

import hashlib
from pathlib import Path

KEYS = ("S", "D", "F", "J", "K", "L")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
