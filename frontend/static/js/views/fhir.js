import { fetchFhirDiagnosticReports, fetchFhirInventory, fetchFhirRecordPreview, fetchFhirResourcePreview, retryFhirRecordSync } from "../api/fhir.js";
import { setStatus } from "../components/status.js";
import { copyTextFromElement } from "../core/clipboard.js";
import { byId, createElement, rowCell } from "../core/dom.js";
import { taipeiTimestamp } from "../core/formatting.js";

const MEDPLUM_SOURCE_LABELS = {
  "medplum-live": "Medplum live JSON",
  "local-submitted": "Local submitted JSON",
  "local-submitted-fallback": "Live fetch failed; local submitted JSON",
  "medplum-live-fetch-failed": "Live Medplum fetch failed",
};

let medplumInventory = [];
let medplumPatients = [];
let medplumResourceTypes = [];
let selectedMedplumRecordId = null;
let selectedMedplumPatientId = null;
let expandedMedplumPatientIds = new Set();
let selectedMedplumLiveReportReference = "";
let selectedMedplumLiveRelatedReference = "";
let medplumDiagnosticReports = {
  key: "", loading: false, error: "", source: "", strategy: "", fallbackReason: "",
  patientReference: "", serviceRequestReference: "", reports: [], bundle: null, requestId: 0,
};
let initialized = false;

function fhirSyncStatusClass(status) {
  return { "Synced": "success", "Sync failed": "error", "Syncing": "pending", "Pending sync": "pending" }[status] || "neutral";
}

export function initializeFhirView() {
  if (initialized) return;
  initialized = true;
  byId("refresh-medplum-inventory").addEventListener("click", refreshMedplumInventory);
  byId("medplum-sync-filter").addEventListener("change", renderMedplumConsole);
  byId("medplum-service-request-select").addEventListener("change", (event) => {
    selectedMedplumLiveReportReference = "";
    selectedMedplumLiveRelatedReference = "";
    resetMedplumDiagnosticReportState();
    renderMedplumRelatedResources(selectedMedplumPatient());
    fetchMedplumDiagnosticReportsForCurrentSelection();
    loadMedplumPreview(Number(event.target.value || 0));
  });
  byId("medplum-diagnostic-report-select").addEventListener("change", (event) => {
    renderMedplumRelatedResources(selectedMedplumPatient());
    if (event.target.value.startsWith("DiagnosticReport/")) loadMedplumLiveReportPreview(event.target.value);
    else loadMedplumPreview(Number(event.target.value || 0));
  });
  byId("copy-medplum-json").addEventListener("click", () => copyTextFromElement("medplum-json-preview"));
}

function medplumSourceLabel(source) {
  return MEDPLUM_SOURCE_LABELS[source] || source || "Unknown source";
}

function medplumPatientLabel(patient) {
  const record = medplumPatientInventoryRecord(patient);
  return record?.summary?.primary
    || patient?.summary?.primary
    || patient?.identifier?.value
    || patient?.localFhirRecordNumber
    || `FHIR-${patient?.id}`;
}

function medplumPatientInventoryRecord(patient) {
  if (!patient) return null;
  return medplumInventory.find((item) => (
    item.resourceType === "Patient" && Number(item.id) === Number(patient.id)
  )) || null;
}

function medplumPatientMrn(patient) {
  const record = medplumPatientInventoryRecord(patient);
  return record?.summary?.secondary || patient?.identifier?.value || "-";
}

function medplumTimestamp(value) {
  const text = taipeiTimestamp(value);
  const match = text.match(/^(\d{4}-\d{2}-\d{2}) TPE (.+)$/);
  if (!match) return text;
  const timestamp = createElement("span", "", "timestamp-cell");
  timestamp.append(
    createElement("span", match[1], "timestamp-date"),
    createElement("span", `TPE ${match[2]}`, "timestamp-time"),
  );
  return timestamp;
}

function selectedMedplumPatient() {
  const selectedId = Number(selectedMedplumPatientId || 0);
  return medplumPatients.find((item) => Number(item.id) === selectedId) || null;
}

function medplumRecordMatchesPatient(item, patient) {
  if (!patient) return true;
  if (item.resourceType === "Patient") return Number(item.id) === Number(patient.id);
  const reference = patient.reference || patient.medplum?.reference || "";
  return Boolean(reference && (item.patientReferences || []).includes(reference));
}

