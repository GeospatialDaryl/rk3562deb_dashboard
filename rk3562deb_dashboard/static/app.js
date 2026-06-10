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
  $("block-io-list").innerHTML = (blocks || []).map((device) => `
    <div class="row table-row">
      <div><strong>${esc(device.name)}</strong><small>${esc(device.kind === "MMC" ? "eMMC" : device.kind || "disk")}</small></div>
      <div>W ${bytes(device.written_bytes_total)} · R ${bytes(device.read_bytes_total)}</div>
      <small>W ${bytes(device.write_bytes_per_sec)}/s · R ${bytes(device.read_bytes_per_sec)}/s</small>
    </div>
  `).join("") || `<p class="muted">No block devices found.</p>`;
}

function renderNpu(npu) {
  const devices = npu?.devices || [];
  const load = devices[0]?.load_percent;
  $("npu-load").textContent = load == null ? "n/a" : percent(load);
  setBar("npu-bar", load == null ? 0 : load);
  const rows = devices.map((device) => `
    <div class="row">
      <strong>${esc(device.name)}</strong>
      <small>${freq(device.frequency_hz)} / max ${freq(device.max_hz)} · ${esc(device.governor || "governor n/a")}</small>
    </div>
  `).join("");
  const driver = npu?.driver_version
    ? `<div class="row"><strong>rknpu driver</strong><small>v${esc(npu.driver_version)}</small></div>`
    : "";
  $("npu-list").innerHTML = (rows + driver)
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

async function refresh() {
  const connection = $("connection");
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    connection.textContent = `Live · ${new Date().toLocaleTimeString()}`;
    connection.className = "status-pill online";
  } catch (error) {
    connection.textContent = `Offline · ${error.message}`;
    connection.className = "status-pill offline";
  }
}

refresh();
setInterval(refresh, 2000);
