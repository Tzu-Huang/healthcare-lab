import { createElement, byId } from "../core/dom.js";
import { hl7Escape, hl7EscapeComposite, hl7Timestamp, localDatetimeValue } from "../core/formatting.js";
import { getPatientRecords } from "../state/patient.js";
import { getSelectedPatientId, setSelectedPatientId } from "../state/selection.js";

export const ORDER_MODE_CONFIG = {
  "hl7-v251": { title: "HL7 v2.5.1 ORM O01", payloadTitle: "MSH, PID, PV1, ORC, OBR", emptyPreview: "Select a local patient to preview an HL7 v2.5.1 ORM O01 payload.", createLabel: "Create Order" },
  fhir: { title: "FHIR R4 ServiceRequest", payloadTitle: "ServiceRequest resource JSON", emptyPreview: "Select a synced FHIR Patient to preview a ServiceRequest resource.", createLabel: "Create FHIR Order" },
  gdt: { title: "GDT ECG Order", payloadTitle: "GDT-OUT with 8402=EKG01", emptyPreview: "Select or create a local patient to preview a GDT ECG order payload.", createLabel: "Create GDT Order" },
  dicom: { title: "DICOM MWL Order", payloadTitle: "DICOM JSON MWL item", emptyPreview: "Select a local patient to preview a DICOM MWL payload.", createLabel: "Create DICOM MWL Order" },
};

const ORDER_PATIENT_PROTOCOL_BY_MODE = { "hl7-v251": "HL7 v2.5.1", fhir: "FHIR R4", gdt: "GDT 2.1", dicom: "DICOM" };
const ORDER_PATIENT_LABEL_BY_MODE = { "hl7-v251": "HL7 v2", fhir: "FHIR R4", gdt: "GDT", dicom: "DICOM" };
let orderCoordinator = {};

export const orderDemoPreset = {
  priority: "R", orderingProvider: "1001^WANG^AMY", clinicalIndication: "Chest pain evaluation",
  orderCode: "ECG12", orderCodeText: "12 Lead ECG", alternateCode: "93000",
  alternateCodeText: "Electrocardiogram, routine ECG with at least 12 leads", alternateCodeSystem: "C4",
};

export function currentOrderMode() {
  const selector = byId("order-protocol");
  return ORDER_MODE_CONFIG[selector?.value] ? selector.value : "hl7-v251";
}

export function orderPatientProtocolForMode(mode = currentOrderMode()) {
  return ORDER_PATIENT_PROTOCOL_BY_MODE[mode] || ORDER_PATIENT_PROTOCOL_BY_MODE["hl7-v251"];
}

export function orderPatientModeLabel(mode = currentOrderMode()) {
  return ORDER_PATIENT_LABEL_BY_MODE[mode] || ORDER_PATIENT_LABEL_BY_MODE["hl7-v251"];
}

export function orderPatientRecordsForMode(mode = currentOrderMode()) {
  const protocolVersion = orderPatientProtocolForMode(mode);
  return getPatientRecords().filter((item) => item.protocolVersion === protocolVersion);
}

export function selectedOrderPatient() {
  const selectedId = Number(byId("order-patient")?.value || 0);
  return getPatientRecords().find((item) => Number(item.id) === selectedId) || null;
}

export function selectedOrderPatientReference() {
  return selectedOrderPatient()?.fhir?.medplum?.reference || "";
}

