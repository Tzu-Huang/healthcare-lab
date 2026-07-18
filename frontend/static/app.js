import { requestJson, requestJsonAllowBusinessFailure } from "./js/api/client.js";
import { setStatus } from "./js/components/status.js";
import { copyTextFromElement as copyElementText } from "./js/core/clipboard.js";
import { createElement, rowCell } from "./js/core/dom.js";
import { fhirBirthDate as formatFhirBirthDate, fhirGender as formatFhirGender, gdtTaipeiTimestamp as formatGdtTaipeiTimestamp, hl7Escape as formatHl7Escape, hl7EscapeComposite as formatHl7EscapeComposite, hl7Timestamp as formatHl7Timestamp, localDatetimeValue as formatLocalDatetimeValue, pad as formatPad, taipeiTimestamp as formatTaipeiTimestamp } from "./js/core/formatting.js";
import { activateView, initializeNavigation, registerViewActivation } from "./js/core/navigation.js";

const byId = (id) => document.getElementById(id);

let dashboardServices = [];
let dashboardEvents = [];
let dashboardResources = null;
let expandedDashboardServiceIds = new Set();
let patientRecords = [];
let orderRecords = [];
let gdtOrderRecords = [];
let selectedOrderRecordId = null;
let selectedOrderRecordKey = "";
let dcm4cheeProfileDiagnostics = null;
let selectedDcm4cheePatientId = null;
let selectedDcm4cheeOrderId = null;
let expandedDcm4cheePatientIds = new Set();
let gdtWorkbench = { patients: [], bridgeInbox: [] };
let gdtBridgeConfig = null;
let selectedGdtPatientId = null;
let expandedGdtPatientIds = new Set();
let selectedGdtPayload = "";
let selectedGdtPatientRawPreview = { patientId: null, payload: "" };
let oieInventory = [];
let oieUnmatchedResults = [];
let selectedOiePatientId = null;
let selectedOieOrderId = null;
let expandedOiePatientIds = new Set();
let selectedOiePayload = "";
let medplumInventory = [];
let medplumPatients = [];
let medplumResourceTypes = [];
let selectedMedplumRecordId = null;
let selectedMedplumPatientId = null;
let expandedMedplumPatientIds = new Set();
let selectedMedplumLiveReportReference = "";
let selectedMedplumLiveRelatedReference = "";
let medplumDiagnosticReports = {
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
  requestId: 0,
};

const VIEW_TITLES = {
  "lab-console-view": "Service Health",
  "patient-view": "Patient",
  "medplum-view": "Medplum",
  "order-view": "Order",
  "dcm4chee-view": "dcm4chee",
  "oie-view": "OIE",
  "gdt-view": "GDT",
};

const MEDPLUM_SOURCE_LABELS = {
  "medplum-live": "Medplum live JSON",
  "local-submitted": "Local submitted JSON",
  "local-submitted-fallback": "Live fetch failed; local submitted JSON",
  "medplum-live-fetch-failed": "Live Medplum fetch failed",
};

const DASHBOARD_RESOURCE_CONTAINERS = [
  { displayName: "oie-1", aliases: ["oie-1", "oie"] },
  { displayName: "medplum-1", aliases: ["medplum-1", "medplum"] },
  { displayName: "dcm4chee-1", aliases: ["dcm4chee-1", "dcm4chee"] },
];

const PATIENT_MODE_CONFIG = {
  "hl7-v2": {
    title: "HL7 v2.5.1 ADT A04",
    payloadTitle: "MSH, EVN, PID, PV1",
    emptyPreview: "Complete required Patient fields to preview an HL7 v2.5.1 ADT A04 payload.",
  },
  fhir: {
    title: "FHIR R4 Patient",
    payloadTitle: "Patient resource JSON",
    emptyPreview: "Complete required Patient fields to preview a FHIR R4 Patient resource.",
  },
  gdt: {
    title: "GDT 2.1 Patient Record",
    payloadTitle: "GDT 6301 patient fields",
    emptyPreview: "Complete required Patient fields to preview a GDT 2.1 patient record.",
  },
  dicom: {
    title: "DICOM Patient Module",
    payloadTitle: "Patient Module attributes",
    emptyPreview: "Complete required Patient fields to preview DICOM Patient Module attributes.",
  },
};

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
  return {
    Healthy: "success",
    Degraded: "warning",
    Down: "error",
    Unknown: "neutral",
  }[status] || "neutral";
}

function renderSummary(summary = {}) {
  byId("dashboard-total-count").textContent = summary.total ?? 0;
  byId("dashboard-running-count").textContent = summary.running ?? 0;
  byId("dashboard-attention-count").textContent = summary.attention ?? 0;
  byId("dashboard-cpu-total").textContent = `${summary.cpuPercent ?? 0}%`;
  byId("dashboard-memory-total").textContent = `${summary.memoryPercent ?? 0}%`;
}

function replaceDashboardService(service) {
  if (!service?.id) return;
  const index = dashboardServices.findIndex((item) => item.id === service.id);
  if (index >= 0) {
    dashboardServices[index] = service;
  } else {
    dashboardServices.push(service);
  }
  renderServices();
}

function applyDashboardPayload(result) {
  if (result.items) dashboardServices = result.items;
  if (result.events) dashboardEvents = result.events;
  if (result.resources) dashboardResources = result.resources;
  if (result.summary) renderSummary(result.summary);
  renderServices();
  renderResources();
  renderEvents();
}

function actionButton(service, action, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = !service.capabilities?.[action];
  button.addEventListener("click", () => runServiceAction(service.id, action));
  return button;
}

function childActionButton(service, child, action, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = !child.capabilities?.[action];
  button.addEventListener("click", () => runChildServiceAction(service.id, child.id, action));
  return button;
}

