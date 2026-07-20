const initialSettingsState = Object.freeze({
  initialized: false,
  profile: null,
  runtimeReloadRequired: false,
});

export function createSettingsState() {
  return { ...initialSettingsState };
}

export function listenerSettingsMatchStatus(profile, status) {
  const listener = profile?.resultListener;
  const runningConfigurationMatches = Boolean(
    listener && status?.running
    && listener.host === status.host
    && Number(listener.port) === Number(status.port)
    && Boolean(listener.mllpFraming) === Boolean(status.mllpFraming)
  );
  const intendedDisabledStateMatches = Boolean(
    listener && listener.autoStart === false
    && !status?.running && status?.state === "stopped"
  );
  return runningConfigurationMatches || intendedDisabledStateMatches;
}
