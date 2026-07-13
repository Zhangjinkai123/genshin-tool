from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import ARTIFACT_DIR, CACHE_DIR, WISH_DIR


SAFE_UID = re.compile(r"[^a-zA-Z0-9_\-.]")


def clean_uid(uid: str) -> str:
    uid = SAFE_UID.sub("_", str(uid or "").strip())
    if not uid:
        raise ValueError("请先填写账号标识。")
    return uid[:80]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def wish_path(uid: str) -> Path:
    return WISH_DIR / f"{clean_uid(uid)}.json"


def artifact_path(uid: str) -> Path:
    return ARTIFACT_DIR / f"{clean_uid(uid)}.json"


def cache_path(uid: str, kind: str) -> Path:
    allowed = {"wish-summary", "artifact-summary"}
    if kind not in allowed:
        raise ValueError("未知缓存类型。")
    return CACHE_DIR / f"{clean_uid(uid)}-{kind}.json"


def save_bundle(uid: str, kind: str, records: list[dict], summary: dict) -> None:
    if kind == "wishes":
        write_json(wish_path(uid), records)
        write_json(cache_path(uid, "wish-summary"), summary)
    elif kind == "artifacts":
        write_json(artifact_path(uid), records)
        write_json(cache_path(uid, "artifact-summary"), summary)
    else:
        raise ValueError("未知数据类型。")


def load_bundle(uid: str) -> dict:
    return {
        "wishes": read_json(wish_path(uid), []),
        "wishSummary": read_json(cache_path(uid, "wish-summary"), None),
        "artifacts": read_json(artifact_path(uid), []),
        "artifactSummary": read_json(cache_path(uid, "artifact-summary"), None),
    }


def clear_cache(uid: str | None = None) -> dict:
    targets: list[Path]
    if uid:
        safe = clean_uid(uid)
        targets = [
            WISH_DIR / f"{safe}.json",
            ARTIFACT_DIR / f"{safe}.json",
            CACHE_DIR / f"{safe}-wish-summary.json",
            CACHE_DIR / f"{safe}-artifact-summary.json",
        ]
    else:
        targets = list(WISH_DIR.glob("*.json")) + list(ARTIFACT_DIR.glob("*.json")) + list(CACHE_DIR.glob("*.json"))

    removed = 0
    for path in targets:
        if path.exists():
            path.unlink()
            removed += 1
    return {"removed": removed}
