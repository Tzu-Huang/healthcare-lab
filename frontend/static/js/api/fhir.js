import { requestJson } from "./client.js";

export const fetchFhirInventory = () => requestJson("/api/fhir/inventory");

export const fetchFhirDiagnosticReports = (patientReference, serviceRequestReference = "") => {
  const params = new URLSearchParams({ patient: patientReference });
  if (serviceRequestReference) params.set("serviceRequest", serviceRequestReference);
  return requestJson(`/api/fhir/diagnostic-reports?${params.toString()}`);
};

export const fetchFhirRecordPreview = (recordId) => requestJson(`/api/fhir/records/${recordId}/preview`);

export const fetchFhirResourcePreview = (reference) => {
  const params = new URLSearchParams({ reference });
  return requestJson(`/api/fhir/resource-preview?${params.toString()}`);
};

export const retryFhirRecordSync = (recordId) => requestJson(`/api/fhir/records/${recordId}/sync`, {
  method: "POST",
  body: JSON.stringify({}),
});
