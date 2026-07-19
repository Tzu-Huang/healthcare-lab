import { requestJson, requestJsonAllowBusinessFailure } from "./js/api/client.js";
import { setStatus } from "./js/components/status.js";
import { copyTextFromElement as copyElementText } from "./js/core/clipboard.js";
import { createElement, rowCell } from "./js/core/dom.js";
import { fhirBirthDate as formatFhirBirthDate, fhirGender as formatFhirGender, gdtTaipeiTimestamp as formatGdtTaipeiTimestamp, hl7Escape as formatHl7Escape, hl7EscapeComposite as formatHl7EscapeComposite, hl7Timestamp as formatHl7Timestamp, localDatetimeValue as formatLocalDatetimeValue, pad as formatPad, taipeiTimestamp as formatTaipeiTimestamp } from "./js/core/formatting.js";
import { activateView, initializeNavigation, registerViewActivation } from "./js/core/navigation.js";
import { initializeOieView, refreshOieInventory, renderOieInventory as renderOieView } from "./js/views/oie.js";
import { initializeDashboardView, refreshDashboard, statusClass as dashboardStatusClass } from "./js/views/dashboard.js";
import { initializeGdtView, refreshGdtConsole, selectedGdtPatient as selectedGdtPatientFromView } from "./js/views/gdt.js";
import { initializeFhirView, refreshMedplumInventory } from "./js/views/fhir.js";
import { getSelectedOrderId, getSelectedPatientId, setSelectedOrderId, setSelectedPatientId } from "./js/state/selection.js";
import { createPatient, fetchPatients, refreshPatientDcm4cheeResults as refreshPatientDcm4cheeResultsRequest, retryPatientFhirSync as retryPatientFhirSyncRequest } from "./js/api/patient.js";
import { PATIENT_MODE_CONFIG, buildPatientGdtPreviewPayload, buildPatientPreviewPayload, patientDemoPresetForMode, patientFormPayload, patientPreviewMrn, renderPatientRecordList, renderPatientValidation, setPatientForm, updatePatientModeFields, validatePatientPayload } from "./js/views/patient.js";

const byId = (id) => document.getElementById(id);

let patientRecords = [];
let orderRecords = [];
let gdtOrderRecords = [];
let selectedOrderRecordKey = "";
let dcm4cheeProfileDiagnostics = null;
let expandedDcm4cheePatientIds = new Set();

const VIEW_TITLES = {
  "lab-console-view": "Service Health",
  "patient-view": "Patient",
  "medplum-view": "Medplum",
  "order-view": "Order",
  "dcm4chee-view": "dcm4chee",
  "oie-view": "OIE",
  "gdt-view": "GDT",
};


const DASHBOARD_RESOURCE_CONTAINERS = [
  { displayName: "oie-1", aliases: ["oie-1", "oie"] },
  { displayName: "medplum-1", aliases: ["medplum-1", "medplum"] },
  { displayName: "dcm4chee-1", aliases: ["dcm4chee-1", "dcm4chee"] },
];

const ORDER_MODE_CONFIG = {
  "hl7-v251": {
    title: "HL7 v2.5.1 ORM O01",
    payloadTitle: "MSH, PID, PV1, ORC, OBR",
    emptyPreview: "Select a local patient to preview an HL7 v2.5.1 ORM O01 payload.",
    createLabel: "Create Order",
  },
  fhir: {
    title: "FHIR R4 ServiceRequest",
    payloadTitle: "ServiceRequest resource JSON",
    emptyPreview: "Select a synced FHIR Patient to preview a ServiceRequest resource.",
    createLabel: "Create FHIR Order",
  },
  gdt: {
    title: "GDT ECG Order",
    payloadTitle: "GDT-OUT with 8402=EKG01",
    emptyPreview: "Select or create a local patient to preview a GDT ECG order payload.",
    createLabel: "Create GDT Order",
  },
  dicom: {
    title: "DICOM MWL Order",
    payloadTitle: "DICOM JSON MWL item",
    emptyPreview: "Select a local patient to preview a DICOM MWL payload.",
    createLabel: "Create DICOM MWL Order",
  },
};

const ORDER_PATIENT_PROTOCOL_BY_MODE = {
  "hl7-v251": "HL7 v2.5.1",
  fhir: "FHIR R4",
  gdt: "GDT 2.1",
  dicom: "DICOM",
};

const ORDER_PATIENT_LABEL_BY_MODE = {
  "hl7-v251": "HL7 v2",
  fhir: "FHIR R4",
  gdt: "GDT",
  dicom: "DICOM",
};

function setActiveView(viewId) {
  return activateView(viewId);
}

function currentOrderMode() {
  const selector = byId("order-protocol");
  return ORDER_MODE_CONFIG[selector?.value] ? selector.value : "hl7-v251";
}

function orderPatientProtocolForMode(mode = currentOrderMode()) {
  return ORDER_PATIENT_PROTOCOL_BY_MODE[mode] || ORDER_PATIENT_PROTOCOL_BY_MODE["hl7-v251"];
}

function orderPatientModeLabel(mode = currentOrderMode()) {
  return ORDER_PATIENT_LABEL_BY_MODE[mode] || ORDER_PATIENT_LABEL_BY_MODE["hl7-v251"];
}

function orderPatientRecordsForMode(mode = currentOrderMode()) {
  const protocolVersion = orderPatientProtocolForMode(mode);
  return patientRecords.filter((item) => item.protocolVersion === protocolVersion);
}

function updateOrderModeFields() {
  const mode = currentOrderMode();
  const config = ORDER_MODE_CONFIG[mode];
  byId("order-mode-title").textContent = config.title;
  const payloadTitle = byId("order-payload-title");
  if (payloadTitle) payloadTitle.textContent = config.payloadTitle;
  byId("create-order").textContent = config.createLabel;
  document.querySelectorAll("[data-order-mode-field]").forEach((element) => {
    const modes = String(element.dataset.orderModeField || "").split(/\s+/);
    element.hidden = !modes.includes(mode);
  });
  renderOrderPatientOptions();
  const subject = byId("fhir-subject-reference");
  if (subject) subject.value = selectedOrderPatientReference();
}

function openGdtOrderFlow() {
  const selector = byId("order-protocol");
  if (selector) selector.value = "gdt";
  setActiveView("order-view");
  setStatus("order-form-status", "GDT ECG order flow ready", "neutral");
}

function statusClass(status) {
  return dashboardStatusClass(status);
}

const orderDemoPreset = {
  priority: "R",
  orderingProvider: "1001^WANG^AMY",
  clinicalIndication: "Chest pain evaluation",
  orderCode: "ECG12",
  orderCodeText: "12 Lead ECG",
  alternateCode: "93000",
  alternateCodeText: "Electrocardiogram, routine ECG with at least 12 leads",
  alternateCodeSystem: "C4",
};

const fhirOrderDemoPreset = {
  status: "active",
  intent: "order",
  category: "Procedure",
  priority: "routine",
  doNotPerform: "false",
  codeSystem: "urn:healthcare-lab:service-code",
  codeCode: "ECG12",
  codeDisplay: "12 Lead ECG",
  reasonCodeText: "Chest pain evaluation",
  requester: "Practitioner/1001",
  performerType: "ECG technician",
  locationCode: "Cardiology lab",
  quantityValue: "1",
  quantityUnit: "procedure",
  note: "ECG order generated by Healthcare Lab.",
  patientInstruction: "Please remain still during the ECG recording.",
};

function hl7Escape(value) {
  return formatHl7Escape(value);
}

function hl7EscapeComposite(value) {
  return formatHl7EscapeComposite(value);
}

function pad(value) {
  return formatPad(value);
}

function hl7Timestamp(date = new Date()) {
  return formatHl7Timestamp(date);
}

function localDatetimeValue(date = new Date()) {
  return formatLocalDatetimeValue(date);
}

function taipeiTimestamp(value) {
  return formatTaipeiTimestamp(value);
}

function gdtTaipeiTimestamp(value) {
  return formatGdtTaipeiTimestamp(value);
}

function fhirBirthDate(dob) {
  return formatFhirBirthDate(dob);
}

function fhirGender(sex) {
  return formatFhirGender(sex);
}

function renderGdtRecord(code, value) {
  const fieldCode = String(code || "").trim();
  const content = String(value ?? "").trim().replace(/[\r\n]+/g, " ");
  const length = 3 + 4 + content.length + 2;
  return `${String(length).padStart(3, "0")}${fieldCode}${content}\r\n`;
}

function renderGdtMessage(records, setType) {
  let totalLength = "00000";
  for (let index = 0; index < 8; index += 1) {
    const lines = [
      ["8000", setType],
      ["8100", totalLength],
      ["9218", "02.10"],
      ["9206", "3"],
      ...records,
    ];
    const payload = lines.map(([code, value]) => renderGdtRecord(code, value)).join("");
    const nextLength = String(payload.length).padStart(5, "0");
    if (nextLength === totalLength) return payload;
    totalLength = nextLength;
  }
  return "";
}

function renderPatientSummaryFromPayload(payload, createdAt = "", dcm4cheePatient = null) {
  const container = byId("patient-summary");
  container.replaceChildren();
  const rows = [
    ["MRN", patientPreviewMrn(payload)],
    ["Name", [payload.firstName, payload.middleName, payload.lastName].filter(Boolean).join(" ")],
    ["DOB", payload.dob],
    ["Sex", payload.sex],
    ["Email", payload.email],
    ["Class", payload.patientClass || "O"],
    ["Visit", payload.visitNumber || "Generated on create"],
    ["Location", payload.assignedLocation],
    ["Created", taipeiTimestamp(createdAt)],
  ];
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
  if (dcm4cheePatient) {
    container.appendChild(dcm4cheeDetailBlock("dcm4chee Patient", [
      ["Status", dcm4cheePatient.displayStatus || dcm4cheePatient.status],
      ["Retryable", dcm4cheePatient.retryable ? "Yes" : "No"],
      ["Patient ID", dcm4cheePatient.patientId],
      ["Issuer", dcm4cheePatient.issuerOfPatientId],
      ["HL7", dcm4cheePatient.hl7Host && dcm4cheePatient.hl7Port ? `${dcm4cheePatient.hl7Host}:${dcm4cheePatient.hl7Port}` : ""],
      ["ACK", dcm4cheePatient.ack?.code],
      ["Error Type", dcm4cheePatient.lastErrorType],
      ["Error", dcm4cheePatient.lastError],
      ["Last Sync", dcm4cheePatient.lastSyncAt],
    ]));
  }
}

function dcm4cheeResultStatusClass(status) {
  return {
    matched: "success",
    no_result: "neutral",
    ambiguous: "warning",
    duplicate: "warning",
    wrong_patient: "error",
    missing_accession: "warning",
    unlinked: "warning",
    query_failed: "error",
  }[status] || "neutral";
}

function dcm4cheeDisplayStatus(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()) || "-";
}

function dcm4cheeWorkflowStatusClass(status) {
  const normalized = String(status || "").toLowerCase().replaceAll("_", " ");
  if (["created", "synced", "verified", "matched"].includes(normalized)) return "success";
  if (["pending", "pending sync", "not verified", "ambiguous", "duplicate", "unlinked"].includes(normalized)) return "warning";
  if (normalized.includes("failed") || normalized.includes("wrong patient") || normalized.includes("missing")) return "error";
  return dcm4cheeResultStatusClass(status);
}

function dcm4cheeCopyButton(label, value) {
  if (!value) return null;
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    navigator.clipboard.writeText(value);
  });
  return button;
}

function dcm4cheeOpenButton(label, url) {
  if (!url) return null;
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    window.open(url, "_blank", "noopener");
  });
  return button;
}

function dcm4cheeActionsForResult(item, level = "study") {
  const actions = document.createElement("div");
  actions.className = "button-row compact-actions dcm4chee-result-actions";
  const artifactUrl = item.artifact?.url || "";
  const artifactPath = item.artifact?.path || "";
  const retrieveUrl = level === "instance"
    ? item.instanceRetrieveUrl
    : level === "series"
      ? item.seriesRetrieveUrl
      : item.studyRetrieveUrl;
  [
    dcm4cheeOpenButton("Open Artifact", artifactUrl),
    dcm4cheeCopyButton("Copy Artifact", artifactUrl || artifactPath),
    dcm4cheeOpenButton("Open Viewer", item.viewerUrl),
    dcm4cheeCopyButton("Copy Retrieve", retrieveUrl),
  ].filter(Boolean).forEach((button) => actions.appendChild(button));
  if (!actions.childElementCount) actions.appendChild(createElement("span", "-", "muted"));
  return actions;
}

function dcm4cheeResultKey(item, fields, fallback) {
  const key = fields.map((field) => String(item?.[field] || "").trim()).find(Boolean);
  return key || fallback;
}

function summarizeDcm4cheeResultGroup(records) {
  const statuses = records.map((item) => item.reconciliationStatus).filter(Boolean);
  if (statuses.includes("matched")) return "matched";
  if (statuses.includes("query_failed")) return "query_failed";
  if (statuses.includes("wrong_patient")) return "wrong_patient";
  if (statuses.includes("ambiguous")) return "ambiguous";
  if (statuses.includes("duplicate")) return "duplicate";
  if (statuses.includes("unlinked")) return "unlinked";
  return statuses[0] || "no_result";
}

function groupDcm4cheeResultsForBrowser(results = []) {
  const groups = new Map();
  const ensureGroup = (key, label, kind) => {
    if (!groups.has(key)) groups.set(key, { key, label, kind, records: [], studies: new Map() });
    return groups.get(key);
  };
  results.forEach((item, index) => {
    const hasOrder = item.orderRecordId !== null && item.orderRecordId !== undefined && item.orderRecordId !== "";
    const group = hasOrder
      ? ensureGroup(`order:${item.orderRecordId}`, `Order ${item.orderRecordId}`, "matched-order")
      : ensureGroup("unresolved", "Unresolved diagnostics", "unresolved");
    group.records.push(item);
    const studyKey = dcm4cheeResultKey(item, ["studyInstanceUid", "accessionNumber"], `diagnostic:${item.resultKey || item.id || index}`);
    if (!group.studies.has(studyKey)) {
      group.studies.set(studyKey, { key: studyKey, records: [], series: new Map() });
    }
    const study = group.studies.get(studyKey);
    study.records.push(item);
    const seriesKey = dcm4cheeResultKey(item, ["seriesInstanceUid"], `series:${item.id || index}`);
    if (!study.series.has(seriesKey)) {
      study.series.set(seriesKey, { key: seriesKey, records: [], instances: [] });
    }
    const series = study.series.get(seriesKey);
    series.records.push(item);
    if (item.sopInstanceUid || item.instanceRetrieveUrl || item.instanceDateTime) {
      series.instances.push(item);
    }
  });
  return Array.from(groups.values()).map((group) => ({
    ...group,
    status: summarizeDcm4cheeResultGroup(group.records),
    studies: Array.from(group.studies.values()).map((study) => ({
      ...study,
      status: summarizeDcm4cheeResultGroup(study.records),
      series: Array.from(study.series.values()).map((series) => ({
        ...series,
        status: summarizeDcm4cheeResultGroup(series.records),
      })),
    })),
  }));
}

function dcm4cheeFirstValue(records, field) {
  return records.map((item) => item?.[field]).find((value) => value !== null && value !== undefined && value !== "") || "";
}

function dcm4cheeFirstArtifact(records) {
  return records
    .map((item) => item?.artifact)
    .find((artifact) => (
      artifact
      && typeof artifact === "object"
      && (artifact.label || artifact.mediaType || artifact.url || artifact.path || artifact.role)
    )) || {};
}

function renderDcm4cheeResultTable(headers, rows, className = "") {
  const { wrap, tbody } = dcm4cheeNestedTable(headers);
  wrap.classList.add("dcm4chee-result-table-wrap");
  if (className) wrap.classList.add(className);
  rows.forEach((values) => {
    const row = document.createElement("tr");
    values.forEach((value) => row.appendChild(rowCell(value === null || value === undefined || value === "" ? "-" : value)));
    tbody.appendChild(row);
  });
  return wrap;
}

function renderDcm4cheeInstanceTable(records) {
  if (!records.length) return createElement("p", "No instance-level DICOM metadata for this series.", "muted dcm4chee-empty-result");
  return renderDcm4cheeResultTable(
    ["SOP Instance UID", "Modality", "Instance Date/Time", "Status", "Actions"],
    records.map((item) => [
      item.sopInstanceUid,
      item.modality,
      taipeiTimestamp(item.instanceDateTime || item.lastRefreshedAt),
      createElement("span", dcm4cheeDisplayStatus(item.reconciliationStatus), `status ${dcm4cheeResultStatusClass(item.reconciliationStatus)}`),
      dcm4cheeActionsForResult(item, "instance"),
    ]),
    "dcm4chee-instance-table-wrap",
  );
}

function renderDcm4cheeSeriesDetails(series) {
  const details = document.createElement("details");
  details.className = "dcm4chee-browser-row dcm4chee-series-row";
  const representative = series.records[0] || {};
  const summary = document.createElement("summary");
  summary.append(
    createElement("span", "Series", "dcm4chee-row-kind"),
    createElement("code", dcm4cheeFirstValue(series.records, "seriesInstanceUid") || "No Series Instance UID"),
    createElement("span", dcm4cheeDisplayStatus(series.status), `status ${dcm4cheeResultStatusClass(series.status)}`),
  );
  details.appendChild(summary);
  details.appendChild(renderDcm4cheeResultTable(
    ["Series Instance UID", "Modality", "Source", "Series Date/Time", "Status", "Actions"],
    [[
      dcm4cheeFirstValue(series.records, "seriesInstanceUid"),
      dcm4cheeFirstValue(series.records, "modality"),
      dcm4cheeFirstValue(series.records, "source") || "dcm4chee",
      taipeiTimestamp(dcm4cheeFirstValue(series.records, "seriesDateTime") || dcm4cheeFirstValue(series.records, "lastRefreshedAt")),
      createElement("span", dcm4cheeDisplayStatus(series.status), `status ${dcm4cheeResultStatusClass(series.status)}`),
      dcm4cheeActionsForResult(representative, "series"),
    ]],
    "dcm4chee-series-table-wrap",
  ));
  details.appendChild(renderDcm4cheeInstanceTable(series.instances));
  return details;
}

function renderDcm4cheeStudyDetails(study) {
  const details = document.createElement("details");
  details.className = "dcm4chee-browser-row dcm4chee-study-row";
  details.open = true;
  const representative = study.records[0] || {};
  const summary = document.createElement("summary");
  summary.append(
    createElement("span", "Study", "dcm4chee-row-kind"),
    createElement("code", dcm4cheeFirstValue(study.records, "studyInstanceUid") || "No Study Instance UID"),
    createElement("span", dcm4cheeDisplayStatus(study.status), `status ${dcm4cheeResultStatusClass(study.status)}`),
  );
  details.appendChild(summary);
  const artifact = dcm4cheeFirstArtifact(study.records);
  const diagnostic = dcm4cheeFirstValue(study.records, "error")
    || dcm4cheeFirstValue(study.records, "errorType")
    || dcm4cheeFirstValue(study.records, "message");
  details.appendChild(renderDcm4cheeResultTable(
    ["Accession Number", "Study Instance UID", "Modality", "Patient ID", "Issuer of Patient ID", "Requested Procedure ID", "Scheduled Procedure Step ID", "Study Date/Time", "Artifact", "Artifact Type", "Artifact Location", "Diagnostic", "Actions"],
    [[
      dcm4cheeFirstValue(study.records, "accessionNumber"),
      dcm4cheeFirstValue(study.records, "studyInstanceUid"),
      dcm4cheeFirstValue(study.records, "modality"),
      dcm4cheeFirstValue(study.records, "patientId"),
      dcm4cheeFirstValue(study.records, "issuerOfPatientId"),
      dcm4cheeFirstValue(study.records, "requestedProcedureId"),
      dcm4cheeFirstValue(study.records, "scheduledProcedureStepId"),
      taipeiTimestamp(dcm4cheeFirstValue(study.records, "studyDateTime") || dcm4cheeFirstValue(study.records, "lastRefreshedAt")),
      artifact.label || artifact.role,
      artifact.mediaType,
      artifact.url || artifact.path,
      diagnostic,
      dcm4cheeActionsForResult({ ...representative, artifact }, "study"),
    ]],
    "dcm4chee-study-table-wrap",
  ));
  study.series.forEach((series) => details.appendChild(renderDcm4cheeSeriesDetails(series)));
  return details;
}

function renderDcm4cheeResultGroup(group) {
  const details = document.createElement("details");
  details.className = `dcm4chee-result-group ${group.kind}`;
  details.open = true;
  const summary = document.createElement("summary");
  summary.append(
    createElement("strong", group.label),
    createElement("span", `${group.records.length} row(s)`, "muted"),
    createElement("span", dcm4cheeDisplayStatus(group.status), `status ${dcm4cheeResultStatusClass(group.status)}`),
  );
  details.appendChild(summary);
  group.studies.forEach((study) => details.appendChild(renderDcm4cheeStudyDetails(study)));
  return details;
}

function renderPatientDcm4cheeResults(container, patient) {
  const results = patient?.dcm4chee?.dicomResults || [];
  const section = document.createElement("details");
  section.className = "detail-block dcm4chee-result-browser";
  section.open = Boolean(results.length);
  const summary = document.createElement("summary");
  summary.append(
    document.createTextNode(`DICOM Results (${results.length})`),
  );
  section.appendChild(summary);
  if (!results.length) {
    section.appendChild(createElement("p", "No refreshed dcm4chee results for this patient.", "muted"));
    container.appendChild(section);
    return;
  }
  groupDcm4cheeResultsForBrowser(results).forEach((group) => {
    section.appendChild(renderDcm4cheeResultGroup(group));
  });
  container.appendChild(section);
}

function renderDcm4cheeResultsBrowser(container, results = [], emptyText = "No refreshed dcm4chee results.") {
  const viewport = createElement("div", "", "dcm4chee-result-browser-viewport");
  const section = document.createElement("details");
  section.className = "detail-block dcm4chee-result-browser";
  section.open = Boolean(results.length);
  const summary = document.createElement("summary");
  summary.appendChild(document.createTextNode(`DICOM Results (${results.length})`));
  section.appendChild(summary);
  if (!results.length) {
    section.appendChild(createElement("p", emptyText, "muted"));
    viewport.appendChild(section);
    container.appendChild(viewport);
    return;
  }
  groupDcm4cheeResultsForBrowser(results).forEach((group) => {
    section.appendChild(renderDcm4cheeResultGroup(group));
  });
  viewport.appendChild(section);
  container.appendChild(viewport);
}

function renderPatientSummaryFromRecord(item) {
  renderPatientSummaryFromPayload({
    ...(item.patient || {}),
    visitNumber: item.visitNumber,
    patientClass: item.patientClass,
    assignedLocation: item.assignedLocation,
  }, item.createdAt);
  renderPatientDcm4cheeResults(byId("patient-summary"), item);
}

function dcm4cheeConsolePatients() {
  const patientIdsWithDicomOrders = new Set(
    orderRecords
      .filter((item) => item.protocolVersion === "DICOM" && item.patientRecordId)
      .map((item) => Number(item.patientRecordId)),
  );
  return patientRecords.filter((item) => (
    item.protocolVersion === "DICOM"
    || item.dcm4chee?.patient
    || patientIdsWithDicomOrders.has(Number(item.id))
  ));
}

