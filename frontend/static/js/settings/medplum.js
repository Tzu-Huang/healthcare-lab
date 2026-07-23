import {
  fetchMedplumProfile, removeMedplumClientSecret, saveAndTestMedplumProfile,
} from "../api/settings.js";
import { byId } from "../core/dom.js";

const state = { initialized: false, profile: null, busy: false };
const element = (id) => byId(id);

function publicProfile(response = {}) {
  const profile = response.item || response.profile || response;
  const fields = profile.fields || profile;
  return {
    ...fields,
    clientSecretConfigured: Boolean(
      profile.secrets?.clientSecret?.configured
      ?? profile.clientSecretConfigured
      ?? profile.secretConfigured
    ),
  };
}

function renderProfile(profile = {}) {
  state.profile = profile;
  element("medplum-enabled").checked = profile.enabled !== false;
  element("medplum-fhir-url").value = profile.fhirBaseUrl || profile.baseUrl || "";
  element("medplum-web-ui-url").value = profile.webUiUrl || "";
  element("medplum-client-id").value = profile.clientId || "";
  element("medplum-client-secret").value = "";
  element("medplum-scope").value = profile.scope || "";
  element("medplum-token-url").value = profile.tokenUrl || "";
  element("medplum-auth-grace").value = profile.authGraceSeconds ?? profile.refreshGraceSeconds ?? 30;
  element("medplum-timeout").value = profile.timeoutSeconds ?? 10;
  const configured = Boolean(profile.clientSecretConfigured || profile.secretConfigured);
  element("medplum-secret-configured").textContent = configured ? "(configured)" : "(not configured)";
  element("medplum-remove-secret").disabled = !configured;
}

function profilePayload() {
  const payload = {
    enabled: element("medplum-enabled").checked,
    baseUrl: element("medplum-fhir-url").value.trim(),
    webUiUrl: element("medplum-web-ui-url").value.trim(),
    clientId: element("medplum-client-id").value.trim(),
    scope: element("medplum-scope").value.trim(),
    tokenUrl: element("medplum-token-url").value.trim(),
    authGraceSeconds: Number(element("medplum-auth-grace").value),
    timeoutSeconds: Number(element("medplum-timeout").value),
  };
  const replacement = element("medplum-client-secret").value;
  return {
    fields: payload,
    secrets: replacement ? { clientSecret: replacement } : {},
  };
}

function normalizedStages(response = {}) {
  const diagnostics = response.diagnostics || response.item?.diagnostics || {};
  const source = diagnostics.stages || response.stages || [];
  if (Array.isArray(source)) return source;
  const labels = {
    metadata: "FHIR metadata",
    oauth: "OAuth token",
    authenticatedRead: "Authenticated FHIR read",
    authenticated_read: "Authenticated FHIR read",
  };
  return Object.entries(source).map(([name, stage]) => ({
    name: labels[name] || name, ...(typeof stage === "object" ? stage : { state: stage }),
  }));
}

function renderStages(response) {
  const container = element("medplum-test-results");
  container.replaceChildren();
  normalizedStages(response).forEach((stage) => {
    const card = document.createElement("article");
    card.className = "settings-diagnostic";
    card.dataset.state = String(stage.state || stage.status || (stage.success ? "ok" : "failed")).toLowerCase();
    const heading = document.createElement("h5");
    heading.textContent = stage.name || stage.stage || "Connection check";
    const summary = document.createElement("p");
    summary.textContent = stage.summary || stage.message || `State: ${stage.state || stage.status || "unknown"}`;
    card.append(heading, summary);
    container.append(card);
  });
}

function setBusy(busy) {
  state.busy = busy;
  element("medplum-save-and-test").disabled = busy;
  element("medplum-remove-secret").disabled = busy || !Boolean(
    state.profile?.clientSecretConfigured || state.profile?.secretConfigured,
  );
}

export async function refreshMedplumSettings() {
  const response = await fetchMedplumProfile();
  renderProfile(publicProfile(response));
  return state;
}

export async function saveAndTestMedplumSettings() {
  if (state.busy) return undefined;
  setBusy(true);
  element("medplum-save-result").textContent = "Saving profile and running bounded checks…";
  try {
    const response = await saveAndTestMedplumProfile(profilePayload());
    const profile = publicProfile(response);
    if (profile && typeof profile === "object") renderProfile(profile);
    element("medplum-save-result").textContent = response.saved === false
      ? `Profile was not saved: ${response.error || response.message || "validation failed"}.`
      : "Medplum profile saved. Connection check results are shown below.";
    renderStages(response);
    return response;
  } catch (error) {
    element("medplum-save-result").textContent = `Profile could not be saved: ${error.message}`;
    throw error;
  } finally {
    setBusy(false);
  }
}

export async function removeMedplumSecret() {
  if (state.busy) return undefined;
  setBusy(true);
  try {
    const response = await removeMedplumClientSecret();
    renderProfile(publicProfile(response));
    element("medplum-save-result").textContent = "Saved OAuth client secret removed.";
    return response;
  } finally {
    setBusy(false);
  }
}

function reportError(error) {
  element("medplum-save-result").textContent = `Medplum settings unavailable: ${error.message}`;
}

export function initializeMedplumSettingsSection(root) {
  if (!root || state.initialized) return state;
  root.dataset.integrationOwner = "medplum";
  element("medplum-save-and-test").addEventListener("click", () => saveAndTestMedplumSettings().catch(reportError));
  element("medplum-remove-secret").addEventListener("click", () => removeMedplumSecret().catch(reportError));
  state.initialized = true;
  return state;
}
