import { fetchSettingsReadiness, runSettingsReadinessChecks } from "../api/readiness.js";
import { SETTINGS_SECTIONS, sectionById } from "./registry.js";

const readinessItems = (payload) => payload?.items || payload?.item?.sections || payload?.sections || [];
const normalizedState = (item) => String(item?.state || item?.readiness || "unknown").toLowerCase();

function activationLabel(item) {
  const impact = String(item.activationImpact || item.activation || "none").toLowerCase();
  return {
    none: "Applies immediately",
    immediate: "Applies immediately",
    "application-restart": "Application restart required",
    restart: "Restart required",
    "restart-required": "Restart required",
    redeploy: "Apply / Redeploy required",
    "container-recreation": "Container recreation required",
  }[impact] || `Activation: ${impact}`;
}

function renderCard(root, registration, item = {}) {
  const card = document.createElement("article");
  card.className = "settings-readiness-card";
  card.dataset.state = normalizedState(item);
  const title = document.createElement("h4"); title.textContent = registration.label;
  const state = document.createElement("p"); state.className = "settings-readiness-state";
  state.textContent = item.enabled === false && !registration.required ? "Disabled (optional)" : item.summary || `State: ${normalizedState(item)}`;
  const activation = document.createElement("p"); activation.className = "settings-activation-impact"; activation.textContent = activationLabel(item);
  const defaults = document.createElement("p"); defaults.className = "muted";
  defaults.textContent = item.safeLocalDefaults || "Safe local defaults are used until you provide an override.";
  const action = document.createElement("button"); action.type = "button"; action.textContent = item.nextAction?.label || "Review";
  action.addEventListener("click", () => root.activate(registration.id, true));
  card.append(title, state, activation, defaults, action);
  return card;
}

function firstIncomplete(items) {
  return SETTINGS_SECTIONS.filter((section) => section.id !== "overview" && section.required)
    .find((section) => {
      const item = items.find((candidate) => candidate.id === section.id || candidate.section === section.id);
      return !["ready", "complete", "disabled"].includes(normalizedState(item));
    });
}

function renderCheckResults(root, payload) {
  const container = root.querySelector("#settings-all-checks-results"); container.replaceChildren();
  const results = payload?.items || payload?.results || payload?.item?.results || [];
  results.forEach((result) => {
    const card = document.createElement("article"); card.className = "settings-diagnostic"; card.dataset.state = normalizedState(result);
    const title = document.createElement("h4"); title.textContent = result.label || result.section || result.name || "Integration check";
    const summary = document.createElement("p"); summary.textContent = result.summary || result.message || `State: ${normalizedState(result)}`;
    card.append(title, summary); container.append(card);
  });
  if (!results.length) container.textContent = "No checks were returned.";
  root.querySelector("#settings-all-checks-summary").textContent =
    payload?.summary || `Checks completed with ${results.length} result${results.length === 1 ? "" : "s"}; unavailable providers do not hide successful results.`;
}

export function initializeSettingsWorkspace(root) {
  const tabs = root.querySelector("#settings-tabs");
  if (!tabs || tabs.dataset.initialized === "true") return;
  const activate = (id, focus = false) => {
    if (!sectionById(id)) return;
    SETTINGS_SECTIONS.forEach((section) => {
      const tab = root.querySelector(`#settings-tab-${section.id}`);
      const panel = root.querySelector(`#settings-section-${section.id}`);
      tab.setAttribute("aria-selected", String(section.id === id)); tab.tabIndex = section.id === id ? 0 : -1;
      panel.hidden = section.id !== id;
    });
    if (focus) root.querySelector(`#settings-tab-${id}`).focus();
  };
  const api = { activate };
  SETTINGS_SECTIONS.forEach((section, index) => {
    const tab = document.createElement("button"); tab.type = "button"; tab.id = `settings-tab-${section.id}`;
    tab.role = "tab"; tab.textContent = section.label; tab.setAttribute("aria-controls", `settings-section-${section.id}`);
    tab.setAttribute("aria-selected", String(index === 0)); tab.tabIndex = index === 0 ? 0 : -1;
    tab.addEventListener("click", () => activate(section.id));
    tabs.append(tab);
  });
  tabs.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = SETTINGS_SECTIONS.findIndex((section) => root.querySelector(`#settings-tab-${section.id}`) === document.activeElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? SETTINGS_SECTIONS.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + SETTINGS_SECTIONS.length) % SETTINGS_SECTIONS.length;
    activate(SETTINGS_SECTIONS[next].id, true);
  });
  root.settingsWorkspace = api; tabs.dataset.initialized = "true"; activate("overview");
  root.querySelector("#settings-run-all-checks").addEventListener("click", async () => {
    const summary = root.querySelector("#settings-all-checks-summary"); summary.textContent = "Running bounded checks…";
    try { renderCheckResults(root, await runSettingsReadinessChecks()); }
    catch (error) { summary.textContent = `Some checks are unavailable: ${error.message}`; }
  });
}

export async function refreshSettingsWorkspace(root) {
  const cards = root.querySelector("#settings-overview-cards");
  try {
    const payload = await fetchSettingsReadiness(); const items = readinessItems(payload); cards.replaceChildren();
    SETTINGS_SECTIONS.filter((section) => section.id !== "overview").forEach((section) => {
      const item = items.find((candidate) => candidate.id === section.id || candidate.section === section.id);
      cards.append(renderCard(root.settingsWorkspace, section, item));
    });
    const next = firstIncomplete(items);
    root.querySelector("#settings-guided-summary").textContent = next
      ? `Continue setup with ${next.label}. Progress is derived from current readiness.`
      : "Required integrations are ready. Optional integrations may remain disabled.";
  } catch (error) {
    root.querySelector("#settings-guided-summary").textContent = `Readiness is temporarily unavailable: ${error.message}`;
    cards.textContent = "Settings remain available by section.";
  }
}
