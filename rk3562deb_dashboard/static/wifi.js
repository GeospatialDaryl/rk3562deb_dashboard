// WiFi page: scan list, tap-to-join with on-screen keyboard, forget.
// All network names are untrusted — DOM is built with createElement +
// textContent only, never innerHTML.
import { createOSK } from "/osk.js";

const $ = (id) => document.getElementById(id);

// Write endpoints are 127.0.0.1-only server-side; hide the affordances for
// LAN viewers so the page doesn't offer taps that will 403.
const CAN_WRITE = ["localhost", "127.0.0.1"].includes(location.hostname);

let openPanel = null; // { destroy() } for the currently open PSK panel/OSK

function setResult(kind, text) {
  const el = $("wifi-result");
  el.className = `${kind} shell`;
  el.textContent = text;
}

async function api(path, body) {
  const response = await fetch(path, body === undefined
    ? { cache: "no-store" }
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = await response.json();
  return { ok: response.ok && payload.ok !== false, payload };
}

async function loadStatus() {
  const connection = $("connection");
  try {
    const { payload } = await api("/api/wifi/status");
    $("wifi-ssid").textContent = payload.ssid || "not connected";
    $("wifi-signal").textContent = payload.signal == null ? "--" : `${payload.signal}%`;
    $("wifi-ip").textContent = payload.ip4 || "--";
    $("wifi-radio").textContent = payload.radio || "--";
    connection.textContent = `Live · ${new Date().toLocaleTimeString()}`;
    connection.className = "status-pill online";
  } catch (error) {
    connection.textContent = `Offline · ${error.message}`;
    connection.className = "status-pill offline";
  }
}

function signalBars(signal) {
  const bars = document.createElement("span");
  bars.className = "signal-bars";
  const level = signal >= 75 ? 4 : signal >= 50 ? 3 : signal >= 25 ? 2 : 1;
  for (let i = 1; i <= 4; i++) {
    const bar = document.createElement("span");
    bar.className = `signal-bar${i <= level ? " on" : ""}`;
    bar.style.height = `${4 + i * 3}px`;
    bars.appendChild(bar);
  }
  return bars;
}

function badge(text, kind) {
  const el = document.createElement("span");
  el.className = `badge badge-${kind}`;
  el.textContent = text;
  return el;
}

function closePanel() {
  if (openPanel) {
    openPanel.destroy();
    openPanel = null;
  }
}

async function connect(ssid, psk, statusEl) {
  statusEl.textContent = "Connecting…";
  setResult("muted", `Joining ${ssid}…`);
  try {
    const { ok, payload } = await api("/api/wifi/connect", psk ? { ssid, psk } : { ssid });
    if (ok) {
      closePanel();
      setResult("ok", `Connected to ${ssid}`);
      await Promise.all([loadStatus(), loadScan(false)]);
      return true;
    }
    const message = payload.error === "wrong-password"
      ? "Wrong password — try again"
      : `Failed: ${payload.detail || payload.error}`;
    statusEl.textContent = message;
    setResult("err", `${ssid}: ${message}`);
  } catch (error) {
    statusEl.textContent = error.message;
    setResult("err", `${ssid}: ${error.message}`);
  }
  return false;
}

function openPskPanel(network, rowEl) {
  closePanel();
  const panel = document.createElement("div");
  panel.className = "psk-panel";

  const warning = document.createElement("p");
  warning.className = "muted psk-note";
  warning.textContent = "Connecting switches networks — the current connection will drop.";
  panel.appendChild(warning);

  const inputRow = document.createElement("div");
  inputRow.className = "psk-input-row";
  const input = document.createElement("input");
  input.type = "password";
  input.className = "psk-input";
  input.placeholder = "Password";
  input.autocomplete = "off";
  const showBtn = document.createElement("button");
  showBtn.type = "button";
  showBtn.className = "btn psk-show";
  showBtn.textContent = "show";
  showBtn.addEventListener("click", () => {
    const hidden = input.type === "password";
    input.type = hidden ? "text" : "password";
    showBtn.textContent = hidden ? "hide" : "show";
  });
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", closePanel);
  inputRow.append(input, showBtn, cancelBtn);
  panel.appendChild(inputRow);

  const statusEl = document.createElement("p");
  statusEl.className = "muted psk-note";
  panel.appendChild(statusEl);

  const oskHost = document.createElement("div");
  panel.appendChild(oskHost);
  const osk = createOSK(input, oskHost, () => {
    if (input.value.length >= 8) connect(network.ssid, input.value, statusEl);
    else statusEl.textContent = "Password must be 8-63 characters";
  });

  rowEl.after(panel);
  openPanel = {
    destroy() {
      osk.destroy();
      panel.remove();
    },
  };
}

function networkRow(network) {
  const row = document.createElement("div");
  row.className = "wifi-row";

  const main = document.createElement("div");
  main.className = "wifi-row-main";
  const nameLine = document.createElement("strong");
  nameLine.textContent = network.ssid;
  // No emoji glyphs anywhere on this page: neither headless chromium nor
  // cog/WPEWebKit has an emoji font installed on this device.
  const subLine = document.createElement("small");
  subLine.textContent = network.security || "open";
  main.append(nameLine, subLine);

  const side = document.createElement("div");
  side.className = "wifi-row-side";
  if (network.in_use) side.appendChild(badge("connected", "ok"));
  else if (network.known) side.appendChild(badge("saved", "info"));
  side.appendChild(signalBars(network.signal));

  const enterprise = (network.security || "").includes("802.1X");
  if (enterprise) {
    row.classList.add("wifi-row-disabled");
    subLine.textContent += " · unsupported";
  }

  if (CAN_WRITE && network.known && !network.in_use) {
    const forget = document.createElement("button");
    forget.type = "button";
    forget.className = "btn wifi-forget";
    forget.textContent = "Forget";
    let armed = false;
    forget.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!armed) {
        armed = true;
        forget.textContent = "Really forget?";
        setTimeout(() => { armed = false; forget.textContent = "Forget"; }, 3000);
        return;
      }
      const { ok, payload } = await api("/api/wifi/forget", { name: network.ssid });
      setResult(ok ? "ok" : "err", ok ? `Forgot ${network.ssid}` : `Forget failed: ${payload.error}`);
      loadScan(false);
    });
    side.appendChild(forget);
  }

  row.append(main, side);

  if (CAN_WRITE && !enterprise && !network.in_use) {
    row.classList.add("wifi-row-tappable");
    row.addEventListener("click", () => {
      const statusEl = document.createElement("p");
      if (network.known || !network.security) {
        connect(network.ssid, null, statusEl);
      } else {
        openPskPanel(network, row);
      }
    });
  }
  return row;
}

async function loadScan(rescan) {
  const list = $("wifi-list");
  const btn = $("btn-rescan");
  if (rescan) {
    btn.disabled = true;
    btn.textContent = "Scanning…";
  }
  try {
    const { ok, payload } = await api(`/api/wifi/scan?rescan=${rescan ? "yes" : "no"}`);
    if (!ok) throw new Error(payload.error || "scan failed");
    closePanel();
    list.textContent = "";
    for (const network of payload.networks) list.appendChild(networkRow(network));
    if (!payload.networks.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No networks found — try Rescan.";
      list.appendChild(empty);
    }
  } catch (error) {
    setResult("err", `Scan failed: ${error.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Rescan";
  }
}

$("btn-rescan").addEventListener("click", () => loadScan(true));

// Status poll with the same hidden-pause pattern as launcher.js; the scan
// list only refreshes on demand or after actions.
let pollTimer = null;

function startPolling() {
  if (pollTimer === null) {
    loadStatus();
    pollTimer = setInterval(loadStatus, 15000);
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

startPolling();
loadScan(false);
