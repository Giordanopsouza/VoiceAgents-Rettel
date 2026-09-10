const PANEL_STATES = ["empty", "loading", "ready", "error"];
const SCHEDULE_POLL_MS = 2000;
const operatorBusy = {
  failureLab: false,
  reset: false,
};

function readConfig() {
  const node = document.getElementById("dashboard-config");
  if (!node?.textContent) {
    return { liveDemoEnabled: false };
  }

  try {
    return JSON.parse(node.textContent);
  } catch {
    return { liveDemoEnabled: false };
  }
}

function setPanelState(panel, state) {
  if (!panel || !PANEL_STATES.includes(state)) {
    return;
  }

  panel.dataset.state = state;
  panel.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== state;
  });
}

function setDemoBanner(state, message) {
  const banner = document.getElementById("demo-banner");
  const messageNode = document.getElementById("demo-banner-message");
  if (!banner || !messageNode) {
    return;
  }

  banner.dataset.state = state;
  messageNode.textContent = message;
}

function describeDemoStatus(config) {
  if (config.liveDemoEnabled) {
    return {
      state: "ready",
      message:
        "Live demo enabled. Confirm the seeded schedule, then use Failure Lab before starting a web call.",
    };
  }

  return {
    state: "ready",
    message:
      "Live web calls are paused (LIVE_DEMO_ENABLED=false). The schedule stays readable; reset stays locked.",
  };
}

function looksLikeInternalError(message) {
  return /traceback \(most recent call last\)|file "\/.*", line \d+/i.test(
    message
  );
}

function publicErrorMessage(body, fallback) {
  const detail = body?.detail;
  let message = fallback;
  if (typeof detail === "string") {
    message = detail;
  } else if (detail && typeof detail.message === "string") {
    message = detail.message;
  }
  if (typeof message !== "string" || looksLikeInternalError(message)) {
    return fallback;
  }
  return message;
}

function errorFromUnknown(error, fallback) {
  if (error instanceof Error && error.message && !looksLikeInternalError(error.message)) {
    return error.message;
  }
  return fallback;
}

async function readJsonBody(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await readJsonBody(response);
  if (!response.ok) {
    throw new Error(publicErrorMessage(body, `Request failed (${response.status})`));
  }
  return body;
}

function showPanelError(panel, messageId, error, fallback) {
  const messageNode = document.getElementById(messageId);
  if (messageNode) {
    messageNode.textContent = errorFromUnknown(error, fallback);
  }
  setPanelState(panel, "error");
}

