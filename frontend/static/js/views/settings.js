import {
  fetchSettings,
  fetchSettingsListenerStatus,
  retrySettingsListener,
  saveSettings,
} from "../api/settings.js";
import { listenerReloadMessage } from "../components/settings-shell.js";
import { byId } from "../core/dom.js";
import { createSettingsState, listenerSettingsMatchStatus } from "../state/settings.js";
import { inspectManagedChannels, mutateManagedChannel, previewManagedChannel } from "../api/settings.js";
import { settingsUnavailableMessage } from "../components/settings-shell.js";
import { clearSettingsPreview, createSettingsState } from "../state/settings.js";

const state = createSettingsState();

function renderReminder() {
  const reminder = byId("settings-listener-reload-reminder");
  reminder.hidden = !state.runtimeReloadRequired;
  reminder.textContent = state.runtimeReloadRequired ? listenerReloadMessage() : "";
}

function renderProfile(profile) {
  state.profile = profile;
  const listener = profile.resultListener || {};
  byId("settings-listener-host").value = listener.host || "";
  byId("settings-listener-port").value = listener.port || "";
  byId("settings-listener-mllp").checked = listener.mllpFraming !== false;
  byId("settings-listener-auto-start").checked = listener.autoStart !== false;
}

function listenerPayload() {
  return {
    host: byId("settings-listener-host").value.trim(),
    port: Number(byId("settings-listener-port").value),
    mllpFraming: byId("settings-listener-mllp").checked,
    autoStart: byId("settings-listener-auto-start").checked,
  };
}

export async function refreshSettings() {
  const result = await fetchSettings();
  renderProfile(result.item);
  const status = await fetchSettingsListenerStatus();
  state.runtimeReloadRequired = !listenerSettingsMatchStatus(state.profile, status.item);
  renderReminder();
  return state;
}

export async function saveListenerSettings() {
  const payload = {
    managementApi: { ...state.profile.managementApi },
    resultListener: listenerPayload(),
    managedChannels: state.profile.managedChannels || [],
  };
  delete payload.managementApi.passwordConfigured;
  const result = await saveSettings(payload);
  renderProfile(result.item);
  state.runtimeReloadRequired = Boolean(result.runtimeReloadRequired);
  renderReminder();
  return result;
}

export async function retryListenerFromSettings() {
  const result = await retrySettingsListener();
  state.runtimeReloadRequired = !listenerSettingsMatchStatus(state.profile, result.item);
  renderReminder();
  return result;
}

export function initializeSettingsView(root) {
  if (!root || state.initialized) return state;
  root.dataset.moduleOwner = "settings";
  byId("save-listener-settings").addEventListener("click", () => saveListenerSettings().catch((error) => {
    byId("settings-listener-reload-reminder").hidden = false;
    byId("settings-listener-reload-reminder").textContent = error.message;
  }));
  byId("retry-settings-listener").addEventListener("click", () => retryListenerFromSettings().catch((error) => {
    byId("settings-listener-reload-reminder").hidden = false;
    byId("settings-listener-reload-reminder").textContent = error.message;
  }));
  root.dataset.emptyState = settingsUnavailableMessage();
  root.querySelector("#settings-refresh").addEventListener("click", refreshSettingsChannels);
  root.querySelector("#settings-managed-list").addEventListener("click", handleAction);
  root.querySelector("#settings-preview-execute").addEventListener("click", executePreview);
  root.querySelector("#settings-delete-confirmation").addEventListener("input", (event) => {
    state.confirmation = event.target.value; updateExecuteState();
  });
  state.initialized = true;
  return state;
}

export async function refreshSettingsChannels() {
  const status = document.querySelector("#settings-status");
  status.textContent = "Refreshing managed Channels…";
  try { state.items = await inspectManagedChannels(); clearSettingsPreview(state); render(); status.textContent = "Channel inventory refreshed"; }
  catch (error) { status.textContent = `Refresh failed: ${error.message}`; }
}

function render() {
  const managed = document.querySelector("#settings-managed-list"); const external = document.querySelector("#settings-external-list");
  managed.replaceChildren(); external.replaceChildren();
  state.items.forEach((item) => (item.classification === "external" ? external : managed).appendChild(channelCard(item)));
}

function channelCard(item) {
  const card = document.createElement("article"); card.className = `settings-channel settings-${item.classification}`;
  const title = document.createElement("h3"); title.textContent = item.name || item.logicalType || "External Channel"; card.append(title);
  const detail = document.createElement("p"); detail.textContent = `${item.classification} · revision ${item.revision ?? "-"}`; card.append(detail);
  if (item.classification === "external") { card.dataset.readOnly = "true"; return card; }
  (item.permittedActions || []).forEach((operation) => { const button = document.createElement("button"); button.type = "button"; button.dataset.logicalType = item.logicalType; button.dataset.operation = operation; button.textContent = `Preview ${operation}`; card.append(button); });
  return card;
}

async function handleAction(event) {
  const button = event.target.closest("button[data-operation]"); if (!button || state.busy) return;
  state.busy = true;
  try { state.selected = button.dataset.logicalType; state.operation = button.dataset.operation; state.preview = await previewManagedChannel(state.selected, state.operation); showPreview(); }
  finally { state.busy = false; updateExecuteState(); }
}

function showPreview() {
  document.querySelector("#settings-preview").hidden = false;
  document.querySelector("#settings-preview-summary").textContent = `${state.operation} ${state.selected}`;
  document.querySelector("#settings-preview-diff").textContent = (state.preview.snapshot?.differences || []).map((item) => item.path).join(", ") || "No owned-field differences";
  document.querySelector("#settings-delete-confirmation-wrap").hidden = state.operation !== "delete";
  updateExecuteState();
}

function updateExecuteState() {
  const button = document.querySelector("#settings-preview-execute"); if (!button) return;
  button.disabled = !state.preview?.previewToken || state.busy || state.refreshRequired || (state.operation === "delete" && state.confirmation !== state.selected);
}

async function executePreview() {
  if (!state.preview?.previewToken || state.busy) return; state.busy = true; updateExecuteState();
  try {
    const response = await mutateManagedChannel(state.selected, state.operation, state.preview.previewToken, state.confirmation);
    const item = response.item || {}; document.querySelector("#settings-operation-steps").textContent = (item.steps || []).map((step) => `${step.name}: ${step.status}`).join("\n");
    state.refreshRequired = true; clearSettingsPreview(state); await refreshSettingsChannels();
  } catch (error) { state.refreshRequired = true; state.preview = null; document.querySelector("#settings-status").textContent = `Operation blocked: ${error.message}`; }
  finally { state.busy = false; updateExecuteState(); }
}