function medplumRecordReference(item) {
  return item?.medplum?.reference || "";
}

function selectedMedplumPatientReference(patient = selectedMedplumPatient()) {
  return patient?.reference || patient?.medplum?.reference || "";
}

function medplumRecordsForPatient(patient, resourceType = "") {
  return medplumInventory.filter((item) => (
    (!resourceType || item.resourceType === resourceType)
    && medplumRecordMatchesPatient(item, patient)
  ));
}

function medplumOrderRecordsForPatient(patient) {
  return medplumInventory.filter((item) => (
    item.resourceType === "ServiceRequest"
    && medplumRecordMatchesPatient(item, patient)
  ));
}

function medplumResultRecordsForPatient(patient) {
  return medplumInventory.filter((item) => (
    ["DiagnosticReport", "Observation", "DocumentReference"].includes(item.resourceType)
    && medplumRecordMatchesPatient(item, patient)
  ));
}

function medplumRecordReferences(item) {
  const references = new Set(item?.references || []);
  if (medplumRecordReference(item)) references.add(medplumRecordReference(item));
  return references;
}

function medplumLiveReportsForPatient(patient) {
  const patientReference = selectedMedplumPatientReference(patient);
  if (
    !patientReference
    || medplumDiagnosticReports.patientReference !== patientReference
    || medplumDiagnosticReports.key !== currentMedplumDiagnosticReportKey(patient)
  ) {
    return [];
  }
  return medplumDiagnosticReports.reports || [];
}

function medplumLiveReportLabel(item) {
  return [
    item.display || item.code || item.reference || "DiagnosticReport",
    item.status,
    item.date,
    item.relationshipType === "patient-level" ? "Patient-level" : item.linkedOrder,
  ].filter(Boolean).join(" | ");
}

function selectedMedplumServiceRequestReference() {
  return medplumRecordReference(selectedMedplumServiceRequest());
}

function currentMedplumDiagnosticReportKey(patient = selectedMedplumPatient()) {
  const patientReference = selectedMedplumPatientReference(patient);
  if (!patientReference) return "";
  return `${patientReference}|${selectedMedplumServiceRequestReference()}`;
}

function medplumDiagnosticReportKeyMatchesCurrent(patient = selectedMedplumPatient()) {
  const key = currentMedplumDiagnosticReportKey(patient);
  return Boolean(key && medplumDiagnosticReports.key === key);
}

function resetMedplumDiagnosticReportState() {
  medplumDiagnosticReports = {
    key: "",
    loading: false,
    error: "",
    source: "",
    strategy: "",
    fallbackReason: "",
    patientReference: "",
    serviceRequestReference: "",
    reports: [],
    bundle: null,
    bundles: {},
    requestId: medplumDiagnosticReports.requestId + 1,
  };
}

function medplumWorkflowLabel(item) {
  if (!item) return "No resource";
  const summary = item.summary || {};
  const reference = medplumRecordReference(item) || item.localFhirRecordNumber || `FHIR-${item.id}`;
  return [summary.primary, summary.status, reference].filter(Boolean).join(" · ");
}

function filteredMedplumPatients() {
  const patient = selectedMedplumPatient();
  const syncStatus = byId("medplum-sync-filter")?.value || "";
  const visible = medplumPatients.filter((item) => !syncStatus || item.sync?.status === syncStatus);
  if (patient && visible.some((item) => Number(item.id) === Number(patient.id))) return visible;
  if (visible.length && !patient) selectedMedplumPatientId = visible[0].id;
  if (patient && !visible.some((item) => Number(item.id) === Number(patient.id))) {
    selectedMedplumPatientId = visible[0]?.id || null;
  }
  return visible;
}

function retryButtonForMedplumRecord(item) {
  if (!item?.retryable) return null;
  const retryButton = createElement("button", "Retry", "small-button");
  retryButton.type = "button";
  retryButton.addEventListener("click", (event) => {
    event.stopPropagation();
    retryMedplumRecord(item.id, retryButton);
  });
  return retryButton;
}

function medplumPreviewButton(item, label = "Preview") {
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    loadMedplumPreview(item.id);
  });
  return button;
}

