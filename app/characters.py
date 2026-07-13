from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from .artifacts import GOOD_CHARACTER_NAMES, normalize_artifacts, toolbox_rv_score


ROLE_TEMPLATES = {
    "crit": {
        "name": "暴击输出毕业模板",
        "main": {
            "时之沙": ("攻击力%", "元素精通"),
            "空之杯": ("元素伤害加成", "攻击力%"),
            "理之冠": ("暴击率", "暴击伤害"),
        },
        "substats": {"暴击率", "暴击伤害", "攻击力%", "元素精通", "元素充能效率"},
        "cvGoal": 170,
        "plan": "攻击/精通沙、元素伤害杯、双暴头，优先双暴与攻击%。",
        "sets": ("角色适配四件套", "攻击/元素伤害 2+2"),
    },
    "burst": {
        "name": "充能副 C 毕业模板",
        "main": {
            "时之沙": ("元素充能效率", "攻击力%"),
            "空之杯": ("元素伤害加成", "攻击力%"),
            "理之冠": ("暴击率", "暴击伤害"),
        },
        "substats": {"元素充能效率", "暴击率", "暴击伤害", "攻击力%"},
        "cvGoal": 145,
        "plan": "充能/攻击沙、元素伤害杯、双暴头，先保证循环再补双暴。",
        "sets": ("绝缘之旗印 4 件", "攻击/元素伤害 2+2"),
    },
    "em": {
        "name": "元素精通毕业模板",
        "main": {
            "时之沙": ("元素精通",),
            "空之杯": ("元素精通", "元素伤害加成"),
            "理之冠": ("元素精通",),
        },
        "substats": {"元素精通", "元素充能效率", "暴击率", "暴击伤害"},
        "cvGoal": 0,
        "plan": "精通沙、精通/元素伤害杯、精通头，优先元素精通与充能。",
        "sets": ("翠绿之影 4 件", "饰金之梦 4 件"),
    },
    "hp_crit": {
        "name": "生命双暴毕业模板",
        "main": {
            "时之沙": ("生命值%",),
            "空之杯": ("元素伤害加成", "生命值%"),
            "理之冠": ("暴击率", "暴击伤害", "生命值%"),
        },
        "substats": {"生命值%", "暴击率", "暴击伤害", "元素充能效率"},
        "cvGoal": 150,
        "plan": "生命沙、元素伤害/生命杯、双暴头，兼顾生命%、双暴与充能。",
        "sets": ("角色适配四件套", "生命/元素伤害 2+2"),
    },
    "hp_support": {
        "name": "生命辅助毕业模板",
        "main": {
            "时之沙": ("生命值%", "元素充能效率"),
            "空之杯": ("生命值%",),
            "理之冠": ("生命值%", "治疗加成"),
        },
        "substats": {"生命值%", "元素充能效率", "元素精通"},
        "cvGoal": 0,
        "plan": "生命/充能沙、生命杯、生命/治疗头，优先生命%与充能。",
        "sets": ("千岩牢固 4 件", "生命值 2+2"),
    },
    "healer": {
        "name": "治疗辅助毕业模板",
        "main": {
            "时之沙": ("元素充能效率", "攻击力%", "生命值%"),
            "空之杯": ("攻击力%", "生命值%"),
            "理之冠": ("治疗加成", "攻击力%", "生命值%"),
        },
        "substats": {"元素充能效率", "攻击力%", "生命值%", "元素精通"},
        "cvGoal": 0,
        "plan": "充能/治疗量对应属性沙、对应属性杯、治疗头，优先充能与治疗量。",
        "sets": ("昔时之歌 4 件", "海染砗磲 4 件"),
    },
    "def": {
        "name": "防御倍率毕业模板",
        "main": {
            "时之沙": ("防御力%",),
            "空之杯": ("元素伤害加成", "防御力%"),
            "理之冠": ("暴击率", "暴击伤害", "防御力%"),
        },
        "substats": {"防御力%", "暴击率", "暴击伤害", "元素充能效率"},
        "cvGoal": 135,
        "plan": "防御沙、元素伤害/防御杯、双暴头，优先防御%、双暴与充能。",
        "sets": ("华馆梦醒形骸记 4 件", "防御/元素伤害 2+2"),
    },
    "atk_support": {
        "name": "攻击辅助毕业模板",
        "main": {
            "时之沙": ("攻击力%", "元素充能效率"),
            "空之杯": ("攻击力%",),
            "理之冠": ("攻击力%", "治疗加成"),
        },
        "substats": {"攻击力%", "元素充能效率", "暴击率", "暴击伤害"},
        "cvGoal": 0,
        "plan": "攻击/充能沙、攻击杯、攻击/治疗头，优先攻击%与充能。",
        "sets": ("昔日宗室之仪 4 件", "攻击力 2+2"),
    },
    "physical": {
        "name": "物理输出毕业模板",
        "main": {
            "时之沙": ("攻击力%",),
            "空之杯": ("物理伤害加成", "攻击力%"),
            "理之冠": ("暴击率", "暴击伤害"),
        },
        "substats": {"暴击率", "暴击伤害", "攻击力%", "元素充能效率"},
        "cvGoal": 160,
        "plan": "攻击沙、物伤杯、双暴头，优先双暴与攻击%。",
        "sets": ("苍白之火 4 件", "物理伤害/攻击 2+2"),
    },
}