function dcm4cheeConsoleOrders(patientId = getSelectedPatientId()) {
  return orderRecords.filter((item) => (
    item.protocolVersion === "DICOM"
    && (!patientId || Number(item.patientRecordId) === Number(patientId))
  ));
}

function selectedDcm4cheePatient() {
  const selectedId = Number(getSelectedPatientId() || 0);
  return dcm4cheeConsolePatients().find((item) => Number(item.id) === selectedId) || null;
}

function selectedDcm4cheeOrder() {
  const selectedId = Number(getSelectedOrderId() || 0);
  return orderRecords.find((item) => item.protocolVersion === "DICOM" && Number(item.id) === selectedId) || null;
}

function dcm4cheePatientLabel(patient) {
  return patient?.summary?.name || patient?.summary?.mrn || `Patient ${patient?.id}`;
}

function dcm4cheeOrderLabel(order) {
  return order?.localOrderNumber || `Order ${order?.id}`;
}

function dcm4cheeOrderPatient(order) {
  return patientRecords.find((patient) => Number(patient.id) === Number(order?.patientRecordId)) || null;
}

function dcm4cheeOrderStatus(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  return mwl.displayStatus || mapping.status || mwl.status || order?.status || "Not synced";
}

function dcm4cheeOrderVerificationStatus(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  const verification = mapping.verification || mwl.verification || {};
  return verification.status || "Not verified";
}

function dcm4cheeOrderActionButtons(order) {
  const actions = createElement("div", "", "button-row compact-actions");
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  const inspectButton = createElement("button", "Inspect", "small-button");
  inspectButton.type = "button";
  inspectButton.addEventListener("click", (event) => {
    event.stopPropagation();
    selectDcm4cheeOrder(order.id);
  });
  actions.appendChild(inspectButton);
  const sendButton = createElement("button", "Send", "small-button");
  sendButton.type = "button";
  sendButton.addEventListener("click", (event) => {
    event.stopPropagation();
    sendDcm4cheeOrder(order.id, sendButton);
  });
  actions.appendChild(sendButton);
  if (mwl.retryable) {
    const retryButton = createElement("button", "Retry", "small-button");
    retryButton.type = "button";
    retryButton.addEventListener("click", (event) => {
      event.stopPropagation();
      retryDcm4cheeOrder(order.id, retryButton);
    });
    actions.appendChild(retryButton);
  }
  if (mapping.id) {
    const verifyButton = createElement("button", "Verify", "small-button");
    verifyButton.type = "button";
    verifyButton.addEventListener("click", (event) => {
      event.stopPropagation();
      verifyDcm4cheeOrder(order.id, verifyButton);
    });
    actions.appendChild(verifyButton);
  }
  return actions;
}

function selectDcm4cheePatient(patientId) {
  setSelectedPatientId(patientId);
  const patientOrders = dcm4cheeConsoleOrders(patientId);
  if (!patientOrders.some((item) => Number(item.id) === Number(getSelectedOrderId()))) {
    setSelectedOrderId(patientOrders[0]?.id || null);
  }
  renderDcm4cheeConsole();
}

function selectDcm4cheeOrder(orderId) {
  setSelectedOrderId(orderId);
  const order = selectedDcm4cheeOrder();
  if (order?.patientRecordId) setSelectedPatientId(order.patientRecordId);
  renderDcm4cheeConsole();
  if (orderId) loadDcm4cheeAttemptHistory(orderId, "dcm4chee-console-attempt-history");
}

function ensureDcm4cheeSelection() {
  const patients = dcm4cheeConsolePatients();
  if (!patients.length) {
    setSelectedPatientId(null);
    setSelectedOrderId(null);
    return;
  }
  if (!getSelectedPatientId() || !patients.some((item) => Number(item.id) === Number(getSelectedPatientId()))) {
    setSelectedPatientId(patients[0].id);
  }
  const orders = dcm4cheeConsoleOrders(getSelectedPatientId());
  if (!orders.some((item) => Number(item.id) === Number(getSelectedOrderId()))) {
    setSelectedOrderId(orders[0]?.id || null);
  }
}

function renderDcm4cheeSelectors() {
  const patientSelect = byId("dcm4chee-patient-select");
  const orderSelect = byId("dcm4chee-order-select");
  if (!patientSelect || !orderSelect) return;
  const patients = dcm4cheeConsolePatients();
  patientSelect.replaceChildren();
  if (!patients.length) {
    patientSelect.appendChild(new Option("No DICOM patients", ""));
  } else {
    patients.forEach((patient) => {
      const mrn = patient.summary?.mrn || `Patient ${patient.id}`;
      const name = patient.summary?.name || "Unnamed patient";
      patientSelect.appendChild(new Option(`${mrn} - ${name}`, String(patient.id)));
    });
    patientSelect.value = String(getSelectedPatientId() || "");
  }
  patientSelect.disabled = !patients.length;

  const orders = dcm4cheeConsoleOrders(getSelectedPatientId());
  orderSelect.replaceChildren();
  if (!orders.length) {
    orderSelect.appendChild(new Option("No DICOM MWL orders", ""));
  } else {
    orders.forEach((order) => {
      const code = order.summary?.orderCode || order.orderCode || "DICOM";
      orderSelect.appendChild(new Option(`${dcm4cheeOrderLabel(order)} - ${code}`, String(order.id)));
    });
    orderSelect.value = String(getSelectedOrderId() || "");
  }
  orderSelect.disabled = !orders.length;
}

function dcm4cheeOrderPreviewPayload(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  return mapping.latestRequestPayload || mwl.requestPayload || mwl.latest?.requestPayload || null;
}

function renderDcm4cheePreview() {
  const order = selectedDcm4cheeOrder();
  const summary = byId("dcm4chee-preview-summary");
  const preview = byId("dcm4chee-payload-preview");
  if (!summary || !preview) return;
  summary.replaceChildren();
  if (!order) {
    summary.appendChild(createElement("p", "Select a DICOM MWL order to inspect its payload.", "muted"));
    preview.textContent = "Select a DICOM MWL order to preview its DICOM JSON payload.";
    return;
  }
  const mapping = order.dcm4chee?.mwl?.mapping || {};
  [
    ["Order", dcm4cheeOrderLabel(order)],
    ["Accession", mapping.accessionNumber],
    ["Status", dcm4cheeOrderStatus(order)],
  ].forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(String(value || "-")));
    summary.appendChild(item);
  });
  const payload = dcm4cheeOrderPreviewPayload(order);
  preview.textContent = payload && Object.keys(payload).length
    ? JSON.stringify(payload, null, 2)
    : "No DICOM JSON payload has been generated for this order yet. Send the order to generate it.";
}

function dcm4cheeNestedTable(headers) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap dcm4chee-nested-table-wrap";
  const table = document.createElement("table");
  table.className = "dcm4chee-nested-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => headRow.appendChild(createElement("th", header)));
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  wrap.appendChild(table);
  return { wrap, tbody };
}

function renderDcm4cheeExpandedOrders(orders) {
  const { wrap, tbody } = dcm4cheeNestedTable(["Order", "Code", "Sync", "MWL", "Accession", "Actions"]);
  if (!orders.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No DICOM MWL orders for this patient.");
    cell.colSpan = 6;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
    return wrap;
  }
  orders.forEach((order) => {
    const mwl = order.dcm4chee?.mwl || {};
    const mapping = mwl.mapping || {};
    const row = document.createElement("tr");
    row.classList.toggle("selected-row", Number(order.id) === Number(getSelectedOrderId()));
    row.append(
      rowCell(dcm4cheeOrderLabel(order)),
      rowCell(order.summary?.orderCode || order.orderCode || "-"),
      rowCell(createElement("span", dcm4cheeOrderStatus(order), `status ${dcm4cheeWorkflowStatusClass(dcm4cheeOrderStatus(order))}`)),
      rowCell(createElement("span", dcm4cheeOrderVerificationStatus(order), `status ${dcm4cheeWorkflowStatusClass(dcm4cheeOrderVerificationStatus(order))}`)),
      rowCell(mapping.accessionNumber || mwl.accessionNumber || "-"),
      rowCell(dcm4cheeOrderActionButtons(order)),
    );
    row.addEventListener("click", () => selectDcm4cheeOrder(order.id));
    tbody.appendChild(row);
  });
  return wrap;
}

