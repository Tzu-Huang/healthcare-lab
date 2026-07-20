import { requestJson, requestJsonAllowBusinessFailure } from "./client.js";

export function fetchOrders() {
  return requestJson("/api/orders");
}

export function fetchGdtOrders() {
  return requestJson("/api/gdt/orders");
}

export function createOrder(payload, mode) {
  return requestJson(mode === "gdt" ? "/api/gdt/orders" : "/api/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function syncDcm4cheeOrder(orderId) {
  return requestJsonAllowBusinessFailure(`/api/orders/${orderId}/dcm4chee-sync`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function verifyDcm4cheeMwl(orderId) {
  return requestJsonAllowBusinessFailure(`/api/orders/${orderId}/dcm4chee-mwl-verify`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function simulateDcm4cheeApReturn(orderId, type) {
  return requestJson(`/api/orders/${orderId}/dcm4chee-simulated-ap-return`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}
