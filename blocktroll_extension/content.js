// BlockTroll content script (YouTube)
// VSCode에서 섹션 접기/펼치기: //#region ... //#endregion

//#region 0) 기본 설정/옵션 (DEFAULTS, OPT, loadOptionsMaybe)
const DEFAULTS = {
  serverUrl: "http://127.0.0.1:8787",
  mode: "blur_click",
  enableTaunt: false,
  enableToxic: true,
  enableSpam: true,
  useCustomThresholds: false,

  // 3-step intensity (1=낮음, 2=중간, 3=높음)
  intensity: 2,

  // fallback thresholds (used only if intensity is missing)
  softThreshold: 0.45,
  hardThreshold: 0.60
};

let OPT = { ...DEFAULTS };
let lastOptFingerprint = "";
let lastOptionsLoad = 0;

// UI 문구/스타일 변경 시, 이미 처리된 댓글에도 1회 재적용하기 위한 버전값
const BT_UI_VERSION = "2026-02-24-2";

// chrome.storage.sync를 Promise로 감싸서 옵션을 가져온다.
// - defaults: 기본값(키/기본값)을 담은 객체
// - 반환: defaults를 기본으로 하고, 저장된 값을 덮어쓴 새 객체
async function storageGet(defaults) {
  return new Promise((resolve) => {
    try {
      // MV3 환경: chrome.storage.sync 사용
      if (typeof chrome !== "undefined" && chrome?.storage?.sync?.get) {
        chrome.storage.sync.get(defaults, (items) => {
          // runtime.lastError가 있으면 defaults로 fallback
          if (chrome.runtime && chrome.runtime.lastError) {
            console.warn("[BlockTroll] storageGet error:", chrome.runtime.lastError);
            resolve({ ...defaults });
            return;
          }
          resolve({ ...defaults, ...(items || {}) });
        });
        return;
      }
    } catch (e) {
      console.warn("[BlockTroll] storageGet exception:", e);
    }

    // storage API가 없으면 defaults 그대로
    resolve({ ...defaults });
  });
}

async function loadOptionsMaybe() {
  const now = Date.now();
  if (now - lastOptionsLoad < 1500) return; // 너무 자주 읽지 않기
  lastOptionsLoad = now;

  OPT = await storageGet(DEFAULTS);

  // Detect option changes so we can re-apply filtering to already-seen comments
  const fp = JSON.stringify({
    serverUrl: OPT.serverUrl,
    mode: OPT.mode,
    enableTaunt: OPT.enableTaunt,
    enableToxic: OPT.enableToxic,
    enableSpam: OPT.enableSpam,
    intensity: OPT.intensity,
    softThreshold: OPT.softThreshold,
    hardThreshold: OPT.hardThreshold
  });
  OPT.__changed = (fp !== lastOptFingerprint);
  lastOptFingerprint = fp;

  // Apply 5-step intensity -> thresholds
  // (If intensity is undefined for older installs, keep the stored thresholds)
  if (!OPT.useCustomThresholds && OPT.intensity !== undefined && OPT.intensity !== null) {
    const t = thresholdsByIntensity(OPT.intensity);
    OPT.softThreshold = t.soft;
    OPT.hardThreshold = t.hard;
  }
}
//#endregion

