"""Build BlockTroll JSONL training files from K-MHaS and handmade samples."""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = Path(os.environ.get("KMHAS_DIR", ROOT / "datasets" / "raw" / "kmhas"))
DEFAULT_OUTPUT_DIR = Path(os.environ.get("BLOCKTROLL_DATA_DIR", ROOT / "datasets" / "generated"))
DEFAULT_HANDMADE_JSON = ROOT / "datasets" / "handmade" / "Blocktroll_dataset.json"

# BlockTroll head order used by the server.
LABELS = ["toxic", "spam", "taunt"]
KMHAS_NOT_HATE_LABEL = 8
HANDMADE_LABELS = {
    "normal": [0, 0, 0],
    "hate": [1, 0, 0],
    "ad": [0, 1, 0],
    "sarcasm": [0, 0, 1],
}


def parse_line(line: str) -> Tuple[str, List[int]]:
    """Parse one K-MHaS row into BlockTroll labels.

    K-MHaS uses label 8 for Not Hate Speech. Any other label is treated as a
    toxic signal for this first BlockTroll toxic head.
    """
    line = line.strip()
    if not line:
        return "", [0, 0, 0]

    parts = line.split("\t")
    if len(parts) >= 2:
        text = parts[0].strip()
        label_str = parts[1].strip()
    else:
        match = re.match(r"^(.*)\s+(\d+(?:,\d+)*)$", line)
        if not match:
            return "", [0, 0, 0]
        text = match.group(1).strip()
        label_str = match.group(2).strip()

    label_ids = [int(tok) for tok in re.split(r"[,\s]+", label_str) if tok.isdigit()]
    if not text or not label_ids or text.lower() in {"document", "text"}:
        return "", [0, 0, 0]

    toxic = int(any(label_id != KMHAS_NOT_HATE_LABEL for label_id in label_ids))
    return text, [toxic, 0, 0]


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def kmhas_rows(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            text, labels = parse_line(line)
            if text:
                yield {"text": text, "labels": labels}


def handmade_rows(path: Path, split: str) -> Iterable[dict]:
    if not path.exists():
        return

    rows = json.loads(path.read_text(encoding="utf-8"))
    for index, row in enumerate(rows):
        label = HANDMADE_LABELS.get(str(row.get("label", "")).strip().lower())
        text = str(row.get("text", "")).strip()
        if not label or not text:
            continue

        # Keep a deterministic 80/20 validation slice without another tool.
        row_split = "valid" if index % 5 == 0 else "train"
        if row_split == split:
            yield {"text": text, "labels": label}


def build_split(split: str, kmhas_path: Path, output_path: Path, handmade_path: Path) -> None:
    rows = list(kmhas_rows(kmhas_path))
    if split in {"train", "valid"}:
        rows.extend(handmade_rows(handmade_path, split))
    count = write_jsonl(output_path, rows)
    print(f"[OK] {split}: {count} rows -> {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory with kmhas_train.txt files.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated JSONL files.")
    parser.add_argument("--handmade-json", type=Path, default=DEFAULT_HANDMADE_JSON, help="Optional BlockTroll handmade JSON.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "valid", "test"):
        build_split(
            split,
            args.input_dir / f"kmhas_{split}.txt",
            args.output_dir / f"kmhas_multilabel_{split}.jsonl",
            args.handmade_json,
        )


if __name__ == "__main__":
    main()
