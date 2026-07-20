import {
  fetchSettings,
  fetchSettingsListenerStatus,
  retrySettingsListener,
  saveSettings,
} from "../api/settings.js";
import { listenerReloadMessage } from "../components/settings-shell.js";
import { byId } from "../core/dom.js";
import { createSettingsState, listenerSettingsMatchStatus } from "../state/settings.js";

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
  if (listenerSettingsMatchStatus(state.profile, status.item)) {
    state.runtimeReloadRequired = false;
  }
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
  state.initialized = true;
  return state;
}
