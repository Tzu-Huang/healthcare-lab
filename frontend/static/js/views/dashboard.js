import { checkAllDashboardServices, fetchDashboardServices, runDashboardChildAction, runDashboardServiceAction } from "../api/dashboard.js";
import { setStatus } from "../components/status.js";
import { byId, createElement, rowCell } from "../core/dom.js";

const state = {
  services: [],
  events: [],
  resources: null,
  expandedServiceIds: new Set(),
};
let initialized = false;

export function initializeDashboardView() {
  if (initialized) return;
  initialized = true;
  byId("refresh-dashboard").addEventListener("click", refreshDashboard);
  byId("run-all-lab-checks").addEventListener("click", runAllChecks);
  byId("dashboard-filter").addEventListener("input", renderServices);
}
export function statusClass(status) {
  return {
    Healthy: "success",
    Degraded: "warning",
    Down: "error",
    Unknown: "neutral",
  }[status] || "neutral";
}

function renderSummary(summary = {}) {
  byId("dashboard-total-count").textContent = summary.total ?? 0;
  byId("dashboard-running-count").textContent = summary.running ?? 0;
  byId("dashboard-attention-count").textContent = summary.attention ?? 0;
  byId("dashboard-cpu-total").textContent = `${summary.cpuPercent ?? 0}%`;
  byId("dashboard-memory-total").textContent = `${summary.memoryPercent ?? 0}%`;
}

function replaceDashboardService(service) {
  if (!service?.id) return;
  const index = state.services.findIndex((item) => item.id === service.id);
  if (index >= 0) {
    state.services[index] = service;
  } else {
    state.services.push(service);
  }
  renderServices();
}

function applyDashboardPayload(result) {
  if (result.items) state.services = result.items;
  if (result.events) state.events = result.events;
  if (result.resources) state.resources = result.resources;
  if (result.summary) renderSummary(result.summary);
  renderServices();
  renderResources();
  renderEvents();
}

function actionButton(service, action, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = !service.capabilities?.[action];
  button.addEventListener("click", () => runServiceAction(service.id, action));
  return button;
}

function childActionButton(service, child, action, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = !child.capabilities?.[action];
  button.addEventListener("click", () => runChildServiceAction(service.id, child.id, action));
  return button;
}

