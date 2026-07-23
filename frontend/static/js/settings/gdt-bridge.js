import { requestJson, requestJsonAllowBusinessFailure } from "../api/client.js";

export const GDT_PROFILE_API = "/api/settings/profiles/gdt-bridge";
export const GDT_OPERATIONS_API = "/api/settings/gdt-bridge";

export function fetchGdtBridgeProfile() {
  return requestJson(GDT_PROFILE_API);
}

export function saveGdtBridgeProfile(payload) {
  return requestJsonAllowBusinessFailure(GDT_PROFILE_API, {
    method: "PUT", body: JSON.stringify(payload),
  });
}

export function provisionGdtBridgeDirectories() {
  return requestJsonAllowBusinessFailure(`${GDT_OPERATIONS_API}/provision`, {
    method: "POST", body: "{}",
  });
}

export function runGdtBridgeDiagnostics() {
  return requestJsonAllowBusinessFailure(`${GDT_OPERATIONS_API}/diagnostics`, {
    method: "POST", body: "{}",
  });
}

const state = { initialized: false, profile: null, busy: false };
const find = (root, id) => root.querySelector(`#${id}`);
const controls = Object.freeze({
  enabled: "gdt-bridge-enabled",
  receiverId: "gdt-bridge-receiver-id",
  senderId: "gdt-bridge-sender-id",
  filenameProfile: "gdt-bridge-filename-profile",
  importSuccessMode: "gdt-bridge-success-mode",
  pollIntervalSeconds: "gdt-bridge-poll-interval",
  stableFileSeconds: "gdt-bridge-stable-interval",
  pollSeconds: "gdt-bridge-poll-interval",
  stableSeconds: "gdt-bridge-stable-interval",
});

function publicProfile(response = {}) {
  const item = response.item || response.profile || response;
  return { ...(item.fields || item), deployment: response.deployment || item.deployment || {} };
}

function clearErrors(root) {
  Object.values(controls).forEach((id) => {
    const control = find(root, id);
    control?.removeAttribute("aria-invalid");
    control?.removeAttribute("aria-errormessage");
    find(root, `${id}-error`)?.remove();
  });
}

function renderErrors(root, error) {
  const issues = error?.payload?.error?.fields || error?.error?.fields;
  if (!Array.isArray(issues)) return false;
  issues.forEach(({ field, reason }) => {
    const control = find(root, controls[field]);
    if (!control) return;
    const message = document.createElement("span");
    message.id = `${control.id}-error`;
    message.className = "settings-field-error";
    message.setAttribute("role", "alert");
    message.textContent = reason || "This value is invalid.";
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-errormessage", message.id);
    control.insertAdjacentElement("afterend", message);
  });
  return issues.length > 0;
}

function renderProfile(root, profile) {
  state.profile = profile;
  find(root, controls.enabled).checked = profile.enabled === true;
  find(root, controls.receiverId).value = profile.receiverId || "";
  find(root, controls.senderId).value = profile.senderId || "";
  find(root, controls.filenameProfile).value = profile.filenameProfile || "permissive";
  find(root, controls.importSuccessMode).value = profile.importSuccessMode || "delete";
  find(root, controls.pollIntervalSeconds).value = profile.pollSeconds ?? 2;
  find(root, controls.stableFileSeconds).value = profile.stableSeconds ?? 1;
  find(root, "gdt-bridge-application-path").textContent = "/data/gdt-bridge";
  find(root, "gdt-bridge-host-path").textContent =
    profile.deployment?.hostBindMountSource || "Unavailable";
}

function profilePayload(root) {
  return { fields: {
    enabled: find(root, controls.enabled).checked,
    applicationPath: "/data/gdt-bridge",
    receiverId: find(root, controls.receiverId).value.trim(),
    senderId: find(root, controls.senderId).value.trim(),
    filenameProfile: find(root, controls.filenameProfile).value,
    importSuccessMode: find(root, controls.importSuccessMode).value,
    pollSeconds: Number(find(root, controls.pollIntervalSeconds).value),
    stableSeconds: Number(find(root, controls.stableFileSeconds).value),
  } };
}

function boundedChecks(response = {}) {
  const source = response.checks || response.diagnostics?.checks || response.item?.checks || [];
  return Array.isArray(source) ? source : Object.entries(source).map(([id, value]) => ({
    id, ...(typeof value === "object" ? value : { state: value }),
  }));
}

