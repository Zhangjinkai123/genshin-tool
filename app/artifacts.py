from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# Five-star artifact substat maximum rolls, converted to a toolbox-style RV score.
ROLL_MAX_VALUES = {
    "\u66b4\u51fb\u7387": 3.9,
    "\u66b4\u51fb\u4f24\u5bb3": 7.8,
    "\u653b\u51fb\u529b%": 5.8,
    "\u751f\u547d\u503c%": 5.8,
    "\u9632\u5fa1\u529b%": 7.3,
    "\u5143\u7d20\u5145\u80fd\u6548\u7387": 6.5,
    "\u5143\u7d20\u7cbe\u901a": 23.3,
    "\u653b\u51fb\u529b": 19.0,
    "\u751f\u547d\u503c": 299.0,
    "\u9632\u5fa1\u529b": 23.0,
}
FULL_VALUE_STATS = {
    "\u66b4\u51fb\u7387", "\u66b4\u51fb\u4f24\u5bb3", "\u653b\u51fb\u529b%", "\u751f\u547d\u503c%", "\u9632\u5fa1\u529b%",
    "\u5143\u7d20\u5145\u80fd\u6548\u7387", "\u5143\u7d20\u7cbe\u901a",
}
LOW_VALUE_STATS = {"\u653b\u51fb\u529b", "\u751f\u547d\u503c", "\u9632\u5fa1\u529b"}
ROLL_VALUE_WEIGHT = 1.18
FLAT_STAT_WEIGHT = 0.5
TOOLBOX_SCORE_MULTIPLIER = 5.86


FIELD_ALIASES = {
    "id": ["id", "artifactId", "artifact_id", "唯一标识"],
    "uid": ["uid", "accountId", "account_id", "账号标识", "账号"],
    "slot": ["slot", "slotKey", "pos", "position", "部位"],
    "rarity": ["rarity", "rank", "star", "星级"],
    "level": ["level", "等级"],
    "setName": ["setName", "set_name", "setKey", "set", "套装名称", "套装"],
    "mainStat": ["mainStat", "main_stat", "mainStatKey", "main", "主词条名称", "主词条"],
    "mainValue": ["mainValue", "main_value", "value", "主词条数值"],
    "subStats": ["subStats", "substats", "sub_stats", "subs", "副词条列表", "副词条"],
    "equippedBy": ["equippedBy", "equipped_by", "location", "character", "装备角色"],
    "locked": ["locked", "lock", "isLocked", "锁定状态"],
}

STAT_ALIASES = {
    "暴击率": "暴击率",
    "暴击率%": "暴击率",
    "CRIT Rate": "暴击率",
    "Crit Rate": "暴击率",
    "暴击伤害": "暴击伤害",
    "暴击伤害%": "暴击伤害",
    "CRIT DMG": "暴击伤害",
    "Crit DMG": "暴击伤害",
    "元素充能效率": "元素充能效率",
    "元素充能效率%": "元素充能效率",
    "Energy Recharge": "元素充能效率",
    "元素精通": "元素精通",
    "Elemental Mastery": "元素精通",
    "攻击力%": "攻击力%",
    "ATK%": "攻击力%",
    "生命值%": "生命值%",
    "HP%": "生命值%",
    "防御力%": "防御力%",
    "DEF%": "防御力%",
    "治疗加成": "治疗加成",
    "Healing Bonus": "治疗加成",
    "hp": "生命值",
    "hp_": "生命值%",
    "atk": "攻击力",
    "atk_": "攻击力%",
    "def": "防御力",
    "def_": "防御力%",
    "eleMas": "元素精通",
    "enerRech_": "元素充能效率",
    "critRate_": "暴击率",
    "critDMG_": "暴击伤害",
    "heal_": "治疗加成",
    "healing_": "治疗加成",
    "physical_dmg_": "物理伤害加成",
    "anemo_dmg_": "风元素伤害加成",
    "geo_dmg_": "岩元素伤害加成",
    "electro_dmg_": "雷元素伤害加成",
    "dendro_dmg_": "草元素伤害加成",
    "hydro_dmg_": "水元素伤害加成",
    "pyro_dmg_": "火元素伤害加成",
    "cryo_dmg_": "冰元素伤害加成",
}

