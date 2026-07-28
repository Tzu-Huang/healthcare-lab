import { ecgRenderSvgUrl, fetchEcgMetadata } from "../api/ecg-viewer.js";

const elements = {
  status: document.getElementById("ecg-viewer-status"),
  loading: document.getElementById("ecg-viewer-loading"),
  content: document.getElementById("ecg-viewer-content"),
  error: document.getElementById("ecg-viewer-error"),
  errorMessage: document.getElementById("ecg-viewer-error-message"),
  retry: document.getElementById("ecg-viewer-retry"),
  graph: document.getElementById("ecg-viewer-graph"),
  graphError: document.getElementById("ecg-viewer-graph-error"),
  leads: document.getElementById("ecg-viewer-leads"),
  sampleRate: document.getElementById("ecg-viewer-sample-rate"),
  unit: document.getElementById("ecg-viewer-unit"),
  duration: document.getElementById("ecg-viewer-duration"),
};

export function resultIdFromPath(pathname = window.location.pathname) {
  const match = pathname.match(/^\/viewer\/ecg\/([1-9]\d*)\/?$/);
  return match ? match[1] : "";
}

function setStatus(message, state) {
  elements.status.textContent = message;
  elements.status.className = `status ${state} ecg-viewer-status`;
}

function resetView() {
  elements.loading.hidden = false;
  elements.content.hidden = true;
  elements.error.hidden = true;
  elements.graphError.hidden = true;
  elements.graph.removeAttribute("src");
  setStatus("Loading ECG metadata...", "pending");
}

function controlledError(error) {
  if (error?.status === 404 || error?.code === "dcm4chee_ecg_result_not_found") {
    return "This ECG result was not found. Return to Healthcare Lab and choose another result.";
  }
  if (
    [409, 415, 422].includes(error?.status)
    || ["dcm4chee_ecg_instance_incomplete", "dcm4chee_ecg_unsupported", "dcm4chee_ecg_invalid"].includes(error?.code)
  ) {
    return "This result cannot be displayed as a supported ECG graph.";
  }
  return "The ECG could not be retrieved. Retry when the archive connection is available.";
}

function displayNumber(value, suffix, maximumFractionDigits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(number)} ${suffix}`;
}

function showMetadata(item) {
  const waveform = item?.waveform || {};
  elements.leads.textContent = Array.isArray(waveform.leads) && waveform.leads.length
    ? waveform.leads.join(", ")
    : "-";
  elements.sampleRate.textContent = displayNumber(waveform.samplingFrequencyHz, "Hz");
  elements.unit.textContent = String(waveform.unit || "-");
  elements.duration.textContent = displayNumber(waveform.durationSeconds, "seconds");
  elements.loading.hidden = true;
  elements.content.hidden = false;
}

function loadGraph(resultId) {
  return new Promise((resolve, reject) => {
    elements.graph.onload = () => resolve();
    elements.graph.onerror = () => reject(new Error("ECG graph failed to load."));
    elements.graph.src = `${ecgRenderSvgUrl(resultId)}?v=${Date.now()}`;
  });
}

export async function loadEcgViewer(resultId = resultIdFromPath()) {
  resetView();
  if (!resultId) {
    elements.loading.hidden = true;
    elements.error.hidden = false;
    elements.errorMessage.textContent = "This ECG viewer address is invalid.";
    setStatus("ECG viewer address is invalid.", "error");
    return;
  }

  try {
    const item = await fetchEcgMetadata(resultId);
    showMetadata(item);
    setStatus("ECG summary loaded. Loading graph...", "pending");
    try {
      await loadGraph(resultId);
      setStatus("ECG graph loaded.", "success");
    } catch {
      elements.graph.removeAttribute("src");
      elements.graphError.hidden = false;
      setStatus("ECG summary loaded, but the graph is unavailable.", "error");
    }
  } catch (error) {
    elements.loading.hidden = true;
    elements.error.hidden = false;
    elements.errorMessage.textContent = controlledError(error);
    setStatus("ECG graph unavailable.", "error");
  }
}

elements.retry?.addEventListener("click", () => loadEcgViewer());
loadEcgViewer();
