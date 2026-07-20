import { requestJson } from "./client.js";

export const SETTINGS_API_NAMESPACE = "/api/oie/settings";

export function fetchSettings() {
  return requestJson(SETTINGS_API_NAMESPACE);
}

export function saveSettings(payload) {
  return requestJson(SETTINGS_API_NAMESPACE, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function fetchSettingsListenerStatus() {
  return requestJson("/api/oie/result-listener/status");
}

export function retrySettingsListener() {
  return requestJson("/api/oie/result-listener/retry", { method: "POST" });
}
