"""Evaluate the rule-based BlockTroll classifier against the handmade dataset.

Usage:
    python train/evaluate_rules.py
    python train/evaluate_rules.py --show-mistakes 0
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from blocktroll_agent.rules import rule_scores
from blocktroll_agent.config import TH_TOXIC, TH_SPAM, TH_TAUNT

DEFAULT_DATASET = ROOT / "datasets" / "handmade" / "Blocktroll_dataset.json"

# Handmade dataset labels -> BlockTroll decision labels.
LABEL_TO_GOLD = {
    "hate": "TOXIC",
    "ad": "SPAM",
    "sarcasm": "TAUNT",
    "normal": "OK",
}
LABELS = ["TOXIC", "SPAM", "TAUNT", "OK"]


def decide(scores: dict, th_toxic: float, th_spam: float, th_taunt: float) -> str:
    # Mirrors blocktroll_agent.app.decide_label, but always evaluates TAUNT
    # regardless of ENABLE_TAUNT so this script can gauge rule quality
    # independent of the current production toggle.
    if scores.get("spam", 0.0) >= th_spam:
        return "SPAM"
    if scores.get("toxic", 0.0) >= th_toxic:
        return "TOXIC"
    if scores.get("taunt", 0.0) >= th_taunt:
        return "TAUNT"
    return "OK"


def evaluate(rows, th_toxic, th_spam, th_taunt):
    confusion = defaultdict(Counter)  # gold -> pred -> count
    by_difficulty = defaultdict(lambda: defaultdict(Counter))
    mistakes = []

    for row in rows:
        gold = LABEL_TO_GOLD.get(str(row.get("label", "")).strip().lower())
        text = str(row.get("text", "")).strip()
        if gold is None or not text:
            continue

        scores, _raw, _reasons = rule_scores(text)
        pred = decide(scores, th_toxic, th_spam, th_taunt)
        confusion[gold][pred] += 1

        difficulty = row.get("difficulty", "unknown")
        by_difficulty[difficulty][gold][pred] += 1

        if pred != gold:
            mistakes.append((gold, pred, text))

    return confusion, by_difficulty, mistakes


def precision_recall_f1(confusion):
    metrics = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in LABELS if g != label)
        fn = sum(confusion[label][p] for p in LABELS if p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        metrics[label] = (precision, recall, f1, tp, fp, fn)
    return metrics


def print_report(confusion, by_difficulty, mistakes, show_mistakes):
    print("=== Confusion (rows = gold, cols = predicted) ===")
    print("gold\\pred".ljust(10) + "".join(l.ljust(8) for l in LABELS))
    for gold in LABELS:
        row = gold.ljust(10) + "".join(str(confusion[gold][p]).ljust(8) for p in LABELS)
        print(row)

    print("\n=== Precision / Recall / F1 (overall) ===")
    metrics = precision_recall_f1(confusion)
    for label, (p, r, f1, tp, fp, fn) in metrics.items():
        print(f"{label:<6} precision={p:.3f} recall={r:.3f} f1={f1:.3f}  (tp={tp} fp={fp} fn={fn})")

    total = sum(sum(c.values()) for c in confusion.values())
    correct = sum(confusion[l][l] for l in LABELS)
    if total:
        print(f"\nOverall accuracy: {correct}/{total} = {correct/total:.3f}")
    else:
        print("\nNo rows evaluated")

    print("\n=== Per-difficulty accuracy ===")
    for difficulty in ("easy", "medium", "hard"):
        conf = by_difficulty.get(difficulty)
        if not conf:
            continue
        d_total = sum(sum(c.values()) for c in conf.values())
        d_correct = sum(conf[l][l] for l in LABELS)
        if d_total:
            print(f"{difficulty:<8} {d_correct}/{d_total} = {d_correct/d_total:.3f}")

    if show_mistakes:
        print(f"\n=== Misclassified samples ({len(mistakes)} total, showing up to {show_mistakes}) ===")
        for gold, pred, text in mistakes[:show_mistakes]:
            print(f"gold={gold:<6} pred={pred:<6} text={text}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--th-toxic", type=float, default=TH_TOXIC)
    parser.add_argument("--th-spam", type=float, default=TH_SPAM)
    parser.add_argument("--th-taunt", type=float, default=TH_TAUNT)
    parser.add_argument("--show-mistakes", type=int, default=20, help="max mistakes to print, 0 to hide")
    args = parser.parse_args()

    rows = json.loads(args.dataset.read_text(encoding="utf-8"))
    confusion, by_difficulty, mistakes = evaluate(rows, args.th_toxic, args.th_spam, args.th_taunt)
    print_report(confusion, by_difficulty, mistakes, args.show_mistakes)


if __name__ == "__main__":
    main()
