const initialSettingsState = Object.freeze({ initialized: false });

export function createSettingsState() {
  return { ...initialSettingsState };
}
