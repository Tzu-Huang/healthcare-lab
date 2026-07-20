import { setStatus } from "./js/components/status.js";
import { copyTextFromElement as copyElementText } from "./js/core/clipboard.js";
import { byId, createElement, rowCell } from "./js/core/dom.js";
import { fhirBirthDate as formatFhirBirthDate, fhirGender as formatFhirGender, gdtTaipeiTimestamp as formatGdtTaipeiTimestamp, hl7Escape as formatHl7Escape, hl7EscapeComposite as formatHl7EscapeComposite, hl7Timestamp as formatHl7Timestamp, localDatetimeValue as formatLocalDatetimeValue, pad as formatPad, taipeiTimestamp as formatTaipeiTimestamp } from "./js/core/formatting.js";
import { activateView, initializeNavigation, registerViewActivation } from "./js/core/navigation.js";
import { initializeOieView, refreshOieInventory, renderOieInventory as renderOieView } from "./js/views/oie.js";
import { initializeDashboardView, refreshDashboard, statusClass as dashboardStatusClass } from "./js/views/dashboard.js";
import { initializeGdtView, refreshGdtConsole, selectedGdtPatient as selectedGdtPatientFromView } from "./js/views/gdt.js";
import { initializeFhirView, refreshMedplumInventory } from "./js/views/fhir.js";
import { configureDcm4cheeCoordinator, dcm4cheeDetailBlock, dcm4cheeDisplayStatus, dcm4cheeFirstValue, dcm4cheeOrderResultRecords, dcm4cheeWorkflowSummary, initializeDcm4cheeView, loadDcm4cheeAttemptHistory, refreshDcm4cheeConsole, renderDcm4cheeConsole, renderDcm4cheeOrderActions, renderDcm4cheeWorkflowStrip, renderPatientDcm4cheeResults, selectedDcm4cheeOrder, summarizeDcm4cheeResultGroup } from "./js/views/dcm4chee.js";
import { setSelectedOrderId, setSelectedPatientId } from "./js/state/selection.js";
import { getPatientRecords } from "./js/state/patient.js";
import { setSelectedOrderRecordKey } from "./js/state/order.js";
import { createPatient } from "./js/api/patient.js";
import { buildPatientGdtPreviewPayload, configurePatientCoordinator, createPatientRecord, initializePatientView, patientPreviewMrn, refreshPatientDcm4cheeResults, refreshPatientPreview, refreshPatients, renderPatientSummaryFromPayload, retryPatientFhirSync } from "./js/views/patient.js";
import { configureOrderCoordinator, createOrderRecord, currentOrderMode, initializeOrderView, orderListKey, orderRecordMode, orderVisitId, refreshOrderPreview, refreshOrders, refreshOrderWorkspace, renderOrderPatientOptions, renderOrderRecordList, retryDcm4cheeOrder, selectedOrderPatientReference, sendDcm4cheeOrder, simulateDcm4cheeApReturn, updateOrderModeFields, verifyDcm4cheeOrder } from "./js/views/order.js";

function setActiveView(viewId) {
  return activateView(viewId);
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

function renderPatientSummaryFromRecord(item) {
  renderPatientSummaryFromPayload({
    ...(item.patient || {}),
    visitNumber: item.visitNumber,
    patientClass: item.patientClass,
    assignedLocation: item.assignedLocation,
  }, item.createdAt, item.dcm4chee?.patient || null, { renderDetailBlock: dcm4cheeDetailBlock });
  renderPatientDcm4cheeResults(byId("patient-summary"), item);
}

function fhirSyncStatusClass(status) {
  return {
    "Synced": "success",
    "Sync failed": "error",
    "Syncing": "pending",
    "Pending sync": "pending",
  }[status] || "neutral";
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
  setSelectedOrderRecordKey(orderListKey(item));
  const summary = item.summary || {};
  const selectedPatient = getPatientRecords().find((patient) => Number(patient.id) === Number(item.patientRecordId));
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
  configureDcm4cheeCoordinator({
    refreshPatientDcm4cheeResults,
    retryDcm4cheeOrder,
    sendDcm4cheeOrder,
    simulateDcm4cheeApReturn,
    verifyDcm4cheeOrder,
  });
  initializeDcm4cheeView();
  configurePatientCoordinator({
    onSelectRecord: (item) => {
      byId("patient-payload-preview").textContent = item.payload || "";
      renderPatientSummaryFromRecord(item);
    },
    renderOrderPatientOptions,
    renderDetailBlock: dcm4cheeDetailBlock,
    renderDcm4cheeConsole,
    refreshOrders,
  });
  initializePatientView({
    onCreate: createPatientRecord,
    onRefresh: refreshPatients,
    onCopy: () => copyTextFromElement("patient-payload-preview"),
  });
  configureOrderCoordinator({
    renderSummary: renderOrderSummary,
    selectRecord: selectOrderRecord,
    refreshPatients,
    refreshDcm4cheeConsole,
    selectedDcm4cheeOrder,
  });
  initializeOrderView({
    onCreate: createOrderRecord,
    onRefresh: refreshOrders,
    onCopy: () => copyTextFromElement("order-payload-preview"),
    onCreateGdtPatient: createGdtPatientFromOrderFlow,
  });
  byId("create-gdt-ecg-order").addEventListener("click", openGdtOrderFlow);
  setActiveView("lab-console-view");
};

document.addEventListener("DOMContentLoaded", initializeApplication);
