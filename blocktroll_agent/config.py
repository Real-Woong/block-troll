# 5. 설정

import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(PROJECT_ROOT, "models", "blocktroll-koelectra"))

# 멀티라벨 출력 순서(학습도 이 순서로 맞추기)
MODEL_LABELS = ["toxic", "spam", "taunt"]

# label threshold (초기값)
TH_SPAM = env_float("TH_SPAM", 0.65)
TH_TOXIC = env_float("TH_TOXIC", 0.55)
TH_TAUNT = env_float("TH_TAUNT", 0.60)
ENABLE_TAUNT = env_bool("ENABLE_TAUNT", False)

# local inference cache
CACHE_MAXSIZE = env_int("CACHE_MAXSIZE", 2048)
