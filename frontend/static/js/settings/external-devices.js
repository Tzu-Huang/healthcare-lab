import { requestJson, requestJsonAllowBusinessFailure } from "../api/client.js";

export const EXTERNAL_DEVICES_API = "/api/settings/external-devices";
const state = { initialized: false, busy: false, profiles: [], selectedId: null };
const byId = (root, id) => root.querySelector(`#${id}`);

export function fetchExternalDeviceProfiles(environment) {
  const query = environment ? `?environment=${encodeURIComponent(environment)}` : "";
  return requestJson(`${EXTERNAL_DEVICES_API}${query}`);
}

export function createExternalDeviceProfile(payload) {
  return requestJsonAllowBusinessFailure(EXTERNAL_DEVICES_API, {
    method: "POST", body: JSON.stringify(payload),
  });
}

export function updateExternalDeviceProfile(id, payload) {
  return requestJsonAllowBusinessFailure(`${EXTERNAL_DEVICES_API}/${encodeURIComponent(id)}`, {
    method: "PUT", body: JSON.stringify(payload),
  });
}

export function selectExternalDeviceDefault(id) {
  return requestJsonAllowBusinessFailure(
    `${EXTERNAL_DEVICES_API}/${encodeURIComponent(id)}/default`,
    { method: "PUT", body: "{}" },
  );
}

export function runExternalDeviceDiagnostics(id) {
  return requestJsonAllowBusinessFailure(
    `${EXTERNAL_DEVICES_API}/${encodeURIComponent(id)}/diagnostics`,
    { method: "POST", body: "{}" },
  );
}

function items(response = {}) {
  const value = response.items || response.profiles || response;
  return Array.isArray(value) ? value : [];
}

function profileFrom(response = {}) {
  return response.item || response.profile || response;
}

function setProtocolVisibility(root, protocol) {
  const enabled = byId(root, `external-device-${protocol}-enabled`).checked;
  const fields = byId(root, `external-device-${protocol}-fields`);
  fields.hidden = !enabled;
  fields.querySelectorAll("input, select").forEach((control) => {
    control.disabled = !enabled;
  });
}

function protocolValue(profile, name) {
  return profile.protocols?.[name] || profile[name] || {};
}

function renderEditor(root, profile = {}) {
  state.selectedId = profile.id || null;
  const hl7 = protocolValue(profile, "hl7");
  const gdt = protocolValue(profile, "gdt");
  const dicom = protocolValue(profile, "dicom");
  byId(root, "external-device-id").value = profile.id || "";
  byId(root, "external-device-name").value = profile.name || profile.displayName || "";
  byId(root, "external-device-environment").value =
    profile.environment || byId(root, "external-device-environment-filter").value;
  byId(root, "external-device-enabled").checked = profile.enabled === true;
  byId(root, "external-device-default").checked = profile.isDefault === true;
  byId(root, "external-device-hl7-enabled").checked = hl7.enabled === true;
  byId(root, "external-device-hl7-host").value = hl7.host || "";
  byId(root, "external-device-hl7-port").value = hl7.port || "";
  byId(root, "external-device-hl7-application").value = hl7.receivingApplication || "";
  byId(root, "external-device-hl7-facility").value = hl7.receivingFacility || "";
  byId(root, "external-device-hl7-sending-application").value = hl7.sendingApplication || "";
  byId(root, "external-device-hl7-sending-facility").value = hl7.sendingFacility || "";
  byId(root, "external-device-gdt-enabled").checked = gdt.enabled === true;
  byId(root, "external-device-gdt-bridge-profile").value = gdt.bridgeProfile || "";
  byId(root, "external-device-gdt-sender-id").value = gdt.senderId || "";
  byId(root, "external-device-gdt-receiver-id").value = gdt.receiverId || "";
  byId(root, "external-device-dicom-enabled").checked = dicom.enabled === true;
  byId(root, "external-device-dicom-ae-title").value = dicom.aeTitle || "";
  byId(root, "external-device-dicom-host").value = dicom.host || "";
  byId(root, "external-device-dicom-port").value = dicom.port || "";
  byId(root, "external-device-dicom-mwl-calling-ae").value = dicom.mwlCallingAeTitle || "";
  byId(root, "external-device-dicom-station-ae").value = dicom.scheduledStationAeTitle || "";
  byId(root, "external-device-dicom-result-role").value = dicom.resultDeliveryRole || "none";
  ["hl7", "gdt", "dicom"].forEach((name) => setProtocolVisibility(root, name));
  byId(root, "external-device-set-default").disabled =
    !profile.id || profile.enabled !== true || profile.isDefault === true;
}

