# train/build_dataset.py

import os, json, re
from typing import List, Tuple
from pathlib import Path

PROJECT_ROOT = Path.home() / "Desktop/project/Project_AI"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),  ".."))
DATA_DIR = PROJECT_ROOT / "datasets" / "Datasets-NLP" / "blocktroll_dataset"
FILES = {
    "train": os.path.join(DATA_DIR, "kmhas_train.txt"),
    "valid": os.path.join(DATA_DIR, "kmhas_valid.txt"),
    "test": os.path.join(DATA_DIR, "kmhas_test.txt")
}

OUT_DIR = os.path.join(ROOT, "../../datasets/Datasets-NLP/blocktroll_dataset")
os.makedirs(OUT_DIR, exist_ok=True)

# 멀티라벨 헤드 순서
# toxic만 1/0으로 만들고, spam/taunt는 일단 0으로 (blocktroll_agent/rules.py가 담당)
LABELS = ["toxic", "spam", "taunt"]


def parse_line(line: str) -> Tuple[str, List[int]]:
    """
    K-MHaS라인 파싱 (포맷이 약간 달라도 최대한 견딤)
    - 탭(\t) 기준이 많음: text \t label
    - label이 "0"또는 "0,3"같은 형태일 수 있음
    """
    line = line.strip()
    if not line:
        return "", [0,0,0]
    
    # 1) 우선 탭으로 분리 시도
    parts = line.split("\t")
    if len(parts) >= 2:
        text = parts[0].strip()
        label_str = parts[1].strip()
    else:
        #2) 탭이 없으면 마지막 토큰을 라벨로 가정(최후의 수단)
        m = re.match(r"^(.*)\s+(\d+(?:,\d+)*)$", line)
        if not m:
            return line.strip(), [0,0,0]
        text = m.group(1).strip()
        label_str = m.group(2).strip()

    # label_str 예: "0" / "0,3" / "1,2,4"
    label_ids = []
    for tok in re.split(r"[,\s]+", label_str):
        tok = tok.strip()
        if tok.isdigit():
            label_ids.append(int(tok))

    # 독하게 단순화: '0만 있으면 정상' 그 외 하나라도 있으면 toxic = 1
    # (K - MHaS가 혐오/독성 중심 데이터라 이게 가장 안정적인 1차 모델)
    toxic = 0 if (len(label_ids) == 0 or (len(label_ids) == 1 and label_ids[0] == 0 )) else 1

    # spam/taunt 는 데이터가 없으니 0 고정(blocktroll_agent/rules.py에서 처리)
    return text, [toxic, 0, 0]

def build(split: str, in_path: str, out_path:str):
    n = 0
    with open(in_path, "r", encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            text, y = parse_line(line)
            if not text:
                continue
            rec = {"text": text, "labels": y}
            f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"[OK] {split}: {n} rows -> {out_path}")

if __name__ == "__main__":
    build("train", FILES["train"], os.path.join(OUT_DIR, "kmhas_multilabel_train.jsonl"))
    build("valid", FILES["valid"], os.path.join(OUT_DIR, "kmhas_multilabel_valid.jsonl"))
    build("test",  FILES["test"],  os.path.join(OUT_DIR, "kmhas_multilabel_test.jsonl"))