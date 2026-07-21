import { copyTextFromElement } from "../core/clipboard.js";
import { byId, createElement, rowCell } from "../core/dom.js";
import { taipeiTimestamp } from "../core/formatting.js";
import { setStatus } from "../components/status.js";
import { fetchDcm4cheeAttempts, fetchDcm4cheeProfileDiagnostics } from "../api/dcm4chee.js";
import { fetchOrders } from "../api/order.js";
import { fetchPatients } from "../api/patient.js";
import { getDcm4cheeProfileDiagnostics, isDcm4cheePatientExpanded, setDcm4cheeProfileDiagnostics, toggleDcm4cheePatientExpanded } from "../state/dcm4chee.js";
import { getOrderRecords, setOrderRecords } from "../state/order.js";
import { getPatientRecords, setPatientRecords } from "../state/patient.js";
import { getSelectedOrderId, getSelectedPatientId, setSelectedOrderId, setSelectedPatientId } from "../state/selection.js";

let dcm4cheeCoordinator = {};
let initialized = false;

export function configureDcm4cheeCoordinator(options = {}) {
  dcm4cheeCoordinator = { ...dcm4cheeCoordinator, ...options };
}

export function initializeDcm4cheeView() {
  if (initialized) return;
  initialized = true;
  byId("refresh-dcm4chee-console")?.addEventListener("click", refreshDcm4cheeConsole);
  byId("dcm4chee-patient-select")?.addEventListener("change", (event) => {
    if (event.target.value) selectDcm4cheePatient(Number(event.target.value));
  });
  byId("dcm4chee-order-select")?.addEventListener("change", (event) => {
    if (event.target.value) selectDcm4cheeOrder(Number(event.target.value));
  });
  byId("copy-dcm4chee-payload")?.addEventListener("click", () => copyTextFromElement("dcm4chee-payload-preview"));
  byId("send-dcm4chee-order")?.addEventListener("click", (event) => {
    if (getSelectedOrderId()) dcm4cheeCoordinator.sendDcm4cheeOrder?.(getSelectedOrderId(), event.currentTarget);
  });
}

export function dcm4cheeResultStatusClass(status) {
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

export function dcm4cheeDisplayStatus(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()) || "-";
}

export function dcm4cheeWorkflowStatusClass(status) {
  const normalized = String(status || "").toLowerCase().replaceAll("_", " ");
  if (["created", "synced", "verified", "matched"].includes(normalized)) return "success";
  if (["pending", "pending sync", "not verified", "ambiguous", "duplicate", "unlinked"].includes(normalized)) return "warning";
  if (normalized.includes("failed") || normalized.includes("wrong patient") || normalized.includes("missing")) return "error";
  return dcm4cheeResultStatusClass(status);
}

export function dcm4cheeCopyButton(label, value) {
  if (!value) return null;
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    navigator.clipboard.writeText(value);
  });
  return button;
}

export function dcm4cheeOpenButton(label, url) {
  if (!url) return null;
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    window.open(url, "_blank", "noopener");
  });
  return button;
}

