import { fetchGdtBridgeConfig, fetchGdtWorkbench, importGdtBridgeFile, saveGdtBridgeConfiguration, startGdtBridgeWatcher, stopGdtBridgeWatcher, writeGdtOrderFile } from "../api/gdt.js";
import { setStatus } from "../components/status.js";
import { copyTextFromElement } from "../core/clipboard.js";
import { byId, createElement, rowCell } from "../core/dom.js";
import { gdtTaipeiTimestamp, taipeiTimestamp } from "../core/formatting.js";

const state = {
  workbench: { patients: [], bridgeInbox: [] },
  bridgeConfig: null,
  selectedPatientId: null,
  expandedPatientIds: new Set(),
  selectedPayload: "",
  selectedPatientRawPreview: { patientId: null, payload: "" },
};
let initialized = false;
let buildPatientPreviewPayload = null;

export function initializeGdtView(options = {}) {
  if (initialized) return;
  initialized = true;
  buildPatientPreviewPayload = options.buildPatientPreviewPayload;
  byId("refresh-gdt-console").addEventListener("click", refreshGdtConsole);
  byId("refresh-gdt-bridge-config").addEventListener("click", refreshGdtBridgeConfig);
  byId("save-gdt-bridge-config").addEventListener("click", saveGdtBridgeConfig);
  byId("start-gdt-watcher").addEventListener("click", startGdtWatcher);
  byId("stop-gdt-watcher").addEventListener("click", stopGdtWatcher);
  byId("copy-gdt-payload").addEventListener("click", () => copyTextFromElement("gdt-payload-preview"));
}
export function selectedGdtPatient() {
  return (state.workbench.patients || []).find((item) => Number(item.id) === Number(state.selectedPatientId)) || null;
}

function renderGdtBridgeConfig() {
  const item = state.bridgeConfig || {};
  const pollSeconds = item.watcher?.pollSeconds || 2;
  byId("gdt-in-folder-path").value = item.inboxPath || "";
  byId("gdt-out-folder-path").value = item.outboxPath || "";
  byId("gdt-in-poll-seconds").value = item.inboxPollSeconds || pollSeconds;
  byId("gdt-out-poll-seconds").value = pollSeconds;
  renderGdtWatcherStatus(item.watcher || {});
}

function renderGdtWatcherStatus(watcher) {
  const running = Boolean(watcher.running);
  setStatus("gdt-watcher-status", running ? `On (${watcher.pollSeconds || "-"}s)` : "Off", running ? "success" : "neutral");
}

async function refreshGdtBridgeConfig() {
  setStatus("gdt-bridge-config-status", "Loading...", "pending");
  try {
    const result = await fetchGdtBridgeConfig();
    state.bridgeConfig = result.item || {};
    renderGdtBridgeConfig();
    setStatus("gdt-bridge-config-status", "Ready", "success");
  } catch (error) {
    setStatus("gdt-bridge-config-status", error.message, "error");
  }
}

async function saveGdtBridgeConfig() {
  setStatus("gdt-bridge-config-status", "Saving...", "pending");
  try {
    const result = await saveGdtBridgeConfiguration({
      gdtInPath: byId("gdt-in-folder-path").value.trim(),
      gdtOutPath: byId("gdt-out-folder-path").value.trim(),
      inboxPollSeconds: Number(byId("gdt-in-poll-seconds").value),
      pollSeconds: Number(byId("gdt-out-poll-seconds").value),
    });
    state.bridgeConfig = result.item || {};
    renderGdtBridgeConfig();
    await refreshGdtConsole();
    setStatus("gdt-bridge-config-status", "Saved", "success");
  } catch (error) {
    setStatus("gdt-bridge-config-status", error.message, "error");
  }
}

async function startGdtWatcher() {
  setStatus("gdt-watcher-status", "Starting...", "pending");
  try {
    const result = await startGdtBridgeWatcher();
    state.bridgeConfig = { ...(state.bridgeConfig || {}), watcher: result.item || {} };
    renderGdtWatcherStatus(result.item || {});
    await refreshGdtConsole();
  } catch (error) {
    setStatus("gdt-watcher-status", error.message, "error");
  }
}

async function stopGdtWatcher() {
  setStatus("gdt-watcher-status", "Stopping...", "pending");
  try {
    const result = await stopGdtBridgeWatcher();
    state.bridgeConfig = { ...(state.bridgeConfig || {}), watcher: result.item || {} };
    renderGdtWatcherStatus(result.item || {});
    await refreshGdtConsole();
  } catch (error) {
    setStatus("gdt-watcher-status", error.message, "error");
  }
}

