"""BlockTroll 추론 스모크 테스트.

1) torch / MPS 가용성
2) 룰 기반 /classify 경로
3) 더미 KoELECTRA 가중치로 model.load_model_if_available() + predict_scores() 경로

3번은 무작위 초기화 모델을 임시 디렉터리에 저장해 쓴다. 분류 품질은 의미 없고,
"가중치가 들어왔을 때 로드/추론이 실제로 되는가"만 검증한다.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def step(msg):
    print(f"\n=== {msg} ===", flush=True)


step("1) torch / device")
import torch
print("torch      :", torch.__version__)
print("mps built  :", torch.backends.mps.is_built())
print("mps avail  :", torch.backends.mps.is_available())
device = "mps" if torch.backends.mps.is_available() else "cpu"
print("device     :", device)

step("2) 룰 기반 classify (현재 .env: ENABLE_MODEL=false)")
from blocktroll_agent import model as m
from blocktroll_agent.app import classify_one_text
from blocktroll_agent.config import ENABLE_MODEL, MODEL_DIR

print("ENABLE_MODEL:", ENABLE_MODEL, "| MODEL_READY:", m.MODEL_READY)
print("MODEL_DIR   :", MODEL_DIR)
for text in ["오늘 영상 진짜 재밌네요", "지금 바로 클릭 http://spam.example.com 무료 코인", "야 이 븅신아"]:
    result, _ = classify_one_text(text)
    print(f"  {result['label']:5s} {result['score']:.3f}  <- {text}")

step("3) 더미 가중치로 모델 로드 경로 검증")
from transformers import AutoTokenizer, ElectraConfig, ElectraForSequenceClassification

base = "monologg/koelectra-base-v3-discriminator"
tmp = tempfile.mkdtemp(prefix="blocktroll-dummy-")
try:
    # 토크나이저는 캐시/네트워크가 필요하므로 실패 시 건너뛴다.
    tok = AutoTokenizer.from_pretrained(base)
except Exception as e:
    print("토크나이저 다운로드 실패, 3번 건너뜀:", repr(e)[:120])
    sys.exit(0)

cfg = ElectraConfig.from_pretrained(base)
cfg.num_labels = 3
cfg.problem_type = "multi_label_classification"
cfg.id2label = {0: "toxic", 1: "spam", 2: "taunt"}
cfg.label2id = {v: k for k, v in cfg.id2label.items()}
ElectraForSequenceClassification(cfg).save_pretrained(tmp, safe_serialization=True)
tok.save_pretrained(tmp)
print("더미 모델 저장:", tmp)
print("파일:", sorted(os.listdir(tmp)))

# config를 우회해 MODEL_DIR만 임시로 바꿔 로드 경로를 태운다.
m.ENABLE_MODEL = True
m.MODEL_DIR = tmp
ok = m.load_model_if_available()
print("load_model_if_available ->", ok, "| MODEL_READY:", m.MODEL_READY, "| device:", m._device)

if ok:
    scores = m.predict_scores(["오늘 영상 진짜 재밌네요", "야 이 븅신아"])
    for s in scores:
        print("  predict_scores:", {k: round(v, 4) for k, v in s.items()})
    print("\n모델 로드/추론 경로 정상. 실제 가중치를 models/에 넣고 ENABLE_MODEL=true 하면 됩니다.")
