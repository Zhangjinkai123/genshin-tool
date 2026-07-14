from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .artifacts import normalize_artifacts, summarize_artifacts
from .characters import analyze_characters
from .config import APP_HOST, APP_NAME, APP_PORT, DEFAULT_ARTIFACTS_PATH, DEFAULT_WISHES_PATH, MAX_BODY_BYTES, STATIC_DIR, ensure_directories
from .recipes import account_from_good, calculate as calculate_training, recipe_status, update_recipes
from .storage import clear_cache, load_bundle, read_json, save_bundle
from .wishes import analyze_wishes, fetch_wishes_from_url, normalize_wishes


class GenshinToolHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.route("GET")

    def do_POST(self) -> None:
        self.route("POST")

    def do_DELETE(self) -> None:
        self.route("DELETE")

    def log_message(self, format: str, *args: object) -> None:
        return

    def route(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            if path == "/" and method == "GET":
                self.serve_static("index.html")
            elif path.startswith("/static/") and method == "GET":
                self.serve_static(path.replace("/static/", "", 1))
            elif path == "/api/health" and method == "GET":
                self.send_json({"ok": True, "name": APP_NAME})
            elif path == "/api/wishes/default" and method == "GET":
                self.send_json(default_wishes())
            elif path == "/api/artifacts/default" and method == "GET":
                self.send_json(default_artifacts())
            elif path == "/api/characters/default" and method == "GET":
                self.send_json(default_characters())
            elif path == "/api/training/default" and method == "GET":
                self.send_json(default_training())
            elif path == "/api/training/analyze" and method == "POST":
                body = self.read_json()
                self.send_json(account_from_good(body.get("records")))
            elif path == "/api/training/calculate" and method == "POST":
                body = self.read_json()
                self.send_json(calculate_training(body.get("records"), body.get("characterKey", ""), body.get("characterTarget", 0), body.get("talents", {}), body.get("weaponKey", ""), body.get("weaponTarget", 0), body.get("travelerElement", "")))
            elif path == "/api/training/recipes" and method == "GET":
                self.send_json(recipe_status())
            elif path == "/api/training/recipes/update" and method == "POST":
                self.send_json(update_recipes())
            elif path == "/api/wishes/analyze" and method == "POST":
                body = self.read_json()
                normalized = normalize_wishes(body.get("records"), body.get("uid", ""), body.get("featuredItems"))
                summary = analyze_wishes(normalized["records"])
                self.send_json({**normalized, "summary": summary})
            elif path == "/api/wishes/fetch" and method == "POST":
                body = self.read_json()
                self.send_json(fetch_wishes_from_url(body.get("url", ""), body.get("uid", ""), body.get("maxPages", 50), body.get("featuredItems")))
            elif path == "/api/artifacts/analyze" and method == "POST":
                body = self.read_json()
                normalized = normalize_artifacts(body.get("records"), body.get("uid", ""))
                summary = summarize_artifacts(normalized["records"])
                self.send_json({**normalized, "summary": summary})
            elif path == "/api/characters/analyze" and method == "POST":
                body = self.read_json()
                self.send_json(analyze_characters(body.get("records")))
            elif path == "/api/cache" and method == "GET":
                uid = _query_one(query, "uid")
                self.send_json(load_bundle(uid))
            elif path == "/api/cache/wishes" and method == "POST":
                body = self.read_json()
                save_bundle(body.get("uid", ""), "wishes", body.get("records", []), body.get("summary", {}))
                self.send_json({"ok": True})
            elif path == "/api/cache/artifacts" and method == "POST":
                body = self.read_json()
                save_bundle(body.get("uid", ""), "artifacts", body.get("records", []), body.get("summary", {}))
                self.send_json({"ok": True})
            elif path == "/api/cache" and method == "DELETE":
                self.send_json(clear_cache(_query_one(query, "uid", required=False)))
            else:
                self.send_error_json("接口不存在。", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_error_json(f"服务处理失败：{exc}", HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, name: str) -> None:
        target = (STATIC_DIR / name).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists():
            self.send_error_json("文件不存在。", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("请求内容过大。")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: HTTPStatus) -> None:
        self.send_json({"error": message}, status)


def _query_one(query: dict[str, list[str]], name: str, required: bool = True) -> str:
    value = (query.get(name) or [""])[0].strip()
    if required and not value:
        raise ValueError(f"缺少查询参数：{name}")
    return value


def default_wishes() -> dict:
    payload = read_json(DEFAULT_WISHES_PATH)
    if not isinstance(payload, dict):
        raise ValueError("默认抽卡数据不可用。")
    uid = default_account_uid()
    normalized = normalize_wishes(payload, uid)
    return {
        **normalized,
        "summary": analyze_wishes(normalized["records"]),
        "account": {"uid": uid},
    }


def default_artifacts() -> dict:
    payload = read_json(DEFAULT_ARTIFACTS_PATH)
    if not isinstance(payload, dict):
        raise ValueError("默认圣遗物数据不可用。")
    uid = default_account_uid()
    normalized = normalize_artifacts(payload, uid)
    return {
        **normalized,
        "summary": summarize_artifacts(normalized["records"]),
        "account": {"uid": uid},
    }


def default_characters() -> dict:
    payload = read_json(DEFAULT_ARTIFACTS_PATH)
    if not isinstance(payload, dict):
        raise ValueError("默认角色数据不可用。")
    return analyze_characters(payload)


def default_training() -> dict:
    payload = read_json(DEFAULT_ARTIFACTS_PATH)
    if not isinstance(payload, dict):
        raise ValueError("默认角色数据不可用。")
    return {**account_from_good(payload), "records": payload}


def default_account_uid() -> str:
    payload = read_json(DEFAULT_WISHES_PATH, {})
    info = payload.get("info") if isinstance(payload, dict) else None
    return str(info.get("uid") or "").strip() if isinstance(info, dict) else ""


def run() -> None:
    ensure_directories()
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), GenshinToolHandler)
    print(f"{APP_NAME} running at http://{APP_HOST}:{APP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
