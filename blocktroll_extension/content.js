const DEFAULTS = {
  serverUrl: "http://127.0.0.1:8787",
  mode: "blur_click",
  enableTaunt: true,
  enableToxic: true,
  enableSpam: true,
  softThreshold: 0.45,
  hardThreshold: 0.60
};

let OPT = { ...DEFAULTS };
let lastOptionsLoad = 0;

async function loadOptionsMaybe() {
  const now = Date.now();
  if (now - lastOptionsLoad < 1500) return; // 너무 자주 읽지 않기
  lastOptionsLoad = now;
  OPT = await chrome.storage.sync.get(DEFAULTS);
}

function clamp01(x) {
  x = Number(x || 0);
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

function getYouTubeCommentTextEls() {
  // YouTube 댓글 텍스트
  return Array.from(document.querySelectorAll("ytd-comment-thread-renderer #content-text"));
}

function normalizeText(s) {
  return (s || "").replace(/\s+/g, " ").trim();
}

function shouldFilterLabel(label) {
  if (label === "TAUNT") return !!OPT.enableTaunt;
  if (label === "TOXIC") return !!OPT.enableToxic;
  if (label === "SPAM") return !!OPT.enableSpam;
  return false;
}

function decideAction(decision) {
  const label = decision?.label || "OK";
  const score = clamp01(decision?.score || 0);

  if (!shouldFilterLabel(label)) return "NONE";
  if (label === "OK") return "NONE";

  // TOXIC/SPAM은 강하게
  if (label === "TOXIC" || label === "SPAM") {
    return score >= OPT.hardThreshold ? "HARD" : "SOFT";
  }

  // TAUNT는 기본 SOFT(블러)
  if (label === "TAUNT") {
    return score >= OPT.softThreshold ? "SOFT" : "NONE";
  }

  return "NONE";
}

function applyActionToEl(el, action, decision) {
  // 이미 처리됐으면 스킵 (단, NONE이면 applied 안 찍고 넘어감)
  if (el.dataset.blocktrollApplied === "1" && action !== "NONE") return;

  if (action === "NONE") {
    // 필요하면 원복 로직도 가능하지만 일단은 건드리지 않음
    return;
  }

  // 실제로 UI를 변경할 때만 applied 찍기 (중요)
  el.dataset.blocktrollApplied = "1";
  el.dataset.blocktrollLabel = decision?.label || "";
  el.dataset.blocktrollScore = String(decision?.score ?? "");

  const mode = OPT.mode || "blur_click";

  if (mode === "hide" && action === "HARD") {
    el.style.visibility = "hidden";
    el.style.filter = "";
    return;
  }

  // blur / blur_click
  el.style.visibility = "visible";

  if (action === "HARD") {
    el.style.filter = "blur(8px)";
  } else {
    el.style.filter = "blur(5px)";
  }

  if (mode === "blur_click") {
    el.style.cursor = "pointer";
    el.title = "BlockTroll: 클릭하면 보기/가리기";
    if (!el.dataset.blocktrollClickBound) {
      el.dataset.blocktrollClickBound = "1";
      el.addEventListener("click", (e) => {
        // 댓글 클릭 토글
        e.stopPropagation();
        const cur = getComputedStyle(el).filter;
        if (cur && cur !== "none") {
          el.style.filter = "none";
        } else {
          // 다시 블러
          el.style.filter = (action === "HARD") ? "blur(8px)" : "blur(5px)";
        }
      }, true);
    }
  }
}

async function classifyBatch(texts) {
  const url = (OPT.serverUrl || DEFAULTS.serverUrl).replace(/\/+$/, "") + "/classify";

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts, platform: "youtube" })
  });

  if (!res.ok) {
    throw new Error(`classify failed: ${res.status}`);
  }

  const data = await res.json();
  // 서버(app.py) 포맷: { results: [...] }
  return Array.isArray(data?.results) ? data.results : [];
}

async function scanAndApply() {
  await loadOptionsMaybe();

  const els = getYouTubeCommentTextEls();
  if (!els.length) return;

  // 아직 처리 안 한 댓글만
  const pending = [];
  const pendingText = [];

  for (const el of els) {
    if (el.dataset.blocktrollSeen === "1") continue;

    const t = normalizeText(el.innerText);
    if (!t) {
      el.dataset.blocktrollSeen = "1";
      continue;
    }

    pending.push(el);
    pendingText.push(t);

    // 너무 많이 한 번에 보내지 않기
    if (pending.length >= 30) break;
  }

  if (!pending.length) return;

  let results;
  try {
    results = await classifyBatch(pendingText);
  } catch (e) {
    // 실패하면 seen 찍지 말고 다음 스캔에서 재시도
    console.warn("[BlockTroll] classify error:", e);
    return;
  }

  // 길이 불일치 방어
  const n = Math.min(pending.length, results.length);

  for (let i = 0; i < n; i++) {
    const el = pending[i];
    const decision = results[i];
    const action = decideAction(decision);

    applyActionToEl(el, action, decision);

    // 적용/판단 끝난 뒤 seen 찍기 (중요)
    el.dataset.blocktrollSeen = "1";

    // 디버그: 필터 걸린 것만 출력
    if (action !== "NONE") {
      console.log("[BlockTroll]", decision?.label, decision?.score, pendingText[i].slice(0, 60));
    }
  }
}

function startObservers() {
  // 최초 1회
  scanAndApply();

  // 주기 스캔 (YouTube는 무한 스크롤/동적 로딩)
  setInterval(scanAndApply, 1200);

  // DOM 변화에도 반응
  const obs = new MutationObserver(() => scanAndApply());
  obs.observe(document.documentElement, { childList: true, subtree: true });
}

startObservers();