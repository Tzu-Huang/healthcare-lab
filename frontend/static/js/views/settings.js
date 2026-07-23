import {
  initializeOieSettingsSection,
  refreshSettings as refreshOieSettings,
} from "../settings/oie.js";
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
  const [oie] = await Promise.all([
    refreshOieSettings(),
    refreshSettingsWorkspace(root),
  ]);
  return oie;
}

export function initializeSettingsView(root) {
  if (!root || root.dataset.moduleOwner === "settings") return;
  root.dataset.moduleOwner = "settings";
  initializeSettingsWorkspace(root);
  initializeOieSettingsSection(root);
  refreshSettingsWorkspace(root);
}
