let patientRecords = [];

export function getPatientRecords() {
  return patientRecords;
}

export function setPatientRecords(records = []) {
  patientRecords = Array.isArray(records) ? records : [];
  return patientRecords;
}

export function replacePatientRecord(patient) {
  if (!patient?.id) return patientRecords;
  patientRecords = patientRecords.map((item) => (
    Number(item.id) === Number(patient.id) ? patient : item
  ));
  return patientRecords;
}
