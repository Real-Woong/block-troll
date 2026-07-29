# KoELECTRA 재학습 가이드 (RTX 2060 / Windows)

이 문서는 `models/blocktroll-koelectra`를 K-MHaS + BlockTroll handmade 데이터(현재
800개, 라벨당 200개)로 재학습할 때 그대로 따라할 수 있는 실행 가이드다. 실행 자체는
Windows + RTX 2060 환경에서 진행한다. Mac은 서버/확장/규칙 개발용이며 학습에는
쓰지 않는다.

관련 코드:
- `train/build_dataset.py` : K-MHaS + handmade JSON -> 학습용 JSONL
- `train/train_multilabel.py` : Hugging Face Trainer 기반 멀티라벨 학습
- `train/evaluate_rules.py` : **규칙 엔진 전용** 평가 스크립트 (모델은 평가하지 않음)
- `datasets/handmade/Blocktroll_dataset.json` : hate/ad/sarcasm/normal 800개

## 0. 사전 점검

- 이 레포를 최신 상태로 pull해서 `datasets/handmade/Blocktroll_dataset.json`이
  800개(라벨당 200개)인지 확인한다.
  ```powershell
  python -c "import json; d=json.load(open('datasets/handmade/Blocktroll_dataset.json',encoding='utf-8')); print(len(d))"
  ```
  `800`이 아니면 최신 커밋을 못 받은 것이니 먼저 `git pull`부터 한다.
- K-MHaS 원본 텍스트(`kmhas_train.txt`, `kmhas_valid.txt`, `kmhas_test.txt`)를
  준비한다. 이 레포에는 포함돼 있지 않다.

## 1. Python 환경 준비

이 프로젝트는 macOS에서는 공용 venv(`~/Desktop/project/Project_AI/_venvs/ai`)만
쓰는 규칙이지만, 그건 macOS 개발용 규칙이다. Windows 학습 머신에서는 별도의
학습 전용 가상환경을 만든다.

```powershell
python -m venv .venv-train
.venv-train\Scripts\activate
```

### 1-1. CUDA PyTorch 먼저 설치

`requirements.txt`에 박혀 있는 `torch==2.10.0`을 그냥 `pip install -r requirements.txt`로
설치하면 Windows에서는 기본적으로 **CPU 전용 빌드**가 깔릴 수 있다. CUDA 빌드를
반드시 먼저(또는 나중에 강제로 덮어써서) 설치한다.

1. https://pytorch.org/get-started/locally/ 에서 OS=Windows, Package=Pip,
   Compute Platform=CUDA(설치된 NVIDIA 드라이버가 지원하는 버전)를 선택해
   나오는 설치 명령을 실행한다. 버전 태그(cu121/cu124 등)는 위 페이지 기준이
   requirements.txt의 `torch==2.10.0`보다 항상 정확하다.
2. 이어서 나머지 의존성을 설치한다.
   ```powershell
   pip install -r requirements.txt
   ```
3. 2번이 torch를 CPU 빌드로 다시 덮어썼다면, 1번 명령을 `--force-reinstall --no-deps`
   옵션과 함께 다시 실행해서 CUDA 빌드로 되돌린다.

### 1-2. CUDA 인식 확인 (필수)

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

`True GeForce RTX 2060`처럼 나와야 한다. `False`가 나온 채로 학습을 돌리면
CPU로 실행되며 수십 배 느려진다.

## 2. 데이터셋 빌드

```powershell
python train/build_dataset.py --input-dir "D:\datasets\kmhas" --output-dir "D:\datasets\blocktroll_generated"
```

- 출력: `kmhas_multilabel_train.jsonl`, `kmhas_multilabel_valid.jsonl`,
  `kmhas_multilabel_test.jsonl`
