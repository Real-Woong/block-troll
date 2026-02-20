from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
from .schemas import ClassifyRequest, ClassifyResponse
from .config import TH_SPAM, TH_TOXIC, TH_TAUNT, MODEL_DIR
from .rules import rule_scores
from . import model as m

app = FastAPI(title="BlockTroll Local Agent", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용. 나중에 chrome-extension://ID로 좁혀도 됨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서버 시작 시 모델 로드 시도
m.load_model_if_available()

def decide_label(scores: Dict[str, float]) -> tuple[str, float]:
    spam  = scores.get("spam", 0.0)
    toxic = scores.get("toxic", 0.0)
    taunt = scores.get("taunt", 0.0)

    if spam >= TH_SPAM:
        return "SPAM", spam
    if toxic >= TH_TOXIC:
        return "TOXIC", toxic
    if taunt >= TH_TAUNT:
        return "TAUNT", taunt
    return "OK", max(spam, toxic, taunt)

@app.get("/health")
def health():
    return {"ok": True, "model_ready": m.MODEL_READY, "model_dir": MODEL_DIR}

@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> Dict[str, Any]:
    texts = req.texts or []

    results = []
    if m.MODEL_READY:
        scores_list = m.predict_scores(texts)
        for scores in scores_list:
            label, score = decide_label(scores)
            results.append({"label": label, "score": score, "scores": scores, "raw": None, "reasons": {"model": ["transformers"]}})
    else:
        for t in texts:
            scores, raw, reasons = rule_scores(t)
            label, score = decide_label(scores)
            results.append({"label": label, "score": score, "scores": scores, "raw": raw, "reasons": reasons})

    return {"results": results}