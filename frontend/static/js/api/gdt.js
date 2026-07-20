import { requestJson } from "./client.js";

export const fetchGdtBridgeConfig = () => requestJson("/api/gdt/bridge/config");
export const saveGdtBridgeConfiguration = (payload) => requestJson("/api/gdt/bridge/config", { method: "PUT", body: JSON.stringify(payload) });
export const startGdtBridgeWatcher = () => requestJson("/api/gdt/bridge/watcher/start", { method: "POST", body: JSON.stringify({}) });
export const stopGdtBridgeWatcher = () => requestJson("/api/gdt/bridge/watcher/stop", { method: "POST", body: JSON.stringify({}) });
export const fetchGdtWorkbench = () => requestJson("/api/gdt/workbench");
export const writeGdtOrderFile = (orderId) => requestJson(`/api/gdt/orders/${orderId}/write-6302`, { method: "POST", body: JSON.stringify({}) });
export const createGdtOrderDemoResult = (orderId) => requestJson(`/api/gdt/orders/${orderId}/demo-result`, { method: "POST", body: JSON.stringify({}) });
export const importGdtBridgeFile = (filename) => requestJson("/api/gdt/bridge/import", { method: "POST", body: JSON.stringify({ filename }) });
