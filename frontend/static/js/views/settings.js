import {
  fetchBootstrapStatus, fetchRuntimeDiagnostics, fetchSettings, fetchSettingsListenerStatus, inspectManagedChannels,
  mutateManagedChannel, previewManagedChannel, retryBootstrap, retrySettingsListener, saveSettings,
  startSettingsListener, stopSettingsListener, testSettingsConnection,
} from "../api/settings.js";
import { listenerPortWarning, listenerReloadMessage, safeConnectionResult, settingsUnavailableMessage } from "../components/settings-shell.js";
import { byId } from "../core/dom.js";
import { channelRoute, clearSettingsPreview, createSettingsState, displayedChannelName, listenerSettingsMatchStatus } from "../state/settings.js";

const state = createSettingsState();
const element = (id) => byId(id);

function managementPayload() {
  const current = state.profile?.managementApi || {};
  const payload = {
    ...current,
    baseUrl: element("settings-api-url").value.trim(),
    username: element("settings-api-username").value.trim(),
    timeoutSeconds: Number(element("settings-api-timeout").value),
  };
  delete payload.passwordConfigured;
  const tlsMode = element("settings-api-tls-mode").value;
  payload.tlsVerify = tlsMode === "verified";
  const replacement = element("settings-api-password").value;
  if (replacement) payload.password = replacement;
  return payload;
}

function listenerPayload() {
  return { host: element("settings-listener-host").value.trim(), port: Number(element("settings-listener-port").value),
    mllpFraming: element("settings-listener-mllp").checked, autoStart: element("settings-listener-auto-start").checked };
}

function profilePayload() {
  return { managementApi: managementPayload(), resultListener: listenerPayload(), managedChannels: state.profile?.managedChannels || [] };
}

function renderProfile(profile) {
  state.profile = profile || {};
  const management = state.profile.managementApi || {};
  element("settings-api-url").value = management.baseUrl || "";
  element("settings-api-username").value = management.username || "";
  element("settings-api-password").value = "";
  element("settings-password-configured").textContent = management.passwordConfigured ? "(configured)" : "(not configured)";
  element("settings-api-timeout").value = management.timeoutSeconds || 10;
  element("settings-api-tls-mode").value = management.tlsVerify === false ? "local-self-signed" : "verified";
  const listener = state.profile.resultListener || {};
  element("settings-listener-host").value = listener.host || "";
  element("settings-listener-port").value = listener.port || "";
  element("settings-listener-mllp").checked = listener.mllpFraming !== false;
  element("settings-listener-auto-start").checked = listener.autoStart !== false;
  state.originalListenerPort = Number(listener.port);
  renderPortWarning();
}

function renderRuntime(status = {}) {
  state.runtime = status;
  const runtimeState = status.state || (status.running ? "running" : "stopped");
  element("settings-listener-state").textContent = runtimeState;
  element("settings-listener-endpoint").textContent = `${status.host || status.attemptedHost || "-"}:${status.port || status.attemptedPort || "-"}`;
  element("settings-listener-framing").textContent = status.mllpFraming === false ? "Off" : status.mllpFraming === true ? "On" : "-";
  element("settings-listener-error").textContent = status.lastError || status.error || "";
  element("start-settings-listener").disabled = Boolean(status.running);
  element("stop-settings-listener").disabled = !status.running;
}

function renderReminder() {
  const reminder = element("settings-listener-reload-reminder");
  reminder.hidden = !state.runtimeReloadRequired;
  reminder.textContent = state.runtimeReloadRequired ? listenerReloadMessage() : "";
}

function bootstrapGuidance(status = {}) {
  return status.guidanceCode || status.errorCategory || "";
}

