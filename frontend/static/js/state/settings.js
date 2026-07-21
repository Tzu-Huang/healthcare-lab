const initialSettingsState = Object.freeze({
  initialized: false,
  profile: null,
  runtimeReloadRequired: false,
});
const initialSettingsState = Object.freeze({ initialized: false, items: [], selected: null, operation: "", preview: null, confirmation: "", busy: false, refreshRequired: false });

export function createSettingsState() {
  return { ...initialSettingsState };
}

export function listenerSettingsMatchStatus(profile, status) {
  const listener = profile?.resultListener;
  const runningConfigurationMatches = Boolean(
    listener && listener.autoStart !== false && status?.running
    && listener.host === status.host
    && Number(listener.port) === Number(status.port)
    && Boolean(listener.mllpFraming) === Boolean(status.mllpFraming)
  );
  const intendedDisabledStateMatches = Boolean(
    listener && listener.autoStart === false
    && !status?.running && status?.state === "stopped"
  );
  return runningConfigurationMatches || intendedDisabledStateMatches;
export function clearSettingsPreview(state) {
  state.preview = null; state.confirmation = ""; state.refreshRequired = false;
}