function renderDiagnostics(root, response) {
  const container = find(root, "gdt-bridge-diagnostics");
  container.replaceChildren();
  boundedChecks(response).forEach((check) => {
    const card = document.createElement("article");
    card.className = "settings-diagnostic";
    card.dataset.state = String(check.state || check.status || "unknown").toLowerCase();
    const title = document.createElement("h5");
    title.textContent = check.label || check.role || check.id || "Bridge check";
    const summary = document.createElement("p");
    summary.textContent = check.summary || check.guidance || `State: ${card.dataset.state}`;
    card.append(title, summary);
    container.append(card);
  });
  const readiness = response.readiness || response.item?.readiness || {};
  const readinessState = readiness.state || response.state || (state.profile?.enabled ? "unknown" : "disabled");
  find(root, "gdt-bridge-readiness").textContent =
    readiness.summary || (readinessState === "disabled" ? "Disabled (optional); setup remains complete." : `State: ${readinessState}`);
  const watcher = response.watcher || readiness.watcher || {};
  find(root, "gdt-bridge-watcher-state").textContent = watcher.state || "Unknown";
  const activation = response.activation || readiness.activation || {};
  find(root, "gdt-bridge-activation").textContent =
    activation.guidance || activation.summary || activation.state || "Applies immediately";
}

function setBusy(root, busy) {
  state.busy = busy;
  ["gdt-bridge-save", "gdt-bridge-provision", "gdt-bridge-run-diagnostics"]
    .forEach((id) => { find(root, id).disabled = busy; });
}

export async function refreshGdtBridgeSettings(root) {
  const response = await fetchGdtBridgeProfile();
  renderProfile(root, publicProfile(response));
  renderDiagnostics(root, response);
  return state;
}

export async function saveGdtBridgeSettings(root) {
  if (state.busy) return undefined;
  setBusy(root, true); clearErrors(root);
  try {
    const response = await saveGdtBridgeProfile(profilePayload(root));
    if (response.success === false || response.saved === false) {
      renderErrors(root, response);
      find(root, "gdt-bridge-save-result").textContent = "Profile was not saved. Correct the highlighted fields.";
      return response;
    }
    renderProfile(root, publicProfile(response));
    renderDiagnostics(root, response);
    find(root, "gdt-bridge-save-result").textContent =
      response.activation?.state === "restart-required"
        ? "Profile saved. Restart is required before the watcher uses these settings."
        : "Profile saved and effective.";
    return response;
  } catch (error) {
    const mapped = renderErrors(root, error);
    find(root, "gdt-bridge-save-result").textContent = mapped
      ? "Profile was not saved. Correct the highlighted fields."
      : `Profile could not be saved: ${error.message}`;
    throw error;
  } finally {
    setBusy(root, false);
  }
}

async function runAction(root, action, pendingText, completeText) {
  if (state.busy) return undefined;
  setBusy(root, true);
  find(root, "gdt-bridge-save-result").textContent = pendingText;
  try {
    const response = await action();
    renderDiagnostics(root, response);
    find(root, "gdt-bridge-save-result").textContent = completeText;
    return response;
  } finally {
    setBusy(root, false);
  }
}

function reportError(root, error) {
  find(root, "gdt-bridge-save-result").textContent = `GDT Bridge action unavailable: ${error.message}`;
}

export function initializeGdtBridgeSettingsSection(root) {
  const owner = root?.querySelector('[data-integration-owner="gdt-bridge"]');
  if (!owner || owner.dataset.initialized === "true") return state;
  find(root, "gdt-bridge-save").addEventListener("click", () => saveGdtBridgeSettings(root).catch((error) => reportError(root, error)));
  find(root, "gdt-bridge-provision").addEventListener("click", () => runAction(
    root, provisionGdtBridgeDirectories, "Creating documented bridge directories…", "Directory provisioning completed.",
  ).catch((error) => reportError(root, error)));
  find(root, "gdt-bridge-run-diagnostics").addEventListener("click", () => runAction(
    root, runGdtBridgeDiagnostics, "Running bounded diagnostics…", "Bounded diagnostics completed.",
  ).catch((error) => reportError(root, error)));
  owner.dataset.initialized = "true";
  state.initialized = true;
  return state;
}
