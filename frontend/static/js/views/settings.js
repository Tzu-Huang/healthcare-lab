import { SETTINGS_MODULES } from "../settings/registry.js";
import {
  initializeSettingsWorkspace,
  refreshSettingsWorkspace,
} from "../settings/workspace.js";

export {
  retryListenerFromSettings,
  saveListenerSettings,
} from "../settings/oie.js";

export async function refreshSettings() {
  const root = document.getElementById("settings-view");
  const results = await Promise.all([
    ...SETTINGS_MODULES.map((module) => module.refresh(root)),
    refreshSettingsWorkspace(root),
  ]);
  return results[SETTINGS_MODULES.findIndex((module) => module.id === "oie")];
}

export function initializeSettingsView(root) {
  if (!root || root.dataset.moduleOwner === "settings") return;
  root.dataset.moduleOwner = "settings";
  initializeSettingsWorkspace(root);
  SETTINGS_MODULES.forEach((module) => module.initialize(root));
  refreshSettingsWorkspace(root);
}