GOOD_SLOT_NAMES = {
    "flower": "生之花",
    "plume": "死之羽",
    "sands": "时之沙",
    "goblet": "空之杯",
    "circlet": "理之冠",
}

GOOD_SET_NAMES = {
    "ADayCarvedFromRisingWinds": "升风雕琢之日",
    "ArchaicPetra": "悠古的磐岩",
    "AubadeOfMorningstarAndMoon": "晨星与月的颂歌",
    "BlizzardStrayer": "冰风迷途的勇士",
    "CelestialGift": "天穹馈赠",
    "CrimsonWitchOfFlames": "炽烈的炎之魔女",
    "DeepwoodMemories": "深林的记忆",
    "DisenchantmentInDeepShadow": "深影解咒",
    "DesertPavilionChronicle": "沙上楼阁史话",
    "EmblemOfSeveredFate": "绝缘之旗印",
    "FinaleOfTheDeepGalleries": "深廊终曲",
    "FlowerOfParadiseLost": "乐园遗落之花",
    "FragmentOfHarmonicWhimsy": "谐律异想断章",
    "GildedDreams": "饰金之梦",
    "GladiatorsFinale": "角斗士的终幕礼",
    "GoldenTroupe": "黄金剧团",
    "HuskOfOpulentDreams": "华馆梦醒形骸记",
    "LongNightsOath": "长夜之誓",
    "MaidenBeloved": "被怜爱的少女",
    "MarechausseeHunter": "逐影猎人",
    "NightOfTheSkysUnveiling": "穹境示现之夜",
    "NighttimeWhispersInTheEchoingWoods": "回声之林夜话",
    "NoblesseOblige": "昔日宗室之仪",
    "NymphsDream": "水仙之梦",
    "ObsidianCodex": "黑曜秘典",
    "OceanHuedClam": "海染砗磲",
    "PaleFlame": "苍白之火",
    "RetracingBolide": "逆飞的流星",
    "ScrollOfTheHeroOfCinderCity": "烬城勇者绘卷",
    "ShimenawasReminiscence": "追忆之注连",
    "SilkenMoonsSerenade": "纺月的夜歌",
    "SongOfDaysPast": "昔时之歌",
    "TenacityOfTheMillelith": "千岩牢固",
    "ThunderingFury": "如雷的盛怒",
    "UnfinishedReverie": "未竟的遐思",
    "VermillionHereafter": "辰砂往生录",
    "ViridescentVenerer": "翠绿之影",
    "VourukashasGlow": "花海甘露之光",
    "WanderersTroupe": "流浪大地的乐团",
}

GOOD_CHARACTER_NAMES = {
    "Aino": "爱诺", "Amber": "安柏", "Arlecchino": "阿蕾奇诺", "Bennett": "班尼特",
    "Beidou": "北斗", "Chasca": "恰斯卡", "Charlotte": "夏洛蒂", "Chevreuse": "夏沃蕾",
    "Clorinde": "克洛琳德", "Columbina": "哥伦比娅", "Dehya": "迪希雅", "Diona": "迪奥娜",
    "Eula": "优菈", "Fischl": "菲谢尔", "Furina": "芙宁娜", "Gaming": "嘉明",
    "Ganyu": "甘雨", "HuTao": "胡桃", "Illuga": "伊露卡", "KaedeharaKazuha": "枫原万叶",
    "Keqing": "刻晴", "Kirara": "绮良良", "Klee": "可莉", "KukiShinobu": "久岐忍",
    "KujouSara": "九条裟罗", "Mona": "莫娜", "Navia": "娜维娅", "Neuvillette": "那维莱特",
    "Nicole": "妮可", "Ningguang": "凝光", "Noelle": "诺艾尔", "RaidenShogun": "雷电将军",
    "Sandrone": "桑多涅", "Shenhe": "申鹤", "Sucrose": "砂糖", "Thoma": "托马",
    "Tighnari": "提纳里", "Venti": "温迪", "Wriothesley": "莱欧斯利", "Xiangling": "香菱",
    "Xianyun": "闲云", "Xilonen": "希诺宁", "Xingqiu": "行秋", "Xinyan": "辛焱",
    "Yanfei": "烟绯", "Yelan": "夜兰", "YunJin": "云堇", "Zhongli": "钟离", "Zibai": "兹白",
}