export function renderOrderPatientOptions() {
  const selector = byId("order-patient");
  if (!selector) return;
  const current = selector.value || String(getSelectedPatientId() || "");
  const mode = currentOrderMode();
  const records = orderPatientRecordsForMode(mode);
  selector.replaceChildren();
  if (!getPatientRecords().length || !records.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = getPatientRecords().length ? `Create a ${orderPatientModeLabel(mode)} patient first` : "Create a patient first";
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
  if ([...selector.options].some((option) => option.value === current)) selector.value = current;
  setSelectedPatientId(Number(selector.value || 0) || null);
}

export function updateOrderModeFields() {
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

function fhirOrderField(id) {
  return byId(id)?.value.trim() || "";
}

export function fhirOrderPayload() {
  const asNeeded = fhirOrderField("fhir-as-needed-boolean");
  const payload = {
    resourceType: "ServiceRequest", id: fhirOrderField("fhir-service-request-id"), identifier: fhirOrderField("fhir-identifier"),
    identifierSystem: fhirOrderField("fhir-identifier-system"), identifierValue: fhirOrderField("fhir-identifier-value"),
    instantiatesCanonical: fhirOrderField("fhir-instantiates-canonical"), instantiatesUri: fhirOrderField("fhir-instantiates-uri"),
    basedOn: fhirOrderField("fhir-based-on"), replaces: fhirOrderField("fhir-replaces"), requisitionSystem: fhirOrderField("fhir-requisition-system"),
    requisitionValue: fhirOrderField("fhir-requisition-value"), status: fhirOrderField("fhir-status") || "active", intent: fhirOrderField("fhir-intent") || "order",
    category: fhirOrderField("fhir-category"), priority: fhirOrderField("fhir-priority") || "routine", doNotPerform: fhirOrderField("fhir-do-not-perform") === "true",
    codeSystem: fhirOrderField("fhir-code-system"), codeCode: fhirOrderField("fhir-code-code"), codeDisplay: fhirOrderField("fhir-code-display"),
    orderDetail: fhirOrderField("fhir-order-detail"), quantityValue: fhirOrderField("fhir-quantity-value"), quantityUnit: fhirOrderField("fhir-quantity-unit"),
    subject: selectedOrderPatientReference(), encounter: fhirOrderField("fhir-encounter"), occurrenceDateTime: fhirOrderField("fhir-occurrence"),
    asNeededCodeText: fhirOrderField("fhir-as-needed-code-text"), authoredOn: fhirOrderField("fhir-authored-on"), requester: fhirOrderField("fhir-requester"),
    performerType: fhirOrderField("fhir-performer-type"), performer: fhirOrderField("fhir-performer"), locationCode: fhirOrderField("fhir-location-code"),
    locationReference: fhirOrderField("fhir-location-reference"), reasonCodeText: fhirOrderField("fhir-reason-code-text"), reasonReference: fhirOrderField("fhir-reason-reference"),
    insurance: fhirOrderField("fhir-insurance"), supportingInfo: fhirOrderField("fhir-supporting-info"), specimen: fhirOrderField("fhir-specimen"),
    bodySite: fhirOrderField("fhir-body-site"), note: fhirOrderField("fhir-note"), patientInstruction: fhirOrderField("fhir-patient-instruction"),
    relevantHistory: fhirOrderField("fhir-relevant-history"),
  };
  if (asNeeded) payload.asNeededBoolean = asNeeded === "true";
  return payload;
}

export function orderFormPayload() {
  const mode = currentOrderMode();
  const patientRecordId = Number(byId("order-patient").value || 0);
  if (mode === "gdt") return { mode, patientRecordId, requestedAt: byId("order-requested-at").value.trim(), orderingProvider: byId("order-provider").value.trim(), clinicalIndication: byId("order-indication").value.trim(), attachmentUrl: byId("gdt-attachment-url").value.trim(), gdtTestCode: "EKG01" };
  if (mode === "fhir") {
    const fhir = fhirOrderPayload();
    return { mode, patientRecordId, priority: fhir.priority, requestedAt: fhir.occurrenceDateTime, orderingProvider: fhir.requester, clinicalIndication: fhir.reasonCodeText, orderCode: fhir.codeCode, orderCodeText: fhir.codeDisplay, alternateCode: orderDemoPreset.alternateCode, alternateCodeText: orderDemoPreset.alternateCodeText, alternateCodeSystem: orderDemoPreset.alternateCodeSystem, fhir };
  }
  return { mode, patientRecordId, priority: byId("order-priority").value, requestedAt: byId("order-requested-at").value.trim(), orderingProvider: byId("order-provider").value.trim(), clinicalIndication: byId("order-indication").value.trim(), orderCode: byId("order-code").value.trim(), orderCodeText: orderDemoPreset.orderCodeText, alternateCode: byId("order-alternate-code").value.trim(), alternateCodeText: orderDemoPreset.alternateCodeText, alternateCodeSystem: orderDemoPreset.alternateCodeSystem };
}

export function setFhirOrderForm(payload) {
  const setValue = (id, value) => { const element = byId(id); if (element) element.value = value || ""; };
  const values = { "fhir-status": payload.status || "active", "fhir-intent": payload.intent || "order", "fhir-category": payload.category || "Procedure", "fhir-priority": payload.priority || "routine", "fhir-do-not-perform": payload.doNotPerform || "false", "fhir-code-system": payload.codeSystem || "urn:healthcare-lab:service-code", "fhir-code-code": payload.codeCode || orderDemoPreset.orderCode, "fhir-code-display": payload.codeDisplay || orderDemoPreset.orderCodeText, "fhir-reason-code-text": payload.reasonCodeText, "fhir-requester": payload.requester, "fhir-performer-type": payload.performerType, "fhir-location-code": payload.locationCode, "fhir-quantity-value": payload.quantityValue, "fhir-quantity-unit": payload.quantityUnit, "fhir-note": payload.note, "fhir-patient-instruction": payload.patientInstruction };
  Object.entries(values).forEach(([id, value]) => setValue(id, value));
  if (!fhirOrderField("fhir-occurrence")) setValue("fhir-occurrence", localDatetimeValue());
  if (!fhirOrderField("fhir-authored-on")) setValue("fhir-authored-on", localDatetimeValue());
}

export function setOrderForm(payload) {
  if (currentOrderMode() === "fhir") setFhirOrderForm(payload.fhir || payload);
  byId("order-priority").value = payload.priority || "R";
  byId("order-provider").value = payload.orderingProvider || orderDemoPreset.orderingProvider;
  byId("order-indication").value = payload.clinicalIndication || "";
  byId("order-code").value = payload.orderCode || orderDemoPreset.orderCode;
  byId("order-alternate-code").value = payload.alternateCode || orderDemoPreset.alternateCode;
  if (!byId("order-requested-at").value.trim()) byId("order-requested-at").value = hl7Timestamp();
}

export function validateOrderPayload(payload) {
  const messages = [];
  if (!payload.patientRecordId) messages.push("Patient is required.");
  if (payload.mode === "fhir") {
    const patient = selectedOrderPatient();
    if (!payload.fhir?.status) messages.push("FHIR status is required.");
    if (!payload.fhir?.intent) messages.push("FHIR intent is required.");
    if (!payload.fhir?.codeCode && !payload.fhir?.codeDisplay) messages.push("FHIR order code is required.");
    if (!patient?.fhir?.medplum?.reference || patient?.fhir?.sync?.status !== "Synced") messages.push("FHIR Order requires a synced FHIR Patient.");
  }
  if (payload.mode === "hl7-v251") {
    if (!payload.orderingProvider) messages.push("Ordering provider is required.");
    if (!payload.orderCode) messages.push("Order code is required.");
    if (!payload.alternateCode) messages.push("Alternate code is required.");
  }
  if (payload.mode !== "fhir" && payload.requestedAt && !/^\d{8}(\d{4})?(\d{2})?$/.test(payload.requestedAt)) messages.push("Requested time must be YYYYMMDD, YYYYMMDDHHMM, or YYYYMMDDHHMMSS.");
  return messages;
}

export function renderOrderValidation(messages) {
  const container = byId("order-validation");
  container.replaceChildren();
  container.appendChild(createElement("span", messages.length ? "Needs input" : "Valid preview", messages.length ? "status pending" : "status success"));
  if (messages.length) {
    const list = document.createElement("ul");
    messages.forEach((message) => list.appendChild(createElement("li", message)));
    container.appendChild(list);
  }
}

export function configureOrderCoordinator(coordinator = {}) {
  orderCoordinator = coordinator;
}

export function refreshOrderPreview() {
  updateOrderModeFields();
  const payload = orderFormPayload();
  const patient = selectedOrderPatient();
  const messages = validateOrderPayload(payload);
  renderOrderValidation(messages);
  orderCoordinator.renderSummary?.(payload, patient);
  byId("order-payload-preview").textContent = messages.length
    ? ORDER_MODE_CONFIG[currentOrderMode()].emptyPreview
    : buildOrderPreviewPayload(payload, patient);
}

export function initializeOrderView({ onCreate, onRefresh, onCopy, onCreateGdtPatient }) {
  byId("load-order-demo").addEventListener("click", () => {
    setOrderForm(orderDemoPreset);
    refreshOrderPreview();
  });
  document.querySelectorAll("#order-view input, #order-view select").forEach((element) => {
    element.addEventListener("input", refreshOrderPreview);
    element.addEventListener("change", refreshOrderPreview);
  });
  byId("refresh-order-preview").addEventListener("click", refreshOrderPreview);
  byId("create-gdt-patient").addEventListener("click", onCreateGdtPatient);
  byId("create-order").addEventListener("click", onCreate);
  byId("refresh-orders").addEventListener("click", onRefresh);
  byId("copy-order-payload").addEventListener("click", onCopy);
}

function renderGdtRecord(code, value) {
  const fieldCode = String(code || "").trim();
  const content = String(value ?? "").trim().replace(/[\r\n]+/g, " ");
  return `${String(3 + 4 + content.length + 2).padStart(3, "0")}${fieldCode}${content}\r\n`;
}

function renderGdtMessage(records, setType) {
  let totalLength = "00000";
  for (let index = 0; index < 8; index += 1) {
    const payload = [["8000", setType], ["8100", totalLength], ["9218", "02.10"], ["9206", "3"], ...records]
      .map(([code, value]) => renderGdtRecord(code, value)).join("");
    const nextLength = String(payload.length).padStart(5, "0");
    if (nextLength === totalLength) return payload;
    totalLength = nextLength;
  }
  return "";
}

export function orderVisitId(patient) {
  return patient?.visitNumber || "VISIT-ORD-GENERATED";
}

function orderAccountNumber(patient) {
  return patient?.accountNumber || "ACC-ORD-GENERATED";
}

export function buildGdtOrderPreviewPayload(payload, patient) {
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

export function buildFhirOrderPreviewPayload(payload) {
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

export function buildOrderPreviewPayload(payload, patient) {
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
