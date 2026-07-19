let orderRecords = [];
let gdtOrderRecords = [];
let selectedOrderRecordKey = "";

export function getOrderRecords() {
  return orderRecords;
}

export function setOrderRecords(records = []) {
  orderRecords = Array.isArray(records) ? records : [];
  return orderRecords;
}

export function getGdtOrderRecords() {
  return gdtOrderRecords;
}

export function setGdtOrderRecords(records = []) {
  gdtOrderRecords = Array.isArray(records) ? records : [];
  return gdtOrderRecords;
}

export function getSelectedOrderRecordKey() {
  return selectedOrderRecordKey;
}

export function setSelectedOrderRecordKey(key = "") {
  selectedOrderRecordKey = String(key || "");
  return selectedOrderRecordKey;
}
