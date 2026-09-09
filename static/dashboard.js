const PANEL_STATES = ["empty", "loading", "ready", "error"];

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
  if (!PANEL_STATES.includes(state)) {
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
        "Live demo enabled. Failure Lab, schedule, and web-call controls will connect in tasks 014–016.",
    };
  }

  return {
    state: "ready",
    message:
      "Live web calls are paused (LIVE_DEMO_ENABLED=false). Prerecorded evidence and read-only views remain available once wired.",
  };
}

function initializeShell() {
  const config = readConfig();
  const demoStatus = describeDemoStatus(config);
  setDemoBanner(demoStatus.state, demoStatus.message);

  document.querySelectorAll("[data-panel]").forEach((panel) => {
    setPanelState(panel, "empty");
  });
}

window.DashboardShell = {
  PANEL_STATES,
  readConfig,
  setPanelState,
  setDemoBanner,
  initializeShell,
};

document.addEventListener("DOMContentLoaded", initializeShell);
