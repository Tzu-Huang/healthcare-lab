import { requestJson, requestJsonAllowBusinessFailure } from "./client.js";

export const SETTINGS_API_NAMESPACE = "/api/oie/settings";
export const MANAGED_CHANNELS_API = "/api/oie/managed-channels";
export const MEDPLUM_PROFILE_API = "/api/settings/profiles/medplum";

export function fetchSettings() { return requestJson(SETTINGS_API_NAMESPACE); }
export function saveSettings(payload) {
  return requestJson(SETTINGS_API_NAMESPACE, { method: "PUT", body: JSON.stringify(payload) });
}
export function testSettingsConnection() {
  return requestJson(`${SETTINGS_API_NAMESPACE}/test-connection`, { method: "POST", body: "{}" });
}
export function fetchMedplumProfile() { return requestJson(MEDPLUM_PROFILE_API); }
export function saveAndTestMedplumProfile(payload) {
  return requestJsonAllowBusinessFailure(`${MEDPLUM_PROFILE_API}/save-and-test`, {
    method: "POST", body: JSON.stringify(payload),
  });
}
export function removeMedplumClientSecret() {
  return requestJson(`${MEDPLUM_PROFILE_API}/secrets/clientSecret`, {
    method: "DELETE", body: "{}",
  });
}
export function fetchRuntimeDiagnostics() { return requestJson(`${SETTINGS_API_NAMESPACE}/diagnostics`); }
export function fetchSettingsListenerStatus() { return requestJson("/api/oie/result-listener/status"); }
export function startSettingsListener() { return requestJson("/api/oie/result-listener/start", { method: "POST" }); }
export function stopSettingsListener() { return requestJson("/api/oie/result-listener/stop", { method: "POST" }); }
export function retrySettingsListener() { return requestJson("/api/oie/result-listener/retry", { method: "POST" }); }

export async function inspectManagedChannels() {
  return (await requestJson(MANAGED_CHANNELS_API)).items || [];
}
export async function previewManagedChannel(logicalType, operation) {
  const wireOperation = operation === "recreate" ? "create" : operation === "apply" ? "update" : operation;
  return (await requestJson(`${MANAGED_CHANNELS_API}/${encodeURIComponent(logicalType)}/previews/${wireOperation}`, { method: "POST", body: "{}" })).item;
}
export async function mutateManagedChannel(logicalType, operation, previewToken, confirmation = "") {
  const wireOperation = operation === "recreate" ? "create" : operation === "apply" ? "update" : operation;
  const body = { previewToken };
  if (wireOperation === "delete") body.confirmation = confirmation;
  return requestJsonAllowBusinessFailure(`${MANAGED_CHANNELS_API}/${encodeURIComponent(logicalType)}/${wireOperation}`, { method: "POST", body: JSON.stringify(body) });
}
