# train/train_multilabel.py
import os
from pathlib import Path
import numpy as np
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
import torch

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("BLOCKTROLL_DATA_DIR", ROOT / "datasets" / "generated"))
TRAIN_JSONL = DATA_DIR / "kmhas_multilabel_train.jsonl"
VALID_JSONL = DATA_DIR / "kmhas_multilabel_valid.jsonl"
OUT_MODEL_DIR = Path(os.environ.get("BLOCKTROLL_MODEL_DIR", ROOT / "models" / "blocktroll-koelectra"))

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
    preds = (probs >= 0.5).astype(int)
    metrics = {}

    for idx, label in enumerate(LABELS):
        true = labels[:, idx].astype(int)
        pred = preds[:, idx]
        tp = int(((pred == 1) & (true == 1)).sum())
        fp = int(((pred == 1) & (true == 0)).sum())
        fn = int(((pred == 0) & (true == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics[f"{label}_precision"] = precision
        metrics[f"{label}_recall"] = recall
        metrics[f"{label}_f1"] = f1
    return metrics


def assert_positive_examples(dataset) -> None:
    positive_counts = np.array(dataset["labels"]).sum(axis=0).astype(int)
    print("[Train positives]", dict(zip(LABELS, positive_counts.tolist())))
    missing = [label for label, count in zip(LABELS, positive_counts) if count == 0]
    if missing:
        raise ValueError(
            "Missing positive examples for "
            + ", ".join(missing)
            + ". Rebuild data with the handmade BlockTroll spam/taunt samples."
        )

def main():
    # Trainer uses CUDA automatically when a CUDA PyTorch build is installed.
    cuda = torch.cuda.is_available()
    mps = torch.backends.mps.is_available()
    print("[Device] cuda =", cuda, "mps =", mps)
    if cuda:
        print("[CUDA]", torch.cuda.get_device_name(0))

    ds = load_dataset("json", data_files={"train": str(TRAIN_JSONL), "validation": str(VALID_JSONL)})
    assert_positive_examples(ds["train"])
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
        id2label={idx: label for idx, label in enumerate(LABELS)},
        label2id={label: idx for idx, label in enumerate(LABELS)},
    )

    # 맥(MPS)에서는 fp16 비권장(불안정할 수 있음)
    args = TrainingArguments(
        output_dir=str(ROOT / "artifacts" / "runs" / "blocktroll-koelectra"),
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=int(os.environ.get("BLOCKTROLL_EPOCHS", "2")),
        weight_decay=0.01,
        seed=42,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=100,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="toxic_f1",
        greater_is_better=True,
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

    OUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(OUT_MODEL_DIR)
    tok.save_pretrained(OUT_MODEL_DIR)

    print(f"[OK] Saved model to: {OUT_MODEL_DIR}")
    print("Put this folder as MODEL_DIR in server (already). Restart uvicorn.")

if __name__ == "__main__":
    main()