TEMPLATES = {
    "暴击主 C": {
        "main": {"时之沙": ["攻击力%", "元素精通"], "空之杯": ["元素伤害加成", "攻击力%"], "理之冠": ["暴击率", "暴击伤害"]},
        "weights": {"暴击率": 2.4, "暴击伤害": 1.2, "攻击力%": 0.9, "元素精通": 0.35, "元素充能效率": 0.45},
        "use": "站场或速切暴击输出",
    },
    "反应输出": {
        "main": {"时之沙": ["元素精通", "攻击力%"], "空之杯": ["元素伤害加成", "元素精通"], "理之冠": ["暴击率", "暴击伤害", "元素精通"]},
        "weights": {"暴击率": 2.0, "暴击伤害": 1.0, "元素精通": 0.65, "攻击力%": 0.7, "元素充能效率": 0.4},
        "use": "蒸发、融化、激化类输出",
    },
    "精通输出": {
        "main": {"时之沙": ["元素精通"], "空之杯": ["元素精通"], "理之冠": ["元素精通"]},
        "weights": {"元素精通": 0.95, "元素充能效率": 0.5, "暴击率": 0.8, "暴击伤害": 0.4, "攻击力%": 0.25},
        "use": "绽放、超绽放、扩散等精通收益角色",
    },
    "充能副 C": {
        "main": {"时之沙": ["元素充能效率", "攻击力%"], "空之杯": ["元素伤害加成", "攻击力%"], "理之冠": ["暴击率", "暴击伤害"]},
        "weights": {"元素充能效率": 0.9, "暴击率": 1.8, "暴击伤害": 0.9, "攻击力%": 0.65, "元素精通": 0.25},
        "use": "依赖爆发循环的后台输出",
    },
    "治疗辅助": {
        "main": {"时之沙": ["元素充能效率", "生命值%"], "空之杯": ["生命值%"], "理之冠": ["治疗加成", "生命值%"]},
        "weights": {"元素充能效率": 0.8, "生命值%": 0.8, "治疗加成": 1.0, "元素精通": 0.2},
        "use": "治疗与生存辅助",
    },
    "生命辅助": {
        "main": {"时之沙": ["生命值%", "元素充能效率"], "空之杯": ["生命值%"], "理之冠": ["生命值%", "暴击率"]},
        "weights": {"生命值%": 1.0, "元素充能效率": 0.65, "暴击率": 0.7, "暴击伤害": 0.35, "元素精通": 0.25},
        "use": "生命倍率辅助或护盾角色",
    },
    "防御倍率输出": {
        "main": {"时之沙": ["防御力%"], "空之杯": ["元素伤害加成", "防御力%"], "理之冠": ["暴击率", "暴击伤害", "防御力%"]},
        "weights": {"防御力%": 1.0, "暴击率": 2.0, "暴击伤害": 1.0, "元素充能效率": 0.45},
        "use": "防御倍率输出角色",
    },
}


