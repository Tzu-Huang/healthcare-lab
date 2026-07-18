import { settingsUnavailableMessage } from "../components/settings-shell.js";
import { createSettingsState } from "../state/settings.js";

const state = createSettingsState();

export function initializeSettingsView(root) {
  if (!root || state.initialized) return state;
  root.dataset.moduleOwner = "settings";
  root.dataset.emptyState = settingsUnavailableMessage();
  state.initialized = true;
  return state;
}
