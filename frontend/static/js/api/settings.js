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
import { requestJson, requestJsonAllowBusinessFailure } from "./client.js";

export const SETTINGS_API_NAMESPACE = "/api/oie/settings";
export const MANAGED_CHANNELS_API = "/api/oie/managed-channels";

export async function inspectManagedChannels() {
  return (await requestJson(MANAGED_CHANNELS_API)).items || [];
}

export async function previewManagedChannel(logicalType, operation) {
  return (await requestJson(`${MANAGED_CHANNELS_API}/${encodeURIComponent(logicalType)}/previews/${operation}`, { method: "POST", body: "{}" })).item;
}

export async function mutateManagedChannel(logicalType, operation, previewToken, confirmation = "") {
  const body = { previewToken };
  if (operation === "delete") body.confirmation = confirmation;
  return requestJsonAllowBusinessFailure(`${MANAGED_CHANNELS_API}/${encodeURIComponent(logicalType)}/${operation}`, { method: "POST", body: JSON.stringify(body) });
}
