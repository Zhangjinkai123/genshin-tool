from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .banner_history import infer_from_banner_history


FIELD_ALIASES = {
    "uid": ["uid", "accountId", "account_id", "账号标识", "账号", "角色UID"],
    "gachaType": ["gachaType", "gacha_type", "gachaTypeId", "gacha_type_id", "卡池编号"],
    "poolType": ["poolType", "gachaType", "gacha_type", "gacha_type_name", "卡池类型", "卡池"],
    "itemName": ["itemName", "name", "item_name", "物品名称", "名称"],
    "itemType": ["itemType", "item_type", "物品类型", "类型"],
    "rank": ["rank", "rankType", "rank_type", "star", "rarity", "星级"],
    "time": ["time", "date", "createdAt", "created_at", "抽取时间", "时间"],
    "id": ["id", "wishId", "wish_id", "唯一标识"],
    "fiftyFifty": ["fiftyFifty", "fifty_fifty", "5050", "50/50", "歪卡结果"],
}

POOL_LABELS = {
    "100": "角色活动祈愿",
    "200": "常驻祈愿",
    "301": "角色活动祈愿",
    "302": "武器活动祈愿",
    "400": "角色活动祈愿",
}

FETCH_GACHA_TYPES = ("301", "302", "200")
FETCH_PAGE_SIZE = 20
FETCH_TIMEOUT_SECONDS = 12
FETCH_REQUEST_DELAY_SECONDS = 0.9
FETCH_RETRY_DELAYS_SECONDS = (2.0, 5.0, 10.0)
ALLOWED_FETCH_HOST_SUFFIXES = (".mihoyo.com", ".hoyoverse.com")


