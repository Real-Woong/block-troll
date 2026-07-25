# BlockTroll Project Archive

이 문서는 BlockTroll 프로젝트를 다른 채팅/세션으로 넘길 때 바로 참고할 수 있도록 만든 상세 아카이브다.

목적:
- 프로젝트 전체 구조 파악
- 각 파일 역할 이해
- 최근 수정 내용 추적
- 현재 동작 방식과 남은 문제점 공유
- 다음 세션에서 오류 수정/구조 개선을 바로 이어가기

## 1. 프로젝트 한 줄 설명

BlockTroll은 유튜브 댓글을 로컬 환경에서 분석해 `TOXIC`, `SPAM`, `TAUNT` 성격을 판정하고, 크롬 확장에서 blur/hide 처리하는 로컬 AI 보조 필터 프로젝트다.

현재 실제 운영 방향:
- 클라우드 서비스보다는 `로컬 실행형 MVP`
- 사용자는 일반 대중보다 `유튜버 본인`
- 목표는 댓글 검수 시 멘탈 보호
- 무조건 삭제보다 `강도 조절`이 중요

현재 권장 운영 모드:
- `TOXIC + SPAM` 중심
- `TAUNT`는 오탐이 많아 기본 비활성화

## 2. 현재 실행 구조

흐름:

1. YouTube 페이지에서 크롬 확장이 댓글 DOM을 읽음
2. `blocktroll_extension/content.js`가 댓글 텍스트를 수집
3. 로컬 FastAPI 서버 `POST /classify`로 전송
4. 서버 `blocktroll_agent/app.py`가 모델 + 규칙 기반 판단 수행
5. 결과 JSON 반환
6. 확장이 댓글을 blur/hide 또는 그대로 유지

## 3. 실제 실행 환경 규칙

중요:
- 이 프로젝트 폴더 안에 `.venv`를 만들면 안 됨
- 공용 AI 가상환경만 사용

공용 환경:
- `~/Desktop/project/Project_AI/_venvs/ai`

활성화:

```bash
source ~/Desktop/project/Project_AI/_venvs/ai/bin/activate
```

서버 실행:

```bash
python -m uvicorn blocktroll_agent.app:app --host 127.0.0.1 --port 8787 --reload
```

헬스체크:

```bash
curl http://127.0.0.1:8787/health
```

크롬 확장 로드:
- `chrome://extensions`
- 개발자 모드 ON
- `blocktroll_extension/` 폴더 로드

## 4. 상위 디렉터리 구조

### 루트 파일

- `README.md`
  - 실행 방법, 공용 venv 규칙, 환경 설정, 전체 흐름 설명

- `.env.example`
  - 환경설정 샘플
  - `MODEL_DIR`, `TH_TOXIC`, `TH_SPAM`, `TH_TAUNT`, `ENABLE_TAUNT`, `CACHE_MAXSIZE`

- `requirements.txt`
  - Python 의존성 목록

- `blocktroll_FW.html`
  - 프로젝트 설명/시연용 HTML 프레임워크 파일

- `Structure.txt`, `ModuleInfo.txt`
  - 초기 구조 메모성 파일

## 5. Python 서버 구조

### `blocktroll_agent/__init__.py`
- 패키지 초기화 파일
- 특별한 로직은 거의 없음

### `blocktroll_agent/config.py`
역할:
- 환경변수/`.env` 기반 설정 관리

중요 설정:
- `MODEL_DIR`
- `MODEL_LABELS`
- `TH_TOXIC`, `TH_SPAM`, `TH_TAUNT`
- `ENABLE_TAUNT`
- `CACHE_MAXSIZE`

핵심 포인트:
- 공용 코드 수정 없이 `.env`로 threshold 조절 가능
- `ENABLE_TAUNT=false`가 현재 기본 방향

### `blocktroll_agent/schemas.py`
역할:
- FastAPI 요청/응답 스키마 정의