function measurementSummary(result) {
  const measurements = result?.canonical?.result?.measurements || {};
  return ["HR", "PR", "QRS", "QT", "QTC"]
    .filter((key) => measurements[key])
    .map((key) => `${key} ${measurements[key]}`)
    .join(" / ");
}

function renderGdtPatients() {
  const body = byId("gdt-patient-list");
  body.replaceChildren();
  const patients = state.workbench.patients || [];
  if (!patients.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local GDT patients or orders yet.");
    cell.colSpan = 7;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    state.selectedPatientId = null;
    return;
  }
  if (!state.selectedPatientId || !patients.some((item) => Number(item.id) === Number(state.selectedPatientId))) {
    state.selectedPatientId = patients[0].id;
  }
  patients.forEach((item) => {
    const summary = item.summary || {};
    const patientId = Number(item.id);
    const row = document.createElement("tr");
    row.className = "gdt-patient-row";
    const toggleButton = createElement("button", state.expandedPatientIds.has(patientId) ? "v" : ">", "gdt-patient-toggle");
    toggleButton.type = "button";
    toggleButton.setAttribute("aria-label", state.expandedPatientIds.has(patientId) ? "Collapse patient details" : "Expand patient details");
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const patientId = Number(item.id);
      if (state.expandedPatientIds.has(patientId)) {
        state.expandedPatientIds.delete(patientId);
      } else {
        state.selectedPatientId = item.id;
        state.expandedPatientIds.add(patientId);
      }
      renderGdtConsole();
    });
    const previewButton = gdtActionButton("Preview", (event) => {
      event.stopPropagation();
      selectGdtPatientForPreview(item);
    });
    row.addEventListener("click", () => {
      state.selectedPatientId = item.id;
      renderGdtSelectedPatient();
    });
    row.append(
      rowCell(toggleButton),
      rowCell(summary.mrn || ""),
      rowCell(summary.name || "Patient"),
      rowCell(gdtTaipeiTimestamp(item.createdAt)),
      rowCell(item.orderCount ?? 0),
      rowCell(item.resultCount ?? 0),
      rowCell(previewButton),
    );
    body.appendChild(row);

    if (state.expandedPatientIds.has(patientId)) {
      const detailRow = document.createElement("tr");
      detailRow.className = "gdt-patient-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 7;
      const content = document.createElement("div");
      content.className = "gdt-patient-rollup-content";
      content.append(
        gdtPatientSection("GDT-OUT", "Orders", renderGdtPatientOrders(item)),
        gdtPatientSection("GDT-IN", "Results", renderGdtPatientResults(item)),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function gdtPatientPreviewPayload(patient) {
  const summary = patient?.summary || {};
  const patientData = patient?.patient || {};
  const nameParts = String(summary.name || "").trim().split(/\s+/);
  return buildPatientPreviewPayload({
    mrn: summary.mrn || "",
    firstName: patientData.firstName || nameParts.slice(0, -1).join(" ") || summary.name || "",
    lastName: patientData.lastName || nameParts.slice(-1).join("") || "",
    dob: summary.dob || patientData.dob || "",
    sex: summary.sex || patientData.sex || "U",
  });
}

function gdtWorkflowPatientId(patient) {
  const orders = patient?.orders || [];
  return orders.find((item) => item?.patientSnapshot?.gdtWorkflowPatientId)
    ?.patientSnapshot?.gdtWorkflowPatientId || "";
}

function gdtPatientSection(label, title, body) {
  const section = document.createElement("section");
  section.className = "gdt-patient-section";
  const heading = document.createElement("div");
  heading.className = "compact-heading gdt-patient-section-heading";
  const text = document.createElement("div");
  text.appendChild(createElement("p", label, "eyebrow"));
  text.appendChild(createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function compactTable(headers, emptyText, colSpan) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap gdt-nested-table-wrap";
  const table = document.createElement("table");
  table.className = "gdt-nested-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => headRow.appendChild(createElement("th", header)));
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  if (emptyText) {
    const row = document.createElement("tr");
    const cell = rowCell(emptyText);
    cell.colSpan = colSpan;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
  }
  table.append(thead, tbody);
  wrap.appendChild(table);
  return { wrap, tbody };
}

function renderGdtSelectedPatient() {
  const patient = selectedGdtPatient();
  const summary = patient?.summary || {};
  byId("gdt-selected-patient-title").textContent = patient
    ? `${summary.mrn || patient.id} - ${summary.name || "Patient"}`
    : "No patient selected";
  const container = byId("gdt-selected-patient-summary");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a GDT patient.", "muted"));
    return;
  }
  [
    ["MRN", summary.mrn],
    ["GDT Workflow Patient ID", gdtWorkflowPatientId(patient)],
    ["DOB", summary.dob],
    ["Sex", summary.sex],
    ["Orders", patient.orderCount],
    ["Results", patient.resultCount],
  ].forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
  if (
    state.selectedPatientRawPreview.payload
    && Number(state.selectedPatientRawPreview.patientId) === Number(patient.id)
  ) {
    container.appendChild(createElement("strong", "Raw Preview"));
    const preview = createElement("pre", state.selectedPatientRawPreview.payload, "compact-output gdt-selected-patient-raw");
    container.appendChild(preview);
  }
}

function gdtActionButton(label, handler) {
  const button = createElement("button", label, "small-button");
  button.type = "button";
  button.addEventListener("click", handler);
  return button;
}

function displayGdtOrderNumber(orderNumber) {
  return String(orderNumber || "").replace(/^GDT-/, "") || "-";
}

function selectGdtPatientForPreview(patient) {
  state.selectedPatientId = patient.id;
  state.selectedPayload = gdtPatientPreviewPayload(patient);
  state.selectedPatientRawPreview = { patientId: patient.id, payload: state.selectedPayload };
  renderGdtSelectedPatient();
  renderGdtArtifacts([]);
  byId("gdt-detail-title").textContent = "Raw Patient";
  byId("gdt-payload-preview").textContent = state.selectedPayload;
  renderGdtDetailSummary([
    ["Local Patient Record ID", patient.id],
    ["Name", patient.summary?.name],
    ["MRN", patient.summary?.mrn],
    ["GDT Workflow Patient ID", gdtWorkflowPatientId(patient)],
    ["Orders", patient.orderCount],
    ["Results", patient.resultCount],
  ]);
}

function renderGdtPatientOrders(patient) {
  const orders = patient?.orders || [];
  const { wrap, tbody } = compactTable(["Order", "MRN", "Status", "Created", "Result", "Actions"], orders.length ? "" : "No GDT-OUT orders for this patient.", 6);
  if (!orders.length) {
    return wrap;
  }
  orders.forEach((item) => {
    const writtenFile = String(item.exportPath || "").split(/[\\/]/).pop();
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.append(
      gdtActionButton("Preview GDT-OUT", (event) => {
        event.stopPropagation();
        selectGdtOrder(item);
      }),
      gdtActionButton("Write GDT-OUT", (event) => {
        event.stopPropagation();
        writeGdtOrder(item.id);
      }),
    );
    const row = document.createElement("tr");
    row.append(
      rowCell(displayGdtOrderNumber(item.localGdtOrderNumber)),
      rowCell(item.summary?.mrn || patient.summary?.mrn || ""),
      rowCell(item.status),
      rowCell(gdtTaipeiTimestamp(item.createdAt)),
      rowCell(writtenFile),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectGdtOrder(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function renderGdtPatientResults(patient) {
  const results = patient?.results || [];
  const orders = patient?.orders || [];
  const { wrap, tbody } = compactTable(["File", "Status", "Updated", "Action"], results.length ? "" : "No imported GDT-IN results for this patient.", 4);
  if (!results.length) {
    return wrap;
  }
  results.forEach((item, index) => {
    const row = document.createElement("tr");
    const attachments = item.attachments || [];
    const matchingOrder = orders.find((order) => Number(order.id) === Number(item.orderRecordId));
    const exportedFile = String(matchingOrder?.exportPath || "").split(/[\\/]/).pop();
    const sourceFile = exportedFile
      || attachments.find((attachment) => attachment.sourceFile)?.sourceFile
      || attachments.find((attachment) => attachment.filename)?.filename
      || item.canonical?.sourceFile
      || `GDT-IN-${item.id || index + 1}.gdt`;
    const status = item.parseStatus || item.matchStatus || "received";
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(gdtActionButton("Preview GDT-IN", (event) => {
      event.stopPropagation();
      selectGdtResult(item);
    }));
    row.append(
      rowCell(sourceFile),
      rowCell(status),
      rowCell(gdtTaipeiTimestamp(item.updatedAt || item.receivedAt)),
      rowCell(actions),
    );
    row.addEventListener("click", () => selectGdtResult(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function renderGdtInbox() {
  const body = byId("gdt-inbox-list");
  body.replaceChildren();
  const files = state.workbench.bridgeInbox || [];
  if (!files.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No returned GDT files found in outbox.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  files.forEach((item) => {
    const action = item.status === "pending"
      ? gdtActionButton("Import GDT-IN", () => importGdtInboxFile(item.name))
      : createElement("span", "-", "muted");
    const row = document.createElement("tr");
    row.append(
      rowCell(item.name),
      rowCell(item.status),
      rowCell(item.size),
      rowCell(taipeiTimestamp(item.updatedAt)),
      rowCell(action),
    );
    body.appendChild(row);
  });
}

function renderGdtArtifacts(artifacts = []) {
  const container = byId("gdt-artifact-list");
  container.replaceChildren();
  if (!artifacts.length) {
    container.appendChild(createElement("p", "No artifact references selected.", "muted"));
    return;
  }
  artifacts.forEach((artifact) => {
    const item = document.createElement("div");
    item.className = "artifact-reference";
    item.appendChild(createElement("strong", `${artifact.contentType || artifact.role || "Artifact"}`));
    item.appendChild(createElement("span", artifact.description || artifact.filename || "Reference"));
    item.appendChild(createElement("code", artifact.reference || artifact.url || artifact.path || "-"));
    item.appendChild(createElement("span", artifact.status || "reference-only", `status ${artifact.status === "warning" ? "warning" : "neutral"}`));
    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(gdtActionButton("Copy", () => navigator.clipboard.writeText(artifact.reference || artifact.url || artifact.path || "")));
    if (artifact.url) {
      const open = gdtActionButton("Open", () => window.open(artifact.url, "_blank", "noopener"));
      actions.appendChild(open);
    }
    item.appendChild(actions);
    container.appendChild(item);
  });
}

function selectGdtOrder(item) {
  state.selectedPayload = item.rawGdtText || item.payload || "";
  byId("gdt-detail-title").textContent = "Raw GDT-OUT";
  byId("gdt-payload-preview").textContent = state.selectedPayload;
  renderGdtArtifacts(item.attachments || []);
  renderGdtDetailSummary([
    ["Order", item.localGdtOrderNumber],
    ["Patient", item.summary?.name],
    ["Status", item.status],
    ["Export", item.exportPath || "-"],
  ]);
}

function selectGdtResult(item) {
  state.selectedPayload = item.rawGdtText || "";
  byId("gdt-detail-title").textContent = "Raw GDT-IN";
  byId("gdt-payload-preview").textContent = state.selectedPayload;
  renderGdtArtifacts(item.attachments || []);
  renderGdtDetailSummary([
    ["Result", item.messageType],
    ["Match", item.matchStatus],
    ["Status", item.canonical?.result?.status || "-"],
    ["Measurements", measurementSummary(item) || "-"],
  ]);
}

function renderGdtDetailSummary(rows) {
  const container = byId("gdt-detail-summary");
  container.replaceChildren();
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
}

function renderGdtConsole() {
  renderGdtPatients();
  renderGdtSelectedPatient();
  renderGdtInbox();
}

export async function refreshGdtConsole() {
  setStatus("gdt-console-status", "Refreshing...", "pending");
  try {
    const [configResult, result] = await Promise.all([
      fetchGdtBridgeConfig(),
      fetchGdtWorkbench(),
    ]);
    state.bridgeConfig = configResult.item || {};
    state.workbench = result;
    renderGdtBridgeConfig();
    renderGdtConsole();
    setStatus("gdt-console-status", "Updated", "success");
    setStatus("gdt-bridge-config-status", "Ready", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}

async function writeGdtOrder(orderId) {
  setStatus("gdt-console-status", "Writing GDT-OUT...", "pending");
  try {
    await writeGdtOrderFile(orderId);
    await refreshGdtConsole();
    setStatus("gdt-console-status", "GDT-OUT written", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}

async function importGdtInboxFile(filename) {
  setStatus("gdt-console-status", "Importing GDT-IN...", "pending");
  try {
    await importGdtBridgeFile(filename);
    await refreshGdtConsole();
    setStatus("gdt-console-status", "GDT-IN imported", "success");
  } catch (error) {
    setStatus("gdt-console-status", error.message, "error");
  }
}