CHARACTER_PROFILES = {
    "Sandrone": ("桑多涅", "crit", ("auto", "burst")),
    "Columbina": ("哥伦比娅", "hp_support", ("skill", "burst")),
    "Nicole": ("妮可", "crit", ("skill", "burst")),
    "Zibai": ("兹白", "crit", ("auto", "skill", "burst")),
    "Sucrose": ("砂糖", "em", ("skill", "burst")),
    "Chevreuse": ("夏沃蕾", "hp_support", ("skill",)),
    "Xilonen": ("希诺宁", "def", ("skill", "burst")),
    "Navia": ("娜维娅", "crit", ("skill", "burst")),
    "Zhongli": ("钟离", "hp_support", ("skill", "burst")),
    "Xianyun": ("闲云", "healer", ("skill", "burst")),
    "KaedeharaKazuha": ("枫原万叶", "em", ("skill", "burst")),
    "Wriothesley": ("莱欧斯利", "crit", ("auto", "skill", "burst")),
    "Eula": ("优菈", "physical", ("auto", "burst")),
    "Ganyu": ("甘雨", "crit", ("auto", "burst")),
    "Clorinde": ("克洛琳德", "crit", ("auto", "skill", "burst")),
    "RaidenShogun": ("雷电将军", "burst", ("skill", "burst")),
    "Keqing": ("刻晴", "crit", ("auto", "skill", "burst")),
    "Furina": ("芙宁娜", "hp_crit", ("skill", "burst")),
    "Neuvillette": ("那维莱特", "hp_crit", ("auto", "skill", "burst")),
    "Yelan": ("夜兰", "hp_crit", ("skill", "burst")),
    "Arlecchino": ("阿蕾奇诺", "crit", ("auto", "skill", "burst")),
    "HuTao": ("胡桃", "hp_crit", ("auto", "skill", "burst")),
    "Klee": ("可莉", "crit", ("auto", "skill", "burst")),
    "Noelle": ("诺艾尔", "def", ("auto", "burst")),
    "Ningguang": ("凝光", "crit", ("auto", "skill", "burst")),
    "Xingqiu": ("行秋", "burst", ("skill", "burst")),
    "Bennett": ("班尼特", "atk_support", ("burst",)),
    "Xiangling": ("香菱", "burst", ("skill", "burst")),
    "Chasca": ("恰斯卡", "crit", ("auto", "skill", "burst")),
    "Venti": ("温迪", "em", ("skill", "burst")),
    "Shenhe": ("申鹤", "atk_support", ("skill", "burst")),
    "Illuga": ("伊露卡", "crit", ("skill", "burst")),
    "Rosaria": ("罗莎莉亚", "crit", ("skill", "burst")),
    "Fischl": ("菲谢尔", "crit", ("skill",)),
    "Razor": ("雷泽", "physical", ("auto", "burst")),
    "Aino": ("爱诺", "hp_support", ("skill", "burst")),
    "Mona": ("莫娜", "burst", ("burst",)),
    "Qiqi": ("七七", "healer", ("skill",)),
    "Tighnari": ("提纳里", "crit", ("auto", "skill", "burst")),
    "Dehya": ("迪希雅", "hp_support", ("skill", "burst")),
    "Kachina": ("卡齐娜", "def", ("skill", "burst")),
    "YunJin": ("云堇", "def", ("burst",)),
    "Prune": ("普露妮", "crit", ("skill", "burst")),
    "Jahoda": ("雅珂达", "healer", ("skill", "burst")),
    "Lynette": ("琳妮特", "burst", ("skill", "burst")),
    "Charlotte": ("夏洛蒂", "healer", ("skill", "burst")),
    "Diona": ("迪奥娜", "hp_support", ("skill", "burst")),
    "Chongyun": ("重云", "crit", ("skill", "burst")),
    "Kaeya": ("凯亚", "burst", ("skill", "burst")),
    "KujouSara": ("九条裟罗", "burst", ("skill", "burst")),
    "Beidou": ("北斗", "burst", ("skill", "burst")),
    "Yaoyao": ("瑶瑶", "healer", ("skill", "burst")),
    "Collei": ("柯莱", "burst", ("skill", "burst")),
    "Barbara": ("芭芭拉", "healer", ("skill", "burst")),
    "Thoma": ("托马", "hp_support", ("skill", "burst")),
    "Yanfei": ("烟绯", "crit", ("auto", "skill", "burst")),
    "YumemizukiMizuki": ("梦见月瑞希", "em", ("skill", "burst")),
    "Faruzan": ("珐露珊", "burst", ("skill", "burst")),
    "Layla": ("莱依拉", "hp_support", ("skill", "burst")),
    "Sayu": ("早柚", "em", ("skill", "burst")),
    "Sethos": ("赛索斯", "em", ("auto", "skill", "burst")),
    "KukiShinobu": ("久岐忍", "em", ("skill",)),
    "Lisa": ("丽莎", "burst", ("skill", "burst")),
    "Gaming": ("嘉明", "crit", ("auto", "skill", "burst")),
    "Jean": ("琴", "healer", ("skill", "burst")),
    "Aloy": ("埃洛伊", "crit", ("auto", "skill", "burst")),
    "Gorou": ("五郎", "def", ("skill", "burst")),
    "ShikanoinHeizou": ("鹿野院平藏", "crit", ("auto", "skill", "burst")),
    "Freminet": ("菲米尼", "physical", ("auto", "skill", "burst")),
    "Mika": ("米卡", "healer", ("skill", "burst")),
    "Dori": ("多莉", "healer", ("skill", "burst")),
    "Kirara": ("绮良良", "hp_support", ("skill",)),
    "Candace": ("坎蒂丝", "hp_support", ("skill", "burst")),
    "Xinyan": ("辛焱", "physical", ("skill", "burst")),
    "Amber": ("安柏", "crit", ("auto", "skill", "burst")),
    "Ifa": ("伊法", "em", ("skill", "burst")),
    "LanYan": ("蓝砚", "hp_support", ("skill", "burst")),
    "Ororon": ("欧洛伦", "burst", ("skill", "burst")),
}

