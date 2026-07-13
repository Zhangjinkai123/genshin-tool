import unittest

from app.artifacts import normalize_artifacts, summarize_artifacts, toolbox_rv_score
from app.characters import analyze_characters
from app.server import default_artifacts, default_characters, default_wishes
from app.wishes import analyze_wishes, normalize_wishes


class WishAnalysisTests(unittest.TestCase):
    def test_default_wishes_are_available(self):
        result = default_wishes()

        self.assertEqual(result["account"]["uid"], "501373549")
        self.assertGreater(len(result["records"]), 0)
        self.assertEqual(result["summary"]["total"], len(result["records"]))

    def test_normalize_dedupes_and_analyzes_pity(self):
        payload = {
            "list": [
                {"uid": "100000001", "gacha_type": "301", "name": "冷刃", "item_type": "武器", "rank_type": "3", "time": "2035-01-01 10:00:00"},
                {"uid": "100000001", "gacha_type": "301", "name": "闲云", "item_type": "角色", "rank_type": "5", "time": "2035-01-01 10:01:00", "id": "x-1"},
                {"uid": "100000001", "gacha_type": "301", "name": "闲云", "item_type": "角色", "rank_type": "5", "time": "2035-01-01 10:01:00", "id": "x-1"},
                {"uid": "100000001", "gacha_type": "301", "name": "嘉明", "item_type": "角色", "rank_type": "4", "time": "2035-01-01 10:02:00"},
            ]
        }

        normalized = normalize_wishes(payload, "100000001")
        summary = analyze_wishes(normalized["records"])

        self.assertEqual(len(normalized["records"]), 3)
        self.assertEqual(normalized["deduped"], 1)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["fiveStarCount"], 1)
        self.assertEqual(summary["poolStats"]["角色活动祈愿"]["currentPity"], 1)
        self.assertEqual(summary["fiveStarIntervals"][0]["fiftyFifty"], "unknown")

    def test_featured_items_infer_fifty_fifty(self):
        payload = {
            "list": [
                {"uid": "100000001", "gacha_type": "301", "name": "闲云", "item_type": "角色", "rank_type": "5", "time": "2035-01-01 10:00:00"},
                {"uid": "100000001", "gacha_type": "301", "name": "迪卢克", "item_type": "角色", "rank_type": "5", "time": "2035-01-01 10:01:00"},
                {"uid": "100000001", "gacha_type": "200", "name": "琴", "item_type": "角色", "rank_type": "5", "time": "2035-01-01 10:02:00"},
            ]
        }

        normalized = normalize_wishes(payload, "100000001", {"character": ["闲云"]})
        results = [item["fiftyFifty"] for item in normalized["records"]]
        summary = analyze_wishes(normalized["records"])

        self.assertEqual(results, ["win", "lose", "unknown"])
        self.assertEqual(summary["fiftyFifty"]["win"], 1)
        self.assertEqual(summary["fiftyFifty"]["lose"], 1)
        self.assertEqual(summary["fiftyFifty"]["winRate"], 50.0)

    def test_banner_history_infers_character_and_weapon_results(self):
        payload = {
            "list": [
                {"uid": "100000001", "gacha_type": "301", "name": "希诺宁", "item_type": "角色", "rank_type": "5", "time": "2024-10-10 10:00:00"},
                {"uid": "100000001", "gacha_type": "301", "name": "七七", "item_type": "角色", "rank_type": "5", "time": "2024-10-10 10:01:00"},
                {"uid": "100000001", "gacha_type": "302", "name": "岩峰巡歌", "item_type": "武器", "rank_type": "5", "time": "2024-10-10 10:02:00"},
                {"uid": "100000001", "gacha_type": "301", "name": "兹白", "item_type": "角色", "rank_type": "5", "time": "2026-02-04 10:00:00"},
                {"uid": "100000001", "gacha_type": "302", "name": "祭星者之望", "item_type": "武器", "rank_type": "5", "time": "2026-07-02 10:00:00"},
            ]
        }

        normalized = normalize_wishes(payload, "100000001")
        self.assertEqual([item["fiftyFifty"] for item in normalized["records"]], ["win", "lose", "win", "win", "win"])

    def test_banner_history_marks_weapon_event_off_banner_as_lose(self):
        payload = {
            "list": [
                {"uid": "100000001", "gacha_type": "302", "name": "赦罪", "item_type": "武器", "rank_type": "5", "time": "2025-02-04 10:00:00"},
                {"uid": "100000001", "gacha_type": "302", "name": "赤月之形", "item_type": "武器", "rank_type": "5", "time": "2025-02-04 10:01:00"},
                {"uid": "100000001", "gacha_type": "302", "name": "天空之翼", "item_type": "武器", "rank_type": "5", "time": "2025-02-04 10:02:00"},
            ]
        }

        normalized = normalize_wishes(payload, "100000001")
        summary = analyze_wishes(normalized["records"])

        self.assertEqual([item["fiftyFifty"] for item in normalized["records"]], ["win", "win", "lose"])
        self.assertEqual([item["fiftyFifty"] for item in summary["fiveStarIntervals"]], ["win", "win", "lose"])
        self.assertEqual(summary["fiftyFifty"]["win"], 2)
        self.assertEqual(summary["fiftyFifty"]["lose"], 1)

    def test_dual_banner_without_gacha_type_keeps_featured_hit_unknown(self):
        payload = {
            "list": [
                {"uid": "100000001", "poolType": "角色活动祈愿", "name": "兹白", "item_type": "角色", "rank_type": "5", "time": "2026-02-04 10:00:00"},
                {"uid": "100000001", "poolType": "角色活动祈愿", "name": "七七", "item_type": "角色", "rank_type": "5", "time": "2026-02-04 10:01:00"},
            ]
        }

        normalized = normalize_wishes(payload, "100000001")
        self.assertEqual([item["fiftyFifty"] for item in normalized["records"]], ["unknown", "lose"])


