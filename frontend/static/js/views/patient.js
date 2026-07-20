import {
  fhirBirthDate,
  fhirGender,
  hl7Escape,
  hl7EscapeComposite,
  hl7Timestamp,
  taipeiTimestamp,
} from "../core/formatting.js";
import { byId, createElement, rowCell } from "../core/dom.js";
import { setStatus } from "../components/status.js";
import {
  createPatient,
  fetchPatients,
  refreshPatientDcm4cheeResults as refreshPatientDcm4cheeResultsRequest,
  retryPatientFhirSync as retryPatientFhirSyncRequest,
} from "../api/patient.js";
import { getPatientRecords, replacePatientRecord, setPatientRecords } from "../state/patient.js";
import { getSelectedPatientId, setSelectedOrderId, setSelectedPatientId } from "../state/selection.js";

const GENERATED_PATIENT_MRN_LABEL = "Generated on create";
let patientCoordinator = {};
let initialized = false;

export const PATIENT_MODE_CONFIG = {
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

const patientDemoPreset = {
  mrn: "", firstName: "Avery", middleName: "Lee", lastName: "Morgan", dob: "19850412", sex: "F",
  visitNumber: "", patientClass: "O", assignedLocation: "CARDIOLOGY^ROOM1",
  attendingProvider: "P123^Rivera^Elena", accountNumber: "ACC-1001", phone: "555-0100",
  email: "avery.morgan@example.org", address: "100 Main St^^Boston^MA^02110", active: true,
  addressLine: "", addressCity: "", addressState: "", addressPostalCode: "", addressCountry: "",
  managingOrganizationReference: "", managingOrganizationDisplay: "",
};

const patientDemoModeOverrides = {
  "hl7-v2": {
    assignedLocation: "CARDIOLOGY^ROOM1", attendingProvider: "P123^Rivera^Elena",
    accountNumber: "ACC-1001", address: "100 Main St^^Boston^MA^02110",
  },
  fhir: {
    assignedLocation: "", attendingProvider: "", accountNumber: "", address: "100 Main St, Boston, MA 02110",
    addressLine: "100 Main St", addressCity: "Boston", addressState: "MA", addressPostalCode: "02110",
    addressCountry: "US", managingOrganizationReference: "Organization/healthcare-lab",
    managingOrganizationDisplay: "Healthcare Lab",
  },
  gdt: { assignedLocation: "", attendingProvider: "", accountNumber: "", address: "100 Main St, Boston, MA 02110" },
  dicom: { assignedLocation: "", attendingProvider: "", accountNumber: "", address: "100 Main St, Boston, MA 02110" },
};

export function patientDemoPresetForMode(mode) {
  const normalizedMode = PATIENT_MODE_CONFIG[mode] ? mode : "hl7-v2";
  return { ...patientDemoPreset, ...(patientDemoModeOverrides[normalizedMode] || {}), mode: normalizedMode };
}

export function patientFormPayload() {
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

export function setPatientForm(payload) {
  const values = {
    "patient-mode": payload.mode || "hl7-v2", "patient-mrn": payload.mrn || "",
    "patient-first-name": payload.firstName || "", "patient-middle-name": payload.middleName || "",
    "patient-last-name": payload.lastName || "", "patient-dob": payload.dob || "",
    "patient-sex": payload.sex || "F", "patient-visit-number": payload.visitNumber || "",
    "patient-class": payload.patientClass || "O", "patient-assigned-location": payload.assignedLocation || "",
    "patient-attending-provider": payload.attendingProvider || "", "patient-account-number": payload.accountNumber || "",
    "patient-phone": payload.phone || "", "patient-email": payload.email || "", "patient-address": payload.address || "",
    "patient-active": payload.active === false ? "false" : "true", "patient-address-line": payload.addressLine || "",
    "patient-address-city": payload.addressCity || "", "patient-address-state": payload.addressState || "",
    "patient-address-postal-code": payload.addressPostalCode || "", "patient-address-country": payload.addressCountry || "",
    "patient-managing-organization-reference": payload.managingOrganizationReference || "",
    "patient-managing-organization-display": payload.managingOrganizationDisplay || "",
  };
  Object.entries(values).forEach(([id, value]) => { byId(id).value = value; });
}

export function updatePatientModeFields(mode) {
  const config = PATIENT_MODE_CONFIG[mode] || PATIENT_MODE_CONFIG["hl7-v2"];
  byId("patient-mode-title").textContent = config.title;
  byId("patient-payload-title").textContent = config.payloadTitle;
  document.querySelectorAll("[data-patient-mode-field]").forEach((element) => {
    const modes = String(element.dataset.patientModeField || "").split(/\s+/);
    element.hidden = !modes.includes(mode);
  });
}

export function validatePatientPayload(payload) {
  const messages = [];
  [["First name", payload.firstName], ["Last name", payload.lastName], ["DOB", payload.dob], ["Sex", payload.sex]]
    .forEach(([label, value]) => { if (!String(value || "").trim()) messages.push(`${label} is required.`); });
  if (payload.dob && !/^\d{8}$/.test(payload.dob)) messages.push("DOB must be YYYYMMDD.");
  if (payload.sex && !["M", "F", "O", "U"].includes(payload.sex)) messages.push("Sex must be M, F, O, or U.");
  return messages;
}

export function renderPatientValidation(messages) {
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

export function patientStateLabel(item) {
  if (item.protocolVersion === "FHIR R4") {
    const syncStatus = item.fhir?.sync?.status || "";
    const reference = item.fhir?.medplum?.reference || "";
    return syncStatus === "Synced" && /^Patient\/[^/]+$/.test(reference) ? "OK" : "Error";
  }
  if (item.protocolVersion === "DICOM") {
    const patient = item.dcm4chee?.patient || {};
    const syncStatus = patient.displayStatus || patient.status || "";
    return syncStatus === "Synced" && patient.ack?.code === "AA" ? "OK" : "Error";
  }
  const messages = Array.isArray(item.validation?.messages) ? item.validation.messages : [];
  return messages.length ? "Error" : "OK";
}

export function renderPatientRecordList(records, { onSelect } = {}) {
  const body = byId("patient-record-list");
  body.replaceChildren();
  if (!records.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local patients created yet.");
    cell.colSpan = 9;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  records.forEach((item) => {
    const summary = item.summary || {};
    const stateLabel = patientStateLabel(item);
    const stateClass = stateLabel === "OK" ? "success" : stateLabel === "Error" ? "error" : "neutral";
    const row = document.createElement("tr");
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
    if (onSelect) row.addEventListener("click", () => onSelect(item));
    body.appendChild(row);
  });
}

export function renderPatientSummaryFromPayload(
  payload,
  createdAt = "",
  dcm4cheePatient = null,
  { renderDetailBlock } = {},
) {
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
  if (dcm4cheePatient && renderDetailBlock) {
    container.appendChild(renderDetailBlock("dcm4chee Patient", [
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

export function refreshPatientPreview() {
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

export function initializePatientView({ onCreate, onRefresh, onCopy }) {
  if (initialized) return;
  initialized = true;
  byId("load-patient-demo").addEventListener("click", () => {
    setPatientForm(patientDemoPresetForMode(byId("patient-mode").value));
    refreshPatientPreview();
  });
  document.querySelectorAll("#patient-view input, #patient-view select").forEach((element) => {
    element.addEventListener("input", refreshPatientPreview);
    element.addEventListener("change", refreshPatientPreview);
  });
  byId("refresh-patient-preview").addEventListener("click", refreshPatientPreview);
  byId("create-patient").addEventListener("click", onCreate);
  byId("refresh-patients").addEventListener("click", onRefresh);
  byId("copy-patient-payload").addEventListener("click", onCopy);
}

export function configurePatientCoordinator(coordinator = {}) {
  patientCoordinator = coordinator;
}

function renderPatientRecords() {
  renderPatientRecordList(getPatientRecords(), { onSelect: patientCoordinator.onSelectRecord });
}

export async function refreshPatients() {
  try {
    const result = await fetchPatients();
    setPatientRecords(result.items || []);
    renderPatientRecords();
    patientCoordinator.renderOrderPatientOptions?.();
  } catch (_error) {
    setStatus("patient-form-status", "Refresh failed", "error");
  }
}

export async function createPatientRecord() {
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
    }, item.createdAt, item.dcm4chee?.patient || null, {
      renderDetailBlock: patientCoordinator.renderDetailBlock,
    });
    await refreshPatients();
  } catch (error) {
    setStatus("patient-form-status", "Create failed", "error");
    byId("patient-payload-preview").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

export async function retryPatientFhirSync(patientId, button) {
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

export async function refreshPatientDcm4cheeResults(patientId, button, options = {}) {
  if (button) button.disabled = true;
  setStatus("patient-form-status", "Refreshing dcm4chee results...", "pending");
  if (options.orderId) setStatus("order-form-status", "Refreshing PACS results...", "pending");
  try {
    const result = await refreshPatientDcm4cheeResultsRequest(patientId);
    const patient = result.patient || {};
    replacePatientRecord(patient);
    setSelectedPatientId(patient.id || getSelectedPatientId());
    renderPatientRecords();
    byId("patient-payload-preview").textContent = patient.payload || "";
    patientCoordinator.onSelectRecord?.(patient);
    patientCoordinator.renderDcm4cheeConsole?.();
    const count = (patient.dcm4chee?.dicomResults || []).length;
    setStatus("patient-form-status", `dcm4chee results refreshed (${count})`, result.success ? "success" : "warning");
    if (options.orderId) {
      setSelectedOrderId(options.orderId);
      setStatus("order-form-status", `PACS results refreshed (${count})`, result.success ? "success" : "warning");
      await patientCoordinator.refreshOrders?.();
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

export function patientPreviewMrn(payload) {
  return String(payload?.mrn || "").trim() || GENERATED_PATIENT_MRN_LABEL;
}

export function buildPatientPreviewPayload(payload) {
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

export function buildPatientFhirPreviewPayload(payload) {
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
      profile: ["https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"],
    },
    identifier: [{ system: "urn:healthcare-lab:mrn", value: patientPreviewMrn(payload) }],
    name: [{
      use: "official",
      text: patientName,
      family: payload.lastName,
      given: [payload.firstName, payload.middleName].filter(Boolean),
    }],
    gender: fhirGender(payload.sex),
    birthDate: fhirBirthDate(payload.dob),
    telecom,
    address: Object.keys(address).length ? [address] : [],
    extension: [{
      url: "urn:healthcare-lab:visit-number",
      valueString: payload.visitNumber || "VISIT-GENERATED",
    }],
  };
  if (Object.keys(managingOrganization).length) resource.managingOrganization = managingOrganization;
  return JSON.stringify(resource, null, 2);
}

function renderGdtRecord(code, value) {
  const fieldCode = String(code || "").trim();
  const content = String(value ?? "").trim().replace(/[\r\n]+/g, " ");
  const length = 3 + 4 + content.length + 2;
  return `${String(length).padStart(3, "0")}${fieldCode}${content}\r\n`;
}

function renderGdtPatientMessage(records) {
  let totalLength = "00000";
  for (let index = 0; index < 8; index += 1) {
    const lines = [["8000", "6301"], ["8100", totalLength], ["9218", "02.10"], ["9206", "3"], ...records];
    const payload = lines.map(([code, value]) => renderGdtRecord(code, value)).join("");
    const nextLength = String(payload.length).padStart(5, "0");
    if (nextLength === totalLength) return payload;
    totalLength = nextLength;
  }
  return "";
}

export function buildPatientGdtPreviewPayload(payload) {
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
  return renderGdtPatientMessage(records);
}

export function buildPatientDicomPreviewPayload(payload) {
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
