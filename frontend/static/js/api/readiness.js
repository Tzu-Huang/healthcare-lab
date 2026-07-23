import { requestJson } from "./client.js";

export const SETTINGS_READINESS_API = "/api/settings/readiness";

export function fetchSettingsReadiness() {
  return requestJson(SETTINGS_READINESS_API);
}

export function runSettingsReadinessChecks() {
  return requestJson(`${SETTINGS_READINESS_API}/checks`, { method: "POST", body: "{}" });
}
