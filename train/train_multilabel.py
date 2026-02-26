# train/train_multilabel.py
import os
import numpy as np
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
import torch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
BAL_ART = os.path.join(ROOT, "artifacts_balanced")
TRAIN_JSONL = os.path.join(BAL_ART, "kmhas_multilabel_train.jsonl")
VALID_JSONL = os.path.join(BAL_ART, "kmhas_multilabel_valid.jsonl")
MODELS_DIR = os.path.join(ROOT, "models")
OUT_MODEL_DIR = os.path.join(MODELS_DIR, "blocktroll-koelectra")

# ✅ 맥북에서 “견딜” 베이스 모델(작은 KoELECTRA 권장)
# 필요하면 바꿔도 됨
BASE_MODEL = os.environ.get("BASE_MODEL", "monologg/koelectra-small-v3-discriminator")

LABELS = ["toxic", "spam", "taunt"]
NUM_LABELS = len(LABELS)

def data_collator(features):
    """Custom collator to force multi-label `labels` to float32.

    Some `datasets`/`set_format` pipelines may yield `labels` as int64 (torch.long),
    which breaks BCEWithLogitsLoss. We cast labels to float here.
    """
    batch = {}

    # Stack common tensor fields
    for k in ("input_ids", "attention_mask", "token_type_ids"):
        if k in features[0]:
            batch[k] = torch.stack([f[k] for f in features])

    # Force labels -> float32 [batch, num_labels]
    # `features[i]["labels"]` may already be a torch.Tensor; stack then cast.
    labels = [f["labels"] for f in features]
    labels = [l if isinstance(l, torch.Tensor) else torch.tensor(l) for l in labels]
    batch["labels"] = torch.stack(labels, dim=0).to(dtype=torch.float32)
    return batch

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = sigmoid(logits)
    # toxic만 우선 확인(0번)
    toxic_pred = (probs[:, 0] >= 0.5).astype(int)
    toxic_true = labels[:, 0].astype(int)
    acc = (toxic_pred == toxic_true).mean().item()
    return {"toxic_acc@0.5": acc}

def main():
    # device 확인
    mps = torch.backends.mps.is_available()
    print("[Device] mps =", mps)

    ds = load_dataset("json", data_files={"train": TRAIN_JSONL, "validation": VALID_JSONL})
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tok_fn(batch):
        enc = tok(batch["text"], truncation=True, max_length=128, padding="max_length")
        # labels: [toxic, spam, taunt]
        # BCEWithLogitsLoss는 float 라벨(0.0/1.0)을 기대함
        enc["labels"] = np.array(batch["labels"], dtype=np.float32)
        return enc

    ds = ds.map(tok_fn, batched=True, remove_columns=["text"])
    ds.set_format(type="torch")

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )

    # 맥(MPS)에서는 fp16 비권장(불안정할 수 있음)
    args = TrainingArguments(
        output_dir=os.path.join(ROOT, "artifacts", "runs"),
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=1,
        weight_decay=0.01,
        seed=42,
        eval_strategy="steps",
        eval_steps=500,
        save_steps=500,
        logging_steps=100,
        save_total_limit=2,
        load_best_model_at_end=False,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    os.makedirs(OUT_MODEL_DIR, exist_ok=True)
    trainer.save_model(OUT_MODEL_DIR)
    tok.save_pretrained(OUT_MODEL_DIR)

    print(f"[OK] Saved model to: {OUT_MODEL_DIR}")
    print("Put this folder as MODEL_DIR in server (already). Restart uvicorn.")

if __name__ == "__main__":
    main()