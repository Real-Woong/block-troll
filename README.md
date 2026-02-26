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
- Python **3.11**
- Chrome (for loading unpacked extensions)

## Setup (Local)
```bash
python -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt

Run the local agent
source .venv311/bin/activate
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
	•	Thresholds: soft/hard
	•	Enable: TAUNT/TOXIC/SPAM

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
rules.py (현재 판단 담당)
   ↓
label 반환
   ↓
content.js
   ↓
blur/hide