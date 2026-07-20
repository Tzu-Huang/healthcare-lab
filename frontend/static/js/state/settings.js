const initialSettingsState = Object.freeze({ initialized: false, items: [], selected: null, operation: "", preview: null, confirmation: "", busy: false, refreshRequired: false });

export function createSettingsState() {
  return { ...initialSettingsState };
}

export function clearSettingsPreview(state) {
  state.preview = null; state.confirmation = ""; state.refreshRequired = false;
}
