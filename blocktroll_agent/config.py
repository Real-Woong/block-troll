# 5. 설정

import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "blocktroll-koelectra")

# 멀티라벨 출력 순서(학습도 이 순서로 맞추기)
MODEL_LABELS = ["toxic", "spam", "taunt"]

# label threshold (초기값)
TH_SPAM  = 0.65
TH_TOXIC = 0.55
TH_TAUNT = 0.60