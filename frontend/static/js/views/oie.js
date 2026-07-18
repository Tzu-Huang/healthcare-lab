import { fetchOieListenerStatus, fetchOieWorkbench, sendOieLocalOrder, startOieResultListener, stopOieResultListener } from "../api/oie.js";
import { setStatus } from "../components/status.js";
import { copyTextFromElement } from "../core/clipboard.js";
import { byId, createElement, rowCell } from "../core/dom.js";
import { taipeiTimestamp } from "../core/formatting.js";

const state = {
  inventory: [],
  unmatchedResults: [],
  selectedPatientId: null,
  selectedOrderId: null,
  expandedPatientIds: new Set(),
  selectedPayload: "",
};
let initialized = false;

export function initializeOieView() {
  if (initialized) return;
  initialized = true;
  byId("refresh-oie-inventory").addEventListener("click", refreshOieInventory);
  byId("copy-oie-payload").addEventListener("click", () => copyTextFromElement("oie-payload-preview"));
  byId("send-selected-oie-order").addEventListener("click", () => {
    if (state.selectedOrderId) sendOieOrder(state.selectedOrderId, byId("send-selected-oie-order"));
  });
  byId("start-oie-listener").addEventListener("click", startOieListener);
  byId("stop-oie-listener").addEventListener("click", stopOieListener);
}

function orderVisitNumber(item) {
  const summary = item?.summary || {};
  return summary.visitNumber || summary.visitId || item?.visitNumber || item?.visitId || "-";
}
export function renderOieInventory() {
  const body = byId("oie-inventory-list");
  body.replaceChildren();
  if (!state.inventory.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local ADT patients have been created.");
    cell.colSpan = 6;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    state.selectedPatientId = null;
    state.selectedOrderId = null;
    byId("oie-selected-patient-title").textContent = "No patient selected";
    byId("oie-payload-preview").textContent = "Create a local Patient A04 record to inspect it here.";
    return;
  }
  if (!state.selectedPatientId || !state.inventory.some((item) => Number(item.id) === Number(state.selectedPatientId))) {
    state.selectedPatientId = state.inventory[0].id;
  }
  state.inventory.forEach((item) => {
    const patientId = Number(item.id);
    const row = document.createElement("tr");
    row.className = "oie-patient-row";
    row.classList.toggle("selected-row", Number(item.id) === Number(state.selectedPatientId));
    const summary = item.summary || {};
    const toggleButton = createElement(
      "button",
      state.expandedPatientIds.has(patientId) ? "v" : ">",
      "oie-patient-toggle",
    );
    toggleButton.type = "button";
    toggleButton.setAttribute(
      "aria-label",
      state.expandedPatientIds.has(patientId) ? "Collapse patient orders and results" : "Expand patient orders and results",
    );
    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      state.selectedPatientId = item.id;
      if (state.expandedPatientIds.has(patientId)) {
        state.expandedPatientIds.delete(patientId);
      } else {
        state.expandedPatientIds.add(patientId);
      }
      renderOieInventory();
      renderSelectedOiePatient();
    });
    const selectPayload = () => {
      state.selectedPatientId = item.id;
      state.selectedPayload = item.payload || "";
      byId("oie-payload-preview").textContent = state.selectedPayload;
      renderOiePreviewSummary("ADT", [
        ["MRN", summary.mrn],
        ["Name", summary.name],
        ["Created", taipeiTimestamp(item.createdAt)],
      ]);
      renderOieInventory();
      renderSelectedOiePatient();
    };
    row.append(
      rowCell(toggleButton),
      rowCell(summary.mrn),
      rowCell(summary.name),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(item.orderCount ?? 0),
      rowCell(item.resultCount ?? 0),
    );
    row.addEventListener("click", selectPayload);
    body.appendChild(row);

    if (state.expandedPatientIds.has(patientId)) {
      const detailRow = document.createElement("tr");
      detailRow.className = "oie-patient-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 6;
      const content = document.createElement("div");
      content.className = "oie-patient-rollup-content";
      content.append(
        oiePatientSection("ORM", "Orders", renderOieOrders(item.orders || [])),
        oiePatientSection("ORU", "Results", renderOieResults(item.results || [])),
      );
      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      body.appendChild(detailRow);
    }
  });
}

function selectedOiePatient() {
  return state.inventory.find((item) => Number(item.id) === Number(state.selectedPatientId)) || null;
}

function renderOiePreviewSummary(kind, rows) {
  const container = byId("oie-preview-summary");
  container.replaceChildren();
  container.appendChild(createElement("span", kind, "status neutral"));
  rows.forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(value || "-"));
    container.appendChild(item);
  });
}

