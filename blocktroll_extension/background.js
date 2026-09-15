// BlockTroll background service worker
//
// 서버 통신은 전부 여기를 거친다. content script에서 직접 fetch 하면 안 되는 이유:
//   1) MV3에서 content script의 fetch는 페이지 origin(https://www.youtube.com)으로
//      CORS가 적용된다. 서버는 chrome-extension:// 만 허용하므로 400으로 막힌다.
//   2) https 페이지에서 http:// 호출은 mixed-content로 차단된다.
//      (127.0.0.1은 예외라 지금까지 로컬에서만 동작했다.)
// service worker는 chrome-extension:// origin으로 돌고 host_permissions가 적용되어
// 두 제약이 모두 사라진다. 덕분에 Tailscale 사설 IP를 평문 http로 부를 수 있다.

const DEFAULTS = {
  serverUrl: "http://100.96.86.10:8787"
};

const CLASSIFY_TIMEOUT_MS = 10000;
const DEBUG_TIMEOUT_MS = 3000;
const HEALTH_TIMEOUT_MS = 4000;

async function serverBase() {
  let stored = {};
  try {
    stored = await chrome.storage.sync.get(DEFAULTS);
  } catch {
    stored = DEFAULTS;
  }
  const raw = String(stored.serverUrl || DEFAULTS.serverUrl).trim() || DEFAULTS.serverUrl;
  try {
    const url = new URL(raw);
    // localhost는 일부 환경에서 ::1로 풀려 연결이 실패한다.
    if (url.hostname === "localhost") url.hostname = "127.0.0.1";
    return url.toString().replace(/\/+$/, "");
  } catch {
    console.warn("[BlockTroll] invalid serverUrl, using default:", raw);
    return DEFAULTS.serverUrl;
  }
}

async function requestJson(path, { method = "GET", body, timeoutMs = HEALTH_TIMEOUT_MS } = {}) {
  const base = await serverBase();
  const url = base + path;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal
    });
    if (!res.ok) {
      return { ok: false, status: res.status, error: `HTTP ${res.status}`, url };
    }
    return { ok: true, status: res.status, data: await res.json(), url };
  } catch (e) {
    const reason = e?.name === "AbortError" ? `timeout after ${timeoutMs}ms` : String(e?.message || e);
    return { ok: false, error: reason, url };
  } finally {
    clearTimeout(timer);
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || typeof msg.type !== "string") return undefined;

  switch (msg.type) {
    case "bt-classify":
      requestJson("/classify", {
        method: "POST",
        body: { texts: msg.texts || [], platform: msg.platform || "unknown" },
        timeoutMs: CLASSIFY_TIMEOUT_MS
      }).then(sendResponse);
      return true; // 비동기 응답

    case "bt-debug":
      requestJson("/debug", {
        method: "POST",
        body: msg.payload || {},
        timeoutMs: DEBUG_TIMEOUT_MS
      }).then(sendResponse);
      return true;

    case "bt-health":
      requestJson("/health", { timeoutMs: HEALTH_TIMEOUT_MS }).then(sendResponse);
      return true;

    default:
      return undefined;
  }
});
