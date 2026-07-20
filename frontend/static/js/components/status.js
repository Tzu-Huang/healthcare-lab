import { byId } from "../core/dom.js";

export function setStatus(id, message, state = "neutral") {
  const element = byId(id);
  if (!element) return;
  element.textContent = message;
  element.className = `status ${state}`;
}
