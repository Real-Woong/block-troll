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

async function load() {
  const v = await chrome.storage.sync.get(DEFAULTS);
  const thresholdState = v.useCustomThresholds
    ? { soft: Number(v.softThreshold || DEFAULTS.softThreshold), hard: Number(v.hardThreshold || DEFAULTS.hardThreshold), label: "직접 설정" }
    : thresholdsByIntensity(v.intensity);

  document.querySelectorAll("button[data-level]").forEach(b => {
    b.classList.toggle("active", Number(b.dataset.level) === Number(v.intensity));
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
}
load();