function formatClock(isoTimestamp) {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):\d{2}Z$/.exec(isoTimestamp);
  if (!match) {
    return isoTimestamp;
  }
  const hour = Number(match[2]);
  const minute = match[3];
  const hour12 = hour % 12 || 12;
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour12}:${minute} ${suffix}`;
}

function formatDay(isoDate) {
  const date = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return isoDate;
  }
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function renderSchedule(payload) {
  const grid = document.getElementById("schedule-grid");
  if (!grid) {
    return;
  }

  const byDate = new Map();
  for (const slot of payload.slots ?? []) {
    const day = String(slot.starts_at ?? "").slice(0, 10);
    if (!byDate.has(day)) {
      byDate.set(day, []);
    }
    byDate.get(day).push(slot);
  }

  grid.replaceChildren();
  for (const [day, slots] of byDate) {
    const section = document.createElement("section");
    section.className = "schedule-day";

    const heading = document.createElement("h3");
    heading.textContent = formatDay(day);

    const list = document.createElement("ul");
    list.className = "slot-list";

    for (const slot of slots) {
      const item = document.createElement("li");
      const status = slot.status === "occupied" ? "occupied" : "available";
      item.className = `slot slot--${status}`;

      const time = document.createElement("span");
      time.className = "slot__time";
      time.textContent = formatClock(slot.starts_at);

      const label = document.createElement("span");
      label.className = "slot__status";
      label.textContent = status;

      const id = document.createElement("span");
      id.className = "slot__id";
      id.textContent = slot.id;

      item.append(time, label, id);
      list.append(item);
    }

    section.append(heading, list);
    grid.append(section);
  }
}

function applyFailureLabSnapshot(snapshot) {
  const switchEl = document.getElementById("failure-lab-switch");
  const help = document.getElementById("failure-lab-help");
  if (switchEl) {
    switchEl.checked = Boolean(snapshot.enabled);
  }
  if (help && snapshot.timeout_seconds != null && snapshot.delay_seconds != null) {
    help.textContent = `Timeout ${snapshot.timeout_seconds}s · delay ${snapshot.delay_seconds}s · matches Retell booking function settings.`;
  }
}

function syncOperatorControls() {
  const config = readConfig();
  const switchEl = document.getElementById("failure-lab-switch");
  const resetButton = document.getElementById("reset-schedule-button");
  const resetHelp = document.getElementById("reset-schedule-help");
  const busy = operatorBusy.failureLab || operatorBusy.reset;

  if (switchEl) {
    switchEl.disabled = busy;
  }
  if (resetButton) {
    resetButton.disabled = busy || !config.liveDemoEnabled;
  }
  if (resetHelp) {
    if (!config.liveDemoEnabled) {
      resetHelp.textContent =
        "Reset is unavailable while the public live demo is paused.";
    } else if (busy) {
      resetHelp.textContent =
        "Wait for the current request to finish before changing controls.";
    } else {
      resetHelp.textContent =
        "Restores the deterministic seed when live demo guardrails allow it.";
    }
  }
}

async function refreshSchedule({ showLoading = false } = {}) {
  const panel = document.querySelector('[data-panel="schedule"]');
  if (showLoading) {
    setPanelState(panel, "loading");
  }
  try {
    const payload = await requestJson("/api/schedule");
    renderSchedule(payload);
    setPanelState(panel, "ready");
  } catch (error) {
    if (showLoading || panel?.dataset.state !== "ready") {
      showPanelError(
        panel,
        "schedule-error-message",
        error,
        "Could not load the schedule. Try again after reset."
      );
    } else {
      setDemoBanner("error", errorFromUnknown(error, "Could not refresh the schedule."));
    }
  }
}

async function loadFailureLab() {
  const panel = document.querySelector('[data-panel="failure-lab"]');
  setPanelState(panel, "loading");
  try {
    const snapshot = await requestJson("/api/failure-lab");
    applyFailureLabSnapshot(snapshot);
    setPanelState(panel, "ready");
  } catch (error) {
    showPanelError(
      panel,
      "failure-lab-error-message",
      error,
      "Could not read Failure Lab status from the server."
    );
  }
}

async function toggleFailureLab(event) {
  if (operatorBusy.failureLab || operatorBusy.reset) {
    event.target.checked = !event.target.checked;
    return;
  }

  const enabled = event.target.checked;
  const panel = document.querySelector('[data-panel="failure-lab"]');
  operatorBusy.failureLab = true;
  syncOperatorControls();
  setPanelState(panel, "loading");
  try {
    const snapshot = await requestJson("/api/failure-lab", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    applyFailureLabSnapshot(snapshot);
    setPanelState(panel, "ready");
  } catch (error) {
    event.target.checked = !enabled;
    showPanelError(
      panel,
      "failure-lab-error-message",
      error,
      "Could not update Failure Lab status."
    );
  } finally {
    operatorBusy.failureLab = false;
    syncOperatorControls();
  }
}

async function resetSchedule() {
  if (operatorBusy.reset || operatorBusy.failureLab) {
    return;
  }

  const panel = document.querySelector('[data-panel="schedule"]');
  operatorBusy.reset = true;
  syncOperatorControls();
  setPanelState(panel, "loading");
  try {
    const payload = await requestJson("/api/demo/reset", { method: "POST" });
    renderSchedule(payload);
    setPanelState(panel, "ready");
    setDemoBanner("ready", "Demo calendar restored to the seeded schedule.");
  } catch (error) {
    showPanelError(
      panel,
      "schedule-error-message",
      error,
      "Could not reset the calendar."
    );
    setDemoBanner("error", errorFromUnknown(error, "Could not reset the calendar."));
  } finally {
    operatorBusy.reset = false;
    syncOperatorControls();
  }
}

function initializeShell() {
  const config = readConfig();
  const demoStatus = describeDemoStatus(config);
  setDemoBanner(demoStatus.state, demoStatus.message);

  document.querySelectorAll("[data-panel]").forEach((panel) => {
    if (panel.dataset.panel === "schedule" || panel.dataset.panel === "failure-lab") {
      return;
    }
    setPanelState(panel, "empty");
  });
}

async function initializeDashboard() {
  initializeShell();
  syncOperatorControls();

  const resetButton = document.getElementById("reset-schedule-button");
  const switchEl = document.getElementById("failure-lab-switch");
  resetButton?.addEventListener("click", resetSchedule);
  switchEl?.addEventListener("change", toggleFailureLab);

  await Promise.all([refreshSchedule({ showLoading: true }), loadFailureLab()]);
  window.setInterval(() => {
    if (!document.hidden && !operatorBusy.reset) {
      refreshSchedule();
    }
  }, SCHEDULE_POLL_MS);
}

window.DashboardShell = {
  PANEL_STATES,
  readConfig,
  setPanelState,
  setDemoBanner,
  initializeShell,
  publicErrorMessage,
  initializeDashboard,
};

document.addEventListener("DOMContentLoaded", initializeDashboard);