function renderBootstrap(status = {}) {
  state.bootstrap = status;
  const running = status.state === "running" || status.state === "waiting";
  element("settings-bootstrap-state").textContent = status.state || "unknown";
  element("settings-bootstrap-outcome").textContent = status.outcome || "-";
  const modeAndTrigger = [];
  if (status.mode) modeAndTrigger.push(status.mode);
  if (status.trigger) modeAndTrigger.push(status.trigger);
  element("settings-bootstrap-mode").textContent = modeAndTrigger.join(" / ") || "-";
  element("settings-bootstrap-attempts").textContent = Number.isInteger(status.attempts) ? String(status.attempts) : "-";
  element("settings-bootstrap-started").textContent = status.startedAt || "-";
  element("settings-bootstrap-completed").textContent = status.completedAt || "-";
  element("settings-bootstrap-guidance").textContent = bootstrapGuidance(status);
  element("retry-settings-bootstrap").disabled = running || !status.retryEligible;
  const channels = element("settings-bootstrap-channels"); channels.replaceChildren();
  (status.channels || []).forEach((channel) => {
    const card = document.createElement("article"); card.className = "settings-diagnostic";
    card.dataset.state = String(channel.outcome || channel.status || "unknown").toLowerCase();
    const title = document.createElement("h4"); title.textContent = channel.logicalType || "Managed Channel";
    card.append(title);
    appendFact(card, "Classification", channel.classification);
    appendFact(card, "Outcome", channel.outcome);
    appendFact(card, "Status", channel.status);
    const guidance = bootstrapGuidance(channel);
    if (guidance) appendFact(card, "Guidance", guidance);
    channels.append(card);
  });
  if (!channels.children.length) channels.textContent = "No per-Channel bootstrap results reported.";
}

function renderPortWarning() {
  const warning = element("settings-listener-port-warning");
  warning.hidden = !state.originalListenerPort || Number(element("settings-listener-port").value) === state.originalListenerPort;
  warning.textContent = warning.hidden ? "" : listenerPortWarning();
}

function reportError(error) { element("settings-status").textContent = error.message || settingsUnavailableMessage(); }

function deliveryEvidenceText(check) {
  if (check.layer !== "delivery-state") return "";
  const evidence = check.evidence || {};
  if (Number.isInteger(evidence.queued) && Number.isInteger(evidence.errors)) {
    return `Queued: ${evidence.queued}; Errors: ${evidence.errors}`;
  }
  return "Counts unavailable.";
}

function renderDiagnostics(report = {}) {
  const checks = report.probes || report.checks || report.items || [];
  const container = element("settings-diagnostics-list"); container.replaceChildren();
  checks.forEach((check) => {
    const card = document.createElement("article"); card.className = "settings-diagnostic";
    card.dataset.state = String(check.state || "unknown").toLowerCase();
    const title = document.createElement("h4"); title.textContent = check.layer || check.name || "Runtime check";
    const stateLine = document.createElement("p"); stateLine.textContent = `State: ${check.state || "unknown"}${check.category ? ` (${check.category})` : ""}`;
    const summary = document.createElement("p"); summary.textContent = check.summary || check.message || "No additional evidence.";
    const evidence = document.createElement("p"); evidence.textContent = deliveryEvidenceText(check);
    const guidance = document.createElement("p"); guidance.textContent = check.guidance || check.recoveryGuidance || "";
    card.append(title, stateLine, summary); if (evidence.textContent) card.append(evidence); if (guidance.textContent) card.append(guidance); container.append(card);
  });
  if (!checks.length) container.textContent = "No diagnostic checks were returned.";
  element("settings-diagnostics-summary").textContent = report.summary || `Diagnostics completed: ${checks.length} layer${checks.length === 1 ? "" : "s"}.`;
}

export async function refreshRuntimeDiagnostics() {
  element("settings-diagnostics-summary").textContent = "Running layered diagnostics…";
  try { const result = await fetchRuntimeDiagnostics(); renderDiagnostics(result.item || result); return result; }
  catch (error) { element("settings-diagnostics-summary").textContent = `Diagnostics unavailable: ${error.message}`; throw error; }
}

