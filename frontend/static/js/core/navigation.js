import { byId } from "./dom.js";

const activators = new Map();
let initialized = false;

export function registerViewActivation(viewId, title, activate) {
  activators.set(viewId, { title, activate });
}

export function activateView(viewId) {
  document.querySelectorAll(".app-view").forEach((view) => {
    view.hidden = view.id !== viewId;
  });
  document.querySelectorAll(".sidebar-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.navTarget === viewId);
  });
  const registration = activators.get(viewId);
  const title = byId("view-title");
  if (title) title.textContent = registration?.title || "Healthcare Lab";
  Promise.resolve(registration?.activate?.()).catch((error) => {
    const view = byId(viewId);
    if (view) view.dataset.initializationError = error?.message || "View activation failed";
    document.dispatchEvent(new CustomEvent("healthcare-lab:view-error", {
      detail: { viewId, error },
    }));
  });
}

export function initializeNavigation() {
  if (initialized) return;
  initialized = true;
  document.querySelectorAll("[data-nav-target]").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.navTarget));
  });
}
