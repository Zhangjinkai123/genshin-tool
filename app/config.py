from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "Genshin Personal Analyzer"
APP_HOST = os.getenv("GENSHIN_TOOL_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("GENSHIN_TOOL_PORT", "8787"))
MAX_BODY_BYTES = int(os.getenv("GENSHIN_TOOL_MAX_BODY_BYTES", str(20 * 1024 * 1024)))

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "app" / "static"
DATA_DIR = ROOT_DIR / "data"
DEFAULT_WISHES_PATH = DATA_DIR / "default-wishes.json"
DEFAULT_ARTIFACTS_PATH = DATA_DIR / "default-artifacts.json"
WISH_DIR = DATA_DIR / "wishes"
ARTIFACT_DIR = DATA_DIR / "artifacts"
CACHE_DIR = DATA_DIR / "cache"
TRAINING_RECIPES_PATH = DATA_DIR / "training-recipes.json"


def ensure_directories() -> None:
    for path in (STATIC_DIR, WISH_DIR, ARTIFACT_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