def extract_records(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("抽卡文件需要是 JSON 数组，或包含 list/items/records/data.list 的对象。")
    for key in ("list", "items", "records", "wishes"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("list", "items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("没有在文件中找到抽卡记录列表。")


def normalize_wishes(payload: Any, default_uid: str = "", featured_items: Any = None) -> dict:
    records = extract_records(payload)
    featured = _normalize_featured_items(featured_items)
    normalized: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()

    for index, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            errors.append(f"第 {index} 条不是对象，已跳过。")
            continue
        row = {
            "uid": str(_get(raw, "uid") or default_uid).strip(),
            "gachaType": _normalize_gacha_type(_get(raw, "gachaType")),
            "poolType": _pool_label(_get(raw, "poolType")),
            "itemName": str(_get(raw, "itemName") or "").strip(),
            "itemType": str(_get(raw, "itemType") or "").strip() or "未知",
            "rank": _to_int(_get(raw, "rank")),
            "time": _normalize_time(_get(raw, "time")),
            "id": str(_get(raw, "id") or "").strip(),
            "fiftyFifty": _normalize_fifty(_get(raw, "fiftyFifty")),
        }
        row["fiftyFifty"] = _infer_fifty(row, featured)
        missing = [name for name in ("uid", "poolType", "itemName", "rank", "time") if not row[name]]
        if missing:
            errors.append(f"第 {index} 条缺少字段：{', '.join(missing)}，已跳过。")
            continue
        key = row["id"] or "|".join([row["uid"], row["gachaType"], row["poolType"], row["itemName"], row["itemType"], str(row["rank"]), row["time"]])
        if key in seen:
            continue
        seen.add(key)
        row["id"] = key
        normalized.append(row)

    normalized.sort(key=lambda item: item["time"])
    return {"records": normalized, "errors": errors, "deduped": len(records) - len(normalized) - len(errors)}


def analyze_wishes(records: list[dict]) -> dict:
    total = len(records)
    by_pool = Counter(item["poolType"] for item in records)
    five_stars = [item for item in records if item["rank"] == 5]
    four_stars = [item for item in records if item["rank"] == 4]
    trend = Counter(item["time"][:7] for item in records if item.get("time"))

    pool_stats = {}
    intervals: list[dict] = []
    pity_cards: list[dict] = []
    wins = losses = unknown = 0

    for pool, pool_records in _group_by_pool(records).items():
        since_five = 0
        five_intervals: list[int] = []
        five_timeline: list[dict] = []
        for item in pool_records:
            since_five += 1
            if item["rank"] == 5:
                interval = since_five
                since_five = 0
                five_intervals.append(interval)
                intervals.append({"poolType": pool, "itemName": item["itemName"], "time": item["time"], "count": interval, "fiftyFifty": item["fiftyFifty"]})
                five_timeline.append({"itemName": item["itemName"], "time": item["time"], "count": interval, "fiftyFifty": item["fiftyFifty"]})
                if item["fiftyFifty"] == "win":
                    wins += 1
                elif item["fiftyFifty"] == "lose":
                    losses += 1
                else:
                    unknown += 1
        average = round(sum(five_intervals) / len(five_intervals), 2) if five_intervals else 0
        pool_stats[pool] = {
            "total": len(pool_records),
            "fiveStarCount": len(five_intervals),
            "fourStarCount": sum(1 for item in pool_records if item["rank"] == 4),
            "currentPity": since_five,
            "averageFiveStarPity": average,
            "fiveStarTimeline": five_timeline,
        }
        pity_cards.append({"poolType": pool, "currentPity": since_five})

    return {
        "total": total,
        "fiveStarCount": len(five_stars),
        "fourStarCount": len(four_stars),
        "poolCounts": [{"name": key, "value": value} for key, value in by_pool.items()],
        "monthlyTrend": [{"month": key, "count": value} for key, value in sorted(trend.items())],
        "fiveStarDistribution": [{"name": key, "value": value} for key, value in Counter(item["itemName"] for item in five_stars).items()],
        "fiveStarIntervals": intervals,
        "pityCards": pity_cards,
        "poolStats": pool_stats,
        "fiftyFifty": {
            "win": wins,
            "lose": losses,
            "unknown": unknown,
            "winRate": round(wins / (wins + losses) * 100, 1) if wins + losses else None,
        },
        "recentRecords": list(reversed(records[-80:])),
    }


def fetch_wishes_from_url(history_url: str, default_uid: str = "", max_pages: int = 50, featured_items: Any = None) -> dict:
    parsed = urlparse(str(history_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请粘贴完整的祈愿历史 URL。")
    if not _is_allowed_host(parsed.hostname or ""):
        raise ValueError("只允许从 mihoyo.com 或 hoyoverse.com 的祈愿历史接口拉取。")

    query = parse_qs(parsed.query)
    if "authkey" not in query:
        raise ValueError("URL 中没有 authkey。请复制游戏内祈愿历史页面的完整链接。")

    endpoints = _gacha_log_endpoints(parsed)
    max_pages = max(1, min(int(max_pages or 50), 200))
    last_error: ValueError | None = None

    for endpoint in endpoints:
        try:
            return _fetch_wishes_from_endpoint(endpoint, query, default_uid, max_pages, featured_items)
        except ValueError as exc:
            last_error = exc
            # Domestic URLs may work on either hk4e-api or public-operation. Try the next
            # official endpoint before giving up.
            if not _can_try_next_endpoint(str(exc)):
                raise

    if last_error:
        raise last_error
    raise ValueError("没有可用的官方祈愿接口。")


def _fetch_wishes_from_endpoint(endpoint: str, query: dict[str, list[str]], default_uid: str, max_pages: int, featured_items: Any) -> dict:
    records: list[dict] = []
    warnings: list[str] = []

    for gacha_type in FETCH_GACHA_TYPES:
        end_id = "0"
        for page in range(1, max_pages + 1):
            request_url = _build_fetch_url(endpoint, query, gacha_type, page, end_id)
            payload = _request_json_with_retry(request_url)
            retcode = payload.get("retcode")
            if retcode not in (0, "0", None):
                message = payload.get("message") or payload.get("msg") or "接口返回错误"
                raise ValueError(_friendly_fetch_error(message))

            data = payload.get("data") or {}
            items = data.get("list") or []
            if not isinstance(items, list):
                warnings.append(f"{POOL_LABELS.get(gacha_type, gacha_type)} 返回格式异常，已跳过。")
                break
            if not items:
                break

            for item in items:
                if isinstance(item, dict):
                    item.setdefault("uid", default_uid)
                    item.setdefault("gacha_type", gacha_type)
                    records.append(item)

            next_id = str(items[-1].get("id") or "")
            if not next_id or next_id == end_id or len(items) < FETCH_PAGE_SIZE:
                break
            end_id = next_id
            time.sleep(FETCH_REQUEST_DELAY_SECONDS)
        time.sleep(FETCH_REQUEST_DELAY_SECONDS)

    normalized = normalize_wishes({"list": records}, default_uid, featured_items)
    return {
        **normalized,
        "summary": analyze_wishes(normalized["records"]),
        "source": {"fetched": len(records), "warnings": warnings},
    }


def _get(row: dict, canonical: str) -> Any:
    for key in FIELD_ALIASES[canonical]:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _to_int(value: Any) -> int:
    try:
        return int(str(value).replace("星", "").strip())
    except (TypeError, ValueError):
        return 0


def _pool_label(value: Any) -> str:
    raw = str(value or "").strip()
    return POOL_LABELS.get(raw, raw)


def _normalize_gacha_type(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if raw.isdigit() else ""


def _normalize_time(value: Any) -> str:
    text = str(value or "").strip().replace("/", "-")
    if not text:
        return ""
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:length], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return text


def _normalize_fifty(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"win", "won", "true", "1", "up", "命中", "不歪", "胜"}:
        return "win"
    if text in {"lose", "lost", "false", "0", "off", "歪", "败"}:
        return "lose"
    return "unknown"


def _normalize_featured_items(value: Any) -> dict[str, set[str]]:
    result = {"character": set(), "weapon": set()}
    if not value:
        return result
    if isinstance(value, dict):
        for group in result:
            raw_items = value.get(group) or value.get(f"{group}s") or []
            if isinstance(raw_items, str):
                raw_items = raw_items.replace("，", ",").replace("\n", ",").split(",")
            if isinstance(raw_items, list):
                result[group] = {str(item).strip() for item in raw_items if str(item).strip()}
    elif isinstance(value, list):
        result["character"] = {str(item).strip() for item in value if str(item).strip()}
    return result


def _infer_fifty(row: dict, featured: dict[str, set[str]]) -> str:
    explicit = row.get("fiftyFifty") or "unknown"
    if explicit != "unknown" or row.get("rank") != 5:
        return explicit
    history_result = infer_from_banner_history(row)
    if history_result != "unknown":
        return history_result
    pool = str(row.get("poolType") or "")
    if "常驻" in pool:
        return explicit
    group = "weapon" if "武器" in pool else "character" if "角色" in pool else ""
    featured_names = featured.get(group) if group else set()
    if not featured_names:
        return explicit
    return "win" if row.get("itemName") in featured_names else "lose"


def _group_by_pool(records: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for item in records:
        result[item["poolType"]].append(item)
    return dict(result)


def _is_allowed_host(hostname: str) -> bool:
    host = hostname.lower()
    return host in {"mihoyo.com", "hoyoverse.com"} or any(host.endswith(suffix) for suffix in ALLOWED_FETCH_HOST_SUFFIXES)


def _gacha_log_endpoints(parsed_url) -> list[str]:
    host = (parsed_url.hostname or "").lower()
    if "getgachalog" in parsed_url.path.lower():
        return [urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "", ""))]
    if "hoyoverse.com" in host or "-sg" in host or "hk4e-api-os" in host:
        return ["https://public-operation-hk4e-sg.hoyoverse.com/gacha_info/api/getGachaLog"]
    return [
        "https://hk4e-api.mihoyo.com/event/gacha_info/api/getGachaLog",
        "https://public-operation-hk4e.mihoyo.com/gacha_info/api/getGachaLog",
    ]


def _build_fetch_url(endpoint: str, source_query: dict[str, list[str]], gacha_type: str, page: int, end_id: str) -> str:
    params = {key: values[-1] for key, values in source_query.items() if values}
    params.update({
        "gacha_type": gacha_type,
        "page": str(page),
        "size": str(FETCH_PAGE_SIZE),
        "end_id": end_id,
    })
    params.setdefault("lang", "zh-cn")
    return f"{endpoint}?{urlencode(params)}"


def _request_json_with_retry(url: str) -> dict:
    last_payload: dict | None = None
    for attempt, delay in enumerate((0.0, *FETCH_RETRY_DELAYS_SECONDS), start=1):
        if delay:
            time.sleep(delay)
        payload = _request_json(url)
        last_payload = payload
        message = str(payload.get("message") or payload.get("msg") or "")
        if payload.get("retcode") in (0, "0", None) or "visit too frequently" not in message.lower():
            return payload
        if attempt <= len(FETCH_RETRY_DELAYS_SECONDS):
            continue
    return last_payload or {}


def _request_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) GenshinPersonalAnalyzer/1.0 Chrome/120 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://webstatic.mihoyo.com/",
            "Origin": "https://webstatic.mihoyo.com",
        },
    )
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"祈愿接口 HTTP {exc.code}。") from exc
    except URLError as exc:
        raise ValueError(f"无法连接祈愿接口：{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("祈愿接口返回的不是 JSON。") from exc


def _friendly_fetch_error(message: str) -> str:
    if "visit too frequently" in message.lower():
        return "拉取失败：官方接口提示访问过于频繁。我已经加入限速和重试；如果仍出现，请等 1-3 分钟后再试，或先只用小程序导出 JSON 再导入。"
    if "authkey" in message.lower() or "expired" in message.lower():
        return "拉取失败：authkey 可能已过期，请重新打开游戏祈愿历史并复制完整 URL。"
    return f"拉取失败：{message}。authkey 可能已过期，请重新打开游戏祈愿历史复制 URL。"


def _can_try_next_endpoint(message: str) -> bool:
    text = message.lower()
    return any(part in text for part in ("visit too frequently", "authkey", "过期", "接口", "retcode", "拉取失败"))