export async function refreshSettings() {
  const [profile, runtime, bootstrap] = await Promise.all([fetchSettings(), fetchSettingsListenerStatus(), fetchBootstrapStatus()]);
  renderProfile(profile.item); renderRuntime(runtime.item);
  renderBootstrap(bootstrap.item);
  state.runtimeReloadRequired = !listenerSettingsMatchStatus(state.profile, runtime.item); renderReminder();
  await refreshSettingsChannels();
  await refreshRuntimeDiagnostics().catch(() => undefined);
  return state;
}

async function persistProfile(successMessage) {
  const result = await saveSettings(profilePayload());
  renderProfile(result.item);
  state.runtimeReloadRequired = Boolean(result.runtimeReloadRequired) || !listenerSettingsMatchStatus(state.profile, state.runtime);
  renderReminder(); element("settings-status").textContent = successMessage;
  return result;
}

export async function saveListenerSettings() { return persistProfile("Listener intent saved. Runtime was not restarted."); }
export async function saveConnectionSettings() { return persistProfile("Connection settings saved."); }

export async function testConnectionFromSettings() {
  element("settings-connection-result").textContent = "Testing saved connection…";
  try { const result = await testSettingsConnection(); element("settings-connection-result").textContent = safeConnectionResult(result.item); return result; }
  catch (error) { element("settings-connection-result").textContent = `Connection test failed: ${error.message}`; throw error; }
}

async function controlListener(action) {
  const result = await ({ start: startSettingsListener, stop: stopSettingsListener, retry: retrySettingsListener }[action])();
  renderRuntime(result.item); state.runtimeReloadRequired = !listenerSettingsMatchStatus(state.profile, result.item); renderReminder();
  return result;
}
export function retryListenerFromSettings() { return controlListener("retry"); }

export async function refreshSettingsChannels() {
  element("settings-status").textContent = "Refreshing managed Channels…";
  try {
    const result = await inspectManagedChannels();
    state.items = result.items || [];
    clearSettingsPreview(state); renderChannels();
    element("settings-status").textContent = result.success === false
      ? `Channel inventory unavailable: ${result.error || result.errorCategory || "live inspection failed"}.`
      : "Channel inventory refreshed.";
  }
  catch (error) { reportError(error); }
}

export async function retryBootstrapFromSettings() {
  const button = element("retry-settings-bootstrap"); button.disabled = true;
  element("settings-bootstrap-guidance").textContent = "Requesting bootstrap retry...";
  try {
    const result = await retryBootstrap();
    if (result.item) renderBootstrap(result.item);
    if (result.success === false) {
      element("settings-bootstrap-guidance").textContent = result.error || result.errorCategory || "Bootstrap retry was not accepted.";
    }
    return result;
  } catch (error) {
    element("settings-bootstrap-guidance").textContent = `Bootstrap retry unavailable: ${error.message}`;
    await fetchBootstrapStatus().then((result) => renderBootstrap(result.item)).catch(() => undefined);
    throw error;
  }
}

function appendFact(card, label, value) {
  const row = document.createElement("p"); const strong = document.createElement("strong"); strong.textContent = `${label}: `;
  row.append(strong, document.createTextNode(value ?? "-")); card.append(row);
}

function renderChannels() {
  const managed = element("settings-managed-list"); const external = element("settings-external-list"); managed.replaceChildren(); external.replaceChildren();
  state.items.forEach((item) => (item.classification === "external" ? external : managed).append(channelCard(item)));
  if (!managed.children.length) managed.textContent = "No managed Channel templates reported.";
  if (!external.children.length) external.textContent = "No external Channels reported.";
}

function normalizedActions(item) {
  const actions = [...(item.permittedActions || item.actions || [])];
  if (actions.includes("update") && !actions.includes("apply")) actions[actions.indexOf("update")] = "apply";
  if ((item.lifecycleState || item.state || item.classification || "").toLowerCase() === "missing" && actions.includes("create")) actions[actions.indexOf("create")] = "recreate";
  return actions;
}

