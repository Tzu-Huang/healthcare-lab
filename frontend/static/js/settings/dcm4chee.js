import { requestJson, requestJsonAllowBusinessFailure } from "../api/client.js";

export const DCM4CHEE_PROFILE_API = "/api/settings/profiles/dcm4chee";
export const DCM4CHEE_DIAGNOSTICS_API = "/api/settings/dcm4chee/diagnostics";

const state = { initialized: false, profile: null, busy: false };
const find = (root, id) => root.querySelector(`#${id}`);
const controls = Object.freeze({
  enabled: "dcm4chee-enabled",
  profileName: "dcm4chee-profile-name",
  displayName: "dcm4chee-display-name",
  environmentName: "dcm4chee-environment-name",
  webUiUrl: "dcm4chee-web-ui-url",
  "dimse.host": "dcm4chee-dimse-host",
  "dimse.port": "dcm4chee-dimse-port",
  "dimse.calledAETitle": "dcm4chee-called-ae-title",
  "dimse.callingAETitle": "dcm4chee-calling-ae-title",
  "mwl.aeTitle": "dcm4chee-mwl-ae-title",
  "mwl.defaultScheduledStationAETitle": "dcm4chee-scheduled-station-ae-title",
  "hl7.host": "dcm4chee-hl7-host",
  "hl7.port": "dcm4chee-hl7-port",
  "hl7.sendingApplication": "dcm4chee-hl7-sending-application",
  "hl7.sendingFacility": "dcm4chee-hl7-sending-facility",
  "hl7.receivingApplication": "dcm4chee-hl7-receiving-application",
  "hl7.receivingFacility": "dcm4chee-hl7-receiving-facility",
  "hl7.patientAssigningAuthority": "dcm4chee-patient-assigning-authority",
  "dicomweb.baseUrl": "dcm4chee-dicomweb-base-url",
  "dicomweb.qidoRsUrl": "dcm4chee-qido-rs-url",
  "dicomweb.wadoRsUrl": "dcm4chee-wado-rs-url",
  "dicomweb.stowRsUrl": "dcm4chee-stow-rs-url",
  "viewer.studyUrlTemplate": "dcm4chee-viewer-template",
  uidRoot: "dcm4chee-uid-root",
  "security.authMode": "dcm4chee-auth-mode",
  "security.tlsEnabled": "dcm4chee-tls-enabled",
  "security.tlsVerify": "dcm4chee-tls-verify",
  "security.username": "dcm4chee-username",
  "security.tokenUrl": "dcm4chee-token-url",
  "security.certificatePath": "dcm4chee-certificate-path",
  "security.privateKeyPath": "dcm4chee-private-key-path",
  "secrets.clientSecret": "dcm4chee-client-secret",
});

export function fetchDcm4cheeProfile() {
  return requestJson(DCM4CHEE_PROFILE_API);
}

export function saveDcm4cheeProfile(payload) {
  return requestJsonAllowBusinessFailure(DCM4CHEE_PROFILE_API, {
    method: "PUT", body: JSON.stringify(payload),
  });
}

export function runDcm4cheeDiagnostics() {
  return requestJsonAllowBusinessFailure(DCM4CHEE_DIAGNOSTICS_API, {
    method: "POST", body: "{}",
  });
}

function publicProfile(response = {}) {
  const item = response.item || response.profile || response;
  return {
    ...(item.fields || item),
    secrets: item.secrets || response.secrets || {},
    references: item.references || response.references || {},
  };
}

function setValue(root, id, value = "") {
  const control = find(root, id);
  if (control) control.value = value ?? "";
}

function configured(projection) {
  return Boolean(typeof projection === "object" ? projection?.configured : projection);
}

function referenceSummary(reference) {
  if (!reference || !configured(reference)) return "Not configured";
  if (reference.readable === false) return "Configured reference is not readable";
  return reference.readable === true ? "Configured and readable" : "Configured reference";
}