TALENT_NAMES = {"auto": "普攻", "skill": "战技", "burst": "爆发"}
SET_RECOMMENDATION_PATTERN = re.compile(r"^(.+?)\s+([24])\s*件$")

# 原魔工具箱同类的副词条折算：先换算为五星单次词条的等效次数，再按词条价值累计。
ROLL_MAX_VALUES = {
    "暴击率": 3.9,
    "暴击伤害": 7.8,
    "攻击力%": 5.8,
    "生命值%": 5.8,
    "防御力%": 7.3,
    "元素充能效率": 6.5,
    "元素精通": 23.3,
    "攻击力": 19.0,
    "生命值": 299.0,
    "防御力": 23.0,
}
FULL_VALUE_STATS = {"暴击率", "暴击伤害", "攻击力%", "生命值%", "防御力%", "元素充能效率", "元素精通"}
LOW_VALUE_STATS = {"攻击力", "生命值", "防御力"}
ROLL_VALUE_WEIGHT = 1.18
FLAT_STAT_WEIGHT = 0.5
TOOLBOX_SCORE_MULTIPLIER = 5.86

CHARACTER_SET_RECOMMENDATIONS = {
    "Sucrose": ("翠绿之影 4 件",),
    "Chevreuse": ("昔日宗室之仪 4 件", "生命值 2+2"),
    "Xilonen": ("烬城勇者绘卷 4 件",),
    "Navia": ("回声之林夜话 4 件",),
    "Zhongli": ("千岩牢固 4 件", "生命值 2+2"),
    "Xianyun": ("昔时之歌 4 件",),
    "KaedeharaKazuha": ("翠绿之影 4 件",),
    "Wriothesley": ("逐影猎人 4 件",),
    "Eula": ("苍白之火 4 件",),
    "Ganyu": ("流浪大地的乐团 4 件", "冰风迷途的勇士 4 件"),
    "Clorinde": ("谐律异想断章 4 件",),
    "RaidenShogun": ("绝缘之旗印 4 件",),
    "Keqing": ("如雷的盛怒 4 件", "饰金之梦 4 件"),
    "Furina": ("黄金剧团 4 件",),
    "Neuvillette": ("逐影猎人 4 件",),
    "Yelan": ("绝缘之旗印 4 件",),
    "Arlecchino": ("谐律异想断章 4 件",),
    "HuTao": ("炽烈的炎之魔女 4 件", "饰金之梦 4 件"),
    "Noelle": ("华馆梦醒形骸记 4 件",),
    "Xingqiu": ("绝缘之旗印 4 件",),
    "Bennett": ("昔日宗室之仪 4 件",),
    "Xiangling": ("绝缘之旗印 4 件",),
    "Chasca": ("黑曜秘典 4 件",),
    "Venti": ("翠绿之影 4 件",),
    "Shenhe": ("攻击力 2+2",),
    "Fischl": ("黄金剧团 4 件",),
    "Razor": ("苍白之火 4 件",),
    "Mona": ("绝缘之旗印 4 件",),
    "Qiqi": ("海染砗磲 4 件",),
    "Tighnari": ("饰金之梦 4 件",),
    "Dehya": ("千岩牢固 4 件",),
    "Kachina": ("烬城勇者绘卷 4 件",),
    "YunJin": ("华馆梦醒形骸记 4 件",),
    "Lynette": ("翠绿之影 4 件",),
    "Charlotte": ("昔时之歌 4 件",),
    "Diona": ("昔日宗室之仪 4 件",),
    "Kaeya": ("绝缘之旗印 4 件",),
    "KujouSara": ("绝缘之旗印 4 件",),
    "Beidou": ("绝缘之旗印 4 件",),
    "Yaoyao": ("深林的记忆 4 件",),
    "Collei": ("深林的记忆 4 件",),
    "Barbara": ("海染砗磲 4 件",),
    "Thoma": ("乐园遗落之花 4 件", "生命值 2+2"),
    "Yanfei": ("流浪大地的乐团 4 件",),
    "YumemizukiMizuki": ("翠绿之影 4 件",),
    "Faruzan": ("昔日宗室之仪 4 件",),
    "Layla": ("千岩牢固 4 件",),
    "Sayu": ("翠绿之影 4 件",),
    "KukiShinobu": ("乐园遗落之花 4 件",),
    "Jean": ("翠绿之影 4 件",),
    "Gorou": ("华馆梦醒形骸记 4 件",),
    "Freminet": ("苍白之火 4 件",),
    "Mika": ("昔日宗室之仪 4 件",),
    "Kirara": ("深林的记忆 4 件", "千岩牢固 4 件"),
    "Xinyan": ("苍白之火 4 件",),
    "Amber": ("流浪大地的乐团 4 件",),
    "LanYan": ("翠绿之影 4 件",),
    "Ororon": ("烬城勇者绘卷 4 件",),
}


