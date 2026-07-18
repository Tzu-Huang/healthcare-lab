import { byId } from "./dom.js";

export async function copyTextFromElement(elementId) {
  const text = byId(elementId)?.textContent || "";
  if (!text.trim()) return;
  await navigator.clipboard.writeText(text);
}
