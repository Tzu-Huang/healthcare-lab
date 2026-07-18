import { requestJson } from "./client.js";

export function fetchDashboardServices() {
  return requestJson("/api/dashboard/services");
}

export function runDashboardServiceAction(serviceId, action, options) {
  return requestJson(`/api/dashboard/services/${serviceId}/${action}`, options);
}

export function runDashboardChildAction(serviceId, childId, action, options) {
  return requestJson(`/api/dashboard/services/${serviceId}/children/${childId}/${action}`, options);
}

export function checkAllDashboardServices(options) {
  return requestJson("/api/dashboard/services/check-all", options);
}