function dashboardServiceToggle(service) {
  const button = document.createElement("button");
  const expanded = state.expandedServiceIds.has(service.id);
  button.type = "button";
  button.className = "dashboard-service-toggle";
  button.textContent = expanded ? "▾" : "▸";
  button.setAttribute("aria-expanded", String(expanded));
  button.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${service.label} sub-services`);
  button.addEventListener("click", () => {
    if (expanded) {
      state.expandedServiceIds.delete(service.id);
    } else {
      state.expandedServiceIds.add(service.id);
    }
    renderServices();
  });
  return button;
}

function renderDashboardChild(service, child, body) {
  const row = document.createElement("tr");
  row.className = "dashboard-child-row";

  const serviceCell = document.createElement("td");
  const identity = createElement("div", "", "dashboard-child-identity");
  identity.append(
    createElement("strong", child.name),
    createElement("span", child.role, "muted dashboard-cell-subtext"),
  );
  serviceCell.appendChild(identity);
  row.appendChild(serviceCell);

  row.appendChild(rowCell(createElement("span", child.runtime?.state || child.status, `status ${statusClass(child.status)}`)));

  const checks = document.createElement("div");
  checks.className = "dashboard-checks";
  checks.appendChild(createElement("span", child.runtime?.detail || "Docker runtime state unavailable"));
  row.appendChild(rowCell(checks));

  const actions = document.createElement("div");
  actions.className = "button-row compact-actions";
  actions.append(
    childActionButton(service, child, "check", "Check"),
    childActionButton(service, child, "enable", "Start"),
    childActionButton(service, child, "disable", "Stop"),
    childActionButton(service, child, "restart", "Restart"),
  );
  row.appendChild(rowCell(actions));
  body.appendChild(row);
}

function renderServices() {
  const body = byId("dashboard-service-list");
  const filter = byId("dashboard-filter").value.trim().toLowerCase();
  body.replaceChildren();
  const visible = state.services.filter((service) => {
    const childNames = (service.children || []).map((child) => child.name).join(" ");
    const haystack = `${service.label} ${service.protocol} ${service.backend} ${childNames}`.toLowerCase();
    return !filter || haystack.includes(filter);
  });
  if (!visible.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No services match the current filter.");
    cell.colSpan = 4;
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  visible.forEach((service) => {
    const row = document.createElement("tr");
    row.className = "dashboard-primary-row";
    const serviceCell = document.createElement("td");
    const identity = createElement("div", "", "dashboard-primary-identity");
    if (service.children?.length) identity.appendChild(dashboardServiceToggle(service));
    const text = createElement("div");
    text.appendChild(createElement("strong", service.label));
    text.appendChild(createElement("span", service.protocol, "muted dashboard-cell-subtext"));
    identity.appendChild(text);
    serviceCell.appendChild(identity);
    row.appendChild(serviceCell);

    const status = createElement("span", service.status, `status ${statusClass(service.status)}`);
    row.appendChild(rowCell(status));

    const checks = document.createElement("div");
    checks.className = "dashboard-checks";
    ["process", "application", "protocol"].forEach((key) => {
      checks.appendChild(createElement("span", `${key}: ${service.checks?.[key] || "Unknown"}`));
    });
    row.appendChild(rowCell(checks));

    const actions = document.createElement("div");
    actions.className = "button-row compact-actions";
    actions.appendChild(actionButton(service, "check", "Check"));
    actions.appendChild(actionButton(service, "enable", "Start"));
    actions.appendChild(actionButton(service, "disable", "Stop"));
    actions.appendChild(actionButton(service, "restart", "Restart"));
    row.appendChild(rowCell(actions));
    body.appendChild(row);
    if (state.expandedServiceIds.has(service.id)) {
      (service.children || []).forEach((child) => renderDashboardChild(service, child, body));
    }
  });
}

function renderResources() {
  const container = byId("dashboard-resource-usage");
  container.replaceChildren();
  if (!state.resources || state.resources.status !== "ok") {
    container.appendChild(createElement("p", state.resources?.message || "Docker stats unavailable.", "muted"));
    return;
  }
  const visibleContainers = DASHBOARD_RESOURCE_CONTAINERS.map((target) => {
    const stats = state.resources.containers.find((item) => {
      const normalizedName = String(item.name || "").replaceAll("_", "-").toLowerCase();
      return target.aliases.some((alias) => (
        normalizedName === alias || normalizedName.endsWith(`-${alias}`)
      ));
    });
    return stats ? { ...stats, displayName: target.displayName } : {
      displayName: target.displayName,
      cpuPercent: null,
      memoryUsedMiB: null,
      memoryLimitMiB: null,
    };
  });
  visibleContainers.forEach((containerStats) => {
    const item = document.createElement("div");
    item.className = "resource-item";
    item.appendChild(createElement("span", containerStats.displayName));
    const cpuPercent = Number(containerStats.cpuPercent);
    const hasStats = Number.isFinite(cpuPercent);
    item.appendChild(createElement("strong", hasStats ? `${containerStats.cpuPercent}% CPU` : "No stats"));
    const progress = document.createElement("div");
    progress.className = "progress";
    const progressBar = document.createElement("i");
    progressBar.style.width = `${hasStats ? Math.min(cpuPercent, 100) : 0}%`;
    progress.appendChild(progressBar);
    item.appendChild(progress);
    item.appendChild(
      createElement(
        "span",
        hasStats
          ? `Memory ${containerStats.memoryUsedMiB} / ${containerStats.memoryLimitMiB} MiB`
          : "Memory unavailable",
      ),
    );
    container.appendChild(item);
  });
}

function renderEvents() {
  const body = byId("dashboard-event-log");
  body.replaceChildren();
  if (!state.events.length) {
    const row = document.createElement("tr");
    const cell = rowCell("No dashboard events recorded.");
    cell.colSpan = 3;
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  state.events.forEach((event) => {
    const row = document.createElement("tr");
    row.appendChild(rowCell(event.timestamp || ""));
    row.appendChild(rowCell(event.level || ""));
    row.appendChild(rowCell(event.message || ""));
    body.appendChild(row);
  });
}

export async function refreshDashboard() {
  setStatus("dashboard-refresh-status", "Refreshing...", "pending");
  try {
    const result = await fetchDashboardServices();
    applyDashboardPayload(result);
    setStatus("dashboard-refresh-status", "Dashboard updated", "success");
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runServiceAction(serviceId, action) {
  setStatus("dashboard-refresh-status", `${action} running...`, "pending");
  try {
    const result = await runDashboardServiceAction(serviceId, action, {
      method: "POST",
      body: JSON.stringify({}),
    });
    replaceDashboardService(result.service);
    setStatus("dashboard-refresh-status", `${action} complete`, "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runChildServiceAction(serviceId, childId, action) {
  setStatus("dashboard-refresh-status", `${childId} ${action} running...`, "pending");
  try {
    const result = await runDashboardChildAction(serviceId, childId, action, {
      method: "POST",
      body: JSON.stringify({}),
    });
    replaceDashboardService(result.service);
    setStatus("dashboard-refresh-status", `${childId} ${action} complete`, "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}

async function runAllChecks() {
  setStatus("dashboard-refresh-status", "Running all checks...", "pending");
  try {
    const result = await checkAllDashboardServices({
      method: "POST",
      body: JSON.stringify({}),
    });
    applyDashboardPayload(result);
    setStatus("dashboard-refresh-status", "Checks complete", "success");
    setTimeout(refreshDashboard, 1000);
  } catch (error) {
    setStatus("dashboard-refresh-status", error.message, "error");
  }
}
