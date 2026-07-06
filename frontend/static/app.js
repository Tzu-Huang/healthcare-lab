const byId = (id) => document.getElementById(id);

let dashboardServices = [];
let dashboardEvents = [];
let dashboardResources = null;
let patientRecords = [];
let orderRecords = [];
let oieInventory = [];
let oieUnmatchedResults = [];
let selectedOiePatientId = null;
let selectedOiePayload = "";

const VIEW_TITLES = {
  "lab-console-view": "Service Health",
  "patient-view": "Patient",
  "order-view": "Order",
  "oie-view": "OIE",
};

const DASHBOARD_RESOURCE_CONTAINERS = [
  { displayName: "oie-1", aliases: ["oie-1", "oie"] },
  { displayName: "medplum-app-1", aliases: ["medplum-app-1", "medplum-app"] },
  { displayName: "openEMR", aliases: ["openemr-1", "openemr"] },
  { displayName: "dcm4chee-1", aliases: ["dcm4chee-1", "dcm4chee"] },
];

const PATIENT_MODE_CONFIG = {
  "hl7-v2": {
    title: "HL7 v2.3.1 ADT A04",
    payloadTitle: "MSH, EVN, PID, PV1",
    emptyPreview: "Complete required Patient fields to preview an HL7 v2.3.1 ADT A04 payload.",
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

function setStatus(id, message, state = "neutral") {
  const element = byId(id);
  if (!element) return;
  element.textContent = message;
  element.className = `status ${state}`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || response.statusText || "Request failed");
  }
  return payload;
}