function medplumResourceRollupTable(items, emptyText) {
  const wrap = createElement("div", "", "table-wrap medplum-nested-table-wrap");
  const table = createElement("table", "", "medplum-nested-table");
  const thead = document.createElement("thead");
  const header = document.createElement("tr");
  ["Type", "Resource", "Status", "Reference", "Updated", "Action"].forEach((label) => {
    header.appendChild(createElement("th", label));
  });
  thead.appendChild(header);
  const tbody = document.createElement("tbody");
  if (!items.length) {
    const row = document.createElement("tr");
    const cell = rowCell(emptyText);
    cell.colSpan = 6;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
  }
  items.forEach((item) => {
    const actions = createElement("div", "", "button-row compact-actions");
    actions.appendChild(medplumPreviewButton(item));
    const retryButton = retryButtonForMedplumRecord(item);
    if (retryButton) actions.appendChild(retryButton);
    const status = item.sync?.status || item.summary?.status || "-";
    const row = document.createElement("tr");
    row.append(
      rowCell(item.resourceType),
      rowCell(item.summary?.primary || item.localFhirRecordNumber || `FHIR-${item.id}`),
      rowCell(createElement("span", status, `status ${fhirSyncStatusClass(status)}`)),
      rowCell(medplumRecordReference(item) || item.localFhirRecordNumber || "-"),
      rowCell(medplumTimestamp(item.updatedAt)),
      rowCell(actions),
    );
    row.addEventListener("click", () => loadMedplumPreview(item.id));
    tbody.appendChild(row);
  });
  table.append(thead, tbody);
  wrap.appendChild(table);
  return wrap;
}

