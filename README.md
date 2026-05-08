# BlockTroll (Prototype)

Local AI-agent + Chrome Extension that filters YouTube comments:
- **TOXIC** (abuse/insults)
- **SPAM** (ads/link bait)
- **TAUNT** (mocking/sarcasm)

The extension sends comment text to a local FastAPI server and applies blur/hide based on the label.

## Architecture
- `blocktroll_agent/` : FastAPI local server (`/classify`)
- `blocktroll_extension/` : Chrome extension (MV3) for YouTube
- `models/blocktroll-koelectra/` : Model folder (weights ignored in git)

## Prerequisites
- Shared AI environment: `~/Desktop/project/Project_AI/_venvs/ai`
- Python **3.12**
- Chrome (for loading unpacked extensions)

## Setup (Local)
```bash
source ~/Desktop/project/Project_AI/_venvs/ai/bin/activate
# install only if this shared environment does not already include them
uv pip install -r requirements.txt
cp .env.example .env

Run the local agent
source ~/Desktop/project/Project_AI/_venvs/ai/bin/activate
python -m uvicorn blocktroll_agent.app:app --host 127.0.0.1 --port 8787 --reload

Health check:
curl http://127.0.0.1:8787/health

Load the Chrome extension
	1.	Open chrome://extensions
	2.	Turn on Developer mode
	3.	Click Load unpacked
	4.	Select blocktroll_extension/
	5.	Open YouTube and check comments

Options

Open the extension options page:
	•	Server URL (default: http://127.0.0.1:8787)
	•	Mode: blur_click / blur / hide
	•	Thresholds: soft/hard or popup intensity
	•	Enable: TAUNT/TOXIC/SPAM

Environment

- `.env`에서 아래 값을 조정 가능
- `MODEL_DIR`
- `TH_TOXIC`, `TH_SPAM`, `TH_TAUNT`
- `CACHE_MAXSIZE`

Shared environment rules

- BlockTroll 내부에 `.venv`를 새로 만들지 않음
- 항상 `~/Desktop/project/Project_AI/_venvs/ai` 활성화 후 실행
- 새 패키지는 공용 환경에 설치

Model

Prototype works with rule-based fallback when no weights are present.

To enable the learning model:
	•	Put a fine-tuned model into models/blocktroll-koelectra/
	•	Ensure it includes config.json, tokenizer files, and weights (model.safetensors or pytorch_model.bin)
	•	Restart the server

Model weights are ignored by git.

Roadmap
	•	Fine-tune KoELECTRA multi-label head for toxic/spam/taunt
	•	Better YouTube DOM handling & performance (batching, caching)
	•	Expand to Instagram/TikTok comment surfaces
	•	On-device inference / WASM option

## Flow
YouTube 댓글
   ↓
content.js
   ↓
POST /classify
   ↓
app.py
   ↓
model.py + rules.py (hybrid)
   ↓
label 반환
   ↓
content.js
   ↓
blur/hide
