import os
from typing import List, Dict
from .config import MODEL_DIR, MODEL_LABELS

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
    import torch

    enc = _tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
    enc = {k: v.to(_device) for k, v in enc.items()}

    with torch.no_grad():
        out = _model(**enc)
        probs = torch.sigmoid(out.logits).detach().cpu().numpy()

    res = []
    for row in probs:
        res.append({MODEL_LABELS[i]: float(row[i]) for i in range(len(MODEL_LABELS))})
    return res