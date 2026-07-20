let profileDiagnostics = null;
const expandedPatientIds = new Set();

export function getDcm4cheeProfileDiagnostics() {
  return profileDiagnostics;
}

export function setDcm4cheeProfileDiagnostics(diagnostics) {
  profileDiagnostics = diagnostics || null;
  return profileDiagnostics;
}

export function isDcm4cheePatientExpanded(patientId) {
  return expandedPatientIds.has(Number(patientId));
}

export function toggleDcm4cheePatientExpanded(patientId) {
  const normalizedId = Number(patientId);
  if (expandedPatientIds.has(normalizedId)) {
    expandedPatientIds.delete(normalizedId);
    return false;
  }
  expandedPatientIds.add(normalizedId);
  return true;
}