function renderSelectedOiePatient() {
  const patient = selectedOiePatient();
  const summary = patient?.summary || {};
  byId("oie-selected-patient-title").textContent = patient
    ? `${summary.mrn || patient.id} - ${summary.name || "Patient"}`
    : "No patient selected";
  const container = byId("oie-selected-patient-summary");
  container.replaceChildren();
  if (!patient) {
    container.appendChild(createElement("p", "Select a patient and expand Orders or Results.", "muted"));
    state.selectedOrderId = null;
    renderOieTransmission(null);
    return;
  }
  [
    ["MRN", summary.mrn],
    ["Name", summary.name],
    ["Orders", patient.orderCount ?? 0],
    ["Results", patient.resultCount ?? 0],
  ].forEach(([label, value]) => {
    const item = document.createElement("p");
    item.appendChild(createElement("strong", `${label}: `));
    item.appendChild(document.createTextNode(String(value ?? "-")));
    container.appendChild(item);
  });
  const orders = patient.orders || [];
  let order = orders.find((item) => Number(item.id) === Number(state.selectedOrderId)) || null;
  if (!order && orders.length) {
    order = orders[0];
    state.selectedOrderId = order.id;
  } else if (!order) {
    state.selectedOrderId = null;
  }
  renderOieTransmission(order);
}

function renderOieOrders(orders) {
  const { wrap, tbody } = oieNestedTable([
    "Order ID",
    "MRN",
    "Visit Number",
    "Code",
    "Status",
    "Created At (Taipei)",
    "ACK",
    "Sent",
    "Action",
  ]);
  if (!orders.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No local ORM O01 orders for this patient.");
    cell.colSpan = 9;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
    return wrap;
  }
  orders.forEach((item) => {
    const row = document.createElement("tr");
    row.classList.toggle("selected-row", Number(item.id) === Number(state.selectedOrderId));
    const summary = item.summary || {};
    const selectButton = createElement("button", "Select", "small-button");
    selectButton.type = "button";
    selectButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieOrder(item);
    });
    row.append(
      rowCell(item.localOrderNumber || item.id),
      rowCell(summary.mrn),
      rowCell(orderVisitNumber(item)),
      rowCell(summary.orderCode),
      rowCell(item.status || "Ready to send"),
      rowCell(taipeiTimestamp(item.createdAt)),
      rowCell(item.ack?.code || item.transportError || "-"),
      rowCell(taipeiTimestamp(item.lastSentAt)),
      rowCell(selectButton),
    );
    row.addEventListener("click", () => selectOieOrder(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function selectOieOrder(item) {
  state.selectedOrderId = item.id;
  state.selectedPayload = item.payload || "";
  byId("oie-payload-preview").textContent = state.selectedPayload;
  byId("oie-ack-preview").textContent = ackPreviewText(item);
  renderOieTransmission(item);
  renderOiePreviewSummary("ORM", [
    ["Order ID", item.localOrderNumber],
    ["MRN", item.summary?.mrn],
    ["Visit Number", orderVisitNumber(item)],
    ["Code", item.summary?.orderCode],
    ["Status", item.status],
    ["Created At", taipeiTimestamp(item.createdAt)],
    ["ACK", item.ack?.code || item.transportError || "-"],
  ]);
  renderOieInventory();
}

function renderOieResults(results) {
  const { wrap, tbody } = oieNestedTable(["Type", "Matched Order", "Status", "Received", "Action"]);
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No ORU results for this patient.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    tbody.appendChild(row);
    return wrap;
  }
  results.forEach((item) => {
    const row = document.createElement("tr");
    const previewButton = createElement("button", "Preview", "small-button");
    previewButton.type = "button";
    previewButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieResult(item);
    });
    row.append(
      rowCell(item.messageType || "ORU"),
      rowCell(item.matchedOrderRecordId || "-"),
      rowCell(item.matchStatus),
      rowCell(taipeiTimestamp(item.receivedAt)),
      rowCell(previewButton),
    );
    row.addEventListener("click", () => selectOieResult(item));
    tbody.appendChild(row);
  });
  return wrap;
}

function oiePatientSection(label, title, body) {
  const section = document.createElement("section");
  section.className = "oie-patient-section";
  const heading = document.createElement("div");
  heading.className = "compact-heading oie-patient-section-heading";
  const text = document.createElement("div");
  text.appendChild(createElement("p", label, "eyebrow"));
  text.appendChild(createElement("h3", title));
  heading.appendChild(text);
  section.append(heading, body);
  return section;
}

function oieNestedTable(headers) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap oie-nested-table-wrap";
  const table = document.createElement("table");
  table.className = "oie-nested-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => headRow.appendChild(createElement("th", header)));
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  wrap.appendChild(table);
  return { wrap, tbody };
}

function renderOieTransmission(item) {
  const title = byId("oie-selected-order-title");
  const summary = byId("oie-selected-order-summary");
  const sendButton = byId("send-selected-oie-order");
  summary.replaceChildren();
  sendButton.disabled = !item;
  if (!item) {
    title.textContent = "No order selected";
    summary.appendChild(createElement("p", "Choose an order from an expanded patient row.", "muted"));
    return;
  }
  title.textContent = String(item.localOrderNumber || item.id);
  [
    ["Code", item.summary?.orderCode],
    ["Priority", item.priority],
    ["Status", item.status || "Ready to send"],
    ["Last ACK", item.ack?.code || item.transportError || "-"],
  ].forEach(([label, value]) => {
    const row = document.createElement("p");
    row.appendChild(createElement("strong", `${label}: `));
    row.appendChild(document.createTextNode(String(value ?? "-")));
    summary.appendChild(row);
  });
}