function dcm4cheePatientSection(label, title, body) {
  const section = document.createElement("section");
  section.className = "dcm4chee-patient-section";
  const heading = document.createElement("div");
  heading.className = "compact-heading dcm4chee-patient-section-heading";
  const text = document.createElement("div");
  text.appendChild(createElement("p", label, "eyebrow"));
  text.appendChild(createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function renderDcm4cheeExpandedResults(patient) {
  const container = document.createElement("div");
  renderDcm4cheeResultsBrowser(
    container,
    patient.dcm4chee?.dicomResults || [],
    "No refreshed dcm4chee results for this patient.",
  );
  return container;
}

function renderDcm4cheePatientList() {
  const body = byId("dcm4chee-patient-list");
  if (!body) return;
  body.replaceChildren();
  const patients = dcm4cheeConsolePatients();
  if (!patients.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local DICOM patients yet. Create a DICOM Patient from the Patient workspace.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  patients.forEach((patient) => {
    const patientId = Number(patient.id);
    const sync = patient.dcm4chee?.patient || {};
    const orders = dcm4cheeConsoleOrders(patient.id);
    const resultCount = patient.dcm4chee?.resultCount ?? (patient.dcm4chee?.dicomResults || []).length;
    const actions = createElement("div", "", "button-row compact-actions");
    const refreshButton = createElement("button", "Refresh", "small-button");
    refreshButton.type = "button";
    refreshButton.addEventListener("click", (event) => {
      event.stopPropagation();
      refreshPatientDcm4cheeResults(patient.id, refreshButton);
    });
    actions.appendChild(refreshButton);
    const row = document.createElement("tr");
    row.className = Number(patient.id) === Number(getSelectedPatientId()) ? "selected-row" : "";
    const toggleButton = createElement("button", "V", "dcm4chee-patient-toggle");
    toggleButton.type = "button";
    toggleButton.classList.toggle("expanded", expandedDcm4cheePatientIds.has(patientId));
    toggleButton.setAttribute("aria-expanded", String(expandedDcm4cheePatientIds.has(patientId)));
    toggleButton.setAttribute(
      "aria-label",
      expandedDcm4cheePatientIds.has(patientId) ? "Collapse patient orders and results" : "Expand patient orders and results",
    );
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (expandedDcm4cheePatientIds.has(patientId)) {
        expandedDcm4cheePatientIds.delete(patientId);
      } else {
        expandedDcm4cheePatientIds.add(patientId);
      }
      renderDcm4cheeConsole();
    });
    row.append(
      rowCell(toggleButton),
      rowCell(patient.summary?.mrn || "-"),
      rowCell(patient.summary?.name || "Unnamed patient"),
      rowCell(createElement("span", sync.displayStatus || sync.status || "Local only", `status ${dcm4cheeWorkflowStatusClass(sync.displayStatus || sync.status)}`)),
      rowCell(orders.length),
      rowCell(resultCount),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectDcm4cheePatient(patient.id));
    body.appendChild(row);

    if (expandedDcm4cheePatientIds.has(patientId)) {
      const detailRow = document.createElement("tr");
      detailRow.className = "dcm4chee-patient-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 7;
      const content = document.createElement("div");
      content.className = "dcm4chee-patient-rollup-content";
      content.append(
        dcm4cheePatientSection("MWL", "Orders", renderDcm4cheeExpandedOrders(orders)),
        dcm4cheePatientSection("PACS", "Results", renderDcm4cheeExpandedResults(patient)),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function renderDcm4cheeSelectedPatient() {
  const patient = selectedDcm4cheePatient();
  const title = byId("dcm4chee-selected-patient-title");
  const container = byId("dcm4chee-selected-patient-summary");
  const refreshButton = byId("dcm4chee-refresh-results");
  if (!title || !container || !refreshButton) return;
  title.textContent = patient ? dcm4cheePatientLabel(patient) : "No patient selected";
  refreshButton.disabled = !patient;
  refreshButton.onclick = () => {
    if (patient) refreshPatientDcm4cheeResults(patient.id, refreshButton);
  };
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a DICOM patient.", "muted"));
    return;
  }
  const sync = patient.dcm4chee?.patient || {};
  container.appendChild(dcm4cheeDetailBlock("Patient", [
    ["MRN", patient.summary?.mrn],
    ["Name", patient.summary?.name],
    ["DOB", patient.summary?.dob],
    ["Sex", patient.summary?.sex],
    ["Patient ID", sync.patientId],
    ["Issuer", sync.issuerOfPatientId],
  ]));
  const syncCard = dcm4cheeDetailBlock("dcm4chee Patient Sync", [
    ["Status", sync.displayStatus || sync.status || "Local only"],
    ["Retryable", sync.retryable === undefined ? "" : (sync.retryable ? "Yes" : "No")],
    ["HL7", sync.hl7Host && sync.hl7Port ? `${sync.hl7Host}:${sync.hl7Port}` : ""],
    ["ACK", sync.ack?.code],
    ["Last Sync", sync.lastSyncAt],
    ["Error Type", sync.lastErrorType],
    ["Error", sync.lastError],
  ]);
  syncCard.classList.add("dcm4chee-patient-sync-card");
  container.appendChild(syncCard);
}

function renderDcm4cheeSelectedOrder() {
  const order = selectedDcm4cheeOrder();
  const title = byId("dcm4chee-selected-order-title");
  const container = byId("dcm4chee-selected-order-summary");
  const sendButton = byId("send-dcm4chee-order");
  if (!title || !container || !sendButton) return;
  title.textContent = order ? dcm4cheeOrderLabel(order) : "No order selected";
  sendButton.disabled = !order;
  container.replaceChildren();
  if (!order) {
    container.appendChild(createElement("p", "Select a DICOM MWL order.", "muted"));
    return;
  }
  const patient = dcm4cheeOrderPatient(order) || selectedDcm4cheePatient();
  const mwl = order.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  const latest = mwl.latest || {};
  const verification = mapping.verification || mwl.verification || {};
  const orderResults = dcm4cheeOrderResultRecords(patient, mapping, order.id);
  container.appendChild(renderDcm4cheeWorkflowStrip(dcm4cheeWorkflowSummary(mwl, mapping, patient, order.id)));
  container.appendChild(renderDcm4cheeOrderActions(order.id, patient?.id || order.patientRecordId, mwl, mapping));
  container.appendChild(dcm4cheeDetailBlock("Order", [
    ["Patient", patient?.summary?.name || order.summary?.name],
    ["MRN", patient?.summary?.mrn || order.summary?.mrn],
    ["Order", dcm4cheeOrderLabel(order)],
    ["Code", order.summary?.orderCode || order.orderCode],
    ["Requested", order.requestedAt],
    ["Created", order.createdAt],
  ]));
  container.appendChild(dcm4cheeDetailBlock("MWL Sync", [
    ["Status", mwl.displayStatus || mapping.status || mwl.status],
    ["Retryable", mwl.retryable ? "Yes" : "No"],
    ["Retry Count", mapping.retryCount ?? latest.retryCount ?? 0],
    ["Last Sync", mapping.lastSyncAt || latest.lastSyncAt],
    ["HTTP", mapping.lastHttpStatus || latest.httpStatus],
    ["Error Type", mapping.lastErrorType || latest.errorType],
    ["Error", mapping.lastError || latest.error],
  ]));
  container.appendChild(dcm4cheeDetailBlock("MWL Verification", [
    ["Status", verification.status],
    ["Method", verification.method],
    ["Last Verified", verification.lastVerifiedAt],
    ["Attempt", verification.attemptId],
    ["Error Type", verification.errorType],
    ["Error", verification.error],
  ]));
  container.appendChild(dcm4cheeDetailBlock("Identifiers", [
    ["Study Instance UID", mapping.studyInstanceUid || mwl.studyInstanceUid],
    ["Accession Number", mapping.accessionNumber || mwl.accessionNumber],
    ["Requested Procedure ID", mapping.requestedProcedureId || mwl.requestedProcedureId],
    ["Scheduled Procedure Step ID", mapping.scheduledProcedureStepId || mwl.scheduledProcedureStepId],
    ["Scheduled Station AE Title", mapping.scheduledStationAETitle || mwl.scheduledStationAETitle],
    ["MWL AE", mapping.mwlAETitle || mwl.mwlAETitle],
    ["Patient ID", mapping.patientId],
    ["Issuer of Patient ID", mapping.issuerOfPatientId],
  ]));
  renderDcm4cheeResultsBrowser(container, orderResults, "No refreshed PACS result rows matched this order.");
  const history = createElement("div", "", "detail-block raw-details");
  history.id = "dcm4chee-console-attempt-history";
  history.appendChild(createElement("h3", "dcm4chee Attempts"));
  history.appendChild(createElement("p", "Loading attempt history...", "muted"));
  container.appendChild(history);
  loadDcm4cheeAttemptHistory(order.id, "dcm4chee-console-attempt-history");
}

function renderDcm4cheeProfileSummary() {
  const container = byId("dcm4chee-profile-summary");
  if (!container) return;
  container.replaceChildren();
  if (!dcm4cheeProfileDiagnostics) {
    container.appendChild(createElement("p", "Profile diagnostics are not loaded.", "muted"));
    return;
  }
  container.appendChild(dcm4cheeDetailBlock("Profile", [
    ["Profile", dcm4cheeProfileDiagnostics.profileName],
    ["Status", dcm4cheeProfileDiagnostics.valid ? "Valid" : "Needs attention"],
    ["Summary", dcm4cheeProfileDiagnostics.summary],
  ]));
  const checks = dcm4cheeProfileDiagnostics.checks || [];
  if (checks.length) {
    const list = createElement("div", "", "dcm4chee-diagnostic-checks full-width");
    checks.forEach((check) => {
      const healthy = check.status === "Healthy";
      const item = createElement("div", "", "dcm4chee-diagnostic-check");
      item.append(
        createElement("strong", check.field || check.name || "Check"),
        createElement("span", check.status || (healthy ? "Healthy" : "Down"), `status ${healthy ? "success" : "error"}`),
        createElement("p", check.message || "-", "muted"),
      );
      list.appendChild(item);
    });
    container.appendChild(list);
  }
}

function renderDcm4cheeConsole() {
  ensureDcm4cheeSelection();
  renderDcm4cheeSelectors();
  renderDcm4cheePatientList();
  renderDcm4cheeSelectedPatient();
  renderDcm4cheeSelectedOrder();
  renderDcm4cheePreview();
  renderDcm4cheeProfileSummary();
}

async function refreshDcm4cheeConsole() {
  setStatus("dcm4chee-console-status", "Refreshing...", "pending");
  try {
    const [patientsResult, ordersResult, diagnosticsResult] = await Promise.all([
      fetchPatients("DICOM"),
      requestJson("/api/orders"),
      requestJson("/api/dcm4chee/profile/diagnostics"),
    ]);
    patientRecords = patientsResult.items || [];
    orderRecords = ordersResult.items || [];
    dcm4cheeProfileDiagnostics = diagnosticsResult;
    renderDcm4cheeConsole();
    setStatus(
      "dcm4chee-console-status",
      diagnosticsResult.valid ? "dcm4chee ready" : "Profile needs attention",
      diagnosticsResult.valid ? "success" : "warning",
    );
  } catch (error) {
    setStatus("dcm4chee-console-status", error.message, "error");
  }
}


function dcm4cheeOrderResultRecords(patient, mapping = {}, orderId = "") {
  const results = patient?.dcm4chee?.dicomResults || [];
  const orderKey = String(orderId || "");
  const studyUid = String(mapping.studyInstanceUid || "").trim();
  const accession = String(mapping.accessionNumber || "").trim();
  const requestedProcedure = String(mapping.requestedProcedureId || "").trim();
  const scheduledStep = String(mapping.scheduledProcedureStepId || "").trim();
  return results.filter((item) => {
    if (orderKey && String(item.orderRecordId || "") === orderKey) return true;
    if (studyUid && item.studyInstanceUid === studyUid) return true;
    if (accession && item.accessionNumber === accession) return true;
    if (requestedProcedure && item.requestedProcedureId === requestedProcedure) return true;
    return Boolean(scheduledStep && item.scheduledProcedureStepId === scheduledStep);
  });
}

function dcm4cheeWorkflowSummary(mwl = {}, mapping = {}, patient = null, orderId = "") {
  const verification = mapping.verification || mwl.verification || {};
  const orderResults = dcm4cheeOrderResultRecords(patient, mapping, orderId);
  const resultStatus = summarizeDcm4cheeResultGroup(orderResults);
  return [
    {
      label: "MWL Sync",
      value: mwl.displayStatus || mapping.status || mwl.status || "Not synced",
      state: dcm4cheeWorkflowStatusClass(mwl.displayStatus || mapping.status || mwl.status),
    },
    {
      label: "MWL Queryable",
      value: verification.status || "Not verified",
      state: dcm4cheeWorkflowStatusClass(verification.status),
    },
    {
      label: "AP C-STORE Result",
      value: orderResults.length ? `${orderResults.length} result row(s)` : "No result",
      state: orderResults.length ? dcm4cheeResultStatusClass(resultStatus) : "neutral",
    },
    {
      label: "Reconciliation",
      value: dcm4cheeDisplayStatus(resultStatus),
      state: dcm4cheeResultStatusClass(resultStatus),
    },
  ];
}

function renderDcm4cheeWorkflowStrip(items) {
  const strip = createElement("div", "", "dcm4chee-workflow-strip full-width");
  items.forEach((item) => {
    const block = createElement("div", "", "dcm4chee-workflow-step");
    block.append(
      createElement("span", item.label, "dcm4chee-workflow-label"),
      createElement("strong", item.value || "-", `status ${item.state || "neutral"}`),
    );
    strip.appendChild(block);
  });
  return strip;
}

function renderDcm4cheeOrderActions(orderId, patientId, mwl = {}, mapping = {}) {
  const actions = createElement("div", "", "dcm4chee-order-actions full-width");
  if (!orderId && !patientId) return actions;
  if (mwl.retryable && orderId) {
    const retryButton = createElement("button", "Retry MWL Sync", "small-button");
    retryButton.type = "button";
    retryButton.addEventListener("click", () => retryDcm4cheeOrder(orderId, retryButton));
    actions.appendChild(retryButton);
  }
  if (mapping.id && orderId) {
    const verifyButton = createElement("button", "Verify MWL Query", "small-button");
    verifyButton.type = "button";
    verifyButton.addEventListener("click", () => verifyDcm4cheeOrder(orderId, verifyButton));
    actions.appendChild(verifyButton);
  }
  if (patientId) {
    const refreshButton = createElement("button", "Refresh PACS Results", "small-button");
    refreshButton.type = "button";
    refreshButton.addEventListener("click", () => refreshPatientDcm4cheeResults(patientId, refreshButton, { orderId }));
    actions.appendChild(refreshButton);
  }
  if (orderId) {
    const simulatePdfButton = createElement("button", "Simulate AP PDF", "small-button");
    simulatePdfButton.type = "button";
    simulatePdfButton.addEventListener("click", () => simulateDcm4cheeApReturn(orderId, simulatePdfButton, "pdf"));
    actions.appendChild(simulatePdfButton);

    const simulateDicomButton = createElement("button", "Simulate AP DICOM", "small-button");
    simulateDicomButton.type = "button";
    simulateDicomButton.addEventListener("click", () => simulateDcm4cheeApReturn(orderId, simulateDicomButton, "dicom"));
    actions.appendChild(simulateDicomButton);
  }
  if (!actions.childElementCount) actions.appendChild(createElement("span", "No DICOM actions available yet.", "muted"));
  return actions;
}

function refreshPatientPreview() {
  const payload = patientFormPayload();
  updatePatientModeFields(payload.mode);
  const messages = validatePatientPayload(payload);
  renderPatientValidation(messages);
  renderPatientSummaryFromPayload(payload);
  const config = PATIENT_MODE_CONFIG[payload.mode] || PATIENT_MODE_CONFIG["hl7-v2"];
  byId("patient-payload-preview").textContent = messages.length
    ? config.emptyPreview
    : buildPatientPreviewPayload(payload);
}

function renderPatientRecords() {
  renderPatientRecordList(patientRecords, {
    onSelect: (item) => {
      byId("patient-payload-preview").textContent = item.payload || "";
      renderPatientSummaryFromRecord(item);
    },
  });
}

function fhirSyncStatusClass(status) {
  return {
    "Synced": "success",
    "Sync failed": "error",
    "Syncing": "pending",
    "Pending sync": "pending",
  }[status] || "neutral";
}

async function refreshPatients() {
  try {
    const result = await fetchPatients();
    patientRecords = result.items || [];
    renderPatientRecords();
    renderOrderPatientOptions();
  } catch (error) {
    setStatus("patient-form-status", "Refresh failed", "error");
  }
}

async function createPatientRecord() {
  const button = byId("create-patient");
  button.disabled = true;
  setStatus("patient-form-status", "Creating...", "pending");
  try {
    const result = await createPatient(patientFormPayload());
    const item = result.item;
    const syncStatus = item.fhir?.sync?.status || item.dcm4chee?.patient?.status || "";
    setStatus(
      "patient-form-status",
      syncStatus === "Synced"
        ? (item.protocolVersion === "DICOM" ? "dcm4chee patient synced" : "FHIR patient synced")
        : "Local patient created",
      syncStatus === "Sync failed" ? "warning" : "success",
    );
    byId("patient-payload-preview").textContent = item.payload || "";
    renderPatientSummaryFromPayload({
      ...(item.patient || {}),
      visitNumber: item.visitNumber,
      patientClass: item.patientClass,
      assignedLocation: item.assignedLocation,
    }, item.createdAt, item.dcm4chee?.patient || null);
    await refreshPatients();
  } catch (error) {
    setStatus("patient-form-status", "Create failed", "error");
    byId("patient-payload-preview").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function retryPatientFhirSync(patientId, button) {
  button.disabled = true;
  setStatus("patient-form-status", "Retrying FHIR sync...", "pending");
  try {
    const result = await retryPatientFhirSyncRequest(patientId);
    const syncStatus = result.item?.fhir?.sync?.status || "";
    setStatus(
      "patient-form-status",
      syncStatus === "Synced" ? "FHIR patient synced" : "FHIR sync needs attention",
      syncStatus === "Synced" ? "success" : "warning",
    );
    await refreshPatients();
  } catch (error) {
    setStatus("patient-form-status", error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function refreshPatientDcm4cheeResults(patientId, button, options = {}) {
  if (button) button.disabled = true;
  setStatus("patient-form-status", "Refreshing dcm4chee results...", "pending");
  if (options.orderId) setStatus("order-form-status", "Refreshing PACS results...", "pending");
  try {
    const result = await refreshPatientDcm4cheeResultsRequest(patientId);
    const patient = result.patient || {};
    patientRecords = patientRecords.map((item) => Number(item.id) === Number(patient.id) ? patient : item);
    setSelectedPatientId(patient.id || getSelectedPatientId());
    renderPatientRecords();
    byId("patient-payload-preview").textContent = patient.payload || "";
    renderPatientSummaryFromRecord(patient);
    renderDcm4cheeConsole();
    const count = (patient.dcm4chee?.dicomResults || []).length;
    setStatus(
      "patient-form-status",
      `dcm4chee results refreshed (${count})`,
      result.success ? "success" : "warning",
    );
    if (options.orderId) {
      setSelectedOrderId(options.orderId);
      setStatus("order-form-status", `PACS results refreshed (${count})`, result.success ? "success" : "warning");
      await refreshOrders();
    }
    setStatus("dcm4chee-console-status", `PACS results refreshed (${count})`, result.success ? "success" : "warning");
  } catch (error) {
    setStatus("patient-form-status", error.message, "error");
    if (options.orderId) setStatus("order-form-status", error.message, "error");
    setStatus("dcm4chee-console-status", error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

function selectedOrderPatient() {
  const selectedId = Number(byId("order-patient")?.value || 0);
  return patientRecords.find((item) => Number(item.id) === selectedId) || null;
}

function selectedOrderPatientReference() {
  const patient = selectedOrderPatient();
  return patient?.fhir?.medplum?.reference || "";
}

function fhirOrderField(id) {
  const element = byId(id);
  return element ? element.value.trim() : "";
}

function fhirOrderPayload() {
  const asNeeded = fhirOrderField("fhir-as-needed-boolean");
  const payload = {
    resourceType: "ServiceRequest",
    id: fhirOrderField("fhir-service-request-id"),
    identifier: fhirOrderField("fhir-identifier"),
    identifierSystem: fhirOrderField("fhir-identifier-system"),
    identifierValue: fhirOrderField("fhir-identifier-value"),
    instantiatesCanonical: fhirOrderField("fhir-instantiates-canonical"),
    instantiatesUri: fhirOrderField("fhir-instantiates-uri"),
    basedOn: fhirOrderField("fhir-based-on"),
    replaces: fhirOrderField("fhir-replaces"),
    requisitionSystem: fhirOrderField("fhir-requisition-system"),
    requisitionValue: fhirOrderField("fhir-requisition-value"),
    status: fhirOrderField("fhir-status") || "active",
    intent: fhirOrderField("fhir-intent") || "order",
    category: fhirOrderField("fhir-category"),
    priority: fhirOrderField("fhir-priority") || "routine",
    doNotPerform: fhirOrderField("fhir-do-not-perform") === "true",
    codeSystem: fhirOrderField("fhir-code-system"),
    codeCode: fhirOrderField("fhir-code-code"),
    codeDisplay: fhirOrderField("fhir-code-display"),
    orderDetail: fhirOrderField("fhir-order-detail"),
    quantityValue: fhirOrderField("fhir-quantity-value"),
    quantityUnit: fhirOrderField("fhir-quantity-unit"),
    subject: selectedOrderPatientReference(),
    encounter: fhirOrderField("fhir-encounter"),
    occurrenceDateTime: fhirOrderField("fhir-occurrence"),
    asNeededCodeText: fhirOrderField("fhir-as-needed-code-text"),
    authoredOn: fhirOrderField("fhir-authored-on"),
    requester: fhirOrderField("fhir-requester"),
    performerType: fhirOrderField("fhir-performer-type"),
    performer: fhirOrderField("fhir-performer"),
    locationCode: fhirOrderField("fhir-location-code"),
    locationReference: fhirOrderField("fhir-location-reference"),
    reasonCodeText: fhirOrderField("fhir-reason-code-text"),
    reasonReference: fhirOrderField("fhir-reason-reference"),
    insurance: fhirOrderField("fhir-insurance"),
    supportingInfo: fhirOrderField("fhir-supporting-info"),
    specimen: fhirOrderField("fhir-specimen"),
    bodySite: fhirOrderField("fhir-body-site"),
    note: fhirOrderField("fhir-note"),
    patientInstruction: fhirOrderField("fhir-patient-instruction"),
    relevantHistory: fhirOrderField("fhir-relevant-history"),
  };
  if (asNeeded) payload.asNeededBoolean = asNeeded === "true";
  return payload;
}

function orderFormPayload() {
  const mode = currentOrderMode();
  if (mode === "gdt") {
    return {
      mode,
      patientRecordId: Number(byId("order-patient").value || 0),
      requestedAt: byId("order-requested-at").value.trim(),
      orderingProvider: byId("order-provider").value.trim(),
      clinicalIndication: byId("order-indication").value.trim(),
      attachmentUrl: byId("gdt-attachment-url").value.trim(),
      gdtTestCode: "EKG01",
    };
  }
  if (mode === "fhir") {
    const fhir = fhirOrderPayload();
    return {
      mode,
      patientRecordId: Number(byId("order-patient").value || 0),
      priority: fhir.priority,
      requestedAt: fhir.occurrenceDateTime,
      orderingProvider: fhir.requester,
      clinicalIndication: fhir.reasonCodeText,
      orderCode: fhir.codeCode,
      orderCodeText: fhir.codeDisplay,
      alternateCode: orderDemoPreset.alternateCode,
      alternateCodeText: orderDemoPreset.alternateCodeText,
      alternateCodeSystem: orderDemoPreset.alternateCodeSystem,
      fhir,
    };
  }
  return {
    mode,
    patientRecordId: Number(byId("order-patient").value || 0),
    priority: byId("order-priority").value,
    requestedAt: byId("order-requested-at").value.trim(),
    orderingProvider: byId("order-provider").value.trim(),
    clinicalIndication: byId("order-indication").value.trim(),
    orderCode: byId("order-code").value.trim(),
    orderCodeText: orderDemoPreset.orderCodeText,
    alternateCode: byId("order-alternate-code").value.trim(),
    alternateCodeText: orderDemoPreset.alternateCodeText,
    alternateCodeSystem: orderDemoPreset.alternateCodeSystem,
  };
}

function setFhirOrderForm(payload) {
  const setValue = (id, value) => {
    const element = byId(id);
    if (element) element.value = value || "";
  };
  setValue("fhir-status", payload.status || "active");
  setValue("fhir-intent", payload.intent || "order");
  setValue("fhir-category", payload.category || "Procedure");
  setValue("fhir-priority", payload.priority || "routine");
  setValue("fhir-do-not-perform", payload.doNotPerform || "false");
  setValue("fhir-code-system", payload.codeSystem || "urn:healthcare-lab:service-code");
  setValue("fhir-code-code", payload.codeCode || orderDemoPreset.orderCode);
  setValue("fhir-code-display", payload.codeDisplay || orderDemoPreset.orderCodeText);
  setValue("fhir-reason-code-text", payload.reasonCodeText || "");
  setValue("fhir-requester", payload.requester || "");
  setValue("fhir-performer-type", payload.performerType || "");
  setValue("fhir-location-code", payload.locationCode || "");
  setValue("fhir-quantity-value", payload.quantityValue || "");
  setValue("fhir-quantity-unit", payload.quantityUnit || "");
  setValue("fhir-note", payload.note || "");
  setValue("fhir-patient-instruction", payload.patientInstruction || "");
  if (!fhirOrderField("fhir-occurrence")) setValue("fhir-occurrence", localDatetimeValue());
  if (!fhirOrderField("fhir-authored-on")) setValue("fhir-authored-on", localDatetimeValue());
}

function setOrderForm(payload) {
  if (currentOrderMode() === "fhir") {
    setFhirOrderForm(payload.fhir || payload);
  }
  byId("order-priority").value = payload.priority || "R";
  byId("order-provider").value = payload.orderingProvider || orderDemoPreset.orderingProvider;
  byId("order-indication").value = payload.clinicalIndication || "";
  byId("order-code").value = payload.orderCode || orderDemoPreset.orderCode;
  byId("order-alternate-code").value = payload.alternateCode || orderDemoPreset.alternateCode;
  if (!byId("order-requested-at").value.trim()) {
    byId("order-requested-at").value = hl7Timestamp();
  }
}

function renderOrderPatientOptions() {
  const selector = byId("order-patient");
  if (!selector) return;
  const current = selector.value || String(getSelectedPatientId() || "");
  const mode = currentOrderMode();
  const records = orderPatientRecordsForMode(mode);
  selector.replaceChildren();
  if (!patientRecords.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Create a patient first";
    selector.appendChild(option);
    selector.disabled = true;
    return;
  }
  if (!records.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = `Create a ${orderPatientModeLabel(mode)} patient first`;
    selector.appendChild(option);
    selector.disabled = true;
    return;
  }
  selector.disabled = false;
  records.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.summary?.mrn || item.id} - ${item.summary?.name || "Patient"}`;
    selector.appendChild(option);
  });
  if ([...selector.options].some((option) => option.value === current)) {
    selector.value = current;
  }
  setSelectedPatientId(Number(selector.value || 0) || null);
}

function validateOrderPayload(payload) {
  const messages = [];
  if (!payload.patientRecordId) messages.push("Patient is required.");
  if (payload.mode === "fhir") {
    const patient = selectedOrderPatient();
    if (!payload.fhir?.status) messages.push("FHIR status is required.");
    if (!payload.fhir?.intent) messages.push("FHIR intent is required.");
    if (!payload.fhir?.codeCode && !payload.fhir?.codeDisplay) messages.push("FHIR order code is required.");
    if (!patient?.fhir?.medplum?.reference || patient?.fhir?.sync?.status !== "Synced") {
      messages.push("FHIR Order requires a synced FHIR Patient.");
    }
  }
  if (payload.mode === "hl7-v251") {
    if (!payload.orderingProvider) messages.push("Ordering provider is required.");
    if (!payload.orderCode) messages.push("Order code is required.");
    if (!payload.alternateCode) messages.push("Alternate code is required.");
  }
  if (payload.mode !== "fhir" && payload.requestedAt && !/^\d{8}(\d{4})?(\d{2})?$/.test(payload.requestedAt)) {
    messages.push("Requested time must be YYYYMMDD, YYYYMMDDHHMM, or YYYYMMDDHHMMSS.");
  }
  return messages;
}

function renderOrderValidation(messages) {
  const container = byId("order-validation");
  container.replaceChildren();
  if (!messages.length) {
    container.appendChild(createElement("span", "Valid preview", "status success"));
    return;
  }
  container.appendChild(createElement("span", "Needs input", "status pending"));
  const list = document.createElement("ul");
  messages.forEach((message) => list.appendChild(createElement("li", message)));
  container.appendChild(list);
}

function orderVisitId(patient) {
  return patient?.visitNumber || "VISIT-ORD-GENERATED";
}

function orderAccountNumber(patient) {
  return patient?.accountNumber || "ACC-ORD-GENERATED";
}

function buildGdtOrderPreviewPayload(payload, patient) {
  const patientData = patient?.patient || {};
  const summary = patient?.summary || {};
  const dob = summary.dob || "";
  const birthDate = dob.length === 8 ? `${dob.slice(6)}${dob.slice(4, 6)}${dob.slice(0, 4)}` : dob;
  const records = [
    ["8315", "LABGDT"],
    ["8316", "HCLAB"],
    ["3000", summary.mrn || ""],
    ["3101", patientData.lastName || ""],
    ["3102", patientData.firstName || ""],
    ["3103", birthDate],
    ["6200", "GDT-ORD-GENERATED"],
    ["8402", "EKG01"],
  ];
  const sexCode = { M: "1", F: "2" }[summary.sex];
  if (sexCode) records.push(["3110", sexCode]);
  if (payload.requestedAt) records.push(["6220", payload.requestedAt]);
  if (payload.orderingProvider) records.push(["6227", payload.orderingProvider]);
  if (payload.clinicalIndication) records.push(["6228", payload.clinicalIndication]);
  return renderGdtMessage(records, "6302");
}

function splitFhirList(value) {
  return String(value || "")
    .replaceAll(",", "\n")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function fhirReferenceList(value) {
  return splitFhirList(value).map((reference) => ({ reference }));
}

function fhirConcept(text, code = "", system = "", display = "") {
  const concept = {};
  if (text) concept.text = text;
  if (code || system || display) {
    const coding = {};
    if (system) coding.system = system;
    if (code) coding.code = code;
    if (display) coding.display = display;
    concept.coding = [coding];
    if (!concept.text) concept.text = display || code;
  }
  return concept;
}

function buildFhirOrderPreviewPayload(payload) {
  const fhir = payload.fhir || {};
  const resource = {
    resourceType: "ServiceRequest",
    status: fhir.status || "active",
    intent: fhir.intent || "order",
    subject: { reference: selectedOrderPatientReference() || "Patient/<synced-id>" },
    identifier: [
      {
        system: fhir.identifierSystem || "https://healthcare-lab.local/fhir/identifier/service-request",
        value: fhir.identifierValue || "local-order-records-generated",
      },
    ],
    code: fhirConcept(
      fhir.codeDisplay || orderDemoPreset.orderCodeText,
      fhir.codeCode || orderDemoPreset.orderCode,
      fhir.codeSystem || "urn:healthcare-lab:service-code",
      fhir.codeDisplay || orderDemoPreset.orderCodeText,
    ),
  };
  if (fhir.id) resource.id = fhir.id;
  splitFhirList(fhir.identifier).forEach((item) => {
    const [system, value] = item.includes("|") ? item.split("|", 2) : ["", item];
    resource.identifier.push(system ? { system, value } : { value });
  });
  if (fhir.instantiatesCanonical) resource.instantiatesCanonical = splitFhirList(fhir.instantiatesCanonical);
  if (fhir.instantiatesUri) resource.instantiatesUri = splitFhirList(fhir.instantiatesUri);
  ["basedOn", "replaces", "reasonReference", "insurance", "supportingInfo", "specimen", "relevantHistory"].forEach((key) => {
    const references = fhirReferenceList(fhir[key]);
    if (references.length) resource[key] = references;
  });
  if (fhir.requisitionSystem || fhir.requisitionValue) {
    resource.requisition = {};
    if (fhir.requisitionSystem) resource.requisition.system = fhir.requisitionSystem;
    if (fhir.requisitionValue) resource.requisition.value = fhir.requisitionValue;
  }
  if (fhir.category) resource.category = [fhirConcept(fhir.category)];
  if (fhir.priority) resource.priority = fhir.priority;
  resource.doNotPerform = Boolean(fhir.doNotPerform);
  if (fhir.orderDetail) resource.orderDetail = [fhirConcept(fhir.orderDetail)];
  if (fhir.quantityValue || fhir.quantityUnit) {
    resource.quantityQuantity = {};
    if (fhir.quantityValue) resource.quantityQuantity.value = Number(fhir.quantityValue);
    if (fhir.quantityUnit) resource.quantityQuantity.unit = fhir.quantityUnit;
  }
  if (fhir.encounter) resource.encounter = { reference: fhir.encounter };
  if (fhir.occurrenceDateTime) resource.occurrenceDateTime = fhir.occurrenceDateTime;
  if (typeof fhir.asNeededBoolean === "boolean") resource.asNeededBoolean = fhir.asNeededBoolean;
  if (fhir.asNeededCodeText) resource.asNeededCodeableConcept = fhirConcept(fhir.asNeededCodeText);
  if (fhir.authoredOn) resource.authoredOn = fhir.authoredOn;
  if (fhir.requester) resource.requester = fhir.requester.includes("/") ? { reference: fhir.requester } : { display: fhir.requester };
  if (fhir.performerType) resource.performerType = fhirConcept(fhir.performerType);
  const performer = fhirReferenceList(fhir.performer);
  if (performer.length) resource.performer = performer;
  if (fhir.locationCode) resource.locationCode = [fhirConcept(fhir.locationCode)];
  const locationReference = fhirReferenceList(fhir.locationReference);
  if (locationReference.length) resource.locationReference = locationReference;
  if (fhir.reasonCodeText) resource.reasonCode = [fhirConcept(fhir.reasonCodeText)];
  if (fhir.bodySite) resource.bodySite = [fhirConcept(fhir.bodySite)];
  if (fhir.note) resource.note = [{ text: fhir.note }];
  if (fhir.patientInstruction) resource.patientInstruction = fhir.patientInstruction;
  return JSON.stringify(resource, null, 2);
}

function buildOrderPreviewPayload(payload, patient) {
  if (payload.mode === "gdt") return buildGdtOrderPreviewPayload(payload, patient);
  if (payload.mode === "fhir") return buildFhirOrderPreviewPayload(payload, patient);
  if (payload.mode === "dicom") {
    const patientData = patient?.patient || {};
    const summary = patient?.summary || {};
    return JSON.stringify({
      "00100010": { vr: "PN", Value: [{ Alphabetic: [patientData.lastName, patientData.firstName, patientData.middleName].filter(Boolean).join("^") }] },
      "00100020": { vr: "LO", Value: [summary.mrn || ""] },
      "00100021": { vr: "LO", Value: ["local-dcm4chee"] },
      "00100030": { vr: "DA", Value: [summary.dob || ""] },
      "00100040": { vr: "CS", Value: [summary.sex || "U"] },
      "00080050": { vr: "SH", Value: ["ACC-GENERATED"] },
      "0020000D": { vr: "UI", Value: ["UID-GENERATED"] },
      "00401001": { vr: "SH", Value: ["RP-GENERATED"] },
      "00741202": { vr: "LO", Value: [payload.orderCodeText || orderDemoPreset.orderCodeText] },
      "00400100": {
        vr: "SQ",
        Value: [{
          "00400001": { vr: "AE", Value: ["ECG_AP"] },
          "00400009": { vr: "SH", Value: ["SPS-GENERATED"] },
          "00400020": { vr: "CS", Value: ["SCHEDULED"] },
        }],
      },
    }, null, 2);
  }
  const timestamp = hl7Timestamp();
  const requestedAt = payload.requestedAt || timestamp;
  const orderNumber = "ORD-GENERATED";
  const patientData = patient?.patient || {};
  const summary = patient?.summary || {};
  const patientName = [
    patientData.lastName,
    patientData.firstName,
    patientData.middleName,
  ].map(hl7Escape).filter(Boolean).join("^");
  const serviceId = [
    payload.orderCode || orderDemoPreset.orderCode,
    orderDemoPreset.orderCodeText,
    "L",
    payload.alternateCode || orderDemoPreset.alternateCode,
    orderDemoPreset.alternateCodeText,
    orderDemoPreset.alternateCodeSystem,
  ].map(hl7Escape).join("^");
  return [
    `MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|${timestamp}||ORM^O01^ORM_O01|ORMPREVIEW${timestamp}|P|2.5.1||||||UNICODE UTF-8`,
    `PID|1||${hl7Escape(summary.mrn)}^^^HEALTHCARE_LAB^MR||${patientName}||${hl7Escape(summary.dob)}|${hl7Escape(summary.sex)}|||||||||||${hl7Escape(orderAccountNumber(patient))}`,
    `PV1|1|${hl7Escape(patient?.patientClass || "O")}|${hl7EscapeComposite(patient?.assignedLocation || "")}||||${hl7EscapeComposite(payload.orderingProvider)}||||||||||||${hl7Escape(orderVisitId(patient))}`,
    `ORC|NW|${orderNumber}|||||^^^${hl7Escape(requestedAt)}^${hl7Escape(payload.priority)}||${timestamp}|||${hl7EscapeComposite(payload.orderingProvider)}`,
    `OBR|1|${orderNumber}||${serviceId}|${hl7Escape(payload.priority)}|${hl7Escape(requestedAt)}||||||||${hl7Escape(payload.clinicalIndication)}|||${hl7EscapeComposite(payload.orderingProvider)}`,
  ].join("\r");
}

function renderOrderSummary(payload, patient, createdAt = "") {
  const container = byId("order-summary");
  container.replaceChildren();
  if (payload.mode === "fhir") {
    const fhir = payload.fhir || {};
    [
      ["Patient", patient?.summary?.name],
      ["Subject", selectedOrderPatientReference() || fhir.subject],
      ["Resource", "ServiceRequest"],
      ["Status", fhir.status],
      ["Intent", fhir.intent],
      ["Priority", fhir.priority],
      ["Code", `${fhir.codeCode || orderDemoPreset.orderCode} / ${fhir.codeDisplay || orderDemoPreset.orderCodeText}`],
      ["Occurrence", fhir.occurrenceDateTime || "Generated on create"],
      ["Requester", fhir.requester],
      ["Created", createdAt],
    ].forEach(([label, value]) => {
      const item = document.createElement("p");
      item.appendChild(createElement("strong", `${label}: `));
      item.appendChild(document.createTextNode(value || "-"));
      container.appendChild(item);
    });
    return;
  }
  if (payload.mode === "gdt") {
    [
      ["Patient", patient?.summary?.name],
      ["MRN", patient?.summary?.mrn],
      ["GDT Field", "8402"],
      ["Test Type", "EKG01 / 12-lead resting ECG"],
      ["Provider", payload.orderingProvider],
      ["Requested", payload.requestedAt || "Generated on create"],
      ["Created", createdAt],
    ].forEach(([label, value]) => {
      const item = document.createElement("p");
      item.appendChild(createElement("strong", `${label}: `));
      item.appendChild(document.createTextNode(value || "-"));
      container.appendChild(item);
    });
    return;
  }
  if (payload.mode === "dicom") {
    const dcm4chee = payload.dcm4chee || {};
    const mwl = dcm4chee.mwl || {};
    const mapping = mwl.mapping || {};
    const latest = mwl.latest || {};
    const orderId = payload.orderRecordId || mapping.orderRecordId || "";
    const patientId = payload.patientRecordId || patient?.id || "";
    const patientSync = patient?.dcm4chee?.patient || {};
    const patientPreconditionErrorType = mapping.lastErrorType || latest.errorType || mwl.errorType || "";
    const patientPreconditionError = mapping.lastError || latest.error || mwl.error || "";
    container.appendChild(renderDcm4cheeWorkflowStrip(dcm4cheeWorkflowSummary(mwl, mapping, patient, orderId)));
    container.appendChild(renderDcm4cheeOrderActions(orderId, patientId, mwl, mapping));
    [
      ["Patient", patient?.summary?.name],
      ["MRN", patient?.summary?.mrn],
      ["MWL AE", mapping.mwlAETitle || mwl.mwlAETitle || "WORKLIST"],
      ["Station AE", mapping.scheduledStationAETitle || mwl.scheduledStationAETitle || "ECG_AP"],
      ["Code", `${payload.orderCode || orderDemoPreset.orderCode}`],
      ["Requested", payload.requestedAt || "Generated on create"],
      ["Created", createdAt],
    ].forEach(([label, value]) => {
      const item = document.createElement("p");
      item.appendChild(createElement("strong", `${label}: `));
      item.appendChild(document.createTextNode(value || "-"));
      container.appendChild(item);
    });
    if (mwl.status || mapping.status) {
      if (patientSync.status || patientPreconditionErrorType === "patient_sync_failed") {
        container.appendChild(dcm4cheeDetailBlock("Patient Precondition", [
          ["Status", patientSync.displayStatus || patientSync.status || "Patient sync failed"],
          ["Patient ID", patientSync.patientId || mapping.patientId],
          ["Issuer", patientSync.issuerOfPatientId || mapping.issuerOfPatientId],
          ["Retryable", patientSync.retryable === undefined ? "" : (patientSync.retryable ? "Yes" : "No")],
          ["Error Type", patientSync.lastErrorType || patientPreconditionErrorType],
          ["Error", patientSync.lastError || patientPreconditionError],
        ]));
      }
      container.appendChild(dcm4cheeDetailBlock("Sync", [
        ["Status", mwl.displayStatus || mapping.status || mwl.status],
        ["Retryable", mwl.retryable ? "Yes" : "No"],
        ["Retry Count", mapping.retryCount ?? latest.retryCount ?? 0],
        ["Last Sync", mapping.lastSyncAt || latest.lastSyncAt],
        ["HTTP", mapping.lastHttpStatus || latest.httpStatus],
        ["Error Type", mapping.lastErrorType || latest.errorType],
        ["Error", mapping.lastError || latest.error],
      ]));
      const verification = mapping.verification || mwl.verification || {};
      container.appendChild(dcm4cheeDetailBlock("MWL Verification", [
        ["Status", verification.status],
        ["Method", verification.method],
        ["Last Verified", verification.lastVerifiedAt],
        ["Attempt", verification.attemptId],
        ["Error Type", verification.errorType],
        ["Error", verification.error],
      ]));
      container.appendChild(dcm4cheeDetailBlock("Identifiers", [
        ["Study Instance UID", mapping.studyInstanceUid || mwl.studyInstanceUid],
        ["Accession Number", mapping.accessionNumber || mwl.accessionNumber],
        ["Requested Procedure ID", mapping.requestedProcedureId || mwl.requestedProcedureId],
        ["Scheduled Procedure Step ID", mapping.scheduledProcedureStepId || mwl.scheduledProcedureStepId],
        ["Scheduled Station AE Title", mapping.scheduledStationAETitle || mwl.scheduledStationAETitle],
        ["Patient ID", mapping.patientId],
        ["Issuer of Patient ID", mapping.issuerOfPatientId],
      ]));
      const orderResults = dcm4cheeOrderResultRecords(patient, mapping, orderId);
      container.appendChild(dcm4cheeDetailBlock("PACS Result Diagnostics", [
        ["AP C-STORE Result", orderResults.length ? `${orderResults.length} result row(s)` : "No result"],
        ["Reconciliation", dcm4cheeDisplayStatus(summarizeDcm4cheeResultGroup(orderResults))],
        ["Latest Refresh", dcm4cheeFirstValue(orderResults, "lastRefreshedAt")],
        ["Error Type", dcm4cheeFirstValue(orderResults, "reconciliationStatus") === "query_failed" ? "query_failed" : ""],
        ["Diagnostic", orderResults.map((item) => item.diagnostic?.message || item.diagnostic?.error || "").find(Boolean)],
      ]));
      const history = createElement("div", "", "detail-block raw-details");
      history.id = "dcm4chee-attempt-history";
      history.appendChild(createElement("h3", "dcm4chee Attempts"));
      history.appendChild(createElement("p", "Loading attempt history...", "muted"));
      container.appendChild(history);
    }
    return;
  }
  const rows = [
    ["Patient", patient?.summary?.name],
    ["MRN", patient?.summary?.mrn],
    ["Visit", orderVisitId(patient)],
    ["Priority", payload.priority],
    ["Provider", payload.orderingProvider],
    ["Code", `${payload.orderCode || orderDemoPreset.orderCode} / ${payload.alternateCode || orderDemoPreset.alternateCode}`],
    ["Requested", payload.requestedAt || "Generated on create"],
    ["Created", createdAt],
  ];
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
}

function dcm4cheeDetailBlock(title, rows) {
  const block = createElement("div", "", "detail-block");
  block.appendChild(createElement("h3", title));
  const list = createElement("dl", "", "detail-list");
  rows.forEach(([label, value]) => {
    const dt = createElement("dt", label);
    const dd = createElement("dd", value === null || value === undefined || value === "" ? "-" : String(value));
    list.append(dt, dd);
  });
  block.appendChild(list);
  return block;
}

function renderDcm4cheeAttemptHistory(attempts, containerId = "dcm4chee-attempt-history") {
  const container = byId(containerId);
  if (!container) return;
  container.replaceChildren(createElement("h3", "dcm4chee Attempts"));
  if (!attempts.length) {
    container.appendChild(createElement("p", "No dcm4chee attempts recorded.", "muted"));
    return;
  }
  const list = createElement("ol", "", "attempt-list");
  attempts.forEach((attempt) => {
    const item = document.createElement("li");
    const parts = [
      attempt.operationType || "attempt",
      attempt.status || "-",
      attempt.httpStatus ? `HTTP ${attempt.httpStatus}` : "",
      attempt.error || "",
    ].filter(Boolean);
    item.textContent = parts.join(" | ");
    if (attempt.requestUrl || attempt.requestPayload || attempt.responseBody) {
      const details = document.createElement("details");
      const payloadLabel = attempt.operationType === "verify-mwl"
        ? "MWL Query Criteria"
        : "MWL Request Payload";
      details.appendChild(createElement("summary", payloadLabel));
      const body = [
        attempt.requestUrl ? `URL: ${attempt.requestUrl}` : "",
        attempt.requestPayload && Object.keys(attempt.requestPayload).length
          ? `Request:\n${JSON.stringify(attempt.requestPayload, null, 2)}`
          : "",
        attempt.responseBody ? `Response: ${attempt.responseBody}` : "",
      ].filter(Boolean).join("\n");
      details.appendChild(createElement("pre", body, "compact-output"));
      item.appendChild(details);
    }
    list.appendChild(item);
  });
  container.appendChild(list);
}

async function loadDcm4cheeAttemptHistory(orderId, containerId = "dcm4chee-attempt-history") {
  const container = byId(containerId);
  if (!container) return;
  try {
    const result = await requestJson(`/api/orders/${orderId}/dcm4chee-attempts`);
    renderDcm4cheeAttemptHistory(result.items || [], containerId);
  } catch (error) {
    container.replaceChildren(createElement("h3", "dcm4chee Attempts"), createElement("p", error.message, "muted"));
  }
}

function selectedOrderPayloadPreview(item, mode) {
  if (mode !== "dicom") return item.payload || "";
  const mwl = item.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  const payload = mapping.latestRequestPayload || mwl.requestPayload || {};
  return Object.keys(payload).length ? JSON.stringify(payload, null, 2) : "";
}

function selectOrderRecord(item, mode) {
  setSelectedOrderId(item.id);
  setSelectedPatientId(item.patientRecordId || null);
  selectedOrderRecordKey = orderListKey(item);
  const summary = item.summary || {};
  const selectedPatient = patientRecords.find((patient) => Number(patient.id) === Number(item.patientRecordId));
  byId("order-payload-preview").textContent = selectedOrderPayloadPreview(item, mode);
  renderOrderSummary({
    mode,
    orderRecordId: item.id,
    patientRecordId: item.patientRecordId,
    priority: item.priority,
    requestedAt: item.requestedAt,
    orderingProvider: item.orderingProvider,
    orderCode: item.orderCode,
    alternateCode: item.alternateCode,
    fhir: item.fhir?.serviceRequest?.resource || {},
    dcm4chee: item.dcm4chee || {},
  }, {
    id: selectedPatient?.id || item.patientRecordId,
    dcm4chee: selectedPatient?.dcm4chee || {},
    summary: {
      name: selectedPatient?.summary?.name || summary.name,
      mrn: selectedPatient?.summary?.mrn || summary.mrn,
    },
    visitNumber: selectedPatient?.visitNumber || item.visitId,
  }, item.createdAt);
  if (mode === "dicom") loadDcm4cheeAttemptHistory(item.id);
}

function refreshOrderPreview() {
  updateOrderModeFields();
  const payload = orderFormPayload();
  const patient = selectedOrderPatient();
  const messages = validateOrderPayload(payload);
  renderOrderValidation(messages);
  renderOrderSummary(payload, patient);
  byId("order-payload-preview").textContent = messages.length
    ? ORDER_MODE_CONFIG[currentOrderMode()].emptyPreview
    : buildOrderPreviewPayload(payload, patient);
}

function renderOrderRecordList() {
  const body = byId("order-record-list");
  const records = [...orderRecords, ...gdtOrderRecords].sort((left, right) => {
    const rightTime = new Date(right.createdAt || 0).getTime();
    const leftTime = new Date(left.createdAt || 0).getTime();
    return (Number.isNaN(rightTime) ? 0 : rightTime) - (Number.isNaN(leftTime) ? 0 : leftTime);
  });
  body.replaceChildren();
  if (!records.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local orders created yet.");
    cell.colSpan = 8;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  records.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    const rowMode = orderRecordMode(item);
    const orderNumber = rowMode === "gdt" ? item.localGdtOrderNumber : item.localOrderNumber;
    const orderCode = rowMode === "gdt" ? summary.testCode : summary.orderCode;
    const statusLabel = orderStateLabel(item, rowMode);
    const statusClass = statusLabel === "Accepted" ? "success" : "error";
    row.append(
      rowCell(orderNumber || item.id),
      rowCell(orderModeLabel(item, rowMode)),
      rowCell(summary.mrn),
      rowCell(orderVisitNumber(item)),
      rowCell(summary.name),
      rowCell(orderCode),
      rowCell(createElement("span", statusLabel, `status ${statusClass}`)),
      rowCell(taipeiTimestamp(item.createdAt)),
    );
    row.addEventListener("click", () => selectOrderRecord(item, rowMode));
    body.appendChild(row);
  });
}

function orderVisitNumber(item) {
  const summary = item?.summary || {};
  return summary.visitNumber || summary.visitId || item?.visitNumber || item?.visitId || "-";
}

function orderRecordMode(item) {
  if (item.protocolVersion === "FHIR R4") return "fhir";
  if (item.protocolVersion === "GDT 2.1") return "gdt";
  if (item.protocolVersion === "DICOM") return "dicom";
  return "hl7-v251";
}

function orderListKey(item) {
  return `${orderRecordMode(item)}:${item.id}`;
}

function orderModeLabel(item, mode) {
  if (mode === "fhir" || item.protocolVersion === "FHIR R4") return "FHIR";
  if (mode === "gdt" || item.protocolVersion === "GDT 2.1") return "GDT";
  if (mode === "dicom" || item.protocolVersion === "DICOM") return "DICOM";
  return "HL7 v2";
}

function orderStateLabel(item, mode) {
  if (mode === "fhir") {
    const serviceRequest = item.fhir?.serviceRequest || {};
    const serviceRequestReference = serviceRequest.medplum?.reference || "";
    return serviceRequest.sync?.status === "Synced"
      && /^ServiceRequest\/[^/]+$/.test(serviceRequestReference)
      ? "Accepted"
      : "Error";
  }
  if (mode === "dicom") {
    const mwl = item.dcm4chee?.mwl || {};
    const status = mwl.mapping?.status || mwl.status || mwl.displayStatus || "";
    return status === "Created" ? "Accepted" : "Error";
  }
  const status = String(item.status || "").toLowerCase();
  return ["error", "rejected", "transport error"].includes(status) ? "Error" : "Accepted";
}

async function refreshOrders() {
  try {
    const [ordersResult, gdtOrdersResult] = await Promise.all([
      requestJson("/api/orders"),
      requestJson("/api/gdt/orders"),
    ]);
    orderRecords = ordersResult.items || [];
    gdtOrderRecords = gdtOrdersResult.items || [];
    renderOrderRecordList();
    const selected = [...orderRecords, ...gdtOrderRecords].find((item) => orderListKey(item) === selectedOrderRecordKey);
    if (selected) selectOrderRecord(selected, orderRecordMode(selected));
  } catch (error) {
    setStatus("order-form-status", "Refresh failed", "error");
  }
}

async function retryDcm4cheeOrder(orderId, button) {
  if (button) button.disabled = true;
  setStatus("order-form-status", "Retrying dcm4chee sync...", "pending");
  try {
    const result = await requestJsonAllowBusinessFailure(`/api/orders/${orderId}/dcm4chee-sync`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const mwl = result.item?.dcm4chee?.mwl || {};
    setStatus("order-form-status", mwl.displayStatus || "dcm4chee sync updated", result.success ? "success" : "error");
    setSelectedOrderId(orderId);
    await refreshOrders();
    await refreshDcm4cheeConsole();
  } catch (error) {
    setStatus("order-form-status", "Retry failed", "error");
    setStatus("dcm4chee-console-status", error.message, "error");
    byId("order-payload-preview").textContent = error.message;
  } finally {
    if (button) button.disabled = false;
  }
}

async function sendDcm4cheeOrder(orderId, button) {
  if (!orderId) return;
  if (button) button.disabled = true;
  setStatus("dcm4chee-send-status", "Sending...", "pending");
  setStatus("dcm4chee-console-status", "Sending MWL order...", "pending");
  try {
    const result = await requestJsonAllowBusinessFailure(`/api/orders/${orderId}/dcm4chee-sync`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const mwl = result.item?.dcm4chee?.mwl || {};
    setSelectedOrderId(orderId);
    if (result.item?.patientRecordId) setSelectedPatientId(result.item.patientRecordId);
    await refreshDcm4cheeConsole();
    const label = mwl.displayStatus || (result.success ? "Order sent" : "Send failed");
    setStatus("dcm4chee-send-status", label, result.success ? "success" : "error");
  } catch (error) {
    setStatus("dcm4chee-send-status", error.message, "error");
    setStatus("dcm4chee-console-status", error.message, "error");
  } finally {
    if (button) button.disabled = !selectedDcm4cheeOrder();
  }
}

async function verifyDcm4cheeOrder(orderId, button) {
  if (button) button.disabled = true;
  setStatus("order-form-status", "Verifying dcm4chee MWL...", "pending");
  try {
    const result = await requestJsonAllowBusinessFailure(`/api/orders/${orderId}/dcm4chee-mwl-verify`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const verification = result.verification || {};
    const status = verification.status || "MWL verification updated";
    setStatus("order-form-status", status, result.success ? "success" : "error");
    setSelectedOrderId(orderId);
    await refreshOrders();
    await refreshDcm4cheeConsole();
  } catch (error) {
    setStatus("order-form-status", "Verification failed", "error");
    setStatus("dcm4chee-console-status", error.message, "error");
    byId("order-payload-preview").textContent = error.message;
  } finally {
    if (button) button.disabled = false;
  }
}

async function simulateDcm4cheeApReturn(orderId, button, type = "both") {
  if (button) button.disabled = true;
  setStatus("order-form-status", "Recording simulated AP return...", "pending");
  try {
    const result = await requestJson(`/api/orders/${orderId}/dcm4chee-simulated-ap-return`, {
      method: "POST",
      body: JSON.stringify({ type }),
    });
    setStatus("order-form-status", `Simulated AP ${type.toUpperCase()} result recorded`, "success");
    if (result.patient) {
      const index = patientRecords.findIndex((item) => Number(item.id) === Number(result.patient.id));
      if (index >= 0) patientRecords[index] = result.patient;
    }
    await refreshPatients();
    await refreshOrders();
    refreshDcm4cheeConsole();
  } catch (error) {
    setStatus("order-form-status", error.message, "error");
    setStatus("dcm4chee-console-status", error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

async function refreshOrderWorkspace() {
  updateOrderModeFields();
  await refreshPatients();
  await refreshOrders();
  refreshOrderPreview();
}

async function createOrderRecord() {
  const button = byId("create-order");
  button.disabled = true;
  setStatus("order-form-status", "Creating...", "pending");
  try {
    const mode = currentOrderMode();
    const result = await requestJson(mode === "gdt" ? "/api/gdt/orders" : "/api/orders", {
      method: "POST",
      body: JSON.stringify(orderFormPayload()),
    });
    const item = result.item;
    setStatus(
      "order-form-status",
      mode === "gdt"
        ? "GDT ECG order created"
        : mode === "fhir"
          ? "FHIR order created"
          : mode === "dicom"
            ? "DICOM MWL order created"
            : "Local order created",
      "success",
    );
    byId("order-payload-preview").textContent = item.payload || "";
    await refreshOrders();
  } catch (error) {
    setStatus("order-form-status", "Create failed", "error");
    byId("order-payload-preview").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function gdtPatientFormPayload() {
  return {
    mode: "gdt",
    mrn: byId("gdt-patient-mrn").value.trim(),
    firstName: byId("gdt-patient-first-name").value.trim(),
    lastName: byId("gdt-patient-last-name").value.trim(),
    dob: byId("gdt-patient-dob").value.trim(),
    sex: byId("gdt-patient-sex").value,
  };
}

async function createGdtPatientFromOrderFlow() {
  const button = byId("create-gdt-patient");
  button.disabled = true;
  setStatus("order-form-status", "Creating patient...", "pending");
  try {
    const result = await createPatient(gdtPatientFormPayload());
    await refreshPatients();
    byId("order-patient").value = String(result.item.id);
    setStatus("order-form-status", "Patient ready for GDT order", "success");
    refreshOrderPreview();
  } catch (error) {
    setStatus("order-form-status", "Patient create failed", "error");
    byId("order-payload-preview").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function renderOieInventory() {
  return renderOieView();
}

function selectedGdtPatient() {
  return selectedGdtPatientFromView();
}

async function copyTextFromElement(elementId) {
  return copyElementText(elementId);
}

const initializeApplication = () => {
  registerViewActivation("lab-console-view", "Service Health", refreshDashboard);
  registerViewActivation("patient-view", "Patient", () => {
    refreshPatientPreview();
    return refreshPatients();
  });
  registerViewActivation("medplum-view", "Medplum", refreshMedplumInventory);
  registerViewActivation("order-view", "Order", refreshOrderWorkspace);
  registerViewActivation("dcm4chee-view", "dcm4chee", refreshDcm4cheeConsole);
  registerViewActivation("oie-view", "OIE", refreshOieInventory);
  registerViewActivation("gdt-view", "GDT", refreshGdtConsole);
  initializeNavigation();
  initializeDashboardView();
  initializeOieView();
  initializeGdtView({ buildPatientPreviewPayload: buildPatientGdtPreviewPayload });
  initializeFhirView();
  byId("load-patient-demo").addEventListener("click", () => {
    setPatientForm(patientDemoPresetForMode(byId("patient-mode").value));
    refreshPatientPreview();
  });
  byId("load-order-demo").addEventListener("click", () => {
    setOrderForm(orderDemoPreset);
    refreshOrderPreview();
  });
  document.querySelectorAll("#patient-view input, #patient-view select").forEach((element) => {
    element.addEventListener("input", refreshPatientPreview);
    element.addEventListener("change", refreshPatientPreview);
  });
  document.querySelectorAll("#order-view input, #order-view select").forEach((element) => {
    element.addEventListener("input", refreshOrderPreview);
    element.addEventListener("change", refreshOrderPreview);
  });
  byId("refresh-patient-preview").addEventListener("click", refreshPatientPreview);
  byId("create-patient").addEventListener("click", createPatientRecord);
  byId("refresh-patients").addEventListener("click", refreshPatients);
  byId("copy-patient-payload").addEventListener("click", () => copyTextFromElement("patient-payload-preview"));
  byId("refresh-order-preview").addEventListener("click", refreshOrderPreview);
  byId("create-gdt-patient").addEventListener("click", createGdtPatientFromOrderFlow);
  byId("create-order").addEventListener("click", createOrderRecord);
  byId("refresh-orders").addEventListener("click", refreshOrders);
  byId("copy-order-payload").addEventListener("click", () => copyTextFromElement("order-payload-preview"));
  byId("refresh-dcm4chee-console").addEventListener("click", refreshDcm4cheeConsole);
  byId("dcm4chee-patient-select").addEventListener("change", (event) => {
    if (event.target.value) selectDcm4cheePatient(Number(event.target.value));
  });
  byId("dcm4chee-order-select").addEventListener("change", (event) => {
    if (event.target.value) selectDcm4cheeOrder(Number(event.target.value));
  });
  byId("copy-dcm4chee-payload").addEventListener("click", () => copyTextFromElement("dcm4chee-payload-preview"));
  byId("send-dcm4chee-order").addEventListener("click", (event) => {
    if (getSelectedOrderId()) sendDcm4cheeOrder(getSelectedOrderId(), event.currentTarget);
  });
  byId("create-gdt-ecg-order").addEventListener("click", openGdtOrderFlow);
  setActiveView("lab-console-view");
};

document.addEventListener("DOMContentLoaded", initializeApplication);