- 콘솔에 `[OK] train: N rows -> ...` 형태로 각 split 행 수가 찍힌다.
- **중요**: `build_dataset.py`는 K-MHaS에서 `toxic`만 채우고, `spam`/`taunt`는
  handmade 데이터에서만 온다(`train/build_dataset.py:51`, `HANDMADE_LABELS`).
  handmade가 800개로 늘었지만 K-MHaS 자체가 훨씬 크기 때문에, 아래처럼 라벨별
  포지티브 개수를 한 번 확인해두면 좋다.
  ```powershell
  python -c "
  import json
  from collections import Counter
  rows = [json.loads(l) for l in open(r'D:\datasets\blocktroll_generated\kmhas_multilabel_train.jsonl', encoding='utf-8')]
  c = Counter(tuple(r['labels']) for r in rows)
  print(len(rows), c)
  "
  ```
  `(0,1,0)`(spam)와 `(0,0,1)`(taunt) 조합이 최소 수백 건은 있어야 한다. 너무
  적으면(예: 수십 건) `train_multilabel.py`가 학습은 진행하지만 spam/taunt 헤드
  품질은 기대하기 어렵다 — 이 경우 handmade 데이터를 더 늘리는 게 우선이다.

## 3. 학습 실행

```powershell
$env:BLOCKTROLL_DATA_DIR="D:\datasets\blocktroll_generated"
$env:BLOCKTROLL_MODEL_DIR="$PWD\models\blocktroll-koelectra"
$env:BLOCKTROLL_EPOCHS="3"
python train/train_multilabel.py
```

- 베이스 모델: `monologg/koelectra-small-v3-discriminator` (small이라 RTX 2060
  6GB에서도 기본 `per_device_train_batch_size=8`로 무리 없이 돌아가는 편이다).
- 시작하자마자 `[Device] cuda = True mps = False`, `[CUDA] NVIDIA GeForce RTX 2060`이
  찍히는지 확인한다. `cuda = False`면 1-2단계로 돌아간다.
- `[Train positives] {'toxic': ..., 'spam': ..., 'taunt': ...}`가 찍힌다. 셋 다
  0보다 커야 학습이 진행된다(`train/train_multilabel.py:71` `assert_positive_examples`
  — 0인 라벨이 있으면 여기서 바로 에러를 내고 멈춘다).
- 에폭마다 `eval_strategy="epoch"` 설정에 따라 `toxic_precision/recall/f1`,
  `spam_precision/recall/f1`, `taunt_precision/recall/f1`이 출력된다.
  `metric_for_best_model="toxic_f1"` 기준으로 가장 좋은 체크포인트가
  `load_best_model_at_end=True`로 최종 저장된다.
- 완료되면 `models/blocktroll-koelectra/`에 `config.json`, `model.safetensors`(또는
  `pytorch_model.bin`), 토크나이저 파일이 저장된다.

### 소요 시간 감 잡기

정확한 소요 시간은 K-MHaS 데이터 크기와 RTX 2060 클럭에 따라 달라 미리 단정하지
않는다. 대신 `logging_steps=100`으로 100 step마다 로그가 찍히므로, 학습 시작 후
`tqdm` 진행바의 `it/s`(초당 step)를 보고
`전체 step 수 = (train 행 수 / 8) * epoch 수`
로 총 소요 시간을 직접 역산하는 게 제일 정확하다.

## 4. 학습 결과 검증 (모델을 켜기 전에 반드시)

`train/evaluate_rules.py`는 규칙 엔진만 평가하므로 모델 품질 확인에는 쓸 수 없다.
아래 두 가지로 직접 확인한다.

### 4-1. Trainer가 찍는 지표부터 본다

마지막 epoch의 `toxic_f1`, `toxic_precision`이 특히 중요하다(PROJECT_ARCHIVE.md에
기록된 기존 문제가 "모델이 일반 감탄/구어체를 toxic으로 과대평가"였다 —
precision이 낮으면 이 문제가 재발했다는 뜻).

### 4-2. 하드 네거티브로 수동 스팟체크

`datasets/handmade/Blocktroll_dataset.json`의 normal 카테고리에는 일부러
"미친 퀄리티", "존나 웃기다", "ㅋㅋㅋ" 같은 표현을 넣어뒀다. 학습 직후 아래 스크립트로
이런 문장들의 확률이 낮게 나오는지 먼저 확인한 뒤 Mac으로 옮긴다.

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_dir = "models/blocktroll-koelectra"
tok = AutoTokenizer.from_pretrained(model_dir)
model = AutoModelForSequenceClassification.from_pretrained(model_dir)
model.eval()

