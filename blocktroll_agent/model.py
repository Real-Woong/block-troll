# 4. AI 모델 (미사용 상태)


import os
from typing import List, Dict
from .config import DEBUG, ENABLE_MODEL, MODEL_DIR, MODEL_LABELS

MODEL_READY = False
_tokenizer = None
_model = None
_device = None

def _has_weights(model_dir: str) -> bool:
    return (
        os.path.exists(os.path.join(model_dir, "model.safetensors"))
        or os.path.exists(os.path.join(model_dir, "pytorch_model.bin"))
    )

def load_model_if_available() -> bool:
    global MODEL_READY, _tokenizer, _model, _device

    if not ENABLE_MODEL:
        MODEL_READY = False
        return False
    if not os.path.isdir(MODEL_DIR):
        MODEL_READY = False
        return False
    if not os.path.exists(os.path.join(MODEL_DIR, "config.json")):
        MODEL_READY = False
        return False
    if not _has_weights(MODEL_DIR):
        MODEL_READY = False
        return False

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        _device = "mps" if torch.backends.mps.is_available() else "cpu"
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        _model.to(_device)
        _model.eval()
        MODEL_READY = True
        return True
    except Exception as e:
        print("[BlockTroll] Model load failed:", repr(e))
        MODEL_READY = False
        return False

def predict_scores(texts: List[str]) -> List[Dict[str, float]]:
    if DEBUG:
        print("[DBG] predict_scores called", flush=True)
    if not MODEL_READY or _tokenizer is None or _model is None or _device is None:
        raise RuntimeError("Model is not loaded. Call load_model_if_available() first.")

    import torch

    enc = _tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
    enc = {k: v.to(_device) for k, v in enc.items()}

    with torch.no_grad():
        out = _model(**enc)
        if DEBUG:
            print("[DBG] logits shape:", tuple(out.logits.shape))
            print("[DBG] id2label:", getattr(_model.config, "id2label", None))
            print("[DBG] label2id:", getattr(_model.config, "label2id", None), flush=True)
        logits = out.logits
        # (batch,) -> (batch, 1)
        if logits.dim() == 1:
            logits = logits.unsqueeze(-1)

        problem_type = getattr(_model.config, "problem_type", None)

        # Multi-label classification:
        # each label is an independent yes/no decision, so use sigmoid per label.
        if problem_type == "multi_label_classification":
            probs = torch.sigmoid(logits).detach().cpu().numpy()
        # Single-label multi-class:
        # labels compete with each other, so use softmax across labels.
        elif logits.size(-1) > 1:
            probs = torch.softmax(logits, dim=-1).detach().cpu().numpy()
        # Single-logit binary case.
        else:
            probs = torch.sigmoid(logits).detach().cpu().numpy()

        if DEBUG:
            for idx, row in enumerate(probs[:3]):
                print(f"[DBG] probs[{idx}]:", row, flush=True)

    res = []
    for row in probs:
        res.append({MODEL_LABELS[i]: float(row[i]) for i in range(len(MODEL_LABELS))})
    return res
