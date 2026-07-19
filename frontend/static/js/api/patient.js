import { requestJson, requestJsonAllowBusinessFailure } from "./client.js";

export function fetchPatients(protocolVersion = "") {
  const params = new URLSearchParams();
  if (protocolVersion) params.set("protocolVersion", protocolVersion);
  const query = params.toString();
  return requestJson(`/api/patients${query ? `?${query}` : ""}`);
}

export function createPatient(payload) {
  return requestJson("/api/patients", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function retryPatientFhirSync(patientId) {
  return requestJson(`/api/patients/${patientId}/fhir-sync`, { method: "POST" });
}

export function refreshPatientDcm4cheeResults(patientId) {
  return requestJsonAllowBusinessFailure(`/api/patients/${patientId}/dcm4chee-results-refresh`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