class ArtifactAnalysisTests(unittest.TestCase):
    def test_default_artifacts_are_available(self):
        result = default_artifacts()

        self.assertEqual(result["account"]["uid"], "501373549")
        self.assertEqual(len(result["records"]), 1074)
        self.assertFalse(result["errors"])
        self.assertEqual(result["summary"]["total"], 1074)

    def test_normalizes_good_artifact_export(self):
        payload = {
            "format": "GOOD",
            "version": 2,
            "artifacts": [{
                "setKey": "MarechausseeHunter",
                "slotKey": "circlet",
                "rarity": 5,
                "level": 0,
                "mainStatKey": "critRate_",
                "substats": [
                    {"key": "critDMG_", "value": 28.0},
                    {"key": "atk_", "value": 9.9},
                    {"key": "enerRech_", "value": 5.8},
                ],
                "location": "Neuvillette",
                "lock": True,
            }],
        }

        normalized = normalize_artifacts(payload, "100000001")
        item = normalized["records"][0]

        self.assertFalse(normalized["errors"])
        self.assertEqual(item["slot"], "理之冠")
        self.assertEqual(item["setName"], "逐影猎人")
        self.assertEqual(item["mainStat"], "暴击率")
        self.assertEqual(item["subStats"][0], {"name": "暴击伤害", "value": 28.0})
        self.assertEqual(item["equippedBy"], "那维莱特")
        self.assertTrue(item["locked"])

    def test_normalizes_good_healing_bonus_key(self):
        payload = {
            "artifacts": [{
                "setKey": "MaidenBeloved",
                "slotKey": "circlet",
                "rarity": 5,
                "level": 20,
                "mainStatKey": "heal_",
                "substats": [{"key": "hp_", "value": 10.0}],
            }],
        }

        normalized = normalize_artifacts(payload, "100000001")

        self.assertEqual(normalized["records"][0]["mainStat"], "治疗加成")

    def test_normalizes_good_set_keys_to_chinese(self):
        payload = {
            "artifacts": [{
                "setKey": "NighttimeWhispersInTheEchoingWoods",
                "slotKey": "flower",
                "rarity": 5,
                "level": 20,
                "mainStatKey": "hp",
                "substats": [],
            }],
        }

        normalized = normalize_artifacts(payload, "100000001")

        self.assertEqual(normalized["records"][0]["setName"], "回声之林夜话")

    def test_scores_and_summarizes_artifacts(self):
        payload = {
            "artifacts": [
                {
                    "id": "a-001",
                    "uid": "100000001",
                    "slot": "理之冠",
                    "rarity": 5,
                    "level": 20,
                    "setName": "逐影猎人",
                    "mainStat": "暴击率",
                    "mainValue": 31.1,
                    "subStats": [
                        {"name": "暴击伤害", "value": 28.0},
                        {"name": "攻击力%", "value": 9.9},
                    ],
                    "locked": True,
                }
            ]
        }

        normalized = normalize_artifacts(payload, "100000001")
        summary = summarize_artifacts(normalized["records"])
        item = normalized["records"][0]

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["highCvCount"], 0)
        self.assertEqual(item["score"]["cv"], 28.0)
        self.assertIn("暴击主 C", item["score"]["templates"])