function renderProfiles(root) {
  const list = byId(root, "external-device-profile-list");
  list.replaceChildren();
  state.profiles.forEach((profile) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const name = document.createElement("strong");
    const status = document.createElement("span");
    button.type = "button";
    button.dataset.profileId = profile.id;
    button.setAttribute("aria-current", String(profile.id === state.selectedId));
    name.textContent = profile.name || profile.displayName || "Unnamed profile";
    status.textContent = [
      profile.enabled ? "Enabled" : "Disabled",
      profile.isDefault ? "Environment default" : null,
    ].filter(Boolean).join(" · ");
    button.append(name, status);
    button.addEventListener("click", () => {
      renderEditor(root, profile);
      renderProfiles(root);
      renderStatus(root, profile);
    });
    item.append(button);
    list.append(item);
  });
  byId(root, "external-device-empty").hidden = state.profiles.length > 0;
}

function numberOrNull(value) {
  return value === "" ? null : Number(value);
}

function profilePayload(root) {
  return {
    name: byId(root, "external-device-name").value.trim(),
    environment: byId(root, "external-device-environment").value,
    enabled: byId(root, "external-device-enabled").checked,
    isDefault: byId(root, "external-device-default").checked,
    metadata: {},
    hl7: {
        enabled: byId(root, "external-device-hl7-enabled").checked,
        host: byId(root, "external-device-hl7-host").value.trim(),
        port: numberOrNull(byId(root, "external-device-hl7-port").value),
        sendingApplication: byId(root, "external-device-hl7-sending-application").value.trim(),
        sendingFacility: byId(root, "external-device-hl7-sending-facility").value.trim(),
        receivingApplication: byId(root, "external-device-hl7-application").value.trim(),
        receivingFacility: byId(root, "external-device-hl7-facility").value.trim(),
      },
    gdt: {
        enabled: byId(root, "external-device-gdt-enabled").checked,
        bridgeProfile: byId(root, "external-device-gdt-bridge-profile").value.trim(),
        senderId: byId(root, "external-device-gdt-sender-id").value.trim(),
        receiverId: byId(root, "external-device-gdt-receiver-id").value.trim(),
      },
    dicom: {
        enabled: byId(root, "external-device-dicom-enabled").checked,
        aeTitle: byId(root, "external-device-dicom-ae-title").value.trim(),
        host: byId(root, "external-device-dicom-host").value.trim(),
        port: numberOrNull(byId(root, "external-device-dicom-port").value),
        mwlCallingAeTitle: byId(root, "external-device-dicom-mwl-calling-ae").value.trim(),
        scheduledStationAeTitle: byId(root, "external-device-dicom-station-ae").value.trim(),
        resultDeliveryRole: byId(root, "external-device-dicom-result-role").value,
      },
  };
}

function clearErrors(root) {
  root.querySelectorAll(".external-device-field-error").forEach((node) => node.remove());
  root.querySelectorAll('[aria-invalid="true"]').forEach((control) => {
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-errormessage");
  });
}

function fieldId(path = "") {
  const fields = {
    name: "external-device-name", environment: "external-device-environment",
    "hl7.host": "external-device-hl7-host", "hl7.port": "external-device-hl7-port",
    "hl7.sendingApplication": "external-device-hl7-sending-application",
    "hl7.sendingFacility": "external-device-hl7-sending-facility",
    "hl7.receivingApplication": "external-device-hl7-application",
    "hl7.receivingFacility": "external-device-hl7-facility",
    "gdt.bridgeProfile": "external-device-gdt-bridge-profile",
    "gdt.senderId": "external-device-gdt-sender-id", "gdt.receiverId": "external-device-gdt-receiver-id",
    "dicom.aeTitle": "external-device-dicom-ae-title", "dicom.host": "external-device-dicom-host",
    "dicom.port": "external-device-dicom-port", "dicom.mwlCallingAETitle": "external-device-dicom-mwl-calling-ae",
    "dicom.scheduledStationAETitle": "external-device-dicom-station-ae",
    "dicom.resultDeliveryRole": "external-device-dicom-result-role",
  };
  return fields[path];
}

function renderErrors(root, response = {}) {
  const errors = response.error?.fields || response.fields || [];
  if (!Array.isArray(errors)) return false;
  errors.forEach(({ field, reason, message }) => {
    const control = byId(root, fieldId(field));
    if (!control) return;
    const error = document.createElement("span");
    error.id = `${control.id}-error`;
    error.className = "settings-field-error external-device-field-error";
    error.setAttribute("role", "alert");
    error.textContent = reason || message || "This value is invalid.";
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-errormessage", error.id);
    control.insertAdjacentElement("afterend", error);
  });
  return errors.length > 0;
}

function safeChecks(response = {}) {
  const checks = response.checks || response.diagnostics?.checks || [];
  return Array.isArray(checks) ? checks : Object.entries(checks).map(([id, value]) => ({
    id, ...(typeof value === "object" ? value : { state: value }),
  }));
}