function medplumPatientSection(label, title, body) {
  const section = createElement("section", "", "medplum-patient-section");
  const heading = createElement("div", "", "compact-heading medplum-patient-section-heading");
  const text = document.createElement("div");
  text.append(createElement("p", label, "eyebrow"), createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function renderMedplumPatientList() {
  const body = byId("medplum-patient-list");
  const visible = filteredMedplumPatients();
  body.replaceChildren();
  if (!visible.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No FHIR Patients match the current filter.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  visible.forEach((patient) => {
    const patientId = Number(patient.id);
    const patientRecord = medplumPatientInventoryRecord(patient) || patient;
    const orders = medplumOrderRecordsForPatient(patient);
    const localResults = medplumResultRecordsForPatient(patient);
    const liveReports = medplumLiveReportsForPatient(patient);
    const resultCount = liveReports.length
      ? liveReports.length + localResults.filter((item) => item.resourceType !== "DiagnosticReport").length
      : localResults.length;
    const status = patient.sync?.status || "-";
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(medplumPreviewButton(patientRecord));
    const retryButton = retryButtonForMedplumRecord(patientRecord);
    if (retryButton) actions.appendChild(retryButton);
    const toggleButton = createElement(
      "button",
      expandedMedplumPatientIds.has(patientId) ? "v" : ">",
      "medplum-patient-toggle",
    );
    toggleButton.type = "button";
    toggleButton.setAttribute("aria-expanded", String(expandedMedplumPatientIds.has(patientId)));
    toggleButton.setAttribute(
      "aria-label",
      expandedMedplumPatientIds.has(patientId) ? "Collapse Patient Orders and Results" : "Expand Patient Orders and Results",
    );
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (expandedMedplumPatientIds.has(patientId)) expandedMedplumPatientIds.delete(patientId);
      else expandedMedplumPatientIds.add(patientId);
      renderMedplumPatientList();
    });
    const row = document.createElement("tr");
    row.className = patientId === Number(selectedMedplumPatientId) ? "selected-row medplum-patient-row" : "medplum-patient-row";
    row.append(
      rowCell(toggleButton),
      rowCell(medplumPatientMrn(patient)),
      rowCell(medplumPatientLabel(patient)),
      rowCell(createElement("span", status, `status ${fhirSyncStatusClass(status)}`)),
      rowCell(orders.length),
      rowCell(resultCount),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectMedplumPatient(patient.id));
    body.appendChild(row);

    if (expandedMedplumPatientIds.has(patientId)) {
      const detailRow = createElement("tr", "", "medplum-patient-detail-row");
      const detailCell = document.createElement("td");
      detailCell.colSpan = 7;
      const content = createElement("div", "", "medplum-patient-rollup-content");
      content.append(
        medplumPatientSection(
          "FHIR ORDERS",
          "ServiceRequest",
          medplumResourceRollupTable(orders, "No FHIR Orders for this Patient."),
        ),
        medplumPatientSection(
          "FHIR RESULTS",
          "DiagnosticReport, Observation & DocumentReference",
          medplumResourceRollupTable(localResults, "No local FHIR Results for this Patient."),
        ),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function renderMedplumPatientSummary(patient) {
  byId("medplum-selected-patient-title").textContent = patient
    ? `${medplumPatientLabel(patient)}`
    : "No patient selected";
  const container = byId("medplum-selected-patient-summary");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a FHIR patient.", "muted"));
    return;
  }
  const record = medplumPatientInventoryRecord(patient) || patient;
  [
    ["MRN", medplumPatientMrn(patient)],
    ["Sync", patient.sync?.status || "-"],
    ["Medplum", medplumRecordReference(record) || patient.sync?.error || "-"],
    ["Updated", medplumTimestamp(record.updatedAt)],
  ].forEach(([label, value]) => {
    const block = createElement("div", "", "detail-block");
    block.append(createElement("h3", label));
    const text = createElement("p", "", value ? "" : "muted");
    if (value instanceof Node) text.appendChild(value);
    else text.textContent = value || "-";
    block.appendChild(text);
    container.appendChild(block);
  });
}

function renderMedplumResourceSelect(selectId, items, emptyText) {
  const select = byId(selectId);
  const previous = select.value;
  select.replaceChildren();
  if (!items.length) {
    select.appendChild(new Option(emptyText, ""));
    select.disabled = true;
    return null;
  }
  select.disabled = false;
  items.forEach((item) => {
    select.appendChild(new Option(medplumWorkflowLabel(item), String(item.id)));
  });
  if ([...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
  return Number(select.value || items[0].id);
}

function selectedMedplumServiceRequest() {
  const selectedId = Number(byId("medplum-service-request-select")?.value || 0);
  return medplumInventory.find((item) => Number(item.id) === selectedId) || null;
}

function selectedMedplumDiagnosticReport() {
  const selectedValue = byId("medplum-diagnostic-report-select")?.value || "";
  if (selectedValue.startsWith("DiagnosticReport/")) {
    return (medplumDiagnosticReports.reports || []).find((item) => item.reference === selectedValue) || null;
  }
  const selectedId = Number(selectedValue || 0);
  return medplumInventory.find((item) => Number(item.id) === selectedId) || null;
}

function renderMedplumDiagnosticReportSelect(localReports) {
  const select = byId("medplum-diagnostic-report-select");
  const previous = select.value;
  const liveReports = medplumDiagnosticReportKeyMatchesCurrent()
    ? medplumDiagnosticReports.reports || []
    : [];
  select.replaceChildren();
  if (liveReports.length) {
    select.disabled = false;
    liveReports.forEach((item) => {
      select.appendChild(new Option(medplumLiveReportLabel(item), item.reference));
    });
  } else if (localReports.length) {
    select.disabled = false;
    localReports.forEach((item) => {
      select.appendChild(new Option(medplumWorkflowLabel(item), String(item.id)));
    });
  } else {
    select.appendChild(new Option(
      medplumDiagnosticReports.loading ? "Fetching live DiagnosticReports" : "No DiagnosticReports for this patient",
      "",
    ));
    select.disabled = true;
    return "";
  }
  if ([...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
  return select.value || select.options[0]?.value || "";
}

function appendMedplumRelatedRow(container, label, item) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = Number(item.id) === Number(selectedMedplumRecordId)
    ? "medplum-related-row selected-row"
    : "medplum-related-row";
  row.addEventListener("click", () => loadMedplumPreview(item.id));
  row.append(
    createElement("strong", label),
    createElement("span", medplumWorkflowLabel(item)),
    createElement("code", medplumRecordReference(item) || item.localFhirRecordNumber || `FHIR-${item.id}`),
  );
  container.appendChild(row);
}

function appendMedplumLiveRelatedRow(container, item) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = item.reference === selectedMedplumLiveRelatedReference
    ? "medplum-related-row selected-row"
    : "medplum-related-row";
  row.addEventListener("click", () => loadMedplumLiveReferencePreview(item.reference));
  row.append(
    createElement("strong", item.resourceType || "FHIR"),
    createElement("span", "Live Medplum reference"),
    createElement("code", item.reference),
  );
  container.appendChild(row);
}

function renderMedplumRelatedResources(patient) {
  const container = byId("medplum-related-resources");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a FHIR patient.", "muted"));
    return;
  }
  const selectedReport = selectedMedplumDiagnosticReport();
  const liveRelated = selectedReport?.relationships?.related || [];
  const reportReferences = selectedReport?.reference
    ? new Set((selectedReport.relationships?.related || []).map((item) => item.reference))
    : medplumRecordReferences(selectedReport);
  const observations = medplumRecordsForPatient(patient, "Observation").filter((item) => {
    const reference = medplumRecordReference(item);
    return selectedReport && reportReferences.size ? reportReferences.has(reference) : medplumRecordMatchesPatient(item, patient);
  });
  const documents = medplumRecordsForPatient(patient, "DocumentReference").filter((item) => {
    const reference = medplumRecordReference(item);
    return selectedReport && reportReferences.size ? reportReferences.has(reference) : medplumRecordMatchesPatient(item, patient);
  });
  [
    ["Observation", observations],
    ["DocumentReference", documents],
  ].forEach(([label, items]) => {
    if (!items.length) return;
    const group = document.createElement("div");
    group.className = "medplum-related-group";
    group.appendChild(createElement("h3", label));
    items.forEach((item) => appendMedplumRelatedRow(group, label, item));
    container.appendChild(group);
  });
  if (liveRelated.length) {
    const group = document.createElement("div");
    group.className = "medplum-related-group";
    group.appendChild(createElement("h3", "Live DiagnosticReport References"));
    liveRelated.forEach((item) => appendMedplumLiveRelatedRow(group, item));
    container.appendChild(group);
  }
  if (!container.childElementCount) {
    container.appendChild(createElement("p", "No related Observation, DocumentReference, or Binary records for the current selection.", "muted"));
  }
}

function clearMedplumPreview() {
  selectedMedplumRecordId = null;
  selectedMedplumLiveReportReference = "";
  selectedMedplumLiveRelatedReference = "";
  byId("medplum-selected-title").textContent = "No resource selected";
  const summary = byId("medplum-selected-summary");
  summary.replaceChildren();
  summary.appendChild(createElement("p", "Select a FHIR Patient, ServiceRequest, DiagnosticReport, Observation, DocumentReference, or Binary.", "muted"));
  byId("medplum-json-preview").textContent = "Select a FHIR resource to inspect raw JSON.";
}

function renderMedplumReportSummaryBlocks(blocks) {
  const container = byId("medplum-selected-summary");
  container.replaceChildren();
  blocks.forEach(([label, value]) => {
    const block = createElement("div", "", "detail-block");
    block.append(createElement("h3", label));
    const text = createElement("p", value || "-", value ? "" : "muted");
    block.appendChild(text);
    container.appendChild(block);
  });
}

function medplumReportActionButton(label, handler) {
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    handler();
  });
  return button;
}

function renderMedplumDiagnosticReportTable(items) {
  const wrap = createElement("div", "", "table-wrap medplum-diagnostic-report-table-wrap");
  const table = createElement("table", "", "medplum-diagnostic-report-table");
  const thead = document.createElement("thead");
  const header = document.createElement("tr");
  ["Report", "Status", "Date", "Order", "Refs", "Action"].forEach((label) => {
    header.appendChild(createElement("th", label));
  });
  thead.appendChild(header);
  const tbody = document.createElement("tbody");
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.className = item.reference === selectedMedplumLiveReportReference ? "selected-row" : "";
    row.addEventListener("click", () => loadMedplumLiveReportPreview(item.reference));
    row.append(
      rowCell(item.display || item.reference),
      rowCell(createElement("span", item.status || "-", `status ${item.status ? "neutral" : "muted"}`)),
      rowCell(item.date || item.issued || "-"),
      rowCell(item.linkedOrder || (item.relationshipType === "patient-level" ? "Patient-level" : "-")),
      rowCell(`${item.resultCount || 0} result / ${item.attachmentCount || 0} attachment`),
      rowCell(medplumReportActionButton("Preview", () => loadMedplumLiveReportPreview(item.reference))),
    );
    tbody.appendChild(row);
  });
  table.append(thead, tbody);
  wrap.appendChild(table);
  return wrap;
}

function renderMedplumReportGroup(label, title, items) {
  const section = createElement("details", "", "medplum-diagnostic-report-group");
  section.open = true;
  const summary = createElement("summary", "");
  summary.append(
    createElement("span", label, "eyebrow"),
    createElement("strong", `${title} (${items.length})`),
  );
  section.append(summary, renderMedplumDiagnosticReportTable(items));
  return section;
}

function renderMedplumDiagnosticReportRollup(patient) {
  const container = byId("medplum-diagnostic-report-rollup");
  const status = byId("medplum-diagnostic-report-status");
  if (!container || !status) return;
  container.replaceChildren();
  if (!patient) {
    setStatus("medplum-diagnostic-report-status", "Ready", "neutral");
    container.appendChild(createElement("p", "Select a synced FHIR patient to fetch live Medplum DiagnosticReports.", "muted"));
    return;
  }
  const patientReference = selectedMedplumPatientReference(patient);
  if (!patientReference) {
    setStatus("medplum-diagnostic-report-status", "Local only", "warning");
    container.appendChild(createElement("p", "Live DiagnosticReport fetch requires a synced Medplum Patient reference.", "muted"));
    return;
  }
  if (medplumDiagnosticReports.loading) {
    setStatus("medplum-diagnostic-report-status", "Fetching...", "pending");
    container.appendChild(createElement("p", "Fetching live Medplum DiagnosticReports.", "muted"));
    return;
  }
  if (medplumDiagnosticReports.error) {
    setStatus("medplum-diagnostic-report-status", "Fetch failed", "error");
    container.appendChild(createElement("p", medplumDiagnosticReports.error, "muted"));
    return;
  }
  const reports = medplumDiagnosticReports.reports || [];
  if (!reports.length) {
    setStatus("medplum-diagnostic-report-status", "No reports", "neutral");
    container.appendChild(createElement("p", "No live DiagnosticReports found for this patient.", "muted"));
    return;
  }
  const orderLinked = reports.filter((item) => item.relationshipType === "order-linked");
  const patientLevel = reports.filter((item) => item.relationshipType !== "order-linked");
  setStatus("medplum-diagnostic-report-status", `${reports.length} live`, "success");
  if (medplumDiagnosticReports.fallbackReason) {
    container.appendChild(createElement("p", "ServiceRequest search fell back to Patient results.", "muted"));
  }
  if (orderLinked.length) {
    container.appendChild(renderMedplumReportGroup("GDT-IN", "Order-linked results", orderLinked));
  }
  if (patientLevel.length) {
    container.appendChild(renderMedplumReportGroup("PATIENT", "Patient-level results", patientLevel));
  }
}

async function fetchMedplumDiagnosticReportsForCurrentSelection() {
  const patient = selectedMedplumPatient();
  const key = currentMedplumDiagnosticReportKey(patient);
  if (!key || (medplumDiagnosticReports.loading && medplumDiagnosticReports.key === key)) {
    renderMedplumDiagnosticReportRollup(patient);
    return;
  }
  const patientReference = selectedMedplumPatientReference(patient);
  const serviceRequestReference = selectedMedplumServiceRequestReference();
  const requestId = medplumDiagnosticReports.requestId + 1;
  medplumDiagnosticReports = {
    ...medplumDiagnosticReports,
    key,
    loading: true,
    error: "",
    patientReference,
    serviceRequestReference,
    requestId,
    reports: [],
    bundle: null,
    bundles: {},
  };
  renderMedplumDiagnosticReportRollup(patient);
  try {
    const result = await fetchFhirDiagnosticReports(patientReference, serviceRequestReference);
    if (medplumDiagnosticReports.requestId !== requestId) return;
    medplumDiagnosticReports = {
      ...medplumDiagnosticReports,
      loading: false,
      error: "",
      source: result.source || "medplum-live",
      strategy: result.strategy || "",
      fallbackReason: result.fallbackReason || "",
      patientReference: result.patientReference || patientReference,
      serviceRequestReference: result.serviceRequestReference || serviceRequestReference,
      reports: result.reports || [],
      bundle: result.bundle || null,
      bundles: result.bundles || {},
    };
    renderMedplumConsole();
  } catch (error) {
    if (medplumDiagnosticReports.requestId !== requestId) return;
    medplumDiagnosticReports = {
      ...medplumDiagnosticReports,
      loading: false,
      error: error.message,
      reports: [],
      bundle: null,
    };
    renderMedplumDiagnosticReportRollup(patient);
  }
}

function ensureMedplumDiagnosticReports(patient) {
  const key = currentMedplumDiagnosticReportKey(patient);
  if (!key) {
    renderMedplumDiagnosticReportRollup(patient);
    return;
  }
  if (medplumDiagnosticReports.key === key && !medplumDiagnosticReports.loading) {
    renderMedplumDiagnosticReportRollup(patient);
    return;
  }
  fetchMedplumDiagnosticReportsForCurrentSelection();
}

function renderMedplumConsole() {
  renderMedplumPatientList();
  const patient = selectedMedplumPatient();
  renderMedplumPatientSummary(patient);
  const serviceRequests = patient ? medplumRecordsForPatient(patient, "ServiceRequest") : [];
  const localReports = patient ? medplumRecordsForPatient(patient, "DiagnosticReport") : [];
  const serviceRequestId = renderMedplumResourceSelect(
    "medplum-service-request-select",
    serviceRequests,
    "No ServiceRequests for this patient",
  );
  const reportValue = renderMedplumDiagnosticReportSelect(localReports);
  ensureMedplumDiagnosticReports(patient);
  renderMedplumRelatedResources(patient);
  if (!patient) {
    clearMedplumPreview();
  } else if (!selectedMedplumRecordId) {
    loadMedplumPreview(patient.id);
  } else if (selectedMedplumRecordId) {
    const selected = medplumInventory.find((item) => Number(item.id) === Number(selectedMedplumRecordId));
    if (!selected || (patient && !medplumRecordMatchesPatient(selected, patient) && Number(selected.id) !== Number(patient.id))) {
      if (reportValue && String(reportValue).startsWith("DiagnosticReport/")) {
        loadMedplumLiveReportPreview(reportValue);
      } else {
        loadMedplumPreview(serviceRequestId || Number(reportValue || 0) || patient?.id);
      }
    }
  }
}

function renderMedplumPreviewSummary(result) {
  const container = byId("medplum-selected-summary");
  const item = result.item || {};
  container.replaceChildren();
  const blocks = [
    ["Type", item.resourceType || "-"],
    ["Sync", item.sync?.status || "-"],
    ["Reference", item.medplum?.reference || "-"],
    ["Preview Source", medplumSourceLabel(result.source)],
  ];
  if (result.live?.error) {
    blocks.push(["Live Fetch", result.live.error]);
  }
  blocks.forEach(([label, value]) => {
    const block = createElement("div", "", "detail-block");
    const title = createElement("h3", label);
    const text = createElement("p", value || "-", value ? "" : "muted");
    block.append(title, text);
    container.appendChild(block);
  });
}

export async function refreshMedplumInventory() {
  setStatus("medplum-inventory-status", "Loading inventory...", "pending");
  try {
    const result = await fetchFhirInventory();
    medplumInventory = result.items || [];
    medplumPatients = result.patients || [];
    medplumResourceTypes = result.resourceTypes || [];
    if (!selectedMedplumPatientId && medplumPatients.length) selectedMedplumPatientId = medplumPatients[0].id;
    renderMedplumConsole();
    setStatus("medplum-inventory-status", "Inventory loaded", "success");
  } catch (error) {
    setStatus("medplum-inventory-status", error.message, "error");
  }
}

async function loadMedplumPreview(recordId) {
  if (!recordId) return;
  selectedMedplumRecordId = recordId;
  selectedMedplumLiveReportReference = "";
  selectedMedplumLiveRelatedReference = "";
  renderMedplumPatientList();
  renderMedplumRelatedResources(selectedMedplumPatient());
  byId("medplum-selected-title").textContent = "Loading resource...";
  byId("medplum-json-preview").textContent = "Loading...";
  try {
    const result = await fetchFhirRecordPreview(recordId);
    byId("medplum-selected-title").textContent =
      `${result.item?.resourceType || "FHIR"} ${result.item?.medplum?.reference || result.item?.localFhirRecordNumber || ""}`.trim();
    renderMedplumPreviewSummary(result);
    byId("medplum-json-preview").textContent = JSON.stringify(result.resource || {}, null, 2);
    setStatus(
      "medplum-inventory-status",
      result.source === "local-submitted-fallback" ? "Live fetch failed; showing local JSON" : "Resource loaded",
      result.source === "local-submitted-fallback" ? "warning" : "success",
    );
  } catch (error) {
    byId("medplum-selected-title").textContent = "Preview failed";
    byId("medplum-json-preview").textContent = error.message;
    setStatus("medplum-inventory-status", error.message, "error");
  }
}

function loadMedplumLiveReportPreview(reference) {
  if (!reference) return;
  if (!medplumDiagnosticReportKeyMatchesCurrent()) return;
  const report = (medplumDiagnosticReports.reports || []).find((item) => item.reference === reference);
  if (!report) return;
  selectedMedplumRecordId = null;
  selectedMedplumLiveReportReference = reference;
  selectedMedplumLiveRelatedReference = "";
  byId("medplum-selected-title").textContent = `${report.display || "DiagnosticReport"} ${reference}`;
  renderMedplumReportSummaryBlocks([
    ["Type", "DiagnosticReport"],
    ["Status", report.status || "-"],
    ["Reference", reference],
    ["Preview Source", medplumSourceLabel("medplum-live")],
    ["Grouping", report.relationshipType === "patient-level" ? "Patient-level result" : "Order-linked result"],
  ]);
  byId("medplum-json-preview").textContent = JSON.stringify(report.resource || {}, null, 2);
  renderMedplumPatientList();
  renderMedplumDiagnosticReportRollup(selectedMedplumPatient());
  renderMedplumRelatedResources(selectedMedplumPatient());
  setStatus("medplum-inventory-status", "Live DiagnosticReport loaded", "success");
}

async function loadMedplumLiveReferencePreview(reference) {
  if (!reference) return;
  selectedMedplumRecordId = null;
  selectedMedplumLiveRelatedReference = reference;
  renderMedplumRelatedResources(selectedMedplumPatient());
  byId("medplum-selected-title").textContent = `Loading ${reference}...`;
  byId("medplum-json-preview").textContent = "Loading...";
  try {
    const result = await fetchFhirResourcePreview(reference);
    byId("medplum-selected-title").textContent = reference;
    renderMedplumReportSummaryBlocks([
      ["Type", result.resource?.resourceType || reference.split("/")[0] || "FHIR"],
      ["Reference", reference],
      ["Preview Source", medplumSourceLabel(result.source)],
      ["HTTP", result.statusCode ? String(result.statusCode) : "-"],
    ]);
    byId("medplum-json-preview").textContent = JSON.stringify(result.resource || {}, null, 2);
    setStatus("medplum-inventory-status", "Live related resource loaded", "success");
  } catch (error) {
    byId("medplum-selected-title").textContent = "Live related preview failed";
    renderMedplumReportSummaryBlocks([
      ["Reference", reference],
      ["Preview Source", medplumSourceLabel("medplum-live-fetch-failed")],
      ["Live Fetch", error.message],
    ]);
    byId("medplum-json-preview").textContent = error.message;
    setStatus("medplum-inventory-status", error.message, "error");
  }
}

async function retryMedplumRecord(recordId, button) {
  button.disabled = true;
  setStatus("medplum-inventory-status", "Retrying sync...", "pending");
  try {
    await retryFhirRecordSync(recordId);
    await refreshMedplumInventory();
    await loadMedplumPreview(recordId);
  } catch (error) {
    setStatus("medplum-inventory-status", error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function selectMedplumPatient(patientId) {
  selectedMedplumPatientId = patientId;
  selectedMedplumRecordId = null;
  selectedMedplumLiveReportReference = "";
  selectedMedplumLiveRelatedReference = "";
  resetMedplumDiagnosticReportState();
  renderMedplumConsole();
}

