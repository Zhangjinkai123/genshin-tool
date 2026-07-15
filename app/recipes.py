from __future__ import annotations

import io
import json
import math
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.request import Request, urlopen

from .config import TRAINING_RECIPES_PATH
from .storage import read_json


PACKAGE_METADATA_URL = "https://registry.npmjs.org/genshin-db/latest"
MAX_METADATA_BYTES = 1 * 1024 * 1024
MAX_TARBALL_BYTES = 64 * 1024 * 1024
TRAVELER_TALENT_KEYS = {
    "anemo": "traveleranemo",
    "geo": "travelergeo",
    "electro": "travelerelectro",
    "dendro": "travelerdendro",
    "hydro": "travelerhydro",
    "pyro": "travelerpyro",
}
# Official AvatarLevelExcelConfigData EXP values for each level-up, level 1->2
# through level 89->90. GOOD does not expose the in-level EXP progress.
LEVEL_EXP_TO_NEXT = (
    1000, 1325, 1700, 2150, 2625, 3150, 3725, 4350, 5000, 5700, 6450, 7225, 8050, 8925, 9825,
    10750, 11725, 12725, 13775, 14875, 16800, 18000, 19250, 20550, 21875, 23250, 24650, 26100, 27575, 29100,
    30650, 32250, 33875, 35550, 37250, 38975, 40750, 42575, 44425, 46300, 50625, 52700, 54775, 56900, 59075,
    61275, 63525, 65800, 68125, 70475, 76500, 79050, 81650, 84275, 86950, 89650, 92400, 95175, 98000, 100875,
    108950, 112050, 115175, 118325, 121525, 124775, 128075, 131400, 134775, 138175, 148700, 152375, 156075,
    159825, 163600, 167425, 171300, 175225, 179175, 183175, 216225, 243025, 273100, 306800, 344600, 386950,
    434425, 487625, 547200,
)
EXP_BOOKS = (("heroswit", 20000), ("adventurersexperience", 5000), ("wanderersadvice", 1000))
TARGET_LEVELS = (20, 40, 50, 60, 70, 80, 90)


def recipe_status() -> dict:
    data = read_json(TRAINING_RECIPES_PATH, {})
    if not isinstance(data, dict) or not data.get("characters"):
        return {"available": False, "message": "尚未下载培养配方。"}
    return {
        "available": True,
        "source": data.get("source", "genshin-db"),
        "version": data.get("version", "未知"),
        "updatedAt": data.get("updatedAt", ""),
        "characterCount": len(data.get("characters", {})),
        "weaponCount": len(data.get("weapons", {})),
    }


def update_recipes() -> dict:
    metadata = _get_json(PACKAGE_METADATA_URL)
    tarball = str(metadata.get("dist", {}).get("tarball") or "")
    if not tarball:
        raise ValueError("配方数据源未返回下载地址。")
    archive = _download(tarball, MAX_TARBALL_BYTES)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        member = bundle.extractfile("package/src/min/data.min.json")
        if member is None:
            raise ValueError("配方数据包格式已变化，找不到主数据文件。")
        raw = json.loads(member.read())
    source = raw.get("data", {}).get("ChineseSimplified", {})
    if not isinstance(source, dict):
        raise ValueError("配方数据包不含简体中文数据。")
    materials = source.get("materials", {})
    material_by_id = {
        str(item.get("id")): {"key": key, "name": item.get("name", key)}
        for key, item in materials.items() if isinstance(item, dict) and item.get("id")
    }
    compact = {
        "source": "genshin-db",
        "version": str(metadata.get("version") or ""),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "characters": _compact_costs(source.get("characters", {})),
        "talents": _compact_costs(source.get("talents", {})),
        "weapons": _compact_costs(source.get("weapons", {})),
        "materials": material_by_id,
    }
    _write_recipes(compact)
    return recipe_status()