function renderProfile(root, profile) {
  state.profile = profile;
  const dimse = profile.dimse || {};
  const mwl = profile.mwl || {};
  const hl7 = profile.hl7 || {};
  const dicomweb = profile.dicomweb || {};
  const viewer = profile.viewer || {};
  const security = profile.security || {};
  find(root, controls.enabled).checked = profile.enabled === true;
  setValue(root, controls.profileName, profile.profileName);
  setValue(root, controls.displayName, profile.displayName);
  setValue(root, controls.environmentName, profile.environmentName);
  setValue(root, controls.webUiUrl, profile.webUiUrl);
  setValue(root, controls["dimse.host"], dimse.host);
  setValue(root, controls["dimse.port"], dimse.port);
  setValue(root, controls["dimse.calledAETitle"], dimse.calledAETitle);
  setValue(root, controls["dimse.callingAETitle"], dimse.callingAETitle);
  setValue(root, controls["mwl.aeTitle"], mwl.aeTitle);
  setValue(root, controls["mwl.defaultScheduledStationAETitle"], mwl.defaultScheduledStationAETitle);
  Object.entries({
    "hl7.host": hl7.host, "hl7.port": hl7.port,
    "hl7.sendingApplication": hl7.sendingApplication, "hl7.sendingFacility": hl7.sendingFacility,
    "hl7.receivingApplication": hl7.receivingApplication, "hl7.receivingFacility": hl7.receivingFacility,
    "hl7.patientAssigningAuthority": hl7.patientAssigningAuthority,
    "dicomweb.baseUrl": dicomweb.baseUrl, "dicomweb.qidoRsUrl": dicomweb.qidoRsUrl,
    "dicomweb.wadoRsUrl": dicomweb.wadoRsUrl, "dicomweb.stowRsUrl": dicomweb.stowRsUrl,
    "viewer.studyUrlTemplate": viewer.studyUrlTemplate, uidRoot: profile.uidRoot,
    "security.authMode": security.authMode || "none", "security.username": security.username,
    "security.tokenUrl": security.tokenUrl,
  }).forEach(([field, value]) => setValue(root, controls[field], value));
  find(root, controls["security.tlsEnabled"]).checked = security.tlsEnabled === true;
  find(root, controls["security.tlsVerify"]).checked = security.tlsVerify !== false;
  find(root, "dcm4chee-password").value = "";
  find(root, "dcm4chee-token").value = "";
  find(root, "dcm4chee-client-secret").value = "";
  find(root, "dcm4chee-certificate-path").value = "";
  find(root, "dcm4chee-private-key-path").value = "";
  const password = profile.secrets?.password || profile.secrets?.["security.password"];
  const token = profile.secrets?.token || profile.secrets?.["security.token"];
  const clientSecret = profile.secrets?.clientSecret;
  find(root, "dcm4chee-password-configured").textContent = configured(password) ? "(configured)" : "(not configured)";
  find(root, "dcm4chee-token-configured").textContent = configured(token) ? "(configured)" : "(not configured)";
  find(root, "dcm4chee-client-secret-configured").textContent = configured(clientSecret) ? "(configured)" : "(not configured)";
  const certificate = profile.references?.certificatePath || profile.references?.["security.certificatePath"];
  const privateKey = profile.references?.privateKeyPath || profile.references?.["security.privateKeyPath"];
  find(root, "dcm4chee-certificate-state").textContent = referenceSummary(certificate);
  find(root, "dcm4chee-private-key-state").textContent = referenceSummary(privateKey);
}

function profilePayload(root) {
  const fields = {
    enabled: find(root, controls.enabled).checked,
    profileName: find(root, controls.profileName).value.trim(),
    displayName: find(root, controls.displayName).value.trim(),
    environmentName: find(root, controls.environmentName).value.trim(),
    webUiUrl: find(root, controls.webUiUrl).value.trim(),
    uidRoot: find(root, controls.uidRoot).value.trim(),
    dimse: {
      host: find(root, controls["dimse.host"]).value.trim(),
      port: Number(find(root, controls["dimse.port"]).value),
      calledAETitle: find(root, controls["dimse.calledAETitle"]).value.trim(),
      callingAETitle: find(root, controls["dimse.callingAETitle"]).value.trim(),
    },
    mwl: {
      aeTitle: find(root, controls["mwl.aeTitle"]).value.trim(),
      defaultScheduledStationAETitle: find(root, controls["mwl.defaultScheduledStationAETitle"]).value.trim(),
    },
    hl7: {
      host: find(root, controls["hl7.host"]).value.trim(),
      port: Number(find(root, controls["hl7.port"]).value),
      sendingApplication: find(root, controls["hl7.sendingApplication"]).value.trim(),
      sendingFacility: find(root, controls["hl7.sendingFacility"]).value.trim(),
      receivingApplication: find(root, controls["hl7.receivingApplication"]).value.trim(),
      receivingFacility: find(root, controls["hl7.receivingFacility"]).value.trim(),
      patientAssigningAuthority: find(root, controls["hl7.patientAssigningAuthority"]).value.trim(),
    },
    dicomweb: {
      baseUrl: find(root, controls["dicomweb.baseUrl"]).value.trim(),
      qidoRsUrl: find(root, controls["dicomweb.qidoRsUrl"]).value.trim(),
      wadoRsUrl: find(root, controls["dicomweb.wadoRsUrl"]).value.trim(),
      stowRsUrl: find(root, controls["dicomweb.stowRsUrl"]).value.trim(),
    },
    viewer: { studyUrlTemplate: find(root, controls["viewer.studyUrlTemplate"]).value.trim() },
    security: {
      authMode: find(root, controls["security.authMode"]).value,
      tlsEnabled: find(root, controls["security.tlsEnabled"]).checked,
      tlsVerify: find(root, controls["security.tlsVerify"]).checked,
      username: find(root, controls["security.username"]).value.trim(),
      tokenUrl: find(root, controls["security.tokenUrl"]).value.trim(),
      certificatePath: find(root, controls["security.certificatePath"]).value.trim(),
      privateKeyPath: find(root, controls["security.privateKeyPath"]).value.trim(),
    },
  };
  const secrets = {};
  const password = find(root, "dcm4chee-password").value;
  const token = find(root, "dcm4chee-token").value;
  const clientSecret = find(root, "dcm4chee-client-secret").value;
  if (password) secrets.password = password;
  if (token) secrets.token = token;
  if (clientSecret) secrets.clientSecret = clientSecret;
  return { fields, secrets };
}