samples = [
    "미친 퀄리티 대박이에요",       # normal (오탐 나면 안 됨)
    "존나 웃기다 ㅋㅋㅋ 이 장면",    # normal (오탐 나면 안 됨)
    "시발 진짜 짜증나",             # hate -> toxic 높아야 함
    "카톡 문의 주시면 안내드릴게요", # ad -> spam 높아야 함
    "역시 대단하시네요 진심으로",    # sarcasm -> taunt 다소 높아도 됨
]
enc = tok(samples, padding=True, truncation=True, max_length=128, return_tensors="pt")
with torch.no_grad():
    probs = torch.sigmoid(model(**enc).logits)
for s, p in zip(samples, probs):
    print(s, dict(zip(["toxic", "spam", "taunt"], (round(x, 3) for x in p.tolist()))))
```

`미친 퀄리티`, `존나 웃기다` 문장의 `toxic` 확률이 0.5 이상으로 나오면, 아직
데이터/학습 구조상 감탄형 표현을 못 거른다는 뜻이니 이 모델을 바로 `ENABLE_MODEL=true`로
켜지 말고 handmade 데이터를 더 보강한 뒤 재학습하는 걸 권장한다.

## 5. Mac으로 모델 옮기기

1. 검증을 통과한 `models/blocktroll-koelectra/` 폴더 전체(`config.json`,
   `tokenizer.json`, `tokenizer_config.json`, `model.safetensors` 등)를 Mac의
   동일 경로로 복사한다.
2. Mac의 `.env`에서 `ENABLE_MODEL=true`로 바꾼다.
3. 서버 재시작 후 확인:
   ```bash
   curl http://127.0.0.1:8787/health
   ```
   `model_enabled=true`, `model_ready=true`가 나와야 정상 로드된 것이다.
   `model_ready=false`면 `MODEL_DIR` 경로나 필수 파일 누락을 의심한다
   (`blocktroll_agent/model.py`의 `_has_weights` 체크).

## 6. 참고 — 현재 하이브리드 로직이 모델 점수를 누르는 방식

`blocktroll_agent/app.py`의 `merge_hybrid_scores`는 규칙 기반 toxic 원점수(`rule_toxic_raw`)가
0.7 미만이고 강한 부정 단서도 없으면, 모델이 아무리 toxic을 확신해도 점수를
`TH_TOXIC - 0.05` 아래로 눌러버린다. 즉 **현재 구조에서는 모델 단독으로는 TOXIC 라벨이
거의 나오지 않는다** — 규칙이 이미 강하게 동의해야 최종 TOXIC이 된다. 이는 의도된
안전장치이므로, 재학습한 모델의 실제 기여도를 체감하려면 4-2단계처럼 모델 확률
자체를 직접 찍어보는 방법이 하이브리드 결과보다 더 정확하다.

## 7. 트러블슈팅

| 증상 | 원인/조치 |
|---|---|
| `torch.cuda.is_available()`가 `False` | CPU 전용 torch가 깔림. 1-1단계의 CUDA 인덱스로 `--force-reinstall --no-deps` 재설치 |
| `assert_positive_examples`에서 `ValueError` | handmade JSON의 `label` 철자가 `normal/hate/ad/sarcasm`과 정확히 일치하는지, `build_dataset.py`가 최신 800개 파일을 읽었는지 확인 |
| 학습 중 CUDA OOM | `train/train_multilabel.py`의 `per_device_train_batch_size`를 8 → 4로 낮추고 `gradient_accumulation_steps`를 늘려 유효 배치 크기를 유지 |
| `model_ready=false` (Mac) | `models/blocktroll-koelectra/`에 `config.json`과 `model.safetensors`(또는 `pytorch_model.bin`)가 실제로 있는지, `MODEL_DIR` 경로가 맞는지 확인 |
| 재학습 후에도 "미친 퀄리티" 같은 문장이 toxic으로 나옴 | 모델/데이터 문제. `ENABLE_MODEL=true`로 켜지 말고 handmade normal 카테고리(하드 네거티브)를 더 늘려 재학습 |