function channelCard(item) {
  const card = document.createElement("article"); card.className = `settings-channel settings-${item.classification || "managed"}`;
  card.dataset.readOnly = item.classification === "external" ? "true" : "false";
  const title = document.createElement("h4"); title.textContent = displayedChannelName(item); card.append(title);
  appendFact(card, "Route", channelRoute(item)); appendFact(card, "Ownership", item.classification || "managed");
  appendFact(card, "Lifecycle", item.lifecycleState || item.state || item.drift || "-"); appendFact(card, "Deployment", item.deploymentState || (item.deployed === true ? "deployed" : item.deployed === false ? "undeployed" : "-"));
  const lastOperation = item.lastOperation ? `${item.lastOperation.operation}: ${item.lastOperation.outcome}` : "-";
  appendFact(card, "Revision", item.revision); appendFact(card, "Last operation", lastOperation);
  const reasons = item.blockingReasons || item.blockers || []; if (reasons.length) appendFact(card, "Blocked", reasons.join("; "));
  if (item.classification === "external") return card;
  const editable = item.editableFields || item.desired || {};
  const editor = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Edit approved fields"; editor.append(summary);
  const editorGrid = document.createElement("div"); editorGrid.className = "settings-channel-editor";
  const approvedFields = [
    ["sourceHost", "Source host", "text"], ["sourcePort", "Source port", "number"],
    ["destinationHost", "Destination host", "text"], ["destinationPort", "Destination port", "number"],
    ["timeoutSeconds", "Timeout (seconds)", "number"], ["queueEnabled", "Queue enabled", "checkbox"],
    ["retryCount", "Retry count", "number"], ["retryIntervalMs", "Retry interval (ms)", "number"],
  ];
  approvedFields.forEach(([field, labelText, type]) => {
    const label = document.createElement("label"); label.textContent = labelText; const input = document.createElement("input"); input.type = type; input.dataset.channelField = field;
    if (type === "checkbox") input.checked = Boolean(editable[field]); else input.value = editable[field] ?? item[field] ?? "";
    label.append(input); editorGrid.append(label);
  });
  const saveEdit = document.createElement("button"); saveEdit.type = "button"; saveEdit.dataset.editSave = item.logicalType; saveEdit.textContent = "Save desired fields"; editorGrid.append(saveEdit); editor.append(editorGrid); card.append(editor);
  const controls = document.createElement("div"); controls.className = "settings-actions";
  normalizedActions(item).forEach((operation) => { const button = document.createElement("button"); button.type = "button"; button.dataset.logicalType = item.logicalType; button.dataset.operation = operation; button.textContent = `Preview ${operation}`; controls.append(button); });
  card.append(controls); return card;
}

async function handleAction(event) {
  const editButton = event.target.closest("button[data-edit-save]");
  if (editButton) { await saveChannelEdits(editButton); return; }
  const button = event.target.closest("button[data-operation]"); if (!button || state.busy) return;
  state.busy = true;
  try { state.selected = button.dataset.logicalType; state.operation = button.dataset.operation; state.preview = await previewManagedChannel(state.selected, state.operation); showPreview(); }
  catch (error) { reportError(error); }
  finally { state.busy = false; updateExecuteState(); }
}

async function saveChannelEdits(button) {
  if (state.busy) return;
  const logicalType = button.dataset.editSave; const editor = button.closest(".settings-channel-editor"); const desired = {};
  editor.querySelectorAll("[data-channel-field]").forEach((input) => {
    desired[input.dataset.channelField] = input.type === "checkbox" ? input.checked : input.type === "number" ? Number(input.value) : input.value.trim();
  });
  const entries = [...(state.profile?.managedChannels || [])]; const index = entries.findIndex((entry) => entry.logicalType === logicalType);
  const inventoryItem = state.items.find((item) => item.logicalType === logicalType);
  const updated = { ...(index >= 0 ? entries[index] : {}), logicalType, channelName: displayedChannelName(inventoryItem), ...desired };
  if (index >= 0) entries[index] = updated; else entries.push(updated);
  state.busy = true;
  try {
    const payload = profilePayload(); payload.managedChannels = entries; const result = await saveSettings(payload); renderProfile(result.item); await refreshSettingsChannels();
    element("settings-status").textContent = "Desired Channel fields saved. Preview Apply before changing OIE.";
  } catch (error) { reportError(error); }
  finally { state.busy = false; }
}