def extract_artifacts(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("圣遗物文件需要是 JSON 数组，或包含 artifacts/items/list 的对象。")
    for key in ("artifacts", "items", "list", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    raise ValueError("没有在文件中找到圣遗物列表。")


def normalize_artifacts(payload: Any, default_uid: str = "") -> dict:
    raw_items = extract_artifacts(payload)
    normalized: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    imported_at = datetime.now(timezone.utc).isoformat()

    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            errors.append(f"第 {index} 件不是对象，已跳过。")
            continue
        subs = _normalize_substats(_get(raw, "subStats"))
        item = {
            "id": str(_get(raw, "id") or "").strip(),
            "uid": str(_get(raw, "uid") or default_uid).strip(),
            "slot": _normalize_slot(_get(raw, "slot")),
            "rarity": _to_int(_get(raw, "rarity")),
            "level": _to_int(_get(raw, "level")),
            "setName": _normalize_set_name(_get(raw, "setName")),
            "mainStat": _normalize_stat_name(_get(raw, "mainStat")),
            "mainValue": _to_float(_get(raw, "mainValue")),
            "subStats": subs,
            "equippedBy": _normalize_equipped_by(_get(raw, "equippedBy")),
            "locked": _to_bool(_get(raw, "locked")),
            "importedAt": str(raw.get("importedAt") or imported_at),
        }
        missing = [name for name in ("uid", "slot", "rarity", "setName", "mainStat") if item[name] in ("", 0)]
        if missing:
            errors.append(f"第 {index} 件缺少字段：{', '.join(missing)}，已跳过。")
            continue
        key = item["id"] or "|".join([item["uid"], item["slot"], item["setName"], item["mainStat"], str(item["level"]), str(subs)])
        if key in seen:
            continue
        seen.add(key)
        item["id"] = key
        normalized.append(score_artifact(item))

    return {"records": normalized, "errors": errors, "deduped": len(raw_items) - len(normalized) - len(errors), "templates": list(TEMPLATES)}


def score_artifact(item: dict) -> dict:
    cv = _crit_value(item["subStats"])
    useful_count = sum(1 for stat in item["subStats"] if _normalize_stat_name(stat["name"]) in {"暴击率", "暴击伤害", "攻击力%", "元素精通", "元素充能效率", "生命值%", "防御力%"})
    level_factor = min(max(item["level"], 0), 20) / 20
    main_bonus = 16 if _is_reasonable_general_main(item) else 6
    score = toolbox_rv_score(item["subStats"])
    template_scores = {name: _score_template(item, template, cv) for name, template in TEMPLATES.items()}
    best_name = max(template_scores, key=lambda name: template_scores[name]["score"]) if template_scores else ""
    grade = _rv_grade(score)
    item["score"] = {
        "general": score,
        "cv": round(cv, 1),
        "grade": grade,
        "recommendedUse": template_scores[best_name]["recommendedUse"] if best_name else "通用胚子",
        "bestTemplate": best_name,
        "templates": template_scores,
        "reasons": _rv_reasons(cv, score),
    }
    return item


def summarize_artifacts(records: list[dict]) -> dict:
    grades: dict[str, int] = {}
    slots: dict[str, int] = {}
    sets: dict[str, int] = {}
    for item in records:
        grades[item["score"]["grade"]] = grades.get(item["score"]["grade"], 0) + 1
        slots[item["slot"]] = slots.get(item["slot"], 0) + 1
        sets[item["setName"]] = sets.get(item["setName"], 0) + 1
    return {
        "total": len(records),
        "averageScore": round(sum(item["score"]["general"] for item in records) / len(records), 1) if records else 0,
        "highCvCount": sum(1 for item in records if item["score"]["cv"] >= 30),
        "lockedCount": sum(1 for item in records if item["locked"]),
        "grades": [{"name": key, "value": grades.get(key, 0)} for key in ("SSS", "SS", "S", "A", "B") if grades.get(key, 0)],
        "slots": [{"name": key, "value": value} for key, value in sorted(slots.items())],
        "sets": [{"name": key, "value": value} for key, value in sorted(sets.items(), key=lambda pair: pair[1], reverse=True)[:12]],
        "templates": list(TEMPLATES),
    }


def _get(row: dict, canonical: str) -> Any:
    for key in FIELD_ALIASES[canonical]:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _normalize_substats(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            name = _normalize_stat_name(item.get("name") or item.get("key") or item.get("stat"))
            amount = _to_float(item.get("value") or item.get("amount"))
        elif isinstance(item, str) and "+" in item:
            name, amount_text = item.split("+", 1)
            name = _normalize_stat_name(name.strip())
            amount = _to_float(amount_text)
        else:
            continue
        if name:
            result.append({"name": name, "value": amount})
    return result


def _normalize_stat_name(value: Any) -> str:
    text = str(value or "").strip()
    return STAT_ALIASES.get(text, text)


def _normalize_slot(value: Any) -> str:
    text = str(value or "").strip()
    return GOOD_SLOT_NAMES.get(text, text)


def _normalize_set_name(value: Any) -> str:
    text = str(value or "").strip()
    if text in GOOD_SET_NAMES:
        return GOOD_SET_NAMES[text]
    if re.fullmatch(r"[A-Za-z0-9]+", text or ""):
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return text


def _normalize_equipped_by(value: Any) -> str:
    text = str(value or "").strip()
    return GOOD_CHARACTER_NAMES.get(text, text)


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value).replace("+", "").replace("星", "").strip()))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "locked", "锁定", "是"}