핵심 클래스:
- `ClassifyRequest`
- `OneResult`
- `ClassifyResponse`

### `blocktroll_agent/model.py`
역할:
- 학습된 KoELECTRA 분류 모델 로딩
- 댓글 리스트를 입력받아 라벨 점수 예측

현재 특징:
- `MODEL_READY` 상태 관리
- 모델 파일 존재 시 로드 시도
- `problem_type == multi_label_classification`이면 `sigmoid` 사용

중요 수정 이력:
- 과거 softmax 사용 문제를 수정함
- 현재 멀티라벨일 때는 `sigmoid` 사용이 맞음

현재 한계:
- 모델이 일반 한국어 감탄/비속어를 toxic으로 과하게 보는 경향이 있음
- 학습 데이터 구조 자체 문제 가능성이 큼

### `blocktroll_agent/rules.py`
역할:
- 규칙 기반 독성/스팸/비꼼 판단

구성:
- `BAD_WORDS`: 욕설 단어 사전
- `TOXIC_PATTERNS`: 조합형 욕설 패턴
- `SPAM_PATTERNS`: 광고/문의/링크 유도 패턴
- `TAUNT_SIGNALS`: 비꼼/조롱 신호
- `POSITIVE_WORDS`, `POSITIVE_EMOJI_RE`: 긍정 문맥 감지
- `NEGATIVE_CUES`: 강한 부정 단서

주요 함수:
- `normalize`
- `score_toxic`
- `score_spam`
- `score_taunt`
- `rule_scores`

최근 핵심 수정:
- `미친` 단독 단어를 욕설 사전에서 제거
- `미친놈`, `미친 새끼`, `미쳤냐` 같은 조합만 별도 패턴으로 처리
- `존나` 가중치 크게 낮춤
- `!!!`, `???`, `...` 같은 문장부호만으로 toxic 점수 올리지 않도록 완화
- 긍정 문맥이면 toxic/taunt 완화

현재 의도:
- 한국어 감탄형 비속어 오탐 줄이기
- 강한 욕설만 더 확실히 잡기

### `blocktroll_agent/app.py`
역할:
- FastAPI 앱 본체
- `/health`, `/classify`
- 모델 점수 + 규칙 점수의 하이브리드 결합

핵심 동작:
- 서버 시작 시 모델 로드 시도
- `LRUCache` 기반 댓글 결과 캐시 유지
- 각 텍스트마다:
  - 모델 점수 계산
  - 규칙 점수 계산
  - 긍정/부정 문맥 가드 적용
  - 최종 라벨 결정

중요 함수:
- `decide_label`
- `merge_hybrid_scores`
- `classify_one_text`
- `health`
- `classify`

최근 핵심 수정:
- 하이브리드 로직 추가
- 캐시 추가
- 긍정 댓글이 모델 단독 toxic으로 가는 것 방지
- rule toxic 근거가 약하면 모델 toxic을 과신하지 않도록 조정
- `ENABLE_TAUNT=false`면 서버에서도 TAUNT 무시

현재 분류 철학:
- `spam`: 규칙 기반 비중 큼
- `toxic`: 모델 + 규칙
- `taunt`: 현재 기본 비활성화

## 6. 크롬 확장 구조

### `blocktroll_extension/manifest.json`
역할:
- MV3 확장 메타데이터
- 권한/호스트/스크립트 등록

### `blocktroll_extension/content.js`
역할:
- 유튜브 댓글 수집
- 서버에 `/classify` 요청
- 결과에 따라 blur/hide UI 적용

중요 기능:
- `DEFAULTS` 설정
- chrome storage 로드
- 강도(intensity) -> threshold 변환
- `decideAction`으로 `NONE / SOFT / HARD` 결정
- DOM 래핑 및 배지 표시
- 클릭 시 reveal/hide 토글
- `MutationObserver` + interval 기반 스캔

