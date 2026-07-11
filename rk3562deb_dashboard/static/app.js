const $ = (id) => document.getElementById(id);
const formatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

function bytes(value = 0) {
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let size = Number(value) || 0;
  let unit = 0;
  while (Math.abs(size) >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${formatter.format(size)} ${units[unit]}`;
}

function freq(value, unit = "Hz") {
  if (!value) return "n/a";
  const units = unit === "kHz" ? ["kHz", "MHz", "GHz"] : ["Hz", "kHz", "MHz", "GHz"];
  let size = Number(value);
  let index = 0;
  while (Math.abs(size) >= 1000 && index < units.length - 1) {
    size /= 1000;
    index += 1;
  }
  return `${formatter.format(size)} ${units[index]}`;
}

function percent(value = 0) {
  return `${formatter.format(value)}%`;
}

function setBar(id, value) {
  $(id).style.width = `${Math.max(0, Math.min(100, value || 0))}%`;
}

function renderHost(host) {
  $("host-title").textContent = host.model || host.hostname || "Debian host";
  $("host-subtitle").textContent = [
    host.compatible,
    host.kernel ? `Linux ${host.kernel}` : null,
    host.machine,
    `up ${formatDuration(host.uptime_seconds)}`,
  ].filter(Boolean).join(" • ");
  $("load-strip").innerHTML = (host.load || []).map((load, index) => (
    `<div class="load" title="${[1, 5, 15][index]} minute load">${formatter.format(load)}</div>`
  )).join("");
}

function formatDuration(seconds = 0) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}

function renderCpu(cpu) {
  const usage = cpu.total?.usage_percent || 0;
  $("cpu-total").textContent = percent(usage);
  setBar("cpu-bar", usage);
  $("cpu-cores").innerHTML = (cpu.cores || []).map((core) => `
    <div class="tile">
      <strong>${core.name.toUpperCase()} · ${percent(core.usage_percent)}</strong>
      <small>${freq(core.frequency_khz, "kHz")} / max ${freq(core.max_khz, "kHz")}</small>
    </div>
  `).join("");
}

function renderMemory(memory, swap) {
  $("memory-percent").textContent = percent(memory.usage_percent);
  setBar("memory-bar", memory.usage_percent);
  $("memory-list").innerHTML = `
    <dt>Used</dt><dd>${bytes(memory.used_bytes)} / ${bytes(memory.total_bytes)}</dd>
    <dt>Available</dt><dd>${bytes(memory.available_bytes)}</dd>
    <dt>Cache</dt><dd>${bytes(memory.cached_bytes)}</dd>
    <dt>Swap</dt><dd>${bytes(swap.used_bytes)} / ${bytes(swap.total_bytes)}</dd>
  `;
}

function renderThermal(thermal) {
  const temps = (thermal || []).map((zone) => zone.temperature_c).filter((temp) => temp !== null);
  const max = temps.length ? Math.max(...temps) : null;
  $("thermal-max").textContent = max === null ? "n/a" : `${formatter.format(max)}°C`;
  $("thermal-max").className = `metric-big${max >= 80 ? " metric-alert" : max >= 70 ? " metric-warn" : ""}`;
  $("thermal-list").innerHTML = (thermal || []).map((zone) => `
    <div class="row">
      <strong>${esc(zone.name)}</strong>
      <small>${zone.temperature_c === null ? "n/a" : `${formatter.format(zone.temperature_c)}°C`} · ${esc(zone.path)}</small>
    </div>
  `).join("") || `<p class="muted">No thermal zones exposed by this kernel.</p>`;
}

function renderDisks(disks) {
  $("disk-list").innerHTML = (disks || []).map((disk) => `
    <div class="row table-row">
      <div><strong>${esc(disk.mount)}</strong><small>${esc(disk.source)} · ${esc(disk.filesystem)}</small></div>
      <div>${percent(disk.usage_percent)} · ${bytes(disk.used_bytes)} / ${bytes(disk.total_bytes)}</div>
      <small>R ${bytes(disk.read_bytes_per_sec)}/s · W ${bytes(disk.write_bytes_per_sec)}/s</small>
    </div>
  `).join("") || `<p class="muted">No block-backed mounts found.</p>`;
}

function renderNetwork(network) {
  $("network-list").innerHTML = (network || []).map((iface) => `
    <div class="row table-row">
      <div><strong>${esc(iface.name)}</strong><small>${esc(iface.operstate || "unknown")}</small></div>
      <div>RX ${bytes(iface.rx_bytes_per_sec)}/s</div>
      <div>TX ${bytes(iface.tx_bytes_per_sec)}/s</div>
    </div>
  `).join("");
}

function renderRockchip(rockchip) {
  const devfreq = (rockchip.devfreq || []).map((device) => `
    <div class="tile"><strong>${esc(device.name)}</strong><small>${freq(device.frequency_hz)} · ${esc(device.governor || "governor n/a")}</small></div>
  `).join("");
  const regulators = (rockchip.regulators || []).map((regulator) => `
    <div class="tile"><strong>${esc(regulator.name)}</strong><small>${esc(regulator.state || "n/a")} · ${regulator.microvolts ? `${formatter.format(regulator.microvolts / 1000)} mV` : "voltage n/a"}</small></div>
  `).join("");
  const storage = (rockchip.storage || []).map((disk) => `
    <div class="tile"><strong>${esc(disk.name)}</strong><small>${bytes(disk.size_bytes)} · ${esc(disk.model || "model n/a")}</small></div>
  `).join("");
  const tiles = [devfreq, regulators, storage].join("");
  $("rockchip-list").innerHTML = tiles
    || `<p class="muted">Rockchip-specific sysfs data is not exposed on this host.</p>`;
}

function renderPower(power) {
  const supplies = (power?.supplies || []);
  const battery = supplies.find((s) => s.capacity_percent !== null && s.capacity_percent !== undefined);
  $("power-capacity").textContent = battery ? percent(battery.capacity_percent) : "n/a";
  $("power-list").innerHTML = supplies.map((supply) => `
    <div class="row">
      <strong>${esc(supply.name)}</strong>
      <small>${esc([
        supply.type,
        supply.status,
        supply.capacity_percent !== null && supply.capacity_percent !== undefined ? percent(supply.capacity_percent) : null,
        supply.voltage_uv != null ? `${formatter.format(supply.voltage_uv / 1_000_000)} V` : null,
        supply.current_ua != null ? `${formatter.format(Math.abs(supply.current_ua) / 1_000)} mA` : null,
      ].filter(Boolean).join(" · "))}</small>
    </div>
  `).join("") || `<p class="muted">No power supplies exposed by sysfs.</p>`;
}

function renderBlockIo(blocks) {
  const sd = (blocks || []).find((device) => device.kind === "SD");
  $("sd-written").textContent = sd ? bytes(sd.written_bytes_total) : "n/a";
  const sdWritten = sd ? sd.written_bytes_total : 0;
  $("sd-written").className =
    `metric-big${sdWritten > 100 * 1024 * 1024 ? " metric-alert" : sdWritten > 0 ? " metric-warn" : ""}`;
  $("block-io-list").innerHTML = (blocks || []).map((device) => `
    <div class="row table-row">
      <div><strong>${esc(device.name)}</strong><small>${esc(device.kind === "MMC" ? "eMMC" : device.kind || "disk")}</small></div>
      <div>W ${bytes(device.written_bytes_total)} · R ${bytes(device.read_bytes_total)}</div>
      <small>W ${bytes(device.write_bytes_per_sec)}/s · R ${bytes(device.read_bytes_per_sec)}/s</small>
    </div>
  `).join("") || `<p class="muted">No block devices found.</p>`;
}

// Some vendor kernels never update the NPU devfreq load attribute; only show it
// as a live percentage once it has been observed to vary.
const npuLoadValues = new Set();

function renderNpu(npu) {
  const devices = npu?.devices || [];
  const primary = devices[0];
  const loadPct = primary?.load_percent;
  $("npu-freq").textContent = primary ? freq(primary.frequency_hz) : "n/a";
  $("npu-freq").className =
    `metric-big${loadPct >= 80 ? " metric-alert" : loadPct >= 50 ? " metric-warn" : ""}`;
  setBar("npu-bar", loadPct || 0);
  $("npu-bar").className = loadPct >= 80 ? "bar-alert" : loadPct >= 50 ? "bar-warn" : "";
  if (loadPct != null) npuLoadValues.add(loadPct);
  const rows = devices.map((device) => `
    <div class="row">
      <strong>${esc(device.name)}</strong>
      <small>${freq(device.min_hz)}–${freq(device.max_hz)} · ${esc(device.governor || "governor n/a")}</small>
    </div>
  `).join("");
  const load = primary?.load_percent == null ? "" : `
    <div class="row">
      <strong>devfreq load</strong>
      <small>${npuLoadValues.size > 1
        ? percent(primary.load_percent)
        : `reports ${percent(primary.load_percent)} — static on this kernel`}</small>
    </div>`;
  const driver = npu?.driver_version
    ? `<div class="row"><strong>rknpu driver</strong><small>v${esc(npu.driver_version)}</small></div>`
    : "";
  $("npu-list").innerHTML = (rows + load + driver)
    || `<p class="muted">No NPU devfreq exposed by this kernel.</p>`;
}

function renderProcesses(processes) {
  $("process-count").textContent = processes.count || 0;
  $("process-list").innerHTML = (processes.top_memory || []).map((proc) => `
    <div class="row">
      <strong>${esc(proc.name)} <small>#${proc.pid}</small></strong>
      <small>${esc(proc.state)} · RSS ${bytes(proc.rss_bytes)}</small>
    </div>
  `).join("");
}

function render(snapshot) {
  renderHost(snapshot.host);
  renderCpu(snapshot.cpu);
  renderMemory(snapshot.memory, snapshot.swap);
  renderThermal(snapshot.thermal);
  renderDisks(snapshot.disks);
  renderBlockIo(snapshot.block_io);
  renderNetwork(snapshot.network);
  renderRockchip(snapshot.rockchip);
  renderProcesses(snapshot.processes);
  renderPower(snapshot.power);
  renderNpu(snapshot.npu);
}

function drawSparkline(canvasId, series, options = {}) {
  const canvas = $(canvasId);
  if (!canvas || !canvas.clientWidth) return;
  const scale = window.devicePixelRatio || 1;
  canvas.width = canvas.clientWidth * scale;
  canvas.height = 44 * scale;
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);
  const width = canvas.clientWidth;
  const height = 44;
  ctx.clearRect(0, 0, width, height);

  const lines = series.filter((line) => line.values.some((value) => value != null));
  if (!lines.length) return;
  const all = lines.flatMap((line) => line.values).filter((value) => value != null);
  const min = options.min ?? Math.min(...all);
  const max = Math.max(options.minSpan ?? 0, ...all.map((value) => value - min)) + min;
  const span = Math.max(max - min, 1e-9);
  const count = Math.max(...lines.map((line) => line.values.length));

  for (const line of lines) {
    const points = [];
    line.values.forEach((value, index) => {
      if (value == null) return;
      const x = count > 1 ? (index / (count - 1)) * width : width;
      const y = height - 3 - ((value - min) / span) * (height - 6);
      points.push({ x, y });
    });
    if (!points.length) continue;

    const fillGrad = ctx.createLinearGradient(0, 0, 0, height);
    fillGrad.addColorStop(0, line.color + "30");
    fillGrad.addColorStop(1, line.color + "00");

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const cur = points[i];
      const cpx = (prev.x + cur.x) / 2;
      ctx.bezierCurveTo(cpx, prev.y, cpx, cur.y, cur.x, cur.y);
    }
    ctx.strokeStyle = line.color;
    ctx.lineWidth = 1.8;
    ctx.stroke();

    ctx.lineTo(points[points.length - 1].x, height);
    ctx.lineTo(points[0].x, height);
    ctx.closePath();
    ctx.fillStyle = fillGrad;
    ctx.fill();
  }
}

function renderHistory(history) {
  const points = history?.points || [];
  drawSparkline("cpu-spark", [
    { values: points.map((point) => point.cpu), color: "#42d9f5" },
  ], { min: 0, minSpan: 100 });
  drawSparkline("thermal-spark", [
    { values: points.map((point) => point.temp), color: "#f7d774" },
  ], { minSpan: 5 });
  drawSparkline("write-spark", [
    { values: points.map((point) => point.emmc_write), color: "#42d9f5" },
    { values: points.map((point) => point.sd_write), color: "#ff6b81" },
  ], { min: 0, minSpan: 1024 });
}

async function refresh() {
  const connection = $("connection");
  try {
    const [snapshotResponse, historyResponse] = await Promise.all([
      fetch("/api/snapshot", { cache: "no-store" }),
      fetch("/api/history", { cache: "no-store" }),
    ]);
    if (!snapshotResponse.ok) throw new Error(`HTTP ${snapshotResponse.status}`);
    render(await snapshotResponse.json());
    if (historyResponse.ok) renderHistory(await historyResponse.json());
    connection.textContent = `Live · ${new Date().toLocaleTimeString()}`;
    connection.className = "status-pill online";
  } catch (error) {
    connection.textContent = `Offline · ${error.message}`;
    connection.className = "status-pill offline";
  }
}

// Pause polling while the page is hidden (blanked kiosk screen, background
// tab) so an always-on display costs nothing when nobody is looking.
let pollTimer = null;

function startPolling() {
  if (pollTimer === null) {
    refresh();
    pollTimer = setInterval(refresh, 30000);
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

async function runControlAction(action, button) {
  const status = $("control-status");
  button.disabled = true;
  status.className = "muted";
  status.textContent = "Running…";
  try {
    const response = await fetch(`/api/control/${action}`, { method: "POST" });
    const body = await response.json();
    if (response.ok && body.ok) {
      status.className = "ok";
      status.textContent = `${action} succeeded`;
    } else {
      status.className = "err";
      status.textContent = `${action} failed: ${body.error || body.stderr || response.status}`;
    }
  } catch (error) {
    status.className = "err";
    status.textContent = `${action} failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

$("btn-kiosk-restart").addEventListener("click", () => {
  runControlAction("kiosk-restart", $("btn-kiosk-restart"));
});
$("btn-sd-backup").addEventListener("click", () => {
  runControlAction("sd-backup", $("btn-sd-backup"));
});

$("btn-switch-camera-cv").addEventListener("click", () => {
  runControlAction("switch-camera-cv", $("btn-switch-camera-cv"));
});

$("btn-transcribe-start").addEventListener("click", () => {
  runControlAction("transcribe-start", $("btn-transcribe-start"));
});
$("btn-transcribe-stop").addEventListener("click", () => {
  runControlAction("transcribe-stop", $("btn-transcribe-stop"));
});

$("btn-display-off").addEventListener("click", () => {
  runControlAction("display-off", $("btn-display-off"));
});

startPolling();
