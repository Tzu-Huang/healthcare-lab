import { requestJson } from "./client.js";

export const fetchGdtBridgeConfig = () => requestJson("/api/gdt/bridge/config");
export const startGdtBridgeWatcher = () => requestJson("/api/gdt/bridge/watcher/start", { method: "POST", body: JSON.stringify({}) });
export const stopGdtBridgeWatcher = () => requestJson("/api/gdt/bridge/watcher/stop", { method: "POST", body: JSON.stringify({}) });
export const fetchGdtWorkbench = () => requestJson("/api/gdt/workbench");
export const writeGdtOrderFile = (orderId) => requestJson(`/api/gdt/orders/${orderId}/write-6302`, { method: "POST", body: JSON.stringify({}) });
export const createGdtOrderDemoResult = (orderId) => requestJson(`/api/gdt/orders/${orderId}/demo-result`, { method: "POST", body: JSON.stringify({}) });
export const importGdtBridgeFile = (filename) => requestJson("/api/gdt/bridge/import", { method: "POST", body: JSON.stringify({ filename }) });

async function controllerJson(url, options = {}) {
  const response = await fetch(url, { ...options, mode: "cors", cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.error || `Host controller returned ${response.status}.`);
  return body;
}

export const fetchGdtHostControllerSession = (controllerUrl) =>
  controllerJson(`${controllerUrl}/v1/session`);
export const fetchGdtHostControllerStatus = (controllerUrl) =>
  controllerJson(`${controllerUrl}/v1/status`);
export const applyGdtHostFolder = (controllerUrl, token, hostPath) =>
  controllerJson(`${controllerUrl}/v1/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Healthcare-Lab-Controller": token },
    body: JSON.stringify({ hostPath }),
  });
export const fetchGdtHostOperation = (controllerUrl, operationId) =>
  controllerJson(`${controllerUrl}/v1/operations/${encodeURIComponent(operationId)}`);