//#region 1) 스타일 주입 (ensureBtStyles)
let __btStyleInjected = false;
function ensureBtStyles() {
  if (__btStyleInjected) return;
  __btStyleInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    /* BlockTroll wrapper-based blur + unblurred badge */
    .bt-host {
      position: relative !important;
      display: inline-block !important;
      overflow: visible !important;
    }
    .bt-text {
      display: inline !important;
    }
    .bt-text.bt-soft { filter: blur(5px); }
    .bt-text.bt-hard { filter: blur(8px); }

    .bt-badge {
      position: static;
      display: inline-flex;
      align-items: center;
      vertical-align: middle;
      margin-right: 6px;
      box-sizing: border-box;
      z-index: 2147483647;
      padding: 1px 6px;
      border-radius: 999px;
      font-size: 11px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: -0.2px;
      pointer-events: none;
      white-space: nowrap;
      box-shadow: 0 1px 2px rgba(0,0,0,0.35);
      border: 1px solid rgba(0,0,0,0.15);
    }

    /* High-contrast badge styles that work on dark theme */
    .bt-badge.taunt { background: rgba(255, 215, 0, 0.92); color: #111; }
    .bt-badge.toxic { background: rgba(255, 80, 80, 0.92); color: #111; }
    .bt-badge.spam  { background: rgba(120, 200, 255, 0.92); color: #111; }
    .bt-badge.generic { background: rgba(230, 230, 230, 0.92); color: #111; }

    /* Add a tiny icon so it is distinguishable even if text is short */
    .bt-badge.taunt::before { content: "😏 "; }
    .bt-badge.toxic::before { content: "⚠️ "; }
    .bt-badge.spam::before  { content: "📣 "; }
    .bt-badge.generic::before { content: "🔎 "; }
  `;
  document.documentElement.appendChild(style);
}
//#endregion

//#region 2) 배지 텍스트/색상 결정 (badgeTextForDecision, badgeClassForDecision)
function badgeTextForDecision(decision) {
  const label = decision?.label || "OK";

  // Prefer label if provided
  if (label === "TAUNT") return "패배자들이랑 답없는 사람들 보기";
  if (label === "TOXIC") return "인생 패배자들 댓글보기";
  if (label === "SPAM") return "광고충 댓글 보기";

  // For extreme mode, label might still be OK. Derive from per-category scores.
  const s = decision?.scores || {};
  const toxic = Number(s.toxic || 0);
  const spam = Number(s.spam || 0);
  const taunt = Number(s.taunt || 0);

  const max = Math.max(toxic, spam, taunt);
  if (max === toxic) return "인생 패배자들 댓글보기";
  if (max === spam) return "광고충 댓글 보기";
  return "패배자들이랑 답없는 사람들 보기";
}

function badgeClassForDecision(decision) {
  const label = decision?.label || "OK";
  if (label === "TAUNT") return "taunt";
  if (label === "TOXIC") return "toxic";
  if (label === "SPAM") return "spam";

  const s = decision?.scores || {};
  const toxic = Number(s.toxic || 0);
  const spam = Number(s.spam || 0);
  const taunt = Number(s.taunt || 0);
  const max = Math.max(toxic, spam, taunt);
  if (max <= 0) return "generic";
  if (max === toxic) return "toxic";
  if (max === spam) return "spam";
  return "taunt";
}
//#endregion

//#region 3) DOM 래핑 (ensureWrapped)
function ensureWrapped(el) {
  // Host wraps the original content (bt-text) and an unblurred badge overlay
  if (!el.classList.contains("bt-host")) el.classList.add("bt-host");

  // 각 댓글 DOM에 안정적인 식별자를 부여 (배치 요청/로그 매칭용)
  if (!el.dataset.btId) {
    el.dataset.btId = (crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : String(Date.now()) + "-" + Math.random().toString(16).slice(2);
  }

  let textSpan = directChildByClass(el, "bt-text");
  let badgeSpan = directChildByClass(el, "bt-badge");

  if (!textSpan) {
    textSpan = document.createElement("span");
    textSpan.className = "bt-text";
    // Move all existing child nodes into bt-text to preserve emojis/links
    while (el.firstChild) {
      textSpan.appendChild(el.firstChild);
    }
    el.appendChild(textSpan);
  }

  if (!badgeSpan) {
    badgeSpan = document.createElement("span");
    badgeSpan.className = "bt-badge generic";
    badgeSpan.textContent = "필터링된 댓글";
    // 배지는 블러 적용 대상(.bt-text) 밖에 있어야 하고, 줄 안에서 잘리지 않도록 앞쪽에 둔다.
    const ts = directChildByClass(el, "bt-text");
    if (ts) el.insertBefore(badgeSpan, ts);
    else el.appendChild(badgeSpan);
  }

  return { textSpan, badgeSpan };
}
//#endregion

//#region 4) 유틸/DOM 수집 (clamp01, getYouTubeCommentTextEls, normalizeText)
function clamp01(x) {
  x = Number(x || 0);
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

// `:scope > .class` 셀렉터가 환경에 따라 오류를 내는 경우가 있어, 직접 자식만 안전하게 찾는다.
function directChildByClass(el, className) {
  if (!el || !el.children) return null;
  for (const child of el.children) {
    if (child && child.classList && child.classList.contains(className)) return child;
  }
  return null;
}

function getYouTubeCommentTextEls() {
  // YouTube 댓글 텍스트
  return Array.from(document.querySelectorAll("ytd-comment-thread-renderer #content-text"));
}

function normalizeText(s) {
  return (s || "").replace(/\s+/g, " ").trim();
}
//#endregion

//#region 5) 필터 결정 엔진 (shouldFilterLabel, decideAction)
function shouldFilterLabel(label) {
  if (label === "TAUNT") return !!OPT.enableTaunt;
  if (label === "TOXIC") return !!OPT.enableToxic;
  if (label === "SPAM") return !!OPT.enableSpam;
  return false;
}

function decideAction(decision) {
  const label = decision?.label || "OK";
  const score = clamp01(decision?.score || 0);

  // label + toggle 기반 필터링 (3단계 intensity는 threshold로만 반영)
  if (!shouldFilterLabel(label)) return "NONE";

  // TOXIC/SPAM은 강하게
  if (label === "TOXIC" || label === "SPAM") {
    return score >= OPT.hardThreshold ? "HARD" : (score >= OPT.softThreshold ? "SOFT" : "NONE");
  }

  // TAUNT는 기본 SOFT 위주
  if (label === "TAUNT") {
    return score >= OPT.softThreshold ? "SOFT" : "NONE";
  }

  return "NONE";
}

//#region 6) UI 적용/토글 (applyActionToEl)
function applyActionToEl(el, action, decision) {
  // YouTube는 DOM이 자주 갈아끼워져서, 스캔 후 적용 시점에 el이 사라질 수 있음
  if (!el || typeof el.querySelector !== "function") return;
  // Always store debug info (even when not filtering) so we can inspect all comments
  el.dataset.blocktrollLabel = decision?.label || "";
  el.dataset.blocktrollScore = String(decision?.score ?? "");
  el.dataset.blocktrollAction = action;

  if (action === "NONE") {
    // Clear filters/badge if present
    const textSpan = directChildByClass(el, "bt-text");
    const badgeSpan = directChildByClass(el, "bt-badge");
    if (textSpan) textSpan.classList.remove("bt-soft", "bt-hard");
    if (badgeSpan) badgeSpan.remove();
    el.classList.remove("bt-host");
    // Not filtering: leave UI unchanged
    delete el.dataset.blocktrollUiVer;
    return;
  }

  // 이미 처리된 DOM이라도 UI 버전이 바뀌었으면(문구/스타일 변경 등) 1회 재적용
  if (el.dataset.blocktrollApplied === "1" && el.dataset.blocktrollUiVer === BT_UI_VERSION) return;
  // 실제로 UI를 변경할 때만 applied 찍기 (중요)
  el.dataset.blocktrollApplied = "1";
  el.dataset.blocktrollUiVer = BT_UI_VERSION;

  const mode = OPT.mode || "blur_click";

  if (mode === "hide" && action === "HARD") {
    el.style.visibility = "hidden";
    el.style.filter = "";
    return;
  }

  // Ensure CSS + structure exists
  ensureBtStyles();
  const { textSpan, badgeSpan } = ensureWrapped(el);

  // Set badge text + style
  const btxt = badgeTextForDecision(decision);
  const bcls = badgeClassForDecision(decision);
  badgeSpan.className = `bt-badge ${bcls}`;
  badgeSpan.textContent = btxt;

  // Apply blur ONLY to the text span (badge remains crisp)
  textSpan.classList.remove("bt-soft", "bt-hard");
  textSpan.classList.add(action === "HARD" ? "bt-hard" : "bt-soft");

  el.style.visibility = "visible";

  if (mode === "blur_click") {
    el.style.cursor = "pointer";
    el.title = "BlockTroll: 클릭하면 보기/가리기";
    if (!el.dataset.blocktrollClickBound) {
      el.dataset.blocktrollClickBound = "1";
      el.addEventListener("click", (e) => {
        // 댓글 클릭 토글
        // - blur 상태에서 클릭: blur 제거 + 안내 배지 숨김 (원문 보기)
        // - 원문 상태에서 클릭: 다시 blur 적용 + 안내 배지 표시
        e.stopPropagation();

        const host = el;
        const textSpan = directChildByClass(host, "bt-text") || host;
        const badgeSpan = directChildByClass(host, "bt-badge");

        // 현재 blur 상태 판단 (클래스 우선, 없으면 computedStyle로 보조)
        const hasSoft = textSpan.classList?.contains("bt-soft");
        const hasHard = textSpan.classList?.contains("bt-hard");
        let isBlurred = !!(hasSoft || hasHard);
        if (!isBlurred) {
          const cur = getComputedStyle(textSpan).filter;
          isBlurred = !!(cur && cur !== "none");
        }

        if (isBlurred) {
          // 1) blur -> reveal
          textSpan.classList.remove("bt-soft", "bt-hard");
          if (badgeSpan) badgeSpan.style.display = "none";
          host.dataset.blocktrollRevealed = "1";
          host.title = "BlockTroll: 클릭하면 다시 가리기";
          return;
        }

        // 2) reveal -> blur (원래 action 기준)
        const originalAction = host.dataset.blocktrollAction || action;
        textSpan.classList.remove("bt-soft", "bt-hard");
        textSpan.classList.add(originalAction === "HARD" ? "bt-hard" : "bt-soft");
        if (badgeSpan) badgeSpan.style.display = "";
        host.dataset.blocktrollRevealed = "0";
        host.title = "BlockTroll: 클릭하면 보기";
      }, true);
    }
  }
}
//#endregion

//#region 7) 서버 통신 (classifyBatch)
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
//#endregion

//#region 8) 스캔 루프 (scanAndApply)
// scanAndApply 동시 실행/폭주 방지용 상태
let __btScanInFlight = false;
let __btScanQueued = false;
let __btScanTimer = null;

// 여러 이벤트(Interval + MutationObserver)에서 호출되더라도, 일정 시간 내 1번만 실행
function scheduleScan(delayMs = 200) {
  if (__btScanTimer) clearTimeout(__btScanTimer);
  __btScanTimer = setTimeout(() => {
    __btScanTimer = null;
    scanAndApply();
  }, delayMs);
}

async function scanAndApply() {
  // 이미 실행 중이면 한 번만 재실행 예약하고 빠진다 (서버/브라우저 과열 방지)
  if (__btScanInFlight) {
    __btScanQueued = true;
    return;
  }
  __btScanInFlight = true;

  await loadOptionsMaybe();

  const els = getYouTubeCommentTextEls();
  if (!els.length) {
    __btScanInFlight = false;
    return;
  }

  // If options changed (e.g., intensity moved to 5), re-process all currently loaded comments
  if (OPT.__changed) {
    for (const el of els) {
      delete el.dataset.blocktrollSeen;
      delete el.dataset.blocktrollApplied;
      delete el.dataset.blocktrollClickBound;
      // Reset UI to a clean baseline before re-applying
      el.style.filter = "";
      el.style.visibility = "";
      el.style.cursor = "";
      el.title = "";
      // Reset wrapper-based UI
      const textSpan = directChildByClass(el, "bt-text");
      if (textSpan) textSpan.classList.remove("bt-soft", "bt-hard");
      const badgeSpan = directChildByClass(el, "bt-badge");
      if (badgeSpan) badgeSpan.remove();
      el.classList.remove("bt-host");
    }
  }

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

  if (!pending.length) {
    __btScanInFlight = false;
    return;
  }

  let results;
  try {
    results = await classifyBatch(pendingText);
  } catch (e) {
    // 실패하면 seen 찍지 말고 다음 스캔에서 재시도
    console.warn("[BlockTroll] classify error:", e);
    __btScanInFlight = false;
    return;
  }

  // 길이 불일치 방어
  const n = Math.min(pending.length, results.length);

  for (let i = 0; i < n; i++) {
    const el = pending[i];
    const decision = results[i];
    const action = decideAction(decision);

    // 중간에 댓글 DOM이 교체/삭제되면 el이 invalid일 수 있음
    if (!el || typeof el.querySelector !== "function") continue;

    applyActionToEl(el, action, decision);

    // 적용/판단 끝난 뒤 seen 찍기 (중요)
    el.dataset.blocktrollSeen = "1";

    // 디버그: 필터 걸린 것만 출력
    console.log(
      `[BlockTroll] label=${decision?.label} score=${Number(decision?.score ?? 0).toFixed(3)} action=${action} soft=${OPT.softThreshold} hard=${OPT.hardThreshold} | ${String(pendingText[i] || "").slice(0, 60)}`
    );
  }

  // 실행 종료 처리 + 중간에 스캔 요청이 쌓였으면 1회만 추가 실행
  __btScanInFlight = false;
  if (__btScanQueued) {
    __btScanQueued = false;
    scheduleScan(50);
  }
}
//#endregion

//#region 9) 옵저버/부트스트랩 (startObservers, thresholdsByIntensity, start)
function startObservers() {
  // 최초 1회
  scheduleScan(0);

  // 주기 스캔 (YouTube는 무한 스크롤/동적 로딩)
  setInterval(() => scheduleScan(0), 1200);

  // DOM 변화에도 반응
  const obs = new MutationObserver(() => scheduleScan(200));
  obs.observe(document.documentElement, { childList: true, subtree: true });
}

function thresholdsByIntensity(level) {
  const L = Number(level || 2);

  // 1=낮음(보수적: 덜 가림), 2=중간, 3=높음(공격적: 더 가림)
  if (L === 1) return { soft: 0.70, hard: 0.85 };
  if (L === 2) return { soft: 0.60, hard: 0.75 };
  if (L === 3) return { soft: 0.50, hard: 0.65 };

  // fallback
  return { soft: 0.60, hard: 0.75 };
}
//#endregion

startObservers();
//#endregion
