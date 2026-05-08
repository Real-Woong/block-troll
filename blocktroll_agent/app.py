# 2. 요청 처리 + 판단 흐름

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
from .schemas import ClassifyRequest, ClassifyResponse
from cachetools import LRUCache
from .config import TH_SPAM, TH_TOXIC, TH_TAUNT, MODEL_DIR, CACHE_MAXSIZE, ENABLE_TAUNT
from .rules import normalize, is_positive_laughter, has_negative_cues, rule_scores
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
_classify_cache: LRUCache[str, Dict[str, Any]] = LRUCache(maxsize=CACHE_MAXSIZE)

def decide_label(scores: Dict[str, float]) -> tuple[str, float]:
    spam  = scores.get("spam", 0.0)
    toxic = scores.get("toxic", 0.0)
    taunt = scores.get("taunt", 0.0) if ENABLE_TAUNT else 0.0

    if spam >= TH_SPAM:
        return "SPAM", spam
    if toxic >= TH_TOXIC:
        return "TOXIC", toxic
    if taunt >= TH_TAUNT:
        return "TAUNT", taunt
    return "OK", max(spam, toxic, taunt)

def merge_hybrid_scores(
    model_scores: Dict[str, float],
    rule_scores_map: Dict[str, float],
    *,
    rule_toxic_raw: float = 0.0,
    positive_guard: bool = False,
    negative_guard: bool = False,
) -> Dict[str, float]:
    """Combine model + rule outputs for local inference.

    Current project reality:
    - model is most useful for toxic/hate-style meaning
    - rules are still stronger for spam/url patterns and simple taunt cues
    """
    toxic = max(model_scores.get("toxic", 0.0), rule_scores_map.get("toxic", 0.0))

    # For the current MVP, do not trust model-only toxic predictions unless
    # the text also contains a strong rule hit or obvious negative wording.
    if rule_toxic_raw < 0.7 and not negative_guard:
        toxic = min(toxic, TH_TOXIC - 0.05)

    # Positive comments should be even harder to push into TOXIC.
    if positive_guard and rule_scores_map.get("toxic", 0.0) == 0.0:
        toxic = min(toxic, TH_TOXIC - 0.05)

    return {
        "toxic": toxic,
        "spam": rule_scores_map.get("spam", 0.0),
        "taunt": rule_scores_map.get("taunt", 0.0) if ENABLE_TAUNT else 0.0,
    }


def classify_one_text(text: str) -> tuple[Dict[str, Any], bool]:
    cached = _classify_cache.get(text)
    if cached is not None:
        return cached, True

    if m.MODEL_READY:
        try:
            model_scores = m.predict_scores([text])[0]
            rule_based_scores, raw, rule_reasons = rule_scores(text)
            normalized = normalize(text)
            positive_guard = is_positive_laughter(normalized)
            negative_guard = has_negative_cues(normalized)
            scores = merge_hybrid_scores(
                model_scores,
                rule_based_scores,
                rule_toxic_raw=raw.get("toxic", 0.0),
                positive_guard=positive_guard,
                negative_guard=negative_guard,
            )
            label, score = decide_label(scores)
            result = {
                "label": label,
                "score": score,
                "scores": scores,
                "raw": {
                    "model": model_scores,
                    "rules": raw,
                },
                "reasons": {
                    "model": ["transformers"],
                    "rules": rule_reasons,
                    "strategy": [
                        "hybrid:max-toxic+rule-spam-taunt",
                        "positive-guard" if positive_guard else "default",
                        "negative-cue" if negative_guard else "no-negative-cue",
                    ],
                    "cache": ["miss"],
                },
            }
            _classify_cache[text] = result
            return result, False
        except Exception as e:
            print("[BlockTroll] Hybrid inference failed, fallback to rules:", repr(e), flush=True)

    scores, raw, reasons = rule_scores(text)
    label, score = decide_label(scores)
    result = {
        "label": label,
        "score": score,
        "scores": scores,
        "raw": raw,
        "reasons": {
            **reasons,
            "cache": ["miss"],
        },
    }
    _classify_cache[text] = result
    return result, False

@app.get("/health")
def health():
    return {
        "ok": True,
        "model_ready": m.MODEL_READY,
        "model_dir": MODEL_DIR,
        "taunt_enabled": ENABLE_TAUNT,
        "cache_size": len(_classify_cache),
        "cache_maxsize": CACHE_MAXSIZE,
    }

@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> Dict[str, Any]:
    texts = req.texts or []
    print("[DBG] incoming texts:", texts, flush=True)
    results = []

    if not texts:
        return {"results": results}

    for t in texts:
        result, cache_hit = classify_one_text(t)
        if result.get("reasons"):
            result = {
                **result,
                "reasons": {
                    **result["reasons"],
                    "cache": ["hit" if cache_hit else "miss"],
                },
            }
        results.append(result)

    return {"results": results}