function renderStatus(root, response = {}) {
  const readiness = response.readiness || {};
  const readinessState = readiness.state || response.readinessState || response.state || "disabled";
  byId(root, "external-device-readiness").textContent =
    readiness.summary || `State: ${readinessState}`;
  byId(root, "external-device-activation-guidance").hidden = readinessState !== "apply-required";
  const diagnostics = byId(root, "external-device-diagnostics");
  diagnostics.replaceChildren();
  safeChecks(response).forEach((check) => {
    const card = document.createElement("article");
    const title = document.createElement("h5");
    const summary = document.createElement("p");
    card.className = "settings-diagnostic";
    card.dataset.state = check.state || check.status || "unknown";
    title.textContent = check.label || check.protocol || check.id || "Device check";
    summary.textContent = check.summary || check.guidance || `State: ${card.dataset.state}`;
    card.append(title, summary);
    diagnostics.append(card);
  });
  const observation = response.lastInteraction || response.observation ||
    profileFrom(response).lastInteraction || {};
  ["protocol", "direction", "timestamp", "outcomeCode"].forEach((key) => {
    root.querySelector(`[data-observation="${key}"]`).textContent = observation[key] || "None";
  });
}

function setBusy(root, busy) {
  state.busy = busy;
  byId(root, "external-device-save").disabled = busy;
  byId(root, "external-device-run-diagnostics").disabled = busy || !state.selectedId;
  const selected = state.profiles.find(({ id }) => id === state.selectedId);
  byId(root, "external-device-set-default").disabled =
    busy || !selected || !selected.enabled || selected.isDefault === true;
}

export async function refreshExternalDeviceSettings(root) {
  const environment = byId(root, "external-device-environment-filter").value;
  const response = await fetchExternalDeviceProfiles(environment);
  state.profiles = items(response);
  const selected = state.profiles.find(({ id }) => id === state.selectedId) ||
    state.profiles.find(({ isDefault }) => isDefault) || state.profiles[0] || {};
  renderEditor(root, selected);
  renderProfiles(root);
  renderStatus(root, response);
  return state;
}

async function saveProfile(root) {
  if (state.busy) return;
  setBusy(root, true);
  clearErrors(root);
  try {
    const payload = profilePayload(root);
    const id = byId(root, "external-device-id").value;
    const response = id
      ? await updateExternalDeviceProfile(id, payload)
      : await createExternalDeviceProfile(payload);
    if (response.success === false || response.saved === false) {
      renderErrors(root, response);
      byId(root, "external-device-save-result").textContent =
        "Profile was not saved. Correct the highlighted fields.";
      return response;
    }
    const saved = profileFrom(response);
    state.selectedId = saved.id || id;
    byId(root, "external-device-environment-filter").value = saved.environment || payload.environment;
    await refreshExternalDeviceSettings(root);
    byId(root, "external-device-save-result").textContent =
      "Profile saved. Integration activation is not automatic.";
    return response;
  } finally {
    setBusy(root, false);
  }
}

async function makeDefault(root) {
  if (!state.selectedId || state.busy) return;
  setBusy(root, true);
  try {
    const response = await selectExternalDeviceDefault(state.selectedId);
    await refreshExternalDeviceSettings(root);
    byId(root, "external-device-save-result").textContent =
      response.success === false ? "Default selection was not changed." : "Environment default updated.";
  } finally {
    setBusy(root, false);
  }
}

async function diagnose(root) {
  if (!state.selectedId || state.busy) return;
  setBusy(root, true);
  byId(root, "external-device-save-result").textContent = "Running bounded diagnostics…";
  try {
    const response = await runExternalDeviceDiagnostics(state.selectedId);
    renderStatus(root, response);
    byId(root, "external-device-save-result").textContent = "Bounded diagnostics completed.";
  } finally {
    setBusy(root, false);
  }
}

function reportError(root, error) {
  byId(root, "external-device-save-result").textContent =
    `AP device settings unavailable: ${error.message}`;
}

export function initializeExternalDeviceSettingsSection(root) {
  const owner = root?.querySelector('[data-integration-owner="external-devices"]');
  if (!owner || owner.dataset.initialized === "true") return state;
  ["hl7", "gdt", "dicom"].forEach((protocol) => {
    byId(root, `external-device-${protocol}-enabled`).addEventListener(
      "change", () => setProtocolVisibility(root, protocol),
    );
  });
  byId(root, "external-device-environment-filter").addEventListener(
    "change", () => refreshExternalDeviceSettings(root).catch((error) => reportError(root, error)),
  );
  byId(root, "external-device-new").addEventListener("click", () => {
    renderEditor(root, { environment: byId(root, "external-device-environment-filter").value });
    renderProfiles(root);
  });
  byId(root, "external-device-form").addEventListener("submit", (event) => {
    event.preventDefault();
    saveProfile(root).catch((error) => reportError(root, error));
  });
  byId(root, "external-device-set-default").addEventListener(
    "click", () => makeDefault(root).catch((error) => reportError(root, error)),
  );
  byId(root, "external-device-run-diagnostics").addEventListener(
    "click", () => diagnose(root).catch((error) => reportError(root, error)),
  );
  owner.dataset.initialized = "true";
  state.initialized = true;
  return state;
}
