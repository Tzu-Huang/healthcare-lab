import { requestJson } from "./client.js";

export function fetchOieWorkbench() {
  return requestJson("/api/oie/workbench");
}

export function fetchOieListenerStatus() {
  return requestJson("/api/oie/result-listener/status");
}

export function startOieResultListener(payload) {
  return requestJson("/api/oie/result-listener/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function stopOieResultListener() {
  return requestJson("/api/oie/result-listener/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function sendOieLocalOrder(orderId, payload) {
  const response = await fetch(`/api/oie/local-orders/${orderId}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  return { response, result };
}
