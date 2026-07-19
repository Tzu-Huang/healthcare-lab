import {
  fhirBirthDate,
  fhirGender,
  hl7Escape,
  hl7EscapeComposite,
  hl7Timestamp,
} from "../core/formatting.js";

const GENERATED_PATIENT_MRN_LABEL = "Generated on create";

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