def account_from_good(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("请导入完整 GOOD JSON。")
    characters = payload.get("characters")
    if not isinstance(characters, list):
        raise ValueError("GOOD 文件中没有角色列表。")
    weapons = payload.get("weapons") if isinstance(payload.get("weapons"), list) else []
    materials = payload.get("materials") if isinstance(payload.get("materials"), dict) else {}
    recipes = read_json(TRAINING_RECIPES_PATH, {})
    material_names = {
        _norm(item.get("key")): item.get("name")
        for item in recipes.get("materials", {}).values()
        if isinstance(item, dict)
    }
    character_names = {
        key: item.get("name", key)
        for key, item in recipes.get("characters", {}).items()
        if isinstance(item, dict)
    }
    weapon_names = {
        key: item.get("name", key)
        for key, item in recipes.get("weapons", {}).items()
        if isinstance(item, dict)
    }
    weapon_options = []
    for item in weapons:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        key = str(item["key"])
        weapon_options.append({
            "key": key,
            "name": weapon_names.get(_norm(key), key),
            "level": _as_int(item.get("level")),
            "ascension": _as_int(item.get("ascension")),
            "refinement": _as_int(item.get("refinement")),
            "location": str(item.get("location") or ""),
        })
    character_records = []
    for item in characters:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        key = _traveler_key(item["key"])
        character_records.append({
            "key": key,
            "name": character_names.get(_norm(key), key),
            "level": _as_int(item.get("level")),
            "ascension": _as_int(item.get("ascension")),
            "talent": item.get("talent") if isinstance(item.get("talent"), dict) else {},
        })
    if not any(_norm(item["key"]) in {"aether", "lumine"} for item in character_records):
        character_records.append({"key": "Aether", "name": "旅行者", "level": 1, "ascension": 0, "talent": {"auto": 1, "skill": 1, "burst": 1}, "isPlaceholder": True})
    return {
        "characters": character_records,
        "weapons": weapon_options,
        "materialCount": len(materials),
        "materials": [{"key": str(key), "name": material_names.get(_norm(key), str(key)), "quantity": _as_int(value)} for key, value in materials.items()],
        "recipeStatus": recipe_status(),
    }


def calculate(
    payload: Any,
    character_key: str,
    character_target: int,
    talents: dict,
    weapon_key: str,
    weapon_target: int,
    traveler_element: str = "",
) -> dict:
    account = account_from_good(payload)
    recipes = read_json(TRAINING_RECIPES_PATH, {})
    if not isinstance(recipes, dict) or not recipes.get("characters"):
        raise ValueError("请先更新培养配方数据库。")
    if not isinstance(talents, dict):
        raise ValueError("天赋目标必须是对象。")
    character = next((item for item in account["characters"] if item["key"] == character_key), None)
    if not character:
        raise ValueError("未找到选择的角色。")
    inventory = {_norm(item["key"]): item["quantity"] for item in account["materials"]}
    requirements = {"level": {}, "talents": {}, "weapon": {}}
    char_recipe = recipes["characters"].get(_norm(character_key))
    talent_key = _talent_recipe_key(character_key, traveler_element)
    talent_recipe = recipes.get("talents", {}).get(talent_key)
    target_level = TARGET_LEVELS[max(0, min(len(TARGET_LEVELS) - 1, _as_int(character_target)))]
    if target_level > character["level"]:
        _add_level_costs(requirements["level"], recipes, inventory, character["level"], target_level)
    if char_recipe:
        _add_costs(requirements["level"], recipes, char_recipe.get("costs", {}), range(max(1, character["ascension"] + 1), min(6, character_target) + 1), "ascend")
    if talent_recipe:
        for name in ("auto", "skill", "burst"):
            current = max(1, _as_int(character["talent"].get(name)))
            target = min(10, max(current, _as_int(talents.get(name))))
            _add_costs(requirements["talents"], recipes, talent_recipe.get("costs", {}), range(current + 1, target + 1), "lvl")
    weapon = next((item for item in account["weapons"] if item["key"] == weapon_key), None)
    weapon_recipe = recipes.get("weapons", {}).get(_norm(weapon_key)) if weapon else None
    if weapon and weapon_recipe:
        _add_costs(requirements["weapon"], recipes, weapon_recipe.get("costs", {}), range(max(1, weapon["ascension"] + 1), min(6, weapon_target) + 1), "ascend")
    categories = _resolve_requirement_categories(requirements, inventory)
    rows = [row for category in categories for row in category["rows"]]
    unmapped_parts = []
    if not char_recipe:
        unmapped_parts.append("character")
    if not talent_recipe:
        unmapped_parts.append("talents")
    if weapon_key and not weapon_recipe:
        unmapped_parts.append("weapon")
    return {
        "rows": rows,
        "categories": categories,
        "recipeStatus": recipe_status(),
        "unmapped": bool(unmapped_parts),
        "unmappedParts": unmapped_parts,
    }


def _compact_costs(records: Any) -> dict:
    if not isinstance(records, dict):
        return {}
    return {key: {"name": item.get("name", key), "costs": item.get("costs", {})}
            for key, item in records.items() if isinstance(item, dict) and isinstance(item.get("costs"), dict)}


def _add_costs(output: dict, recipes: dict, costs: dict, levels: range, prefix: str) -> None:
    material_by_id = recipes.get("materials", {})
    for level in levels:
        for item in costs.get(f"{prefix}{level}", []):
            if not isinstance(item, dict):
                continue
            material = material_by_id.get(str(item.get("id")), {})
            key = str(material.get("key") or item.get("name") or "")
            if not key:
                continue
            row = output.setdefault(key, {"key": key, "inventoryKey": key, "name": material.get("name") or item.get("name") or key, "required": 0})
            row["required"] += _as_int(item.get("count"))


def _resolve_requirement_categories(requirements: dict[str, dict], inventory: dict[str, int]) -> list[dict]:
    labels = (("level", "角色等级所需"), ("talents", "天赋所需"), ("weapon", "武器所需"))
    remaining = dict(inventory)
    categories = []
    for category_id, label in labels:
        rows = []
        for item in requirements[category_id].values():
            key = _norm(item["inventoryKey"])
            available = remaining.get(key, 0)
            allocated = min(available, item["required"])
            remaining[key] = max(0, available - allocated)
            missing = item["required"] - allocated
            rows.append({**item, "owned": allocated, "missing": missing})
        rows.sort(key=lambda item: (-item["missing"], item["name"]))
        visible_rows = rows if category_id == "level" else [item for item in rows if item["missing"]]
        if visible_rows:
            categories.append({"id": category_id, "name": label, "rows": visible_rows})
    return categories


def _add_level_costs(output: dict, recipes: dict, inventory: dict[str, int], current_level: int, target_level: int) -> None:
    start = max(1, min(90, _as_int(current_level)))
    end = max(start, min(90, _as_int(target_level)))
    experience = sum(LEVEL_EXP_TO_NEXT[start - 1:end - 1])
    if experience <= 0:
        return
    for key, count in _experience_book_plan(experience, inventory).items():
        _add_material(output, recipes, key, count)
    _add_material(output, recipes, "mora", math.ceil(experience / 5))


def _add_material(output: dict, recipes: dict, material_key: str, count: int) -> None:
    if count <= 0:
        return
    material = next((item for item in recipes.get("materials", {}).values() if isinstance(item, dict) and _norm(item.get("key")) == material_key), {})
    key = str(material.get("key") or material_key)
    row = output.setdefault(key, {"key": key, "inventoryKey": key, "name": material.get("name") or key, "required": 0})
    row["required"] += count


def _experience_book_plan(experience: int, inventory: dict[str, int]) -> dict[str, int]:
    remaining = experience
    planned: dict[str, int] = {}
    for key, value in EXP_BOOKS:
        count = min(inventory.get(key, 0), remaining // value)
        if count:
            planned[key] = count
            remaining -= count * value
    if remaining:
        available = [(value, key) for key, value in EXP_BOOKS if inventory.get(key, 0) > planned.get(key, 0)]
        if available:
            value, key = min(available)
        else:
            key, value = EXP_BOOKS[0]
        planned[key] = planned.get(key, 0) + math.ceil(remaining / value)
    return planned


def _get_json(url: str) -> dict:
    data = json.loads(_download(url, MAX_METADATA_BYTES).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("配方数据源返回了无效的元数据。")
    return data


def _download(url: str, max_bytes: int) -> bytes:
    request = Request(url, headers={"User-Agent": "genshin-tool/1.0"})
    with urlopen(request, timeout=90) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("配方数据包过大，已取消下载。")
        chunks = io.BytesIO()
        while chunk := response.read(64 * 1024):
            chunks.write(chunk)
            if chunks.tell() > max_bytes:
                raise ValueError("配方数据包过大，已取消下载。")
        return chunks.getvalue()


def _write_recipes(payload: dict) -> None:
    TRAINING_RECIPES_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with NamedTemporaryFile("w", encoding="utf-8", dir=TRAINING_RECIPES_PATH.parent, delete=False) as temporary:
        temporary.write(serialized)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(TRAINING_RECIPES_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def _talent_recipe_key(character_key: str, traveler_element: str) -> str:
    normalized_character = _norm(character_key)
    if normalized_character in {"aether", "lumine"}:
        return TRAVELER_TALENT_KEYS.get(str(traveler_element).lower(), "")
    return normalized_character


def _traveler_key(value: Any) -> str:
    key = str(value or "")
    return {"PlayerBoy": "Aether", "PlayerGirl": "Lumine"}.get(key, key)


def _norm(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _as_int(value: Any) -> int:
    try:
        return int(float(str(value or 0)))
    except (TypeError, ValueError):
        return 0