function selectedItem() { return state.items.find((item) => item.logicalType === state.selected); }
function showPreview() {
  const item = selectedItem(); const name = displayedChannelName(item, state.preview); const route = channelRoute(item, state.preview);
  element("settings-preview").hidden = false; element("settings-preview-summary").textContent = `${state.operation} — ${name}`;
  element("settings-preview-target").textContent = `Single target: ${state.preview?.channelId || item?.channelId || "not created"} · ${route}`;
  const differences = state.preview?.snapshot?.differences || state.preview?.differences || [];
  element("settings-preview-diff").textContent = differences.length ? differences.map((value) => value.path || value.summary || String(value)).join("; ") : "No owned-field differences.";
  const steps = state.preview?.expectedSteps || state.preview?.steps || []; element("settings-preview-steps").replaceChildren(...steps.map((step) => { const li = document.createElement("li"); li.textContent = step.name || step; return li; }));
  element("settings-delete-confirmation-wrap").hidden = state.operation !== "delete"; element("settings-delete-name").textContent = name;
  state.confirmation = ""; element("settings-delete-confirmation").value = ""; updateExecuteState();
}

function updateExecuteState() {
  const expectedName = displayedChannelName(selectedItem(), state.preview);
  element("settings-preview-execute").disabled = !state.preview?.previewToken || state.busy || state.refreshRequired || (state.operation === "delete" && state.confirmation !== expectedName);
}

async function executePreview() {
  if (!state.preview?.previewToken || state.busy) return;
  state.busy = true; updateExecuteState();
  try {
    const response = await mutateManagedChannel(state.selected, state.operation, state.preview.previewToken, state.confirmation);
    const item = response.item || {}; const steps = item.steps || [];
    element("settings-operation-steps").textContent = steps.map((step) => `${step.name}: ${step.status}${step.message ? ` — ${step.message}` : ""}`).join("\n") || item.message || "Operation completed.";
    const operationMessage = response.success === false || item.outcome === "partial-failure"
      ? item.message || "Operation did not fully complete. Refresh and preview again."
      : "Channel operation completed and inventory refreshed.";
    state.refreshRequired = true; state.preview = null; await refreshSettingsChannels();
    element("settings-status").textContent = operationMessage;
  } catch (error) { state.refreshRequired = true; state.preview = null; element("settings-status").textContent = `Operation blocked: ${error.message}. Refresh and request a fresh preview.`; }
  finally { state.busy = false; updateExecuteState(); }
}

function bind(id, handler) { element(id).addEventListener("click", () => handler().catch(reportError)); }
export function initializeSettingsView(root) {
  if (!root || state.initialized) return state;
  root.dataset.moduleOwner = "settings"; root.dataset.emptyState = settingsUnavailableMessage();
  bind("save-connection-settings", saveConnectionSettings); bind("test-settings-connection", testConnectionFromSettings);
  bind("save-listener-settings", saveListenerSettings); bind("start-settings-listener", () => controlListener("start")); bind("stop-settings-listener", () => controlListener("stop")); bind("retry-settings-listener", retryListenerFromSettings);
  bind("retry-settings-bootstrap", retryBootstrapFromSettings);
  bind("settings-refresh", refreshSettings); bind("settings-refresh-diagnostics", refreshRuntimeDiagnostics); element("settings-listener-port").addEventListener("input", renderPortWarning);
  element("settings-managed-list").addEventListener("click", handleAction); element("settings-preview-execute").addEventListener("click", executePreview);
  element("settings-delete-confirmation").addEventListener("input", (event) => { state.confirmation = event.target.value; updateExecuteState(); });
  state.initialized = true; return state;
}