def analyze_characters(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("角色练度需要导入包含 characters、weapons、artifacts 的 GOOD JSON。")
    raw_characters = payload.get("characters")
    if not isinstance(raw_characters, list):
        raise ValueError("文件中没有找到角色列表。请导入 Inventory Kamera 的完整 GOOD JSON。")

    normalized_artifacts = normalize_artifacts(payload, "GOOD")["records"]
    artifacts_by_owner: dict[str, list[dict]] = defaultdict(list)
    for artifact in normalized_artifacts:
        if artifact["equippedBy"]:
            artifacts_by_owner[artifact["equippedBy"]].append(artifact)

    weapons_by_owner: dict[str, dict] = {}
    for weapon in payload.get("weapons", []):
        if not isinstance(weapon, dict):
            continue
        owner = str(weapon.get("location") or "").strip()
        if not owner:
            continue
        current = weapons_by_owner.get(owner)
        if current is None or _weapon_sort_key(weapon) > _weapon_sort_key(current):
            weapons_by_owner[owner] = weapon

    records = []
    for raw in raw_characters:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        if not key:
            continue
        profile = _profile_for(key)
        artifacts = artifacts_by_owner.get(GOOD_CHARACTER_NAMES.get(key, key), [])
        weapon = weapons_by_owner.get(key)
        records.append(_analyze_character(raw, key, profile, artifacts, weapon))

    records.sort(key=lambda item: (-item["score"], item["name"]))
    return {"records": records, "summary": _summary(records)}


def _analyze_character(raw: dict, key: str, profile: dict, artifacts: list[dict], weapon: dict | None) -> dict:
    level = _as_int(raw.get("level"))
    constellation = _as_int(raw.get("constellation"))
    talents = raw.get("talent") if isinstance(raw.get("talent"), dict) else {}
    role = ROLE_TEMPLATES[profile["role"]]

    weapon_result = _weapon_assessment(weapon)
    artifact_result = _artifact_assessment(artifacts, role)
    recommended_sets = list(CHARACTER_SET_RECOMMENDATIONS.get(key, role["sets"]))
    score = artifact_result["score"]
    suggestions = _suggestions(artifact_result, role)

    return {
        "key": key,
        "name": profile["name"],
        "role": role["name"],
        "roleKey": profile["role"],
        "templatePlan": role["plan"],
        "recommendedSets": recommended_sets,
        "recommendedSetMatched": _recommended_sets_match(recommended_sets, artifact_result["sets"]),
        "level": level,
        "ascension": _as_int(raw.get("ascension")),
        "constellation": constellation,
        "talents": {name: _as_int(talents.get(name)) for name in TALENT_NAMES},
        "priority": list(profile["priority"]),
        "weapon": weapon_result,
        "artifacts": artifact_result,
        "breakdown": {"artifacts": artifact_result["score"]},
        "score": score,
        "grade": _grade(score),
        "rating": _toolbox_rating(score),
        "suggestions": suggestions,
    }


def _profile_for(key: str) -> dict:
    name, role, priority = CHARACTER_PROFILES.get(key, (_humanize(key), "crit", ("auto", "skill", "burst")))
    return {"name": name, "role": role, "priority": priority}


def _weapon_assessment(weapon: dict | None) -> dict:
    if not weapon:
        return {"name": "未装备", "level": 0, "refinement": 0}
    level = _as_int(weapon.get("level"))
    refinement = max(1, _as_int(weapon.get("refinement")))
    return {
        "name": _humanize(str(weapon.get("key") or "未知武器")),
        "level": level,
        "refinement": refinement,
    }


def _artifact_assessment(artifacts: list[dict], role: dict) -> dict:
    slots = {item["slot"]: item for item in artifacts}
    required_main = role["main"]
    main_hits = []
    main_misses = []
    for slot, expected in required_main.items():
        artifact = slots.get(slot)
        if artifact and any(value in artifact["mainStat"] for value in expected):
            main_hits.append(slot)
        else:
            main_misses.append(slot)

    set_counts = Counter(item["setName"] for item in artifacts)
    top_set, top_set_count = set_counts.most_common(1)[0] if set_counts else ("无", 0)
    total_cv = round(sum(item["score"]["cv"] for item in artifacts), 1)
    desired_occurrences = sum(
        1
        for item in artifacts
        for stat in item["subStats"]
        if stat["name"] in role["substats"]
    )
    piece_scores = [{"slot": item["slot"], "score": _toolbox_piece_score(item["subStats"])} for item in artifacts]

    return {
        "count": len(artifacts),
        "level20Count": sum(item["level"] >= 20 for item in artifacts),
        "mainHits": main_hits,
        "mainMisses": main_misses,
        "topSet": top_set,
        "topSetCount": top_set_count,
        "sets": [{"name": name, "count": count} for name, count in set_counts.most_common()],
        "totalCv": total_cv,
        "desiredOccurrences": desired_occurrences,
        "pieceScores": piece_scores,
        "score": round(sum(item["score"] for item in piece_scores), 1),
    }


def _suggestions(artifacts: dict, role: dict) -> list[str]:
    suggestions = []
    if artifacts["count"] < 5:
        suggestions.append(f"当前仅装备 {artifacts['count']} 件圣遗物，先补齐五个部位。")
    elif artifacts["level20Count"] < 5:
        suggestions.append(f"已有 {artifacts['count']} 件装备，但仅 {artifacts['level20Count']} 件达到 +20，优先补满主力套装。")
    if artifacts["mainMisses"]:
        slots = "、".join(artifacts["mainMisses"])
        suggestions.append(f"{slots}主词条未完全匹配模板：{role['plan']}")
    if artifacts["topSetCount"] < 2:
        suggestions.append("当前没有成型的两件套效果，建议先凑 2+2 或四件套。")
    elif artifacts["topSetCount"] < 4:
        suggestions.append(f"当前最高为 {artifacts['topSet']} {artifacts['topSetCount']} 件，可根据队伍目标补成四件套或另一组两件套。")
    if role["cvGoal"] and artifacts["totalCv"] < role["cvGoal"]:
        suggestions.append(f"已装备圣遗物总 CV 为 {artifacts['totalCv']}，通用毕业线参考约 {role['cvGoal']}；优先替换低双暴部位。")
    elif not role["cvGoal"] and artifacts["desiredOccurrences"] < 7:
        suggestions.append("有效副词条偏少，优先寻找带充能、精通或对应主属性的部位。")
    if not suggestions:
        suggestions.append("当前圣遗物已达到该通用毕业模板的优秀线，可结合队伍循环与专武进一步微调。")
    return suggestions[:5]


def _summary(records: list[dict]) -> dict:
    return {
        "total": len(records),
        "averageScore": round(sum(item["score"] for item in records) / len(records), 1) if records else 0,
        "graduateCount": sum(item["score"] >= 90 for item in records),
        "completeArtifactCount": sum(item["artifacts"]["count"] >= 5 for item in records),
        "grades": [{"name": grade, "value": sum(item["grade"] == grade for item in records)} for grade in ("毕业", "优秀", "可用", "待培养")],
    }


def _recommended_sets_match(recommended_sets: list[str], actual_sets: list[dict]) -> bool:
    actual_counts = {str(item.get("name") or ""): _as_int(item.get("count")) for item in actual_sets}
    for recommendation in recommended_sets:
        match = SET_RECOMMENDATION_PATTERN.match(recommendation)
        if not match:
            continue
        set_name, required_count = match.groups()
        if actual_counts.get(set_name, 0) >= int(required_count):
            return True
    return False


def _grade(score: float) -> str:
    if score >= 220:
        return "毕业"
    if score >= 170:
        return "优秀"
    if score >= 120:
        return "可用"
    return "待培养"


def _toolbox_rating(score: float) -> str:
    if score >= 220:
        return "SSS"
    if score >= 180:
        return "SS"
    if score >= 140:
        return "S"
    if score >= 100:
        return "A"
    return "B"


def _toolbox_piece_score(substats: list[dict]) -> float:
    return toolbox_rv_score(substats)


def _weapon_sort_key(weapon: dict) -> tuple[int, int]:
    return (_as_int(weapon.get("level")), _as_int(weapon.get("refinement")))


def _as_int(value: Any) -> int:
    try:
        return int(float(str(value or 0)))
    except (TypeError, ValueError):
        return 0


def _humanize(value: str) -> str:
    text = str(value or "未知")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
