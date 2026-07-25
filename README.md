# BlockTroll (Prototype)

Local AI-agent + Chrome Extension that filters social comments:
- **TOXIC** (abuse/insults)
- **SPAM** (ads/link bait)
- **TAUNT** (mocking/sarcasm)

The extension sends comment text to a local FastAPI server and applies blur/hide based on the label.
Comment DOM collection currently supports YouTube and Instagram. The manifest also allows
major social domains so more platform-specific collectors can be added without widening
the extension scope again. A domain being allowed in the manifest does not mean its
comment collector is implemented yet.

## Architecture
- `blocktroll_agent/` : FastAPI local server (`/classify`)
- `blocktroll_extension/` : Chrome extension (MV3) for social comment pages
- `models/blocktroll-koelectra/` : Windows training output copied here only for model tests
- `train/` : Dataset conversion and Windows training scripts

## Machine roles
- MacBook: BlockTroll server, Chrome extension, rules, and app development
- Windows + RTX GPU: dataset build and transformer training

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
```

## Run the local agent
```bash
source ~/Desktop/project/Project_AI/_venvs/ai/bin/activate
python -m uvicorn blocktroll_agent.app:app --host 127.0.0.1 --port 8787 --reload
```

Health check:
```bash
curl http://127.0.0.1:8787/health
```

## Load the Chrome extension
1. Open `chrome://extensions`
2. Turn on Developer mode
3. Click Load unpacked
4. Select `blocktroll_extension/`
5. Open YouTube or Instagram and check comments

## Options
- Server URL (default: `http://127.0.0.1:8787`)
- Mode: `blur_click` / `blur` / `hide`
- Thresholds: soft/hard or popup intensity
- Enable: TAUNT/TOXIC/SPAM

`blur_click` keeps the suspicious comment blurred until the comment or its badge is
clicked. Click it again to restore the blur.

## Environment
- `.env`에서 아래 값을 조정 가능
- `DEBUG`
- `LOG_COMMENTS`
- `ENABLE_MODEL`
- `MODEL_DIR`
- `TH_TOXIC`, `TH_SPAM`, `TH_TAUNT`
- `ENABLE_TAUNT`
- `CACHE_MAXSIZE`

Set `LOG_COMMENTS=true` and restart the server when you want the server terminal to
print incoming `/classify` comment batches and labels. Set `DEBUG=true` when you also
want lower-level model debug output. Keep them off for quieter normal use.

## Shared environment rules
- BlockTroll 내부에 `.venv`를 새로 만들지 않음
- 항상 `~/Desktop/project/Project_AI/_venvs/ai` 활성화 후 실행
- 새 패키지는 공용 환경에 설치

## Model
Prototype works with rule-based fallback when no weights are present.
By default, `ENABLE_MODEL=false` keeps the server in rule-based safe mode.

To enable the learning model:
- Put a fine-tuned model into `models/blocktroll-koelectra/`
- Ensure it includes `config.json`, tokenizer files, and weights (`model.safetensors` or `pytorch_model.bin`)
- Set `ENABLE_MODEL=true`
- Restart the server

Generated model weights, tokenizer files, and model configs are ignored by git.

The `/health` response is the quickest model check:
- `model_enabled=false`: `.env` keeps KoELECTRA disabled.
- `model_enabled=true` and `model_ready=false`: the server could not load the model directory or files.
- `model_ready=true`: KoELECTRA inference is available to the server.

## Debugging the extension
- Reload the unpacked extension from `chrome://extensions` after editing extension files.
- Refresh already-open YouTube or Instagram tabs after reloading the extension. Old tabs
  can still contain an invalidated content script and Chrome may record
  `Extension context invalidated` from that old page state.
- Open the page DevTools console and inspect BlockTroll logs when extension-side
  debugging is enabled.
- Use the server terminal with `DEBUG=true` when you need to see comment text sent to
  `/classify`.

The YouTube collector rescans a DOM node when YouTube reuses it for different visible
comment text, so an earlier `OK` decision should not stick to a later toxic comment.

## Windows training
1. Clone or pull this project on Windows.
2. Put the K-MHaS text files in a folder containing `kmhas_train.txt`, `kmhas_valid.txt`, and `kmhas_test.txt`.
3. Create a Python environment with CUDA PyTorch, then install this project's `requirements.txt`.
   Verify that PyTorch sees the RTX GPU before training:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

4. Build corrected JSONL data. The repo handmade data adds SPAM/TAUNT positives:

```powershell
python train/build_dataset.py --input-dir "D:\datasets\kmhas" --output-dir "D:\datasets\blocktroll_generated"
```

5. Train with the generated data and GPU environment:

```powershell
$env:BLOCKTROLL_DATA_DIR="D:\datasets\blocktroll_generated"
$env:BLOCKTROLL_MODEL_DIR="$PWD\models\blocktroll-koelectra"
$env:BLOCKTROLL_EPOCHS="2"
python train/train_multilabel.py
```

6. Check validation metrics before using the model, especially `toxic_f1`, `toxic_precision`, and false-positive samples from normal YouTube comments.
7. Copy the verified Windows `models\blocktroll-koelectra` output to the Mac model directory only when you want Mac model inference testing.

## Roadmap
- Fine-tune KoELECTRA multi-label head for toxic/spam/taunt
- Better YouTube DOM handling & performance (batching, caching)
- Expand to Instagram/TikTok comment surfaces
- On-device inference / WASM option

## Flow
```text
YouTube or Instagram comments
  -> content.js
  -> POST /classify
  -> app.py
  -> model.py + rules.py
  -> label response
  -> content.js
  -> blur/hide
```