현재 threshold 로직:
- `낮음`: `soft=0.70`, `hard=0.85`
- `보통`: `soft=0.60`, `hard=0.75`
- `높음`: `soft=0.50`, `hard=0.65`

주의점:
- 옵션 페이지에서 직접 threshold 저장 시 `useCustomThresholds=true`
- 이때 팝업 intensity보다 직접 threshold가 우선

### `blocktroll_extension/popup.html`
역할:
- 확장 팝업 UI

최근 수정:
- 서버 연결 상태 표시
- 모델 ON/OFF 표시
- 현재 강도 표시
- 실제 soft/hard threshold 표시
- TAUNT 상태 표시
- 현재 권장 운영 모드 안내 배너 추가

### `blocktroll_extension/popup.js`
역할:
- 팝업 상태 로드
- intensity 버튼 처리
- checkbox 토글 저장
- 서버 `/health` 조회

최근 수정:
- 현재 강도와 실제 threshold를 UI에 표시
- 서버 연결 상태를 초록/빨강 점으로 표시
- 서버에서 `taunt_enabled`, `model_ready` 읽어 팝업에 반영

### `blocktroll_extension/options.html`
역할:
- 고급 설정 페이지 UI

최근 수정:
- `현재 권장: TOXIC + SPAM 중심` 안내 추가
- TAUNT 오탐 주의 문구 추가
- popup intensity와 custom threshold 우선순위 설명 추가

### `blocktroll_extension/options.js`
역할:
- 고급 설정 값 저장
- 직접 threshold 저장 시 `useCustomThresholds=true`

## 7. 학습 코드 구조

### `train/build_dataset.py`
역할:
- 원본 데이터셋을 JSONL 학습 포맷으로 변환

현재 방식:
- K-MHaS 계열 데이터를 읽어서
- `0이면 정상`
- `그 외는 toxic=1`
- `spam=0`, `taunt=0` 고정

중대한 한계:
- 현재 모델은 사실상 `toxic`만 제대로 학습
- `spam`, `taunt`는 학습된 적이 없음
- 현재 오탐 원인의 큰 부분

### `train/train_multilabel.py`
역할:
- Hugging Face Trainer 기반 학습 스크립트

현재 학습 방식:
- 베이스 모델: `monologg/koelectra-small-v3-discriminator`
- 문제 설정: `multi_label_classification`
- 라벨: `toxic`, `spam`, `taunt`
- loss 관점에서 멀티라벨 학습
- 추론은 sigmoid 구조가 맞음

현재 문제:
- 학습 데이터 자체가 3라벨 의미를 못 살림
- 평가 지표도 `toxic_acc@0.5` 하나만 보고 있음
- 감탄 vs 욕설, 피드백 vs 악성 구분을 학습하지 못함

## 8. 현재 모델 폴더

### `models/blocktroll-koelectra/`
- `config.json`
- `model.safetensors`
- `tokenizer.json`
- `tokenizer_config.json`
- `training_args.bin`

현재 상태:
- 모델은 실제 로드 가능
- `/health` 기준 `model_ready=true` 확인 가능
- 하지만 품질은 데이터 설계 한계로 인해 오탐이 많음

## 9. 지금까지 큰 수정 내용 요약

1. 멀티라벨 추론에서 softmax 대신 sigmoid 적용
2. `.env` 기반 설정 도입
3. 공용 AI venv 사용 규칙으로 문서 수정
4. BlockTroll 내부 `.venv` 제거
5. 서버 캐시 도입
6. 모델 + 규칙 하이브리드 분류 구조 도입
7. TAUNT 기본 비활성화
8. 긍정 댓글 오탐 방지 가드 추가
9. 문장부호만 많은 댓글 오탐 완화
10. `존나` 가중치 하향
11. `미친` 단독 제거, 조합 패턴으로 전환
12. 팝업/옵션 UI 개선
13. 현재 강도/실제 threshold/서버 상태 가시화

