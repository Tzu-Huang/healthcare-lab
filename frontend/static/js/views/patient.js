import {
  fhirBirthDate,
  fhirGender,
  hl7Escape,
  hl7EscapeComposite,
  hl7Timestamp,
} from "../core/formatting.js";
import { byId, createElement } from "../core/dom.js";

const GENERATED_PATIENT_MRN_LABEL = "Generated on create";

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
