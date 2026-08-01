const ICONS = {
  idle: "⏳",
  waiting_usb: "🔌",
  scanning: "🔍",
  clean: "✅",
  infected: "🦠",
  error: "⚠️",
  multiple_usb: "⚠️",
  waiting_eject: "⏏️",
};

const CLASSES = {
  idle: "status-waiting",
  waiting_usb: "status-waiting",
  scanning: "status-scanning",
  clean: "status-clean",
  infected: "status-infected",
  error: "status-error",
  multiple_usb: "status-error",
  waiting_eject: "status-waiting",
};

const panel = document.getElementById("status-panel");
const icon = document.getElementById("status-icon");
const message = document.getElementById("status-message");
const logEl = document.getElementById("scan-log");
const scannersList = document.getElementById("scanners-list");
const currentScanner = document.getElementById("current-scanner");

async function poll() {
  try {
    const res = await fetch("/api/scan/status");
    const data = await res.json();

    icon.textContent = ICONS[data.state] || "⏳";
    message.textContent = data.message;
    panel.className = "status-panel " + (CLASSES[data.state] || "status-waiting");

    if (data.scanners && scannersList) {
      scannersList.textContent = "Moteurs : " + data.scanners
        .map((s) => s.display_name + (s.available ? " ✓" : " ✗"))
        .join(" | ");
    }

    if (currentScanner) {
      currentScanner.textContent = data.current_scanner
        ? `En cours : ${data.current_scanner}`
        : "";
    }

    if (data.log && data.log.length) {
      logEl.textContent = data.log.join("\n");
      logEl.scrollTop = logEl.scrollHeight;
    }
  } catch (e) {
    message.textContent = "Connexion au service de scan impossible.";
  }
}

setInterval(poll, 1500);
poll();