function createElement(tag, text = "", className = "") {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function rowCell(content) {
  const cell = document.createElement("td");
  if (content instanceof Node) {
    cell.appendChild(content);
  } else {
    cell.textContent = String(content ?? "");
  }
  return cell;
}

function setActiveView(viewId) {
  document.querySelectorAll(".app-view").forEach((view) => {
    view.hidden = view.id !== viewId;
  });
  document.querySelectorAll(".sidebar-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.navTarget === viewId);
  });
  const title = byId("view-title");
  if (title) title.textContent = VIEW_TITLES[viewId] || "Healthcare Lab";
  if (viewId === "lab-console-view") refreshDashboard();
  if (viewId === "patient-view") {
    refreshPatientPreview();
    refreshPatients();
  }
  if (viewId === "order-view") refreshOrderWorkspace();
  if (viewId === "oie-view") refreshOieInventory();
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

function renderServices() {
  const body = byId("dashboard-service-list");
  const filter = byId("dashboard-filter").value.trim().toLowerCase();
  body.replaceChildren();
  const visible = dashboardServices.filter((service) => {
    const haystack = `${service.label} ${service.protocol} ${service.backend}`.toLowerCase();
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
    const serviceCell = document.createElement("td");
    serviceCell.appendChild(createElement("strong", service.label));
    serviceCell.appendChild(createElement("span", service.protocol, "muted dashboard-cell-subtext"));
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

const patientDemoPreset = {
  mrn: "MRN-A04-001",
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
  address: "100 Main St^^Boston^MA^02110",
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
    address: byId("patient-address").value.trim(),
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
  byId("patient-address").value = payload.address || "";
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
    ["MRN", payload.mrn],
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

function hl7Escape(value) {
  return String(value ?? "")
    .replaceAll("\\", "\\E\\")
    .replaceAll("|", "\\F\\")
    .replaceAll("&", "\\T\\")
    .replaceAll("~", "\\R\\")
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n")
    .replaceAll("\n", "\\.br\\");
}

function hl7EscapeComposite(value) {
  return String(value ?? "").split("^").map(hl7Escape).join("^");
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function hl7Timestamp(date = new Date()) {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join("");
}

function taipeiTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date).replace(",", " TPE");
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
    `MSH|^~\\&|HEALTHCARE_LAB|LAB_DEMO|OIE|ADT|${timestamp}||ADT^A04|A04PREVIEW${timestamp}|P|2.3.1`,
    `EVN|A04|${timestamp}`,
    `PID|1||${hl7Escape(payload.mrn)}^^^HEALTHCARE_LAB^MR||${patientName}||${hl7Escape(payload.dob)}|${hl7Escape(payload.sex)}|||${hl7EscapeComposite(payload.address)}||${hl7Escape(payload.phone)}|||||${hl7Escape(payload.accountNumber)}`,
    `PV1|1|${hl7Escape(payload.patientClass || "O")}|${hl7EscapeComposite(payload.assignedLocation)}||||${hl7EscapeComposite(payload.attendingProvider)}||||||||||||${hl7Escape(visitNumber)}`,
  ].join("\r");
}

function fhirBirthDate(dob) {
  return `${dob.slice(0, 4)}-${dob.slice(4, 6)}-${dob.slice(6)}`;
}

function fhirGender(sex) {
  return { M: "male", F: "female", O: "other", U: "unknown" }[sex] || "unknown";
}

function buildPatientFhirPreviewPayload(payload) {
  const patientName = [payload.firstName, payload.middleName, payload.lastName].filter(Boolean).join(" ");
  return JSON.stringify({
    resourceType: "Patient",
    id: "PAT-GENERATED",
    meta: {
      profile: [
        "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore",
      ],
    },
    identifier: [
      {
        system: "urn:healthcare-lab:mrn",
        value: payload.mrn,
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
    telecom: payload.phone ? [{ system: "phone", value: payload.phone }] : [],
    address: payload.address ? [{ text: payload.address }] : [],
    extension: [
      {
        url: "urn:healthcare-lab:visit-number",
        valueString: payload.visitNumber || "VISIT-GENERATED",
      },
    ],
  }, null, 2);
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
    ["3000", payload.mrn],
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
    "(0010,0020) PatientID": payload.mrn,
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

function renderPatientSummaryFromPayload(payload, createdAt = "") {
  const container = byId("patient-summary");
  container.replaceChildren();
  const rows = [
    ["MRN", payload.mrn],
    ["Name", [payload.firstName, payload.middleName, payload.lastName].filter(Boolean).join(" ")],
    ["DOB", payload.dob],
    ["Sex", payload.sex],
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
    cell.colSpan = 8;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  patientRecords.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    row.append(
      rowCell(item.localPatientNumber || item.id),
      rowCell(item.protocolVersion),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(summary.dob),
      rowCell(summary.sex),
      rowCell(summary.visitNumber),
      rowCell(taipeiTimestamp(item.createdAt)),
    );
    row.addEventListener("click", () => {
      byId("patient-payload-preview").textContent = item.payload || "";
      renderPatientSummaryFromPayload({
        ...(item.patient || {}),
        visitNumber: item.visitNumber,
        patientClass: item.patientClass,
        assignedLocation: item.assignedLocation,
      }, item.createdAt);
    });
    body.appendChild(row);
  });
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
    setStatus("patient-form-status", "Local patient created", "success");
    byId("patient-payload-preview").textContent = item.payload || "";
    renderPatientSummaryFromPayload({
      ...(item.patient || {}),
      visitNumber: item.visitNumber,
      patientClass: item.patientClass,
      assignedLocation: item.assignedLocation,
    }, item.createdAt);
    await refreshPatients();
  } catch (error) {
    setStatus("patient-form-status", "Create failed", "error");
    byId("patient-payload-preview").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function selectedOrderPatient() {
  const selectedId = Number(byId("order-patient")?.value || 0);
  return patientRecords.find((item) => Number(item.id) === selectedId) || null;
}

function orderFormPayload() {
  return {
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

function setOrderForm(payload) {
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
  selector.replaceChildren();
  if (!patientRecords.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Create a patient first";
    selector.appendChild(option);
    selector.disabled = true;
    return;
  }
  selector.disabled = false;
  patientRecords.forEach((item) => {
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
  if (!payload.orderingProvider) messages.push("Ordering provider is required.");
  if (!payload.orderCode) messages.push("Order code is required.");
  if (!payload.alternateCode) messages.push("Alternate code is required.");
  if (payload.requestedAt && !/^\d{8}(\d{4})?(\d{2})?$/.test(payload.requestedAt)) {
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

function buildOrderPreviewPayload(payload, patient) {
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
    `MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|${timestamp}||ORM^O01|ORMPREVIEW${timestamp}|P|2.3.1`,
    `PID|1||${hl7Escape(summary.mrn)}^^^HEALTHCARE_LAB^MR||${patientName}||${hl7Escape(summary.dob)}|${hl7Escape(summary.sex)}|||||||||||${hl7Escape(orderAccountNumber(patient))}`,
    `PV1|1|${hl7Escape(patient?.patientClass || "O")}|${hl7EscapeComposite(patient?.assignedLocation || "")}||||${hl7EscapeComposite(payload.orderingProvider)}||||||||||||${hl7Escape(orderVisitId(patient))}`,
    `ORC|NW|${orderNumber}|||||^^^${hl7Escape(requestedAt)}^${hl7Escape(payload.priority)}||${timestamp}|||${hl7EscapeComposite(payload.orderingProvider)}`,
    `OBR|1|${orderNumber}||${serviceId}|${hl7Escape(payload.priority)}|${hl7Escape(requestedAt)}||||||||${hl7Escape(payload.clinicalIndication)}|||${hl7EscapeComposite(payload.orderingProvider)}`,
  ].join("\r");
}

function renderOrderSummary(payload, patient, createdAt = "") {
  const container = byId("order-summary");
  container.replaceChildren();
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

function refreshOrderPreview() {
  const payload = orderFormPayload();
  const patient = selectedOrderPatient();
  const messages = validateOrderPayload(payload);
  renderOrderValidation(messages);
  renderOrderSummary(payload, patient);
  byId("order-payload-preview").textContent = messages.length
    ? "Complete required Order fields to preview an HL7 v2.3.1 ORM O01 payload."
    : buildOrderPreviewPayload(payload, patient);
}

function renderOrderRecordList() {
  const body = byId("order-record-list");
  body.replaceChildren();
  if (!orderRecords.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local orders created yet.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  orderRecords.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    row.append(
      rowCell(item.localOrderNumber || item.id),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(summary.orderCode),
      rowCell(item.status),
      rowCell(item.requestedAt),
      rowCell(item.createdAt),
    );
    row.addEventListener("click", () => {
      byId("order-payload-preview").textContent = item.payload || "";
      renderOrderSummary({
        priority: item.priority,
        requestedAt: item.requestedAt,
        orderingProvider: item.orderingProvider,
        orderCode: item.orderCode,
        alternateCode: item.alternateCode,
      }, {
        summary: {
          name: summary.name,
          mrn: summary.mrn,
        },
        visitNumber: item.visitId,
      }, item.createdAt);
    });
    body.appendChild(row);
  });
}

async function refreshOrders() {
  try {
    const result = await requestJson("/api/orders");
    orderRecords = result.items || [];
    renderOrderRecordList();
  } catch (error) {
    setStatus("order-form-status", "Refresh failed", "error");
  }
}

async function refreshOrderWorkspace() {
  await refreshPatients();
  await refreshOrders();
  refreshOrderPreview();
}

async function createOrderRecord() {
  const button = byId("create-order");
  button.disabled = true;
  setStatus("order-form-status", "Creating...", "pending");
  try {
    const result = await requestJson("/api/orders", {
      method: "POST",
      body: JSON.stringify(orderFormPayload()),
    });
    const item = result.item;
    setStatus("order-form-status", "Local order created", "success");
    byId("order-payload-preview").textContent = item.payload || "";
    await refreshOrders();
  } catch (error) {
    setStatus("order-form-status", "Create failed", "error");
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
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    selectedOiePatientId = null;
    byId("oie-selected-patient-title").textContent = "No patient selected";
    byId("oie-payload-preview").textContent = "Create a local Patient A04 record to inspect it here.";
    return;
  }
  if (!selectedOiePatientId || !oieInventory.some((item) => Number(item.id) === Number(selectedOiePatientId))) {
    selectedOiePatientId = oieInventory[0].id;
  }
  oieInventory.forEach((item) => {
    const row = document.createElement("tr");
    row.classList.toggle("selected-row", Number(item.id) === Number(selectedOiePatientId));
    const summary = item.summary || {};
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
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(item.orderCount ?? 0),
      rowCell(item.resultCount ?? 0),
    );
    row.addEventListener("click", selectPayload);
    body.appendChild(row);
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
  byId("oie-selected-patient-title").textContent = patient
    ? `${patient.summary?.mrn || patient.id} - ${patient.summary?.name || "Patient"}`
    : "No patient selected";
  renderOieOrders(patient?.orders || []);
  renderOieResults(patient?.results || []);
}

function renderOieOrders(orders) {
  const body = byId("oie-order-list");
  body.replaceChildren();
  if (!orders.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local ORM O01 orders for this patient.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  orders.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    const previewButton = createElement("button", "Preview", "small-button");
    previewButton.type = "button";
    const sendButton = createElement("button", "Send", "small-button");
    sendButton.type = "button";
    previewButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieOrder(item);
    });
    sendButton.addEventListener("click", (event) => {
      event.stopPropagation();
      sendOieOrder(item.id, sendButton);
    });
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.append(previewButton, sendButton);
    row.append(
      rowCell(item.localOrderNumber || item.id),
      rowCell(summary.orderCode),
      rowCell(item.priority),
      rowCell(item.status || "Ready to send"),
      rowCell(item.ack?.code || item.transportError || "-"),
      rowCell(taipeiTimestamp(item.lastSentAt)),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectOieOrder(item));
    body.appendChild(row);
  });
}

function selectOieOrder(item) {
  selectedOiePayload = item.payload || "";
  byId("oie-payload-preview").textContent = selectedOiePayload;
  byId("oie-ack-preview").textContent = ackPreviewText(item);
  renderOiePreviewSummary("ORM", [
    ["Order", item.localOrderNumber],
    ["Code", item.summary?.orderCode],
    ["Status", item.status],
    ["ACK", item.ack?.code || item.transportError || "-"],
  ]);
}

function renderOieResults(results) {
  const body = byId("oie-result-list");
  body.replaceChildren();
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No ORU results for this patient.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
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
    body.appendChild(row);
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
  } catch (error) {
    setStatus("oie-inventory-status", "Send failed", "error");
    if (!byId("oie-ack-preview").textContent.trim()) {
      byId("oie-ack-preview").textContent = error.message;
    }
  } finally {
    button.disabled = false;
    await refreshOieInventory();
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

async function copyTextFromElement(elementId) {
  const text = byId(elementId).textContent || "";
  if (!text.trim()) return;
  await navigator.clipboard.writeText(text);
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-nav-target]").forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.navTarget));
  });
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
  byId("refresh-order-preview").addEventListener("click", refreshOrderPreview);
  byId("create-order").addEventListener("click", createOrderRecord);
  byId("refresh-orders").addEventListener("click", refreshOrders);
  byId("copy-order-payload").addEventListener("click", () => copyTextFromElement("order-payload-preview"));
  byId("refresh-oie-inventory").addEventListener("click", refreshOieInventory);
  byId("copy-oie-payload").addEventListener("click", () => copyTextFromElement("oie-payload-preview"));
  byId("start-oie-listener").addEventListener("click", startOieListener);
  byId("stop-oie-listener").addEventListener("click", stopOieListener);
  setActiveView("lab-console-view");
});