class CharacterAnalysisTests(unittest.TestCase):
    def test_toolbox_style_roll_score_matches_reference_stat_total(self):
        stats = [
            {"name": "暴击率", "value": 45.9},
            {"name": "暴击伤害", "value": 80.0},
            {"name": "元素精通", "value": 89},
            {"name": "攻击力", "value": 64},
            {"name": "攻击力%", "value": 5.8},
            {"name": "生命值", "value": 269},
            {"name": "生命值%", "value": 14.6},
            {"name": "防御力", "value": 104},
        ]

        self.assertEqual(toolbox_rv_score(stats), 228.8)

    def test_analyzes_good_characters_with_equipment_and_suggestions(self):
        payload = {
            "characters": [{
                "key": "RaidenShogun",
                "level": 80,
                "constellation": 0,
                "talent": {"auto": 1, "skill": 8, "burst": 8},
            }],
            "weapons": [{"key": "EngulfingLightning", "level": 80, "refinement": 1, "location": "RaidenShogun"}],
            "artifacts": [{
                "id": 1,
                "setKey": "EmblemOfSeveredFate",
                "slotKey": "sands",
                "rarity": 5,
                "level": 20,
                "mainStatKey": "enerRech_",
                "substats": [{"key": "critRate_", "value": 10.0}],
                "location": "RaidenShogun",
            }],
        }

        result = analyze_characters(payload)
        character = result["records"][0]

        self.assertEqual(character["name"], "雷电将军")
        self.assertEqual(character["artifacts"]["count"], 1)
        self.assertEqual(character["weapon"]["level"], 80)
        self.assertTrue(character["suggestions"])

    def test_character_score_only_uses_equipped_artifacts(self):
        artifacts = [{
            "id": 1,
            "setKey": "EmblemOfSeveredFate",
            "slotKey": "sands",
            "rarity": 5,
            "level": 20,
            "mainStatKey": "enerRech_",
            "substats": [{"key": "critRate_", "value": 10.0}],
            "location": "RaidenShogun",
        }]
        payload = {
            "characters": [
                {"key": "RaidenShogun", "level": 20, "talent": {"auto": 1, "skill": 1, "burst": 1}},
                {"key": "RaidenShogun", "level": 90, "talent": {"auto": 10, "skill": 10, "burst": 10}},
            ],
            "artifacts": artifacts,
            "weapons": [{"key": "EngulfingLightning", "level": 90, "refinement": 5, "location": "RaidenShogun"}],
        }

        scores = [item["score"] for item in analyze_characters(payload)["records"]]

        self.assertEqual(scores[0], scores[1])

    def test_default_characters_are_available(self):
        result = default_characters()
        raiden = next(item for item in result["records"] if item["key"] == "RaidenShogun")

        self.assertEqual(result["summary"]["total"], 78)
        self.assertEqual(len(result["records"]), 78)
        self.assertGreater(result["summary"]["graduateCount"], 0)
        self.assertTrue(raiden["recommendedSetMatched"])


if __name__ == "__main__":
    unittest.main()