export function dcm4cheeActionsForResult(item, level = "study") {
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

export function dcm4cheeResultKey(item, fields, fallback) {
  const key = fields.map((field) => String(item?.[field] || "").trim()).find(Boolean);
  return key || fallback;
}

export function summarizeDcm4cheeResultGroup(records) {
  const statuses = records.map((item) => item.reconciliationStatus).filter(Boolean);
  if (statuses.includes("matched")) return "matched";
  if (statuses.includes("query_failed")) return "query_failed";
  if (statuses.includes("wrong_patient")) return "wrong_patient";
  if (statuses.includes("ambiguous")) return "ambiguous";
  if (statuses.includes("duplicate")) return "duplicate";
  if (statuses.includes("unlinked")) return "unlinked";
  return statuses[0] || "no_result";
}

export function groupDcm4cheeResultsForBrowser(results = []) {
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

export function dcm4cheeFirstValue(records, field) {
  return records.map((item) => item?.[field]).find((value) => value !== null && value !== undefined && value !== "") || "";
}

export function dcm4cheeFirstArtifact(records) {
  return records
    .map((item) => item?.artifact)
    .find((artifact) => (
      artifact
      && typeof artifact === "object"
      && (artifact.label || artifact.mediaType || artifact.url || artifact.path || artifact.role)
    )) || {};
}

export function renderDcm4cheeResultTable(headers, rows, className = "") {
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

export function renderDcm4cheeInstanceTable(records) {
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

export function renderDcm4cheeSeriesDetails(series) {
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

export function renderDcm4cheeStudyDetails(study) {
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

export function renderDcm4cheeResultGroup(group) {
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

export function renderPatientDcm4cheeResults(container, patient) {
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

export function renderDcm4cheeResultsBrowser(container, results = [], emptyText = "No refreshed dcm4chee results.") {
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

export function dcm4cheeConsolePatients() {
  const patientIdsWithDicomOrders = new Set(
    getOrderRecords()
      .filter((item) => item.protocolVersion === "DICOM" && item.patientRecordId)
      .map((item) => Number(item.patientRecordId)),
  );
  return getPatientRecords().filter((item) => (
    item.protocolVersion === "DICOM"
    || item.dcm4chee?.patient
    || patientIdsWithDicomOrders.has(Number(item.id))
  ));
}

export function dcm4cheeConsoleOrders(patientId = getSelectedPatientId()) {
  return getOrderRecords().filter((item) => (
    item.protocolVersion === "DICOM"
    && (!patientId || Number(item.patientRecordId) === Number(patientId))
  ));
}

export function selectedDcm4cheePatient() {
  const selectedId = Number(getSelectedPatientId() || 0);
  return dcm4cheeConsolePatients().find((item) => Number(item.id) === selectedId) || null;
}

export function selectedDcm4cheeOrder() {
  const selectedId = Number(getSelectedOrderId() || 0);
  return getOrderRecords().find((item) => item.protocolVersion === "DICOM" && Number(item.id) === selectedId) || null;
}

export function dcm4cheePatientLabel(patient) {
  return patient?.summary?.name || patient?.summary?.mrn || `Patient ${patient?.id}`;
}

export function dcm4cheeOrderLabel(order) {
  return order?.localOrderNumber || `Order ${order?.id}`;
}

export function dcm4cheeOrderPatient(order) {
  return getPatientRecords().find((patient) => Number(patient.id) === Number(order?.patientRecordId)) || null;
}

export function dcm4cheeOrderStatus(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  return mwl.displayStatus || mapping.status || mwl.status || order?.status || "Not synced";
}

export function dcm4cheeOrderVerificationStatus(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  const verification = mapping.verification || mwl.verification || {};
  return verification.status || "Not verified";
}

export function dcm4cheeOrderActionButtons(order) {
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
    dcm4cheeCoordinator.sendDcm4cheeOrder?.(order.id, sendButton);
  });
  actions.appendChild(sendButton);
  if (mwl.retryable) {
    const retryButton = createElement("button", "Retry", "small-button");
    retryButton.type = "button";
    retryButton.addEventListener("click", (event) => {
      event.stopPropagation();
      dcm4cheeCoordinator.retryDcm4cheeOrder?.(order.id, retryButton);
    });
    actions.appendChild(retryButton);
  }
  if (mapping.id) {
    const verifyButton = createElement("button", "Verify", "small-button");
    verifyButton.type = "button";
    verifyButton.addEventListener("click", (event) => {
      event.stopPropagation();
      dcm4cheeCoordinator.verifyDcm4cheeOrder?.(order.id, verifyButton);
    });
    actions.appendChild(verifyButton);
  }
  return actions;
}

export function selectDcm4cheePatient(patientId) {
  setSelectedPatientId(patientId);
  const patientOrders = dcm4cheeConsoleOrders(patientId);
  if (!patientOrders.some((item) => Number(item.id) === Number(getSelectedOrderId()))) {
    setSelectedOrderId(patientOrders[0]?.id || null);
  }
  renderDcm4cheeConsole();
}

export function selectDcm4cheeOrder(orderId) {
  setSelectedOrderId(orderId);
  const order = selectedDcm4cheeOrder();
  if (order?.patientRecordId) setSelectedPatientId(order.patientRecordId);
  renderDcm4cheeConsole();
  if (orderId) loadDcm4cheeAttemptHistory(orderId, "dcm4chee-console-attempt-history");
}

export function ensureDcm4cheeSelection() {
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

export function renderDcm4cheeSelectors() {
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

export function dcm4cheeOrderPreviewPayload(order) {
  const mwl = order?.dcm4chee?.mwl || {};
  const mapping = mwl.mapping || {};
  return mapping.latestRequestPayload || mwl.requestPayload || mwl.latest?.requestPayload || null;
}

export function renderDcm4cheePreview() {
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

export function dcm4cheeNestedTable(headers) {
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

export function renderDcm4cheeExpandedOrders(orders) {
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

export function dcm4cheePatientSection(label, title, body) {
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

export function renderDcm4cheeExpandedResults(patient) {
  const container = document.createElement("div");
  renderDcm4cheeResultsBrowser(
    container,
    patient.dcm4chee?.dicomResults || [],
    "No refreshed dcm4chee results for this patient.",
  );
  return container;
}

export function renderDcm4cheePatientList() {
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
      dcm4cheeCoordinator.refreshPatientDcm4cheeResults?.(patient.id, refreshButton);
    });
    actions.appendChild(refreshButton);
    const row = document.createElement("tr");
    row.className = Number(patient.id) === Number(getSelectedPatientId()) ? "selected-row" : "";
    const toggleButton = createElement("button", "V", "dcm4chee-patient-toggle");
    toggleButton.type = "button";
    toggleButton.classList.toggle("expanded", isDcm4cheePatientExpanded(patientId));
    toggleButton.setAttribute("aria-expanded", String(isDcm4cheePatientExpanded(patientId)));
    toggleButton.setAttribute(
      "aria-label",
      isDcm4cheePatientExpanded(patientId) ? "Collapse patient orders and results" : "Expand patient orders and results",
    );
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleDcm4cheePatientExpanded(patientId);
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

    if (isDcm4cheePatientExpanded(patientId)) {
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

export function renderDcm4cheeSelectedPatient() {
  const patient = selectedDcm4cheePatient();
  const title = byId("dcm4chee-selected-patient-title");
  const container = byId("dcm4chee-selected-patient-summary");
  const refreshButton = byId("dcm4chee-refresh-results");
  if (!title || !container || !refreshButton) return;
  title.textContent = patient ? dcm4cheePatientLabel(patient) : "No patient selected";
  refreshButton.disabled = !patient;
  refreshButton.onclick = () => {
    if (patient) dcm4cheeCoordinator.refreshPatientDcm4cheeResults?.(patient.id, refreshButton);
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
    ["DICOM Patient ID", sync.patientId],
    ["Patient ID Issuer", sync.issuerOfPatientId],
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

export function renderDcm4cheeSelectedOrder() {
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

export function renderDcm4cheeProfileSummary() {
  const container = byId("dcm4chee-profile-summary");
  if (!container) return;
  container.replaceChildren();
  const diagnostics = getDcm4cheeProfileDiagnostics();
  if (!diagnostics) {
    container.appendChild(createElement("p", "Profile diagnostics are not loaded.", "muted"));
    return;
  }
  container.appendChild(dcm4cheeDetailBlock("Profile", [
    ["Profile", diagnostics.profileName],
    ["Status", diagnostics.valid ? "Valid" : "Needs attention"],
    ["Summary", diagnostics.summary],
  ]));
  const checks = diagnostics.checks || [];
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

export function renderDcm4cheeConsole() {
  ensureDcm4cheeSelection();
  renderDcm4cheeSelectors();
  renderDcm4cheePatientList();
  renderDcm4cheeSelectedPatient();
  renderDcm4cheeSelectedOrder();
  renderDcm4cheePreview();
  renderDcm4cheeProfileSummary();
}

export async function refreshDcm4cheeConsole() {
  setStatus("dcm4chee-console-status", "Refreshing...", "pending");
  try {
    const [patientsResult, ordersResult, diagnosticsResult] = await Promise.all([
      fetchPatients("DICOM"),
      fetchOrders(),
      fetchDcm4cheeProfileDiagnostics(),
    ]);
    setPatientRecords(patientsResult.items || []);
    setOrderRecords(ordersResult.items || []);
    setDcm4cheeProfileDiagnostics(diagnosticsResult);
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


export function dcm4cheeOrderResultRecords(patient, mapping = {}, orderId = "") {
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

export function dcm4cheeWorkflowSummary(mwl = {}, mapping = {}, patient = null, orderId = "") {
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

export function renderDcm4cheeWorkflowStrip(items) {
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

export function renderDcm4cheeOrderActions(orderId, patientId, mwl = {}, mapping = {}) {
  const actions = createElement("div", "", "dcm4chee-order-actions full-width");
  if (!orderId && !patientId) return actions;
  if (mwl.retryable && orderId) {
    const retryButton = createElement("button", "Retry MWL Sync", "small-button");
    retryButton.type = "button";
    retryButton.addEventListener("click", () => dcm4cheeCoordinator.retryDcm4cheeOrder?.(orderId, retryButton));
    actions.appendChild(retryButton);
  }
  if (mapping.id && orderId) {
    const verifyButton = createElement("button", "Verify MWL Query", "small-button");
    verifyButton.type = "button";
    verifyButton.addEventListener("click", () => dcm4cheeCoordinator.verifyDcm4cheeOrder?.(orderId, verifyButton));
    actions.appendChild(verifyButton);
  }
  if (patientId) {
    const refreshButton = createElement("button", "Refresh PACS Results", "small-button");
    refreshButton.type = "button";
    refreshButton.addEventListener("click", () => dcm4cheeCoordinator.refreshPatientDcm4cheeResults?.(patientId, refreshButton, { orderId }));
    actions.appendChild(refreshButton);
  }
  if (orderId) {
    const simulatePdfButton = createElement("button", "Simulate AP PDF", "small-button");
    simulatePdfButton.type = "button";
    simulatePdfButton.addEventListener("click", () => dcm4cheeCoordinator.simulateDcm4cheeApReturn?.(orderId, simulatePdfButton, "pdf"));
    actions.appendChild(simulatePdfButton);

    const simulateDicomButton = createElement("button", "Simulate AP DICOM", "small-button");
    simulateDicomButton.type = "button";
    simulateDicomButton.addEventListener("click", () => dcm4cheeCoordinator.simulateDcm4cheeApReturn?.(orderId, simulateDicomButton, "dicom"));
    actions.appendChild(simulateDicomButton);
  }
  if (!actions.childElementCount) actions.appendChild(createElement("span", "No DICOM actions available yet.", "muted"));
  return actions;
}

export function dcm4cheeDetailBlock(title, rows) {
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

export function renderDcm4cheeAttemptHistory(attempts, containerId = "dcm4chee-attempt-history") {
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

export async function loadDcm4cheeAttemptHistory(orderId, containerId = "dcm4chee-attempt-history") {
  const container = byId(containerId);
  if (!container) return;
  try {
    const result = await fetchDcm4cheeAttempts(orderId);
    renderDcm4cheeAttemptHistory(result.items || [], containerId);
  } catch (error) {
    container.replaceChildren(createElement("h3", "dcm4chee Attempts"), createElement("p", error.message, "muted"));
  }
}