## 10. 현재 확인된 주요 문제점

### A. 모델 품질 문제
- 현재 학습 구조로는 감탄/욕설 구분이 어려움
- 모델이 일반 감탄이나 강한 구어체를 toxic으로 과대평가하는 경향

### B. 데이터 설계 문제
- `spam`, `taunt`는 학습 데이터가 사실상 없음
- 현재 3라벨 멀티라벨 구조가 이름만 3라벨이고 실제론 1라벨에 가까움

### C. 한국어 애매 표현 문제
- `미친`, `개미친`, `존나`, `레전드`, `돌았다`, `쩐다` 등은 맥락 의존이 큼
- 단어 단독 사전 방식은 오탐이 많음

### D. UI 인지 문제
- 이전에는 현재 강도/threshold가 실제로 적용되는지 사용자가 알기 어려웠음
- 이 부분은 일부 개선했지만 더 다듬을 여지는 있음

## 11. 현재 추천 운영 방식

현재 이 프로젝트는 다음처럼 쓰는 것이 가장 안정적이다.

- `TAUNT` 끔
- `TOXIC + SPAM` 중심
- 팝업 강도는 `낮음` 또는 `보통`부터 테스트
- 옵션에서 custom threshold를 저장했다면 popup intensity보다 우선된다는 점 확인

## 12. 향후 개선 우선순위

### 1순위: 데이터/학습 구조 재설계
추천 방향:
- `spam` 별도 binary
- `tone`: `supportive / neutral / critical / abusive`
- `severity`: 0~3 또는 0~4 단계

### 2순위: 감탄형 비속어 하드네거티브 구축
예시:
- `미친 퀄리티` vs `미친놈`
- `존나 잘하네` vs `존나 못하네`
- `개레전드` vs `개새끼`

### 3순위: 룰 엔진 정교화
- 조합 패턴 강화
- 감탄 문맥 완화 규칙 추가
- 약한 비속어/강한 욕설 분리

### 4순위: 확장 성능 최적화
- DOM 전체 스캔 빈도 최적화
- 텍스트 hash 캐시
- 새 댓글만 처리하는 방향 강화

## 13. 새 세션에서 바로 물어볼 만한 질문 예시

다른 채팅에서 바로 이어갈 때 아래 질문이 유효하다.

- `rules.py에서 감탄형 비속어 오탐을 더 줄이려면 어떻게 수정해야 하나요?`
- `현재 KoELECTRA 학습 구조가 왜 감탄/욕설을 구분 못하는지 분석해 주세요.`
- `tone/severity/spam 분리형 학습 구조로 train 코드를 어떻게 개편하면 좋을까요?`
- `content.js의 DOM 스캔 구조를 성능 좋게 리팩토링해 주세요.`
- `popup/options UI에서 현재 설정 우선순위를 더 명확하게 보여주게 바꿔 주세요.`

## 14. 현재 파일별 요약 한 줄 버전

- `config.py`: 환경설정
- `schemas.py`: API 입출력 형식
- `model.py`: KoELECTRA 로딩/추론
- `rules.py`: 규칙 기반 독성/스팸/비꼼 판단
- `app.py`: 서버 본체, 하이브리드 판단, 캐시
- `content.js`: 유튜브 댓글 읽기/서버 요청/blur-hide 적용
- `popup.*`: 빠른 강도 조절 UI
- `options.*`: 고급 threshold/모드 설정 UI
- `build_dataset.py`: 학습 데이터셋 변환
- `train_multilabel.py`: 현재 학습 스크립트

## 15. 이 프로젝트의 현재 상태를 한 문장으로 요약

`로컬에서 실제 동작하는 한국어 댓글 필터링 MVP는 완성됐지만, 모델 품질은 아직 초기 단계이며 현재는 규칙 기반 보완과 학습 데이터 재설계가 가장 중요한 상태다.`