function dashboardServiceToggle(service) {
  const button = document.createElement("button");
  const expanded = expandedDashboardServiceIds.has(service.id);
  button.type = "button";
  button.className = "dashboard-service-toggle";
  button.textContent = expanded ? "▾" : "▸";
  button.setAttribute("aria-expanded", String(expanded));
  button.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${service.label} sub-services`);
  button.addEventListener("click", () => {
    if (expanded) {
      expandedDashboardServiceIds.delete(service.id);
    } else {
      expandedDashboardServiceIds.add(service.id);
    }
    renderServices();
  });
  return button;
}

function renderDashboardChild(service, child, body) {
  const row = document.createElement("tr");
  row.className = "dashboard-child-row";

  const serviceCell = document.createElement("td");
  const identity = createElement("div", "", "dashboard-child-identity");
  identity.append(
    createElement("strong", child.name),
    createElement("span", child.role, "muted dashboard-cell-subtext"),
  );
  serviceCell.appendChild(identity);
  row.appendChild(serviceCell);

  row.appendChild(rowCell(createElement("span", child.runtime?.state || child.status, `status ${statusClass(child.status)}`)));

  const checks = document.createElement("div");
  checks.className = "dashboard-checks";
  checks.appendChild(createElement("span", child.runtime?.detail || "Docker runtime state unavailable"));
  row.appendChild(rowCell(checks));

  const actions = document.createElement("div");
  actions.className = "button-row compact-actions";
  actions.append(
    childActionButton(service, child, "check", "Check"),
    childActionButton(service, child, "enable", "Start"),
    childActionButton(service, child, "disable", "Stop"),
    childActionButton(service, child, "restart", "Restart"),
  );
  row.appendChild(rowCell(actions));
  body.appendChild(row);
}

function renderServices() {
  const body = byId("dashboard-service-list");
  const filter = byId("dashboard-filter").value.trim().toLowerCase();
  body.replaceChildren();
  const visible = dashboardServices.filter((service) => {
    const childNames = (service.children || []).map((child) => child.name).join(" ");
    const haystack = `${service.label} ${service.protocol} ${service.backend} ${childNames}`.toLowerCase();
    return !filter || haystack.includes(filter);
  });
  if (!visible.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No services match the current filter.");
    cell.colSpan = 4;
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  visible.forEach((service) => {
    const row = document.createElement("tr");
    row.className = "dashboard-primary-row";
    const serviceCell = document.createElement("td");
    const identity = createElement("div", "", "dashboard-primary-identity");
    if (service.children?.length) identity.appendChild(dashboardServiceToggle(service));
    const text = createElement("div");
    text.appendChild(createElement("strong", service.label));
    text.appendChild(createElement("span", service.protocol, "muted dashboard-cell-subtext"));
    identity.appendChild(text);
    serviceCell.appendChild(identity);
    row.appendChild(serviceCell);

    const status = createElement("span", service.status, `status ${statusClass(service.status)}`);
    row.appendChild(rowCell(status));

    const checks = document.createElement("div");
    checks.className = "dashboard-checks";
    ["process", "application", "protocol"].forEach((key) => {
      checks.appendChild(createElement("span", `${key}: ${service.checks?.[key] || "Unknown"}`));
    });
    row.appendChild(rowCell(checks));

    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(actionButton(service, "check", "Check"));
    actions.appendChild(actionButton(service, "enable", "Start"));
    actions.appendChild(actionButton(service, "disable", "Stop"));
    actions.appendChild(actionButton(service, "restart", "Restart"));
    row.appendChild(rowCell(actions));
    body.appendChild(row);
    if (expandedDashboardServiceIds.has(service.id)) {
      (service.children || []).forEach((child) => renderDashboardChild(service, child, body));
    }
  });
}

function renderResources() {
  const container = byId("dashboard-resource-usage");
  container.replaceChildren();
  if (!dashboardResources || dashboardResources.status !== "ok") {
    container.appendChild(createElement("p", dashboardResources?.message || "Docker stats unavailable.", "muted"));
    return;
  }
  const visibleContainers = DASHBOARD_RESOURCE_CONTAINERS.map((target) => {
    const stats = dashboardResources.containers.find((item) => {
      const normalizedName = String(item.name || "").replaceAll("_", "-").toLowerCase();
      return target.aliases.some((alias) => (
        normalizedName === alias || normalizedName.endsWith(`-${alias}`)
      ));
    });
    return stats ? { ...stats, displayName: target.displayName } : {
      displayName: target.displayName,
      cpuPercent: null,
      memoryUsedMiB: null,
      memoryLimitMiB: null,
    };
  });
  visibleContainers.forEach((containerStats) => {
    const item = document.createElement("div");
    item.className = "resource-item";
    item.appendChild(createElement("span", containerStats.displayName));
    const cpuPercent = Number(containerStats.cpuPercent);
    const hasStats = Number.isFinite(cpuPercent);
    item.appendChild(createElement("strong", hasStats ? `${containerStats.cpuPercent}% CPU` : "No stats"));
    const progress = document.createElement("div");
    progress.className = "progress";
    const progressBar = document.createElement("i");
    progressBar.style.width = `${hasStats ? Math.min(cpuPercent, 100) : 0}%`;
    progress.appendChild(progressBar);
    item.appendChild(progress);
    item.appendChild(
      createElement(
        "span",
        hasStats
          ? `Memory ${containerStats.memoryUsedMiB} / ${containerStats.memoryLimitMiB} MiB`
          : "Memory unavailable",
      ),
    );
    container.appendChild(item);
  });
}

function renderEvents() {
  const body = byId("dashboard-event-log");
  body.replaceChildren();
  if (!dashboardEvents.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No dashboard events recorded.");
    cell.colSpan = 3;
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  dashboardEvents.forEach((event) => {
    const row = document.createElement("tr");
    row.appendChild(rowCell(event.timestamp || ""));
    row.appendChild(rowCell(event.level || ""));
    row.appendChild(rowCell(event.message || ""));
    body.appendChild(row);
  });
}

async function refreshDashboard() {
  setStatus("dashboard-refresh-status", "Refreshing...", "pending");
  try {
    const result = await requestJson("/api/dashboard/services");
    applyDashboardPayload(result);
    setStatus("dashboard-refresh-status", "Dashboard updated", "success");
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runServiceAction(serviceId, action) {
  setStatus("dashboard-refresh-status", `${action} running...`, "pending");
  try {
    const result = await requestJson(`/api/dashboard/services/${serviceId}/${action}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    replaceDashboardService(result.service);
    setStatus("dashboard-refresh-status", `${action} complete`, "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runChildServiceAction(serviceId, childId, action) {
  setStatus("dashboard-refresh-status", `${childId} ${action} running...`, "pending");
  try {
    const result = await requestJson(`/api/dashboard/services/${serviceId}/children/${childId}/${action}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    replaceDashboardService(result.service);
    setStatus("dashboard-refresh-status", `${childId} ${action} complete`, "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runAllChecks() {
  setStatus("dashboard-refresh-status", "Running all checks...", "pending");
  try {
    const result = await requestJson("/api/dashboard/services/check-all", {
      method: "POST",
      body: JSON.stringify({}),
    });
    applyDashboardPayload(result);
    setStatus("dashboard-refresh-status", "Checks complete", "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

const GENERATED_PATIENT_MRN_LABEL = "Generated on create";

const patientDemoPreset = {
  mrn: "",
  firstName: "Avery",
  middleName: "Lee",
  lastName: "Morgan",
  dob: "19850412",
  sex: "F",
  visitNumber: "",
  patientClass: "O",
  assignedLocation: "CARDIOLOGY^ROOM1",
  attendingProvider: "P123^Rivera^Elena",
  accountNumber: "ACC-1001",
  phone: "555-0100",
  email: "avery.morgan@example.org",
  address: "100 Main St^^Boston^MA^02110",
  active: true,
  addressLine: "",
  addressCity: "",
  addressState: "",
  addressPostalCode: "",
  addressCountry: "",
  managingOrganizationReference: "",
  managingOrganizationDisplay: "",
};

const patientDemoModeOverrides = {
  "hl7-v2": {
    assignedLocation: "CARDIOLOGY^ROOM1",
    attendingProvider: "P123^Rivera^Elena",
    accountNumber: "ACC-1001",
    address: "100 Main St^^Boston^MA^02110",
  },
  fhir: {
    assignedLocation: "",
    attendingProvider: "",
    accountNumber: "",
    address: "100 Main St, Boston, MA 02110",
    addressLine: "100 Main St",
    addressCity: "Boston",
    addressState: "MA",
    addressPostalCode: "02110",
    addressCountry: "US",
    managingOrganizationReference: "Organization/healthcare-lab",
    managingOrganizationDisplay: "Healthcare Lab",
  },
  gdt: {
    assignedLocation: "",
    attendingProvider: "",
    accountNumber: "",
    address: "100 Main St, Boston, MA 02110",
  },
  dicom: {
    assignedLocation: "",
    attendingProvider: "",
    accountNumber: "",
    address: "100 Main St, Boston, MA 02110",
  },
};

function patientDemoPresetForMode(mode) {
  const normalizedMode = PATIENT_MODE_CONFIG[mode] ? mode : "hl7-v2";
  return {
    ...patientDemoPreset,
    ...(patientDemoModeOverrides[normalizedMode] || {}),
    mode: normalizedMode,
  };
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

function patientFormPayload() {
  return {
    mode: byId("patient-mode").value,
    mrn: byId("patient-mrn").value.trim(),
    firstName: byId("patient-first-name").value.trim(),
    middleName: byId("patient-middle-name").value.trim(),
    lastName: byId("patient-last-name").value.trim(),
    dob: byId("patient-dob").value.trim(),
    sex: byId("patient-sex").value,
    visitNumber: byId("patient-visit-number").value.trim(),
    patientClass: byId("patient-class").value.trim() || "O",
    assignedLocation: byId("patient-assigned-location").value.trim(),
    attendingProvider: byId("patient-attending-provider").value.trim(),
    accountNumber: byId("patient-account-number").value.trim(),
    phone: byId("patient-phone").value.trim(),
    email: byId("patient-email").value.trim(),
    address: byId("patient-address").value.trim(),
    active: byId("patient-active").value === "true",
    addressLine: byId("patient-address-line").value.trim(),
    addressCity: byId("patient-address-city").value.trim(),
    addressState: byId("patient-address-state").value.trim(),
    addressPostalCode: byId("patient-address-postal-code").value.trim(),
    addressCountry: byId("patient-address-country").value.trim(),
    managingOrganizationReference: byId("patient-managing-organization-reference").value.trim(),
    managingOrganizationDisplay: byId("patient-managing-organization-display").value.trim(),
  };
}

function setPatientForm(payload) {
  byId("patient-mode").value = payload.mode || "hl7-v2";
  byId("patient-mrn").value = payload.mrn || "";
  byId("patient-first-name").value = payload.firstName || "";
  byId("patient-middle-name").value = payload.middleName || "";
  byId("patient-last-name").value = payload.lastName || "";
  byId("patient-dob").value = payload.dob || "";
  byId("patient-sex").value = payload.sex || "F";
  byId("patient-visit-number").value = payload.visitNumber || "";
  byId("patient-class").value = payload.patientClass || "O";
  byId("patient-assigned-location").value = payload.assignedLocation || "";
  byId("patient-attending-provider").value = payload.attendingProvider || "";
  byId("patient-account-number").value = payload.accountNumber || "";
  byId("patient-phone").value = payload.phone || "";
  byId("patient-email").value = payload.email || "";
  byId("patient-address").value = payload.address || "";
  byId("patient-active").value = payload.active === false ? "false" : "true";
  byId("patient-address-line").value = payload.addressLine || "";
  byId("patient-address-city").value = payload.addressCity || "";
  byId("patient-address-state").value = payload.addressState || "";
  byId("patient-address-postal-code").value = payload.addressPostalCode || "";
  byId("patient-address-country").value = payload.addressCountry || "";
  byId("patient-managing-organization-reference").value = payload.managingOrganizationReference || "";
  byId("patient-managing-organization-display").value = payload.managingOrganizationDisplay || "";
}

function updatePatientModeFields(mode) {
  const config = PATIENT_MODE_CONFIG[mode] || PATIENT_MODE_CONFIG["hl7-v2"];
  byId("patient-mode-title").textContent = config.title;
  byId("patient-payload-title").textContent = config.payloadTitle;
  document.querySelectorAll("[data-patient-mode-field]").forEach((element) => {
    const modes = String(element.dataset.patientModeField || "").split(/\s+/);
    element.hidden = !modes.includes(mode);
  });
}

function validatePatientPayload(payload) {
  const messages = [];
  [
    ["First name", payload.firstName],
    ["Last name", payload.lastName],
    ["DOB", payload.dob],
    ["Sex", payload.sex],
  ].forEach(([label, value]) => {
    if (!String(value || "").trim()) messages.push(`${label} is required.`);
  });
  if (payload.dob && !/^\d{8}$/.test(payload.dob)) {
    messages.push("DOB must be YYYYMMDD.");
  }
  if (payload.sex && !["M", "F", "O", "U"].includes(payload.sex)) {
    messages.push("Sex must be M, F, O, or U.");
  }
  return messages;
}

function patientPreviewMrn(payload) {
  return String(payload?.mrn || "").trim() || GENERATED_PATIENT_MRN_LABEL;
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

function buildPatientPreviewPayload(payload) {
  if (payload.mode === "fhir") return buildPatientFhirPreviewPayload(payload);
  if (payload.mode === "gdt") return buildPatientGdtPreviewPayload(payload);
  if (payload.mode === "dicom") return buildPatientDicomPreviewPayload(payload);
  const timestamp = hl7Timestamp();
  const visitNumber = payload.visitNumber || "VISIT-GENERATED";
  const patientName = [payload.lastName, payload.firstName, payload.middleName]
    .map(hl7Escape)
    .filter(Boolean)
    .join("^");
  return [
    `MSH|^~\\&|HEALTHCARE_LAB|LAB_DEMO|OIE|ADT|${timestamp}||ADT^A04^ADT_A01|A04PREVIEW${timestamp}|P|2.5.1||||||UNICODE UTF-8`,
    `EVN|A04|${timestamp}`,
    `PID|1||${hl7Escape(patientPreviewMrn(payload))}^^^HEALTHCARE_LAB^MR||${patientName}||${hl7Escape(payload.dob)}|${hl7Escape(payload.sex)}|||${hl7EscapeComposite(payload.address)}||${hl7Escape(payload.phone)}|||||${hl7Escape(payload.accountNumber)}`,
    `PV1|1|${hl7Escape(payload.patientClass || "O")}|${hl7EscapeComposite(payload.assignedLocation)}||||${hl7EscapeComposite(payload.attendingProvider)}||||||||||||${hl7Escape(visitNumber)}`,
  ].join("\r");
}

function fhirBirthDate(dob) {
  return formatFhirBirthDate(dob);
}

function fhirGender(sex) {
  return formatFhirGender(sex);
}

function buildPatientFhirPreviewPayload(payload) {
  const patientName = [payload.firstName, payload.middleName, payload.lastName].filter(Boolean).join(" ");
  const telecom = [];
  if (payload.phone) telecom.push({ system: "phone", value: payload.phone });
  if (payload.email) telecom.push({ system: "email", value: payload.email });
  const address = {};
  if (payload.address) address.text = payload.address;
  if (payload.addressLine) address.line = [payload.addressLine];
  if (payload.addressCity) address.city = payload.addressCity;
  if (payload.addressState) address.state = payload.addressState;
  if (payload.addressPostalCode) address.postalCode = payload.addressPostalCode;
  if (payload.addressCountry) address.country = payload.addressCountry;
  const managingOrganization = {};
  if (payload.managingOrganizationReference) managingOrganization.reference = payload.managingOrganizationReference;
  if (payload.managingOrganizationDisplay) managingOrganization.display = payload.managingOrganizationDisplay;
  const resource = {
    resourceType: "Patient",
    id: "PAT-GENERATED",
    active: payload.active !== false,
    meta: {
      profile: [
        "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore",
      ],
    },
    identifier: [
      {
        system: "urn:healthcare-lab:mrn",
        value: patientPreviewMrn(payload),
      },
    ],
    name: [
      {
        use: "official",
        text: patientName,
        family: payload.lastName,
        given: [payload.firstName, payload.middleName].filter(Boolean),
      },
    ],
    gender: fhirGender(payload.sex),
    birthDate: fhirBirthDate(payload.dob),
    telecom,
    address: Object.keys(address).length ? [address] : [],
    extension: [
      {
        url: "urn:healthcare-lab:visit-number",
        valueString: payload.visitNumber || "VISIT-GENERATED",
      },
    ],
  };
  if (Object.keys(managingOrganization).length) {
    resource.managingOrganization = managingOrganization;
  }
  return JSON.stringify(resource, null, 2);
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

function buildPatientGdtPreviewPayload(payload) {
  const gdtBirthDate = `${payload.dob.slice(6)}${payload.dob.slice(4, 6)}${payload.dob.slice(0, 4)}`;
  const gdtSex = { M: "1", F: "2" }[payload.sex];
  const records = [
    ["8315", "LABGDT"],
    ["8316", "HCLAB"],
    ["3000", patientPreviewMrn(payload)],
    ["3101", payload.lastName],
    ["3102", payload.firstName],
    ["3103", gdtBirthDate],
  ];
  if (gdtSex) records.push(["3110", gdtSex]);
  return renderGdtMessage(records, "6301");
}

function buildPatientDicomPreviewPayload(payload) {
  const dataset = {
    "(0010,0010) PatientName": [payload.lastName, payload.firstName, payload.middleName].filter(Boolean).join("^"),
    "(0010,0020) PatientID": patientPreviewMrn(payload),
    "(0010,0030) PatientBirthDate": payload.dob,
    "(0010,0040) PatientSex": payload.sex,
    "(0010,2154) PatientTelephoneNumbers": payload.phone,
    "(0038,0010) AdmissionID": payload.visitNumber || "VISIT-GENERATED",
    "(0038,0500) PatientState": payload.patientClass || "O",
  };
  if (payload.address) dataset["(0010,1040) PatientAddress"] = payload.address;
  return JSON.stringify(dataset, null, 2);
}

function renderPatientValidation(messages) {
  const container = byId("patient-validation");
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

function dcm4cheeConsoleOrders(patientId = selectedDcm4cheePatientId) {
  return orderRecords.filter((item) => (
    item.protocolVersion === "DICOM"
    && (!patientId || Number(item.patientRecordId) === Number(patientId))
  ));
}

function selectedDcm4cheePatient() {
  const selectedId = Number(selectedDcm4cheePatientId || 0);
  return dcm4cheeConsolePatients().find((item) => Number(item.id) === selectedId) || null;
}

function selectedDcm4cheeOrder() {
  const selectedId = Number(selectedDcm4cheeOrderId || 0);
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
  selectedDcm4cheePatientId = patientId;
  const patientOrders = dcm4cheeConsoleOrders(patientId);
  if (!patientOrders.some((item) => Number(item.id) === Number(selectedDcm4cheeOrderId))) {
    selectedDcm4cheeOrderId = patientOrders[0]?.id || null;
  }
  renderDcm4cheeConsole();
}

function selectDcm4cheeOrder(orderId) {
  selectedDcm4cheeOrderId = orderId;
  const order = selectedDcm4cheeOrder();
  if (order?.patientRecordId) selectedDcm4cheePatientId = order.patientRecordId;
  renderDcm4cheeConsole();
  if (orderId) loadDcm4cheeAttemptHistory(orderId, "dcm4chee-console-attempt-history");
}

function ensureDcm4cheeSelection() {
  const patients = dcm4cheeConsolePatients();
  if (!patients.length) {
    selectedDcm4cheePatientId = null;
    selectedDcm4cheeOrderId = null;
    return;
  }
  if (!selectedDcm4cheePatientId || !patients.some((item) => Number(item.id) === Number(selectedDcm4cheePatientId))) {
    selectedDcm4cheePatientId = patients[0].id;
  }
  const orders = dcm4cheeConsoleOrders(selectedDcm4cheePatientId);
  if (!orders.some((item) => Number(item.id) === Number(selectedDcm4cheeOrderId))) {
    selectedDcm4cheeOrderId = orders[0]?.id || null;
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
    patientSelect.value = String(selectedDcm4cheePatientId || "");
  }
  patientSelect.disabled = !patients.length;

  const orders = dcm4cheeConsoleOrders(selectedDcm4cheePatientId);
  orderSelect.replaceChildren();
  if (!orders.length) {
    orderSelect.appendChild(new Option("No DICOM MWL orders", ""));
  } else {
    orders.forEach((order) => {
      const code = order.summary?.orderCode || order.orderCode || "DICOM";
      orderSelect.appendChild(new Option(`${dcm4cheeOrderLabel(order)} - ${code}`, String(order.id)));
    });
    orderSelect.value = String(selectedDcm4cheeOrderId || "");
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
    row.classList.toggle("selected-row", Number(order.id) === Number(selectedDcm4cheeOrderId));
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
    row.className = Number(patient.id) === Number(selectedDcm4cheePatientId) ? "selected-row" : "";
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
      requestJson("/api/patients?protocolVersion=DICOM"),
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

function renderPatientRecordList() {
  const body = byId("patient-record-list");
  body.replaceChildren();
  if (!patientRecords.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local patients created yet.");
    cell.colSpan = 9;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  patientRecords.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    const fhir = item.fhir || null;
    const dcm4cheePatient = item.dcm4chee?.patient || null;
    const stateLabel = patientStateLabel(item);
    const stateClass = stateLabel === "OK" ? "success" : stateLabel === "Error" ? "error" : "neutral";
    row.append(
      rowCell(item.localPatientNumber || item.id),
      rowCell(item.protocolVersion),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(summary.dob),
      rowCell(summary.sex),
      rowCell(summary.visitNumber),
      rowCell(createElement("span", stateLabel, `status ${stateClass}`)),
      rowCell(taipeiTimestamp(item.createdAt)),
    );
    row.addEventListener("click", () => {
      byId("patient-payload-preview").textContent = item.payload || "";
      renderPatientSummaryFromRecord(item);
    });
    body.appendChild(row);
  });
}

function patientStateLabel(item) {
  if (item.protocolVersion === "FHIR R4") {
    const fhir = item.fhir || {};
    const syncStatus = fhir.sync?.status || "";
    const reference = fhir.medplum?.reference || "";
    return syncStatus === "Synced" && /^Patient\/[^/]+$/.test(reference) ? "OK" : "Error";
  }
  if (item.protocolVersion === "DICOM") {
    const dcm4cheePatient = item.dcm4chee?.patient || {};
    const syncStatus = dcm4cheePatient.displayStatus || dcm4cheePatient.status || "";
    return syncStatus === "Synced" && dcm4cheePatient.ack?.code === "AA" ? "OK" : "Error";
  }
  const validation = item.validation || {};
  const messages = Array.isArray(validation.messages) ? validation.messages : [];
  return messages.length ? "Error" : "OK";
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
    const result = await requestJson("/api/patients");
    patientRecords = result.items || [];
    renderPatientRecordList();
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
    const result = await requestJson("/api/patients", {
      method: "POST",
      body: JSON.stringify(patientFormPayload()),
    });
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
    const result = await requestJson(`/api/patients/${patientId}/fhir-sync`, { method: "POST" });
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
    const result = await requestJsonAllowBusinessFailure(`/api/patients/${patientId}/dcm4chee-results-refresh`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const patient = result.patient || {};
    patientRecords = patientRecords.map((item) => Number(item.id) === Number(patient.id) ? patient : item);
    selectedDcm4cheePatientId = patient.id || selectedDcm4cheePatientId;
    renderPatientRecordList();
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
      selectedOrderRecordId = options.orderId;
      selectedDcm4cheeOrderId = options.orderId;
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
    const params = new URLSearchParams({ patient: patientReference });
    if (serviceRequestReference) params.set("serviceRequest", serviceRequestReference);
    const result = await requestJson(`/api/fhir/diagnostic-reports?${params.toString()}`);
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

async function refreshMedplumInventory() {
  setStatus("medplum-inventory-status", "Loading inventory...", "pending");
  try {
    const result = await requestJson("/api/fhir/inventory");
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
    const result = await requestJson(`/api/fhir/records/${recordId}/preview`);
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
    const params = new URLSearchParams({ reference });
    const result = await requestJson(`/api/fhir/resource-preview?${params.toString()}`);
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
    await requestJson(`/api/fhir/records/${recordId}/sync`, {
      method: "POST",
      body: JSON.stringify({}),
    });
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
  const current = selector.value;
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
  selectedOrderRecordId = item.id;
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
    selectedOrderRecordId = orderId;
    selectedDcm4cheeOrderId = orderId;
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
    selectedDcm4cheeOrderId = orderId;
    if (result.item?.patientRecordId) selectedDcm4cheePatientId = result.item.patientRecordId;
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
    selectedOrderRecordId = orderId;
    selectedDcm4cheeOrderId = orderId;
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
    const result = await requestJson("/api/patients", {
      method: "POST",
      body: JSON.stringify(gdtPatientFormPayload()),
    });
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
  const body = byId("oie-inventory-list");
  body.replaceChildren();
  if (!oieInventory.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local ADT patients have been created.");
    cell.colSpan = 6;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    selectedOiePatientId = null;
    selectedOieOrderId = null;
    byId("oie-selected-patient-title").textContent = "No patient selected";
    byId("oie-payload-preview").textContent = "Create a local Patient A04 record to inspect it here.";
    return;
  }
  if (!selectedOiePatientId || !oieInventory.some((item) => Number(item.id) === Number(selectedOiePatientId))) {
    selectedOiePatientId = oieInventory[0].id;
  }
  oieInventory.forEach((item) => {
    const patientId = Number(item.id);
    const row = document.createElement("tr");
    row.className = "oie-patient-row";
    row.classList.toggle("selected-row", Number(item.id) === Number(selectedOiePatientId));
    const summary = item.summary || {};
    const toggleButton = createElement(
      "button",
      expandedOiePatientIds.has(patientId) ? "v" : ">",
      "oie-patient-toggle",
    );
    toggleButton.type = "button";
    toggleButton.setAttribute(
      "aria-label",
      expandedOiePatientIds.has(patientId) ? "Collapse patient orders and results" : "Expand patient orders and results",
    );
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectedOiePatientId = item.id;
      if (expandedOiePatientIds.has(patientId)) {
        expandedOiePatientIds.delete(patientId);
      } else {
        expandedOiePatientIds.add(patientId);
      }
      renderOieInventory();
      renderSelectedOiePatient();
    });
    const selectPayload = () => {
      selectedOiePatientId = item.id;
      selectedOiePayload = item.payload || "";
      byId("oie-payload-preview").textContent = selectedOiePayload;
      renderOiePreviewSummary("ADT", [
        ["MRN", summary.mrn],
        ["Name", summary.name],
        ["Created", taipeiTimestamp(item.createdAt)],
      ]);
      renderOieInventory();
      renderSelectedOiePatient();
    };
    row.append(
      rowCell(toggleButton),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(item.orderCount ?? 0),
      rowCell(item.resultCount ?? 0),
    );
    row.addEventListener("click", selectPayload);
    body.appendChild(row);

    if (expandedOiePatientIds.has(patientId)) {
      const detailRow = document.createElement("tr");
      detailRow.className = "oie-patient-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 6;
      const content = document.createElement("div");
      content.className = "oie-patient-rollup-content";
      content.append(
        oiePatientSection("ORM", "Orders", renderOieOrders(item.orders || [])),
        oiePatientSection("ORU", "Results", renderOieResults(item.results || [])),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function selectedOiePatient() {
  return oieInventory.find((item) => Number(item.id) === Number(selectedOiePatientId)) || null;
}

function renderOiePreviewSummary(kind, rows) {
  const container = byId("oie-preview-summary");
  container.replaceChildren();
  container.appendChild(createElement("span", kind, "status neutral"));
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
}

function renderSelectedOiePatient() {
  const patient = selectedOiePatient();
  const summary = patient?.summary || {};
  byId("oie-selected-patient-title").textContent = patient
    ? `${summary.mrn || patient.id} - ${summary.name || "Patient"}`
    : "No patient selected";
  const container = byId("oie-selected-patient-summary");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a patient and expand Orders or Results.", "muted"));
    selectedOieOrderId = null;
    renderOieTransmission(null);
    return;
  }
  [
    ["MRN", summary.mrn],
    ["Name", summary.name],
    ["Orders", patient.orderCount ?? 0],
    ["Results", patient.resultCount ?? 0],
  ].forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(String(value ?? "-")));
    container.appendChild(item);
  });
  const orders = patient.orders || [];
  let order = orders.find((item) => Number(item.id) === Number(selectedOieOrderId)) || null;
  if (!order && orders.length) {
    order = orders[0];
    selectedOieOrderId = order.id;
  } else if (!order) {
    selectedOieOrderId = null;
  }
  renderOieTransmission(order);
}

function renderOieOrders(orders) {
  const { wrap, tbody } = oieNestedTable([
    "Order ID",
    "MRN",
    "Visit Number",
    "Code",
    "Status",
    "Created At (Taipei)",
    "ACK",
    "Sent",
    "Action",
  ]);
  if (!orders.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local ORM O01 orders for this patient.");
    cell.colSpan = 9;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
    return wrap;
  }
  orders.forEach((item) => {
    const row = document.createElement("tr");
    row.classList.toggle("selected-row", Number(item.id) === Number(selectedOieOrderId));
    const summary = item.summary || {};
    const selectButton = createElement("button", "Select", "small-button");
    selectButton.type = "button";
    selectButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieOrder(item);
    });
    row.append(
      rowCell(item.localOrderNumber || item.id),
      rowCell(summary.mrn),
      rowCell(orderVisitNumber(item)),
      rowCell(summary.orderCode),
      rowCell(item.status || "Ready to send"),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(item.ack?.code || item.transportError || "-"),
      rowCell(taipeiTimestamp(item.lastSentAt)),
      rowCell(selectButton),
    );
    row.addEventListener("click", () => selectOieOrder(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function selectOieOrder(item) {
  selectedOieOrderId = item.id;
  selectedOiePayload = item.payload || "";
  byId("oie-payload-preview").textContent = selectedOiePayload;
  byId("oie-ack-preview").textContent = ackPreviewText(item);
  renderOieTransmission(item);
  renderOiePreviewSummary("ORM", [
    ["Order ID", item.localOrderNumber],
    ["MRN", item.summary?.mrn],
    ["Visit Number", orderVisitNumber(item)],
    ["Code", item.summary?.orderCode],
    ["Status", item.status],
    ["Created At", taipeiTimestamp(item.createdAt)],
    ["ACK", item.ack?.code || item.transportError || "-"],
  ]);
  renderOieInventory();
}

function renderOieResults(results) {
  const { wrap, tbody } = oieNestedTable(["Type", "Matched Order", "Status", "Received", "Action"]);
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No ORU results for this patient.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
    return wrap;
  }
  results.forEach((item) => {
    const row = document.createElement("tr");
    const previewButton = createElement("button", "Preview", "small-button");
    previewButton.type = "button";
    previewButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieResult(item);
    });
    row.append(
      rowCell(item.messageType || "ORU"),
      rowCell(item.matchedOrderRecordId || "-"),
      rowCell(item.matchStatus),
      rowCell(taipeiTimestamp(item.receivedAt)),
      rowCell(previewButton),
    );
    row.addEventListener("click", () => selectOieResult(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function oiePatientSection(label, title, body) {
  const section = document.createElement("section");
  section.className = "oie-patient-section";
  const heading = document.createElement("div");
  heading.className = "compact-heading oie-patient-section-heading";
  const text = document.createElement("div");
  text.appendChild(createElement("p", label, "eyebrow"));
  text.appendChild(createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function oieNestedTable(headers) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap oie-nested-table-wrap";
  const table = document.createElement("table");
  table.className = "oie-nested-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => headRow.appendChild(createElement("th", header)));
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  wrap.appendChild(table);
  return { wrap, tbody };
}

function renderOieTransmission(item) {
  const title = byId("oie-selected-order-title");
  const summary = byId("oie-selected-order-summary");
  const sendButton = byId("send-selected-oie-order");
  summary.replaceChildren();
  sendButton.disabled = !item;
  if (!item) {
    title.textContent = "No order selected";
    summary.appendChild(createElement("p", "Choose an order from an expanded patient row.", "muted"));
    return;
  }
  title.textContent = String(item.localOrderNumber || item.id);
  [
    ["Code", item.summary?.orderCode],
    ["Priority", item.priority],
    ["Status", item.status || "Ready to send"],
    ["Last ACK", item.ack?.code || item.transportError || "-"],
  ].forEach(([label, value]) => {
    const row = document.createElement("p");
    row.appendChild(createElement("strong", `${label}: `));
    row.appendChild(document.createTextNode(String(value ?? "-")));
    summary.appendChild(row);
  });
}

function renderOieUnmatchedResults() {
  const body = byId("oie-unmatched-result-list");
  body.replaceChildren();
  if (!oieUnmatchedResults.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No unmatched ORU results.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  oieUnmatchedResults.forEach((item) => {
    const row = document.createElement("tr");
    const previewButton = createElement("button", "Preview", "small-button");
    previewButton.type = "button";
    previewButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieResult(item);
    });
    row.append(
      rowCell(item.messageType || "ORU"),
      rowCell(item.patientMrn || "-"),
      rowCell(item.matchStatus || item.parseStatus),
      rowCell(taipeiTimestamp(item.receivedAt)),
      rowCell(previewButton),
    );
    row.addEventListener("click", () => selectOieResult(item));
    body.appendChild(row);
  });
}

function selectOieResult(item) {
  selectedOiePayload = item.payload || "";
  byId("oie-payload-preview").textContent = selectedOiePayload;
  byId("oie-ack-preview").textContent = item.error || "Result accepted.";
  renderOiePreviewSummary("ORU", [
    ["Type", item.messageType],
    ["MRN", item.patientMrn],
    ["Placer", item.placerOrderNumber],
    ["Filler", item.fillerOrderNumber],
    ["Match", item.matchStatus],
  ]);
}

function ackPreviewText(item) {
  if (item.transportError) return `Transport error: ${item.transportError}`;
  if (item.ack?.payload) return item.ack.payload;
  if (item.ack?.code) return `ACK ${item.ack.code} ${item.ack.controlId || ""} ${item.ack.text || ""}`.trim();
  return "No ACK recorded for this order.";
}

async function refreshOieInventory() {
  setStatus("oie-inventory-status", "Refreshing...", "pending");
  try {
    const [workbench] = await Promise.all([
      requestJson("/api/oie/workbench"),
      refreshOieListenerStatus(),
    ]);
    oieInventory = workbench.patients || [];
    oieUnmatchedResults = workbench.unmatchedResults || [];
    renderOieInventory();
    renderSelectedOiePatient();
    renderOieUnmatchedResults();
    setStatus("oie-inventory-status", "Updated", "success");
  } catch (error) {
    setStatus("oie-inventory-status", "Refresh failed", "error");
  }
}

async function sendOieOrder(orderId, button) {
  button.disabled = true;
  setStatus("oie-inventory-status", "Sending order...", "pending");
  setStatus("oie-send-status", "Sending...", "pending");
  const payload = {
    host: byId("oie-send-host").value.trim(),
    port: Number(byId("oie-send-port").value || 0),
    timeoutSeconds: Number(byId("oie-send-timeout").value || 5),
    mllpFraming: byId("oie-send-mllp").checked,
  };
  try {
    const response = await fetch(`/api/oie/local-orders/${orderId}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    if (result.item) {
      byId("oie-payload-preview").textContent = result.item.payload || "";
      byId("oie-ack-preview").textContent = ackPreviewText(result.item);
    }
    if (!response.ok || result.success === false) {
      throw new Error(result.error || response.statusText || "Send failed");
    }
    setStatus("oie-inventory-status", "Order sent", "success");
    setStatus("oie-send-status", "Sent", "success");
  } catch (error) {
    setStatus("oie-inventory-status", "Send failed", "error");
    setStatus("oie-send-status", "Send failed", "error");
    if (!byId("oie-ack-preview").textContent.trim()) {
      byId("oie-ack-preview").textContent = error.message;
    }
  } finally {
    await refreshOieInventory();
    button.disabled = !selectedOieOrderId;
  }
}

function renderOieListenerStatus(item = {}) {
  const label = item.running ? `Running ${item.host}:${item.port}` : "Stopped";
  setStatus("oie-listener-status", item.lastError || label, item.lastError ? "error" : (item.running ? "success" : "neutral"));
  if (item.host) byId("oie-listener-host").value = item.host;
  if (item.port) byId("oie-listener-port").value = item.port;
  byId("oie-listener-mllp").checked = item.mllpFraming !== false;
}

async function refreshOieListenerStatus() {
  const result = await requestJson("/api/oie/result-listener/status");
  renderOieListenerStatus(result.item || {});
}

async function startOieListener() {
  setStatus("oie-listener-status", "Starting...", "pending");
  try {
    const result = await requestJson("/api/oie/result-listener/start", {
      method: "POST",
      body: JSON.stringify({
        host: byId("oie-listener-host").value.trim(),
        port: Number(byId("oie-listener-port").value || 6665),
        mllpFraming: byId("oie-listener-mllp").checked,
      }),
    });
    renderOieListenerStatus(result.item || {});
  } catch (error) {
    setStatus("oie-listener-status", error.message, "error");
  }
}

async function stopOieListener() {
  setStatus("oie-listener-status", "Stopping...", "pending");
  try {
    const result = await requestJson("/api/oie/result-listener/stop", { method: "POST", body: JSON.stringify({}) });
    renderOieListenerStatus(result.item || {});
  } catch (error) {
    setStatus("oie-listener-status", error.message, "error");
  }
}

function selectedGdtPatient() {
  return (gdtWorkbench.patients || []).find((item) => Number(item.id) === Number(selectedGdtPatientId)) || null;
}

function renderGdtBridgeConfig() {
  const item = gdtBridgeConfig || {};
  byId("gdt-bridge-path").value = item.bridgePath || "";
  byId("gdt-bridge-host-path").value = item.hostPath || "";
  const summary = byId("gdt-bridge-config-summary");
  summary.replaceChildren();
  [
    ["Output (inbox)", item.inboxPath],
    ["Returned data (outbox)", item.outboxPath],
    ["Archive", item.archivePath],
    ["Error", item.errorPath],
    ["Import mode", item.successMode],
    ["Filename binding", item.filenameProfile],
  ].forEach(([label, value]) => {
    const row = document.createElement("p");
    row.appendChild(createElement("strong", `${label}: `));
    row.appendChild(document.createTextNode(value || "-"));
    summary.appendChild(row);
  });
  if (item.dockerHint) {
    summary.appendChild(createElement("p", item.dockerHint, "muted"));
  }
  renderGdtWatcherStatus(item.watcher || {});
}

function renderGdtWatcherStatus(watcher) {
  const running = Boolean(watcher.running);
  setStatus("gdt-watcher-status", running ? `On (${watcher.pollSeconds || "-"}s)` : "Off", running ? "success" : "neutral");
  const summary = byId("gdt-watcher-summary");
  summary.replaceChildren();
  const lastResult = watcher.lastResult || {};
  [
    ["Bridge root", watcher.bridgeRoot],
    ["Success mode", watcher.successMode],
    ["Filename binding", watcher.filenameProfile],
    ["Last run", watcher.lastRunAt ? gdtTaipeiTimestamp(watcher.lastRunAt) : "-"],
    ["Imported", (lastResult.imported || []).length],
    ["Skipped", (lastResult.skipped || []).length],
    ["Failures", (lastResult.failures || []).length],
    ["Last error", watcher.lastError || "-"],
  ].forEach(([label, value]) => {
    const row = document.createElement("p");
    row.appendChild(createElement("strong", `${label}: `));
    row.appendChild(document.createTextNode(String(value ?? "-")));
    summary.appendChild(row);
  });
}

async function refreshGdtBridgeConfig() {
  setStatus("gdt-bridge-config-status", "Loading...", "pending");
  try {
    const result = await requestJson("/api/gdt/bridge/config");
    gdtBridgeConfig = result.item || {};
    renderGdtBridgeConfig();
    setStatus("gdt-bridge-config-status", "Ready", "success");
  } catch (error) {
    setStatus("gdt-bridge-config-status", error.message, "error");
  }
}

async function saveGdtBridgeConfig() {
  setStatus("gdt-bridge-config-status", "Saving...", "pending");
  try {
    const result = await requestJson("/api/gdt/bridge/config", {
      method: "PUT",
      body: JSON.stringify({ bridgePath: byId("gdt-bridge-path").value.trim() }),
    });
    gdtBridgeConfig = result.item || {};
    renderGdtBridgeConfig();
    await refreshGdtConsole();
    setStatus("gdt-bridge-config-status", "Saved", "success");
  } catch (error) {
    setStatus("gdt-bridge-config-status", error.message, "error");
  }
}

async function startGdtWatcher() {
  setStatus("gdt-watcher-status", "Starting...", "pending");
  try {
    const result = await requestJson("/api/gdt/bridge/watcher/start", {
      method: "POST",
      body: JSON.stringify({}),
    });
    gdtBridgeConfig = { ...(gdtBridgeConfig || {}), watcher: result.item || {} };
    renderGdtWatcherStatus(result.item || {});
    await refreshGdtConsole();
  } catch (error) {
    setStatus("gdt-watcher-status", error.message, "error");
  }
}

async function stopGdtWatcher() {
  setStatus("gdt-watcher-status", "Stopping...", "pending");
  try {
    const result = await requestJson("/api/gdt/bridge/watcher/stop", {
      method: "POST",
      body: JSON.stringify({}),
    });
    gdtBridgeConfig = { ...(gdtBridgeConfig || {}), watcher: result.item || {} };
    renderGdtWatcherStatus(result.item || {});
    await refreshGdtConsole();
  } catch (error) {
    setStatus("gdt-watcher-status", error.message, "error");
  }
}

function measurementSummary(result) {
  const measurements = result?.canonical?.result?.measurements || {};
  return ["HR", "PR", "QRS", "QT", "QTC"]
    .filter((key) => measurements[key])
    .map((key) => `${key} ${measurements[key]}`)
    .join(" / ");
}

function renderGdtPatients() {
  const body = byId("gdt-patient-list");
  body.replaceChildren();
  const patients = gdtWorkbench.patients || [];
  if (!patients.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local GDT patients or orders yet.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    selectedGdtPatientId = null;
    return;
  }
  if (!selectedGdtPatientId || !patients.some((item) => Number(item.id) === Number(selectedGdtPatientId))) {
    selectedGdtPatientId = patients[0].id;
  }
  patients.forEach((item) => {
    const summary = item.summary || {};
    const patientId = Number(item.id);
    const row = document.createElement("tr");
    row.className = "gdt-patient-row";
    const toggleButton = createElement("button", expandedGdtPatientIds.has(patientId) ? "v" : ">", "gdt-patient-toggle");
    toggleButton.type = "button";
    toggleButton.setAttribute("aria-label", expandedGdtPatientIds.has(patientId) ? "Collapse patient details" : "Expand patient details");
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const patientId = Number(item.id);
      if (expandedGdtPatientIds.has(patientId)) {
        expandedGdtPatientIds.delete(patientId);
      } else {
        selectedGdtPatientId = item.id;
        expandedGdtPatientIds.add(patientId);
      }
      renderGdtConsole();
    });
    const previewButton = gdtActionButton("Preview", (event) => {
      event.stopPropagation();
      selectGdtPatientForPreview(item);
    });
    row.addEventListener("click", () => {
      selectedGdtPatientId = item.id;
      renderGdtSelectedPatient();
    });
    row.append(
      rowCell(toggleButton),
      rowCell(item.id),
      rowCell(summary.name || "Patient"),
      rowCell(gdtTaipeiTimestamp(item.createdAt)),
      rowCell(item.orderCount ?? 0),
      rowCell(item.resultCount ?? 0),
      rowCell(previewButton),
    );
    body.appendChild(row);

    if (expandedGdtPatientIds.has(patientId)) {
      const detailRow = document.createElement("tr");
      detailRow.className = "gdt-patient-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 7;
      const content = document.createElement("div");
      content.className = "gdt-patient-rollup-content";
      content.append(
        gdtPatientSection("GDT-OUT", "Orders", renderGdtPatientOrders(item)),
        gdtPatientSection("GDT-IN", "Results", renderGdtPatientResults(item)),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function gdtPatientPreviewPayload(patient) {
  const summary = patient?.summary || {};
  const patientData = patient?.patient || {};
  const nameParts = String(summary.name || "").trim().split(/\s+/);
  return buildPatientGdtPreviewPayload({
    mrn: summary.gdtPatientNumber || patient.gdtPatientNumber || summary.mrn || "",
    firstName: patientData.firstName || nameParts.slice(0, -1).join(" ") || summary.name || "",
    lastName: patientData.lastName || nameParts.slice(-1).join("") || "",
    dob: summary.dob || patientData.dob || "",
    sex: summary.sex || patientData.sex || "U",
  });
}

function gdtPatientSection(label, title, body) {
  const section = document.createElement("section");
  section.className = "gdt-patient-section";
  const heading = document.createElement("div");
  heading.className = "compact-heading gdt-patient-section-heading";
  const text = document.createElement("div");
  text.appendChild(createElement("p", label, "eyebrow"));
  text.appendChild(createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function compactTable(headers, emptyText, colSpan) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap gdt-nested-table-wrap";
  const table = document.createElement("table");
  table.className = "gdt-nested-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => headRow.appendChild(createElement("th", header)));
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  if (emptyText) {
    const row = document.createElement("tr");
    const cell = rowCell(emptyText);
    cell.colSpan = colSpan;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
  }
  table.append(thead, tbody);
  wrap.appendChild(table);
  return { wrap, tbody };
}

function renderGdtSelectedPatient() {
  const patient = selectedGdtPatient();
  const summary = patient?.summary || {};
  byId("gdt-selected-patient-title").textContent = patient
    ? `${summary.mrn || patient.id} - ${summary.name || "Patient"}`
    : "No patient selected";
  const container = byId("gdt-selected-patient-summary");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a GDT patient.", "muted"));
    return;
  }
  [
    ["GDT Patient", summary.gdtPatientNumber],
    ["MRN", summary.mrn],
    ["DOB", summary.dob],
    ["Sex", summary.sex],
    ["Orders", patient.orderCount],
    ["Results", patient.resultCount],
  ].forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
  if (
    selectedGdtPatientRawPreview.payload
    && Number(selectedGdtPatientRawPreview.patientId) === Number(patient.id)
  ) {
    container.appendChild(createElement("strong", "Raw Preview"));
    const preview = createElement("pre", selectedGdtPatientRawPreview.payload, "compact-output gdt-selected-patient-raw");
    container.appendChild(preview);
  }
}

function gdtActionButton(label, handler) {
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", handler);
  return button;
}

function displayGdtOrderNumber(orderNumber) {
  return String(orderNumber || "").replace(/^GDT-/, "") || "-";
}

function selectGdtPatientForPreview(patient) {
  selectedGdtPatientId = patient.id;
  selectedGdtPayload = gdtPatientPreviewPayload(patient);
  selectedGdtPatientRawPreview = { patientId: patient.id, payload: selectedGdtPayload };
  renderGdtSelectedPatient();
  renderGdtArtifacts([]);
  byId("gdt-detail-title").textContent = "Raw Patient";
  byId("gdt-payload-preview").textContent = selectedGdtPayload;
  renderGdtDetailSummary([
    ["Patient ID", patient.id],
    ["Name", patient.summary?.name],
    ["GDT Patient", patient.summary?.gdtPatientNumber],
    ["Orders", patient.orderCount],
    ["Results", patient.resultCount],
  ]);
}

function renderGdtPatientOrders(patient) {
  const orders = patient?.orders || [];
  const { wrap, tbody } = compactTable(["Order", "Status", "Created", "Result", "Actions"], orders.length ? "" : "No GDT-OUT orders for this patient.", 5);
  if (!orders.length) {
    return wrap;
  }
  orders.forEach((item) => {
    const resultCount = (item.messages || []).filter((message) => message.direction === "inbound").length;
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.append(
      gdtActionButton("Preview GDT-OUT", (event) => {
        event.stopPropagation();
        selectGdtOrder(item);
      }),
      gdtActionButton("Write GDT-OUT", (event) => {
        event.stopPropagation();
        writeGdtOrder(item.id);
      }),
      gdtActionButton("Demo Result", (event) => {
        event.stopPropagation();
        createGdtDemoResult(item.id);
      }),
    );
    const row = document.createElement("tr");
    row.append(
      rowCell(displayGdtOrderNumber(item.localGdtOrderNumber)),
      rowCell(item.status),
      rowCell(gdtTaipeiTimestamp(item.createdAt)),
      rowCell(resultCount ? `${resultCount} result(s)` : "-"),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectGdtOrder(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function renderGdtPatientResults(patient) {
  const results = patient?.results || [];
  const { wrap, tbody } = compactTable(["Result", "Artifacts", "Received", "Actions"], results.length ? "" : "No imported GDT-IN results for this patient.", 4);
  if (!results.length) {
    return wrap;
  }
  results.forEach((item, index) => {
    const row = document.createElement("tr");
    const attachments = item.attachments || [];
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(gdtActionButton("Preview GDT-IN", (event) => {
      event.stopPropagation();
      selectGdtResult(item);
    }));
    row.append(
      rowCell(index + 1),
      rowCell(attachments.length),
      rowCell(gdtTaipeiTimestamp(item.receivedAt)),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectGdtResult(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function renderGdtInbox() {
  const body = byId("gdt-inbox-list");
  body.replaceChildren();
  const files = gdtWorkbench.bridgeInbox || [];
  if (!files.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No returned GDT files found in outbox.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  files.forEach((item) => {
    const action = item.status === "pending"
      ? gdtActionButton("Import GDT-IN", () => importGdtInboxFile(item.name))
      : createElement("span", "-", "muted");
    const row = document.createElement("tr");
    row.append(
      rowCell(item.name),
      rowCell(item.status),
      rowCell(item.size),
      rowCell(taipeiTimestamp(item.updatedAt)),
      rowCell(action),
    );
    body.appendChild(row);
  });
}

function renderGdtArtifacts(artifacts = []) {
  const container = byId("gdt-artifact-list");
  container.replaceChildren();
  if (!artifacts.length) {
    container.appendChild(createElement("p", "No artifact references selected.", "muted"));
    return;
  }
  artifacts.forEach((artifact) => {
    const item = document.createElement("div");
    item.className = "artifact-reference";
    item.appendChild(createElement("strong", `${artifact.contentType || artifact.role || "Artifact"}`));
    item.appendChild(createElement("span", artifact.description || artifact.filename || "Reference"));
    item.appendChild(createElement("code", artifact.reference || artifact.url || artifact.path || "-"));
    item.appendChild(createElement("span", artifact.status || "reference-only", `status ${artifact.status === "warning" ? "warning" : "neutral"}`));
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(gdtActionButton("Copy", () => navigator.clipboard.writeText(artifact.reference || artifact.url || artifact.path || "")));
    if (artifact.url) {
      const open = gdtActionButton("Open", () => window.open(artifact.url, "_blank", "noopener"));
      actions.appendChild(open);
    }
    item.appendChild(actions);
    container.appendChild(item);
  });
}

function selectGdtOrder(item) {
  selectedGdtPayload = item.rawGdtText || item.payload || "";
  byId("gdt-detail-title").textContent = "Raw GDT-OUT";
  byId("gdt-payload-preview").textContent = selectedGdtPayload;
  renderGdtArtifacts(item.attachments || []);
  renderGdtDetailSummary([
    ["Order", item.localGdtOrderNumber],
    ["Patient", item.summary?.name],
    ["Status", item.status],
    ["Export", item.exportPath || "-"],
  ]);
}

function selectGdtResult(item) {
  selectedGdtPayload = item.rawGdtText || "";
  byId("gdt-detail-title").textContent = "Raw GDT-IN";
  byId("gdt-payload-preview").textContent = selectedGdtPayload;
  renderGdtArtifacts(item.attachments || []);
  renderGdtDetailSummary([
    ["Result", item.messageType],
    ["Match", item.matchStatus],
    ["Status", item.canonical?.result?.status || "-"],
    ["Measurements", measurementSummary(item) || "-"],
  ]);
}

function renderGdtDetailSummary(rows) {
  const container = byId("gdt-detail-summary");
  container.replaceChildren();
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
}

function renderGdtConsole() {
  renderGdtPatients();
  renderGdtSelectedPatient();
  renderGdtInbox();
}

async function refreshGdtConsole() {
  setStatus("gdt-console-status", "Refreshing...", "pending");
  try {
    const [configResult, result] = await Promise.all([
      requestJson("/api/gdt/bridge/config"),
      requestJson("/api/gdt/workbench"),
    ]);
    gdtBridgeConfig = configResult.item || {};
    gdtWorkbench = result;
    renderGdtBridgeConfig();
    renderGdtConsole();
    setStatus("gdt-console-status", "Updated", "success");
    setStatus("gdt-bridge-config-status", "Ready", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}

async function writeGdtOrder(orderId) {
  setStatus("gdt-console-status", "Writing GDT-OUT...", "pending");
  try {
    await requestJson(`/api/gdt/orders/${orderId}/write-6302`, { method: "POST", body: JSON.stringify({}) });
    await refreshGdtConsole();
    setStatus("gdt-console-status", "GDT-OUT written", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}

async function createGdtDemoResult(orderId) {
  setStatus("gdt-console-status", "Creating demo result...", "pending");
  try {
    await requestJson(`/api/gdt/orders/${orderId}/demo-result`, { method: "POST", body: JSON.stringify({}) });
    await refreshGdtConsole();
    setStatus("gdt-console-status", "Demo result imported", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}

async function importGdtInboxFile(filename) {
  setStatus("gdt-console-status", "Importing GDT-IN...", "pending");
  try {
    await requestJson("/api/gdt/bridge/import", {
      method: "POST",
      body: JSON.stringify({ filename }),
    });
    await refreshGdtConsole();
    setStatus("gdt-console-status", "GDT-IN imported", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
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
  byId("refresh-dashboard").addEventListener("click", refreshDashboard);
  byId("run-all-lab-checks").addEventListener("click", runAllChecks);
  byId("dashboard-filter").addEventListener("input", renderServices);
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
    if (event.target.value.startsWith("DiagnosticReport/")) {
      loadMedplumLiveReportPreview(event.target.value);
    } else {
      loadMedplumPreview(Number(event.target.value || 0));
    }
  });
  byId("copy-medplum-json").addEventListener("click", () => copyTextFromElement("medplum-json-preview"));
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
    if (selectedDcm4cheeOrderId) sendDcm4cheeOrder(selectedDcm4cheeOrderId, event.currentTarget);
  });
  byId("refresh-oie-inventory").addEventListener("click", refreshOieInventory);
  byId("copy-oie-payload").addEventListener("click", () => copyTextFromElement("oie-payload-preview"));
  byId("send-selected-oie-order").addEventListener("click", () => {
    if (selectedOieOrderId) sendOieOrder(selectedOieOrderId, byId("send-selected-oie-order"));
  });
  byId("start-oie-listener").addEventListener("click", startOieListener);
  byId("stop-oie-listener").addEventListener("click", stopOieListener);
  byId("refresh-gdt-console").addEventListener("click", refreshGdtConsole);
  byId("create-gdt-ecg-order").addEventListener("click", openGdtOrderFlow);
  byId("refresh-gdt-bridge-config").addEventListener("click", refreshGdtBridgeConfig);
  byId("save-gdt-bridge-config").addEventListener("click", saveGdtBridgeConfig);
  byId("start-gdt-watcher").addEventListener("click", startGdtWatcher);
  byId("stop-gdt-watcher").addEventListener("click", stopGdtWatcher);
  byId("copy-gdt-payload").addEventListener("click", () => copyTextFromElement("gdt-payload-preview"));
  setActiveView("lab-console-view");
};

document.addEventListener("DOMContentLoaded", initializeApplication);