def _crit_value(substats: list[dict]) -> float:
    crit_rate = sum(stat["value"] for stat in substats if stat["name"] == "暴击率")
    crit_damage = sum(stat["value"] for stat in substats if stat["name"] == "暴击伤害")
    return crit_damage + 2 * crit_rate


def _is_reasonable_general_main(item: dict) -> bool:
    if item["slot"] in {"生之花", "死之羽", "花", "羽"}:
        return True
    return item["mainStat"] in {"攻击力%", "元素精通", "元素充能效率", "元素伤害加成", "暴击率", "暴击伤害", "生命值%", "防御力%", "治疗加成"}


def _score_template(item: dict, template: dict, cv: float) -> dict:
    slot_expectations = template["main"].get(item["slot"], [])
    main_ok = not slot_expectations or any(expected in item["mainStat"] for expected in slot_expectations)
    main_score = 22 if main_ok else 6
    weighted = 0.0
    hits = []
    for stat in item["subStats"]:
        weight = template["weights"].get(stat["name"], 0)
        if weight:
            weighted += stat["value"] * weight
            hits.append(stat["name"])
    score = min(100, round(main_score + weighted + min(cv, 45) * 0.45 + min(item["level"], 20) * 0.6, 1))
    reasons = []
    reasons.append("主词条命中模板预期" if main_ok else "主词条不是该模板的优先选择")
    if hits:
        reasons.append("有效副词条：" + "、".join(sorted(set(hits))))
    else:
        reasons.append("副词条未命中高权重需求")
    return {"score": score, "grade": _template_grade(score), "recommendedUse": template["use"], "reasons": reasons}


def _template_grade(score: float) -> str:
    if score >= 85:
        return "S"
    if score >= 72:
        return "A"
    if score >= 58:
        return "B"
    if score >= 42:
        return "C"
    return "D"


def _rv_grade(score: float) -> str:
    if score >= 50:
        return "SSS"
    if score >= 40:
        return "SS"
    if score >= 30:
        return "S"
    if score >= 20:
        return "A"
    return "B"


def toolbox_rv_score(substats: list[dict]) -> float:
    roll_points = 0.0
    for stat in substats:
        name = str(stat.get("name") or "")
        max_value = ROLL_MAX_VALUES.get(name)
        if not max_value:
            continue
        weight = ROLL_VALUE_WEIGHT if name in FULL_VALUE_STATS else FLAT_STAT_WEIGHT if name in LOW_VALUE_STATS else 0
        roll_points += max(float(stat.get("value") or 0), 0) / max_value * weight
    return round(roll_points * TOOLBOX_SCORE_MULTIPLIER, 1)


def _rv_reasons(cv: float, score: float) -> list[str]:
    return [f"RV/\u7b49\u6548\u8bcd\u6761\u7d2f\u8ba1\u5206 {score:.1f}", f"CV {cv:.1f}"]


def _general_reasons(item: dict, cv: float, score: float) -> list[str]:
    reasons = [f"双暴值 {cv:.1f}"]
    reasons.append("主词条较通用" if _is_reasonable_general_main(item) else "主词条适用面较窄")
    useful = [stat["name"] for stat in item["subStats"] if stat["name"] in {"暴击率", "暴击伤害", "攻击力%", "元素精通", "元素充能效率", "生命值%", "防御力%"}]
    if useful:
        reasons.append("有效副词条：" + "、".join(sorted(set(useful))))
    reasons.append(f"RV/等效词条累计分 {score:.1f}")
    return reasons
