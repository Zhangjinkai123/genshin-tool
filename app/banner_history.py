from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .banner_aliases import ITEM_ALIASES
from .config import DATA_DIR


BANNER_HISTORY_PATH = DATA_DIR / "banners" / "history.json"
_NORMALIZE_PATTERN = re.compile(r"[\s_'\-:：·・.。,’，`]+")


@lru_cache(maxsize=1)
def load_banner_history() -> list[dict]:
    if not BANNER_HISTORY_PATH.exists():
        return []
    payload = json.loads(BANNER_HISTORY_PATH.read_text(encoding="utf-8"))
    banners = payload.get("banners") if isinstance(payload, dict) else payload
    return banners if isinstance(banners, list) else []


def infer_from_banner_history(row: dict) -> str:
    if row.get("rank") != 5:
        return "unknown"
    pool = _pool_kind(row)
    if not pool:
        return "unknown"

    matched = _matching_banners(row, pool)
    if not matched:
        return "unknown"

    item_name = str(row.get("itemName") or "")
    featured_keys = [key for banner in matched for key in banner.get("featuredKeys", [])]
    if any(item_matches_key(item_name, key) for key in featured_keys):
        if _is_ambiguous_dual_character_match(row, pool, matched):
            return "unknown"
        return "win"
    return "lose"


def item_matches_key(item_name: str, key: str) -> bool:
    item = normalize_name(item_name)
    if not item:
        return False
    aliases = {key, key.replace("_", " "), key.replace("_", "-"), key.replace("-", " ")}
    aliases.update(ITEM_ALIASES.get(key, set()))
    return item in {normalize_name(alias) for alias in aliases}


def normalize_name(value: Any) -> str:
    return _NORMALIZE_PATTERN.sub("", str(value or "").strip().lower())


def _matching_banners(row: dict, pool: str) -> list[dict]:
    time_text = str(row.get("time") or "")[:19]
    gacha_type = str(row.get("gachaType") or "").strip()
    candidates = [
        banner
        for banner in load_banner_history()
        if banner.get("pool") == pool
        and str(banner.get("start") or "") <= time_text <= str(banner.get("end") or "")
    ]
    if gacha_type:
        exact = [banner for banner in candidates if gacha_type in {str(item) for item in banner.get("gachaTypes", [])}]
        if exact:
            return exact
    return candidates


def _is_ambiguous_dual_character_match(row: dict, pool: str, matched: list[dict]) -> bool:
    if pool != "character" or row.get("gachaType"):
        return False
    gacha_types = {str(item) for banner in matched for item in banner.get("gachaTypes", [])}
    return len(matched) > 1 and len(gacha_types) > 1


def _pool_kind(row: dict) -> str:
    gacha_type = str(row.get("gachaType") or "").strip()
    pool = str(row.get("poolType") or "")
    if gacha_type == "302" or "武器" in pool:
        return "weapon"
    if gacha_type in {"301", "400"} or "角色" in pool:
        return "character"
    return ""
