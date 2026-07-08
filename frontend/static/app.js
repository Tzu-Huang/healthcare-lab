const byId = (id) => document.getElementById(id);

let dashboardServices = [];
let dashboardEvents = [];
let dashboardResources = null;
let patientRecords = [];
let orderRecords = [];
let gdtOrderRecords = [];
let gdtWorkbench = { patients: [], bridgeInbox: [] };
let gdtBridgeConfig = null;
let selectedGdtPatientId = null;
let expandedGdtPatientIds = new Set();
let selectedGdtPayload = "";
let selectedGdtPatientRawPreview = { patientId: null, payload: "" };
let oieInventory = [];
let oieUnmatchedResults = [];
let selectedOiePatientId = null;
let selectedOiePayload = "";
let medplumInventory = [];
let medplumPatients = [];
let medplumResourceTypes = [];
let selectedMedplumRecordId = null;

const VIEW_TITLES = {
  "lab-console-view": "Service Health",
  "patient-view": "Patient",
  "medplum-view": "Medplum",
  "order-view": "Order",
  "oie-view": "OIE",
  "gdt-view": "GDT",
};

const MEDPLUM_SOURCE_LABELS = {
  "medplum-live": "Medplum live JSON",
  "local-submitted": "Local submitted JSON",
  "local-submitted-fallback": "Live fetch failed; local submitted JSON",
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

const ORDER_MODE_CONFIG = {
  "hl7-v231": {
    title: "HL7 v2.3.1 ORM O01",
    payloadTitle: "MSH, PID, PV1, ORC, OBR",
    emptyPreview: "Select a local patient to preview an HL7 v2.3.1 ORM O01 payload.",
    createLabel: "Create Order",
  },
  gdt: {
    title: "GDT ECG Order",
    payloadTitle: "GDT-OUT with 8402=EKG01",
    emptyPreview: "Select or create a local patient to preview a GDT ECG order payload.",
    createLabel: "Create GDT Order",
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
  if (viewId === "medplum-view") refreshMedplumInventory();
  if (viewId === "order-view") refreshOrderWorkspace();
  if (viewId === "oie-view") refreshOieInventory();
  if (viewId === "gdt-view") refreshGdtConsole();
}

function currentOrderMode() {
  const selector = byId("order-protocol");
  return ORDER_MODE_CONFIG[selector?.value] ? selector.value : "hl7-v231";
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
    if (service.id === "openemr-gdt") {
      const orderButton = document.createElement("button");
      orderButton.type = "button";
      orderButton.textContent = "ECG Order";
      orderButton.addEventListener("click", openGdtOrderFlow);
      actions.appendChild(orderButton);
    }
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

function gdtTaipeiTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date).reduce((acc, part) => {
    acc[part.type] = part.value;
    return acc;
  }, {});
  return `${parts.year}-${parts.month}-${parts.day} TPE ${parts.hour}:${parts.minute}:${parts.second}`;
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
    cell.colSpan = 11;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  patientRecords.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    const fhir = item.fhir || null;
    const syncStatus = fhir?.sync?.status || (item.protocolVersion === "FHIR R4" ? "Pending sync" : "-");
    const syncLabel = createElement("span", syncStatus, `status ${fhirSyncStatusClass(syncStatus)}`);
    const actionCell = document.createElement("div");
    actionCell.className = "button-row compact-actions";
    if (item.protocolVersion === "FHIR R4" && fhir?.recordId && syncStatus !== "Synced") {
      const retryButton = createElement("button", "Retry", "");
      retryButton.type = "button";
      retryButton.addEventListener("click", (event) => {
        event.stopPropagation();
        retryPatientFhirSync(item.id, retryButton);
      });
      actionCell.appendChild(retryButton);
    } else {
      actionCell.appendChild(createElement("span", "-", "muted"));
    }
    row.append(
      rowCell(item.localPatientNumber || item.id),
      rowCell(item.protocolVersion),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(summary.dob),
      rowCell(summary.sex),
      rowCell(summary.visitNumber),
      rowCell(syncLabel),
      rowCell(fhir?.medplum?.reference || fhir?.sync?.error || "-"),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(actionCell),
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
    const syncStatus = item.fhir?.sync?.status || "";
    setStatus(
      "patient-form-status",
      syncStatus === "Synced" ? "FHIR patient synced" : "Local patient created",
      syncStatus === "Sync failed" ? "warning" : "success",
    );
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

function medplumSourceLabel(source) {
  return MEDPLUM_SOURCE_LABELS[source] || source || "Unknown source";
}

function medplumPatientLabel(patient) {
  const identifier = patient?.identifier?.value || patient?.localFhirRecordNumber || `FHIR-${patient?.id}`;
  const reference = patient?.reference || patient?.medplum?.reference || "No Medplum reference";
  return `${identifier} | ${reference}`;
}

function selectedMedplumPatient() {
  const selectedId = Number(byId("medplum-patient-filter")?.value || 0);
  return medplumPatients.find((item) => Number(item.id) === selectedId) || null;
}

function medplumRecordMatchesPatient(item, patient) {
  if (!patient) return true;
  if (item.resourceType === "Patient") return Number(item.id) === Number(patient.id);
  const reference = patient.reference || patient.medplum?.reference || "";
  return Boolean(reference && (item.patientReferences || []).includes(reference));
}

function filteredMedplumInventory() {
  const patient = selectedMedplumPatient();
  const resourceType = byId("medplum-resource-filter")?.value || "";
  const syncStatus = byId("medplum-sync-filter")?.value || "";
  return medplumInventory.filter((item) => {
    if (resourceType && item.resourceType !== resourceType) return false;
    if (syncStatus && item.sync?.status !== syncStatus) return false;
    return medplumRecordMatchesPatient(item, patient);
  });
}

function renderMedplumFilters() {
  const patientFilter = byId("medplum-patient-filter");
  const selectedPatientId = patientFilter.value;
  patientFilter.replaceChildren();
  patientFilter.appendChild(new Option("All patients", ""));
  medplumPatients.forEach((patient) => {
    patientFilter.appendChild(new Option(medplumPatientLabel(patient), String(patient.id)));
  });
  if ([...patientFilter.options].some((option) => option.value === selectedPatientId)) {
    patientFilter.value = selectedPatientId;
  }

  const resourceFilter = byId("medplum-resource-filter");
  const selectedResourceType = resourceFilter.value;
  resourceFilter.replaceChildren();
  resourceFilter.appendChild(new Option("All supported resources", ""));
  medplumResourceTypes.forEach((resourceType) => {
    resourceFilter.appendChild(new Option(resourceType, resourceType));
  });
  if ([...resourceFilter.options].some((option) => option.value === selectedResourceType)) {
    resourceFilter.value = selectedResourceType;
  }
}

function renderMedplumInventory() {
  renderMedplumFilters();
  const body = byId("medplum-resource-list");
  const visible = filteredMedplumInventory();
  body.replaceChildren();
  if (!visible.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No FHIR resources match the current filters.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  visible.forEach((item) => {
    const row = document.createElement("tr");
    row.className = Number(item.id) === Number(selectedMedplumRecordId) ? "selected-row" : "";
    row.addEventListener("click", () => loadMedplumPreview(item.id));
    const status = item.sync?.status || "-";
    const source = item.previewSource || "local-submitted";
    const actionCell = document.createElement("div");
    actionCell.className = "button-row compact-actions";
    if (item.retryable) {
      const retryButton = createElement("button", "Retry", "");
      retryButton.type = "button";
      retryButton.addEventListener("click", (event) => {
        event.stopPropagation();
        retryMedplumRecord(item.id, retryButton);
      });
      actionCell.appendChild(retryButton);
    } else {
      actionCell.appendChild(createElement("span", "-", "muted"));
    }
    row.append(
      rowCell(item.localFhirRecordNumber || item.id),
      rowCell(item.resourceType),
      rowCell(createElement("span", status, `status ${fhirSyncStatusClass(status)}`)),
      rowCell(item.medplum?.reference || item.sync?.error || "-"),
      rowCell(medplumSourceLabel(source)),
      rowCell(taipeiTimestamp(item.updatedAt)),
      rowCell(actionCell),
    );
    body.appendChild(row);
  });
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
    renderMedplumInventory();
    setStatus("medplum-inventory-status", "Inventory loaded", "success");
  } catch (error) {
    setStatus("medplum-inventory-status", error.message, "error");
  }
}

async function loadMedplumPreview(recordId) {
  selectedMedplumRecordId = recordId;
  renderMedplumInventory();
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

function selectedOrderPatient() {
  const selectedId = Number(byId("order-patient")?.value || 0);
  return patientRecords.find((item) => Number(item.id) === selectedId) || null;
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
  if (payload.mode !== "gdt") {
    if (!payload.orderingProvider) messages.push("Ordering provider is required.");
    if (!payload.orderCode) messages.push("Order code is required.");
    if (!payload.alternateCode) messages.push("Alternate code is required.");
  }
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

function buildOrderPreviewPayload(payload, patient) {
  if (payload.mode === "gdt") return buildGdtOrderPreviewPayload(payload, patient);
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
  const mode = currentOrderMode();
  const records = mode === "gdt" ? gdtOrderRecords : orderRecords;
  body.replaceChildren();
  if (!records.length) {
    const row = document.createElement("tr");
    const cell = rowCell(mode === "gdt" ? "No local GDT ECG orders created yet." : "No local orders created yet.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  records.forEach((item) => {
    const row = document.createElement("tr");
    const summary = item.summary || {};
    const orderNumber = mode === "gdt" ? item.localGdtOrderNumber : item.localOrderNumber;
    const orderCode = mode === "gdt" ? summary.testCode : summary.orderCode;
    row.append(
      rowCell(orderNumber || item.id),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(orderCode),
      rowCell(item.status),
      rowCell(item.requestedAt),
      rowCell(item.createdAt),
    );
    row.addEventListener("click", () => {
      byId("order-payload-preview").textContent = item.payload || "";
      renderOrderSummary({
        mode,
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
    if (currentOrderMode() === "gdt") {
      const result = await requestJson("/api/gdt/orders");
      gdtOrderRecords = result.items || [];
    } else {
      const result = await requestJson("/api/orders");
      orderRecords = result.items || [];
    }
    renderOrderRecordList();
  } catch (error) {
    setStatus("order-form-status", "Refresh failed", "error");
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
    setStatus("order-form-status", mode === "gdt" ? "GDT ECG order created" : "Local order created", "success");
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
    ["Outbox", item.outboxPath],
    ["Inbound", item.inboundPath],
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
    const cell = rowCell("No inbound GDT files found.");
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
  byId("refresh-medplum-inventory").addEventListener("click", refreshMedplumInventory);
  byId("medplum-patient-filter").addEventListener("change", renderMedplumInventory);
  byId("medplum-resource-filter").addEventListener("change", renderMedplumInventory);
  byId("medplum-sync-filter").addEventListener("change", renderMedplumInventory);
  byId("copy-medplum-json").addEventListener("click", () => copyTextFromElement("medplum-json-preview"));
  byId("refresh-order-preview").addEventListener("click", refreshOrderPreview);
  byId("create-gdt-patient").addEventListener("click", createGdtPatientFromOrderFlow);
  byId("create-order").addEventListener("click", createOrderRecord);
  byId("refresh-orders").addEventListener("click", refreshOrders);
  byId("copy-order-payload").addEventListener("click", () => copyTextFromElement("order-payload-preview"));
  byId("refresh-oie-inventory").addEventListener("click", refreshOieInventory);
  byId("copy-oie-payload").addEventListener("click", () => copyTextFromElement("oie-payload-preview"));
  byId("start-oie-listener").addEventListener("click", startOieListener);
  byId("stop-oie-listener").addEventListener("click", stopOieListener);
  byId("refresh-gdt-console").addEventListener("click", refreshGdtConsole);
  byId("refresh-gdt-bridge-config").addEventListener("click", refreshGdtBridgeConfig);
  byId("save-gdt-bridge-config").addEventListener("click", saveGdtBridgeConfig);
  byId("start-gdt-watcher").addEventListener("click", startGdtWatcher);
  byId("stop-gdt-watcher").addEventListener("click", stopGdtWatcher);
  byId("copy-gdt-payload").addEventListener("click", () => copyTextFromElement("gdt-payload-preview"));
  setActiveView("lab-console-view");
});
