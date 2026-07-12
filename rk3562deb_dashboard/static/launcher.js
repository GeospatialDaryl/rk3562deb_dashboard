// Launcher home page: app tiles + device status. Talks only to
// /api/launcher-status (GET, polled) and /api/control/<action> (POST).
const $ = (id) => document.getElementById(id);

let currentDemo = null;
let demosRendered = false;

async function postControl(action, body) {
  const status = $("control-status");
  status.className = "muted shell";
  status.textContent = "Running…";
  try {
    const response = await fetch(`/api/control/${action}`, {
      method: "POST",
      ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
    });
    const payload = await response.json();
    if (response.ok && payload.ok) {
      status.className = "ok shell";
      status.textContent = `${action} ok`;
      return true;
    }
    status.className = "err shell";
    status.textContent = `${action} failed: ${payload.error || payload.stderr || response.status}`;
  } catch (error) {
    status.className = "err shell";
    status.textContent = `${action} failed: ${error.message}`;
  }
  return false;
}

function renderDemoChips(demos) {
  if (demosRendered) {
    for (const chip of document.querySelectorAll(".demo-chip")) {
      chip.classList.toggle("demo-chip-active", chip.dataset.demo === currentDemo);
    }
    return;
  }
  const container = $("demo-chips");
  container.textContent = "";
  for (const demo of demos) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "demo-chip";
    chip.dataset.demo = demo;
    chip.textContent = demo;
    chip.classList.toggle("demo-chip-active", demo === currentDemo);
    chip.addEventListener("click", async () => {
      if (await postControl("set-cv-demo", { demo })) {
        await postControl("switch-camera-cv");
      }
    });
    container.appendChild(chip);
  }
  demosRendered = true;
}

function renderStatus(data) {
  currentDemo = data.cv_demo;
  $("status-app").textContent = data.active_app || "none";
  const battery = data.battery || {};
  $("status-battery").textContent = battery.capacity_percent == null
    ? "n/a"
    : `${battery.capacity_percent}%${battery.status ? ` · ${battery.status}` : ""}`;
  $("status-profile").textContent = data.power_profile || "n/a";
  $("power-label").textContent = data.power_profile || "--";
  $("status-demo").textContent = data.cv_demo || "default";
  $("camera-demo").textContent = data.cv_demo || "yolov8";
  for (const [tileId, app] of [
    ["tile-dashboard", "dashboard"],
    ["tile-camera", "camera-cv"],
    ["tile-mapping", "mapping"],
    ["tile-display-off", "display-off"],
  ]) {
    $(tileId).classList.toggle("tile-active", data.active_app === app);
  }
  renderDemoChips(data.cv_demos || []);
}

async function refresh() {
  const connection = $("connection");
  try {
    const response = await fetch("/api/launcher-status", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderStatus(await response.json());
    connection.textContent = `Live · ${new Date().toLocaleTimeString()}`;
    connection.className = "status-pill online";
  } catch (error) {
    connection.textContent = `Offline · ${error.message}`;
    connection.className = "status-pill offline";
  }
}

// Same hidden-pause pattern as app.js: an unattended kiosk costs nothing.
let pollTimer = null;

function startPolling() {
  if (pollTimer === null) {
    refresh();
    pollTimer = setInterval(refresh, 15000);
  }
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopPolling(); else startPolling();
});

$("tile-camera").addEventListener("click", () => postControl("switch-camera-cv"));
$("tile-mapping").addEventListener("click", () => postControl("switch-mapping"));
$("tile-display-off").addEventListener("click", () => postControl("display-off"));
$("btn-sd-backup").addEventListener("click", () => postControl("sd-backup"));
$("btn-kiosk-restart").addEventListener("click", () => postControl("kiosk-restart"));
$("btn-power-toggle").addEventListener("click", async () => {
  await postControl("power-toggle");
  await refresh();
});

startPolling();