function clearErrors(root) {
  Object.values(controls).forEach((id) => {
    find(root, id)?.removeAttribute("aria-invalid");
    find(root, id)?.removeAttribute("aria-errormessage");
    find(root, `${id}-error`)?.remove();
  });
}

function renderErrors(root, response) {
  const issues = response?.payload?.error?.fields || response?.error?.fields;
  if (!Array.isArray(issues)) return false;
  issues.forEach(({ field, reason }) => {
    const id = controls[field];
    const control = id ? find(root, id) : null;
    if (!control) return;
    const message = document.createElement("span");
    message.id = `${id}-error`;
    message.className = "settings-field-error";
    message.setAttribute("role", "alert");
    message.textContent = reason || "This value is invalid.";
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-errormessage", message.id);
    control.insertAdjacentElement("afterend", message);
  });
  return issues.length > 0;
}

function boundedChecks(response = {}) {
  const source = response.checks || response.diagnostics?.checks || response.item?.checks || [];
  return Array.isArray(source) ? source : Object.entries(source).map(([id, check]) => ({
    id, ...(typeof check === "object" ? check : { state: check }),
  }));
}

function renderDiagnostics(root, response) {
  const container = find(root, "dcm4chee-diagnostics");
  container.replaceChildren();
  boundedChecks(response).forEach((check) => {
    const card = document.createElement("article");
    card.className = "settings-diagnostic";
    card.dataset.state = String(check.state || check.status || "unknown").toLowerCase();
    const title = document.createElement("h5");
    title.textContent = check.label || check.role || check.id || "Connection check";
    const summary = document.createElement("p");
    const code = check.code ? ` (${check.code})` : "";
    summary.textContent = `${check.summary || check.guidance || `State: ${card.dataset.state}`}${code}`;
    card.append(title, summary);
    container.append(card);
  });
  const overall = response.readiness || response.diagnostics || response;
  find(root, "dcm4chee-diagnostics-summary").textContent =
    overall.summary || `State: ${overall.state || (state.profile?.enabled ? "unknown" : "disabled")}`;
}

function setBusy(root, busy) {
  state.busy = busy;
  ["dcm4chee-save", "dcm4chee-run-diagnostics"].forEach((id) => {
    find(root, id).disabled = busy;
  });
}

export async function refreshDcm4cheeSettings(root) {
  const response = await fetchDcm4cheeProfile();
  renderProfile(root, publicProfile(response));
  if (response.checks || response.diagnostics || response.readiness) renderDiagnostics(root, response);
  return state;
}

export async function saveDcm4cheeSettings(root) {
  if (state.busy) return undefined;
  setBusy(root, true);
  clearErrors(root);
  try {
    const response = await saveDcm4cheeProfile(profilePayload(root));
    if (response.success === false || response.saved === false) {
      renderErrors(root, response);
      find(root, "dcm4chee-save-result").textContent = "Profile was not saved. Correct the highlighted fields.";
      return response;
    }
    renderProfile(root, publicProfile(response));
    find(root, "dcm4chee-save-result").textContent = "Profile saved.";
    const activation = response.activation || response.item?.activation || {};
    find(root, "dcm4chee-activation-result").textContent =
      activation.summary || activation.guidance || "Saved settings apply to subsequent operations.";
    return response;
  } catch (error) {
    const mapped = renderErrors(root, error);
    find(root, "dcm4chee-save-result").textContent = mapped
      ? "Profile was not saved. Correct the highlighted fields."
      : `Profile could not be saved: ${error.message}`;
    throw error;
  } finally {
    setBusy(root, false);
  }
}

export async function diagnoseDcm4cheeSettings(root) {
  if (state.busy) return undefined;
  setBusy(root, true);
  find(root, "dcm4chee-diagnostics-summary").textContent = "Running bounded diagnostics…";
  try {
    const response = await runDcm4cheeDiagnostics();
    renderDiagnostics(root, response);
    return response;
  } finally {
    setBusy(root, false);
  }
}

function reportError(root, error) {
  find(root, "dcm4chee-save-result").textContent = `dcm4chee action unavailable: ${error.message}`;
}

export function initializeDcm4cheeSettingsSection(root) {
  const owner = root?.querySelector('[data-integration-owner="dcm4chee"]');
  if (!owner || owner.dataset.initialized === "true") return state;
  find(root, "dcm4chee-save").addEventListener("click", () =>
    saveDcm4cheeSettings(root).catch((error) => reportError(root, error)));
  find(root, "dcm4chee-run-diagnostics").addEventListener("click", () =>
    diagnoseDcm4cheeSettings(root).catch((error) => reportError(root, error)));
  owner.dataset.initialized = "true";
  state.initialized = true;
  return state;
}
