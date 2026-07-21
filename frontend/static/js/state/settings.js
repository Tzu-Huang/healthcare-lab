const initialSettingsState = Object.freeze({
  initialized: false, profile: null, runtime: null, runtimeReloadRequired: false,
  items: [], selected: null, operation: "", preview: null, confirmation: "",
  busy: false, refreshRequired: false, originalListenerPort: null,
});

export function createSettingsState() { return { ...initialSettingsState, items: [] }; }

export function listenerSettingsMatchStatus(profile, status) {
  const listener = profile?.resultListener;
  const runningConfigurationMatches = Boolean(listener && listener.autoStart !== false && status?.running
    && listener.host === status.host && Number(listener.port) === Number(status.port)
    && Boolean(listener.mllpFraming) === Boolean(status.mllpFraming));
  const intendedDisabledStateMatches = Boolean(listener && listener.autoStart === false
    && !status?.running && status?.state === "stopped");
  return runningConfigurationMatches || intendedDisabledStateMatches;
}

export function clearSettingsPreview(state) {
  state.preview = null; state.confirmation = ""; state.refreshRequired = false;
}

export function displayedChannelName(item, preview = null) {
  return preview?.channelName || preview?.snapshot?.name || item?.name || item?.channelName || item?.logicalType || "Managed Channel";
}

export function channelRoute(item, preview = null) {
  return preview?.route || item?.route || item?.displayRoute
    || [item?.source, item?.destination].filter(Boolean).join(" → ") || "Route unavailable";
}
