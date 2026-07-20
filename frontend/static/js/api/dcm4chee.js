import { requestJson } from "./client.js";

export function fetchDcm4cheeProfileDiagnostics() {
  return requestJson("/api/dcm4chee/profile/diagnostics");
}

export function fetchDcm4cheeAttempts(orderId) {
  return requestJson(`/api/orders/${orderId}/dcm4chee-attempts`);
}
