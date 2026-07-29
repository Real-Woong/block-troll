const DEFAULTS = {
  serverUrl: "http://127.0.0.1:8787",
  useCustomThresholds: false,
  intensity: 2,
  enableTaunt: false,
  enableToxic: true,
  enableSpam: true,
  softThreshold: 0.45,
  hardThreshold: 0.60
};

function thresholdsByIntensity(level) {
  const L = Number(level || 2);
  if (L === 1) return { soft: 0.70, hard: 0.85, label: "낮음" };
  if (L === 2) return { soft: 0.60, hard: 0.75, label: "보통" };
  if (L === 3) return { soft: 0.50, hard: 0.65, label: "높음" };
  return { soft: 0.60, hard: 0.75, label: "보통" };
}

async function refreshServerStatus(serverUrl) {
  const dot = document.getElementById("serverDot");
  const text = document.getElementById("serverStatus");
  try {
    const res = await fetch((serverUrl || DEFAULTS.serverUrl).replace(/\/+$/, "") + "/health");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    dot.className = "dot ok";
    text.textContent = `서버 연결됨 · model=${data.model_ready ? "ON" : "OFF"} · taunt=${data.taunt_enabled ? "ON" : "OFF"}`;
    return data;
  } catch {
    dot.className = "dot bad";
    text.textContent = "서버 연결 실패";
    return null;
  }
}

// manifest.json에는 매치돼 있지만 아직 댓글 수집기(content.js)가 없는 곳.
const MATCHED_BUT_UNSUPPORTED_RE = /(^|\.)(x\.com|twitter\.com|threads\.net|facebook\.com|tiktok\.com)$/;

async function refreshSiteSupportBanner() {
  const banner = document.getElementById("siteSupportBanner");
  if (!banner) return;

  let hostname = "";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    hostname = new URL(tab?.url || "").hostname;
  } catch {
    banner.style.display = "none";
    return;
  }

  if (MATCHED_BUT_UNSUPPORTED_RE.test(hostname)) {
    banner.textContent = `⚠ ${hostname}은(는) 아직 댓글 필터링을 지원하지 않습니다 (현재 YouTube/Instagram만 지원)`;
    banner.style.display = "block";
    return;
  }

  banner.style.display = "none";
}

async function injectCurrentTab() {
  const status = document.getElementById("status");
  status.textContent = "현재 탭 연결 중...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https:\/\/([^/]+\.)?youtube\.com\//.test(tab.url || "")) {
      status.textContent = "YouTube 탭에서 다시 눌러주세요";
      return;
    }

    await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      files: ["content.js"]
    });

    status.textContent = "주입 완료: 터미널의 extension-debug를 확인하세요";
  } catch (e) {
    status.textContent = `주입 실패: ${String(e?.message || e).slice(0, 80)}`;
  }
}

async function load() {
  await refreshSiteSupportBanner();
  const v = await chrome.storage.sync.get(DEFAULTS);
  const thresholdState = v.useCustomThresholds
    ? { soft: Number(v.softThreshold || DEFAULTS.softThreshold), hard: Number(v.hardThreshold || DEFAULTS.hardThreshold), label: "직접 설정" }
    : thresholdsByIntensity(v.intensity);

  document.querySelectorAll("button[data-level]").forEach(b => {
    const isActive = Number(b.dataset.level) === Number(v.intensity);
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-pressed", String(isActive));
    b.onclick = async () => {
      await chrome.storage.sync.set({
        intensity: Number(b.dataset.level),
        useCustomThresholds: false
      });
      await load();
      document.getElementById("status").textContent = "저장됨";
      setTimeout(() => document.getElementById("status").textContent = "", 800);
    };
  });

  document.getElementById("currentIntensity").textContent = thresholdState.label;
  document.getElementById("softValue").textContent = Number(thresholdState.soft).toFixed(2);
  document.getElementById("hardValue").textContent = Number(thresholdState.hard).toFixed(2);
  const serverStatus = await refreshServerStatus(v.serverUrl);
  const tauntEnabledOnServer = serverStatus?.taunt_enabled !== false;
  document.getElementById("tauntStatus").textContent = tauntEnabledOnServer && v.enableTaunt ? "ON" : "OFF";

  for (const k of ["enableTaunt","enableToxic","enableSpam"]) {
    const el = document.getElementById(k);
    el.checked = !!v[k];
    if (k === "enableTaunt") {
      el.disabled = !tauntEnabledOnServer;
      el.parentElement.title = tauntEnabledOnServer
        ? ""
        : "서버 .env에서 ENABLE_TAUNT=true로 켜야 적용됩니다";
    }
    el.onchange = async () => {
      await chrome.storage.sync.set({ [k]: el.checked });
      await load();
    };
  }

  const injectBtn = document.getElementById("injectBtn");
  if (injectBtn) injectBtn.onclick = injectCurrentTab;
}
load();