function renderOieUnmatchedResults() {
  const body = byId("oie-unmatched-result-list");
  body.replaceChildren();
  if (!state.unmatchedResults.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No unmatched ORU results.");
    cell.colSpan = 5;
    cell.className = "muted";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  state.unmatchedResults.forEach((item) => {
    const row = document.createElement("tr");
    const previewButton = createElement("button", "Preview", "small-button");
    previewButton.type = "button";
    previewButton.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOieResult(item);
    });
    row.append(
      rowCell(item.messageType || "ORU"),
      rowCell(item.patientMrn || "-"),
      rowCell(item.matchStatus || item.parseStatus),
      rowCell(taipeiTimestamp(item.receivedAt)),
      rowCell(previewButton),
    );
    row.addEventListener("click", () => selectOieResult(item));
    body.appendChild(row);
  });
}

function selectOieResult(item) {
  state.selectedPayload = item.payload || "";
  byId("oie-payload-preview").textContent = state.selectedPayload;
  byId("oie-ack-preview").textContent = item.error || "Result accepted.";
  renderOiePreviewSummary("ORU", [
    ["Type", item.messageType],
    ["MRN", item.patientMrn],
    ["Placer", item.placerOrderNumber],
    ["Filler", item.fillerOrderNumber],
    ["Match", item.matchStatus],
  ]);
}

function ackPreviewText(item) {
  if (item.transportError) return `Transport error: ${item.transportError}`;
  if (item.ack?.payload) return item.ack.payload;
  if (item.ack?.code) return `ACK ${item.ack.code} ${item.ack.controlId || ""} ${item.ack.text || ""}`.trim();
  return "No ACK recorded for this order.";
}

export async function refreshOieInventory() {
  setStatus("oie-inventory-status", "Refreshing...", "pending");
  try {
    const [workbench] = await Promise.all([
      fetchOieWorkbench(),
      refreshOieListenerStatus(),
    ]);
    state.inventory = workbench.patients || [];
    state.unmatchedResults = workbench.unmatchedResults || [];
    renderOieInventory();
    renderSelectedOiePatient();
    renderOieUnmatchedResults();
    setStatus("oie-inventory-status", "Updated", "success");
  } catch (error) {
    setStatus("oie-inventory-status", "Refresh failed", "error");
  }
}

export async function sendOieOrder(orderId, button) {
  button.disabled = true;
  setStatus("oie-inventory-status", "Sending order...", "pending");
  setStatus("oie-send-status", "Sending...", "pending");
  const payload = {
    host: byId("oie-send-host").value.trim(),
    port: Number(byId("oie-send-port").value || 0),
    timeoutSeconds: Number(byId("oie-send-timeout").value || 5),
    mllpFraming: byId("oie-send-mllp").checked,
  };
  try {
    const { response, result } = await sendOieLocalOrder(orderId, payload);
    if (result.item) {
      byId("oie-payload-preview").textContent = result.item.payload || "";
      byId("oie-ack-preview").textContent = ackPreviewText(result.item);
    }
    if (!response.ok || result.success === false) {
      throw new Error(result.error || response.statusText || "Send failed");
    }
    setStatus("oie-inventory-status", "Order sent", "success");
    setStatus("oie-send-status", "Sent", "success");
  } catch (error) {
    setStatus("oie-inventory-status", "Send failed", "error");
    setStatus("oie-send-status", "Send failed", "error");
    if (!byId("oie-ack-preview").textContent.trim()) {
      byId("oie-ack-preview").textContent = error.message;
    }
  } finally {
    await refreshOieInventory();
    button.disabled = !state.selectedOrderId;
  }
}

function renderOieListenerStatus(item = {}) {
  const label = item.running ? `Running ${item.host}:${item.port}` : "Stopped";
  setStatus("oie-listener-status", item.lastError || label, item.lastError ? "error" : (item.running ? "success" : "neutral"));
  if (item.host) byId("oie-listener-host").value = item.host;
  if (item.port) byId("oie-listener-port").value = item.port;
  byId("oie-listener-mllp").checked = item.mllpFraming !== false;
}

async function refreshOieListenerStatus() {
  const result = await fetchOieListenerStatus();
  renderOieListenerStatus(result.item || {});
}

export async function startOieListener() {
  setStatus("oie-listener-status", "Starting...", "pending");
  try {
    const result = await startOieResultListener({
      host: byId("oie-listener-host").value.trim(),
      port: Number(byId("oie-listener-port").value || 6665),
      mllpFraming: byId("oie-listener-mllp").checked,
    });
    renderOieListenerStatus(result.item || {});
  } catch (error) {
    setStatus("oie-listener-status", error.message, "error");
  }
}

export async function stopOieListener() {
  setStatus("oie-listener-status", "Stopping...", "pending");
  try {
    const result = await stopOieResultListener();
    renderOieListenerStatus(result.item || {});
  } catch (error) {
    setStatus("oie-listener-status", error.message, "error");
  }
}
