const selections = new Map();

const PATIENT_SELECTION = "patient";
const ORDER_SELECTION = "order";

export function getSelection(name, fallback = null) {
  return selections.has(name) ? selections.get(name) : fallback;
}

export function setSelection(name, value) {
  selections.set(name, value);
  return value;
}

export function clearSelection(name) {
  selections.delete(name);
}

export function getSelectedPatientId() {
  return getSelection(PATIENT_SELECTION);
}

export function setSelectedPatientId(patientId) {
  return patientId == null ? clearSelection(PATIENT_SELECTION) : setSelection(PATIENT_SELECTION, patientId);
}

export function getSelectedOrderId() {
  return getSelection(ORDER_SELECTION);
}

export function setSelectedOrderId(orderId) {
  return orderId == null ? clearSelection(ORDER_SELECTION) : setSelection(ORDER_SELECTION, orderId);
}
