import {
  initializeOieSettingsSection,
  refreshSettings as refreshOieSettings,
} from "./oie.js";
import {
  initializeMedplumSettingsSection,
  refreshMedplumSettings,
} from "./medplum.js";
import {
  initializeGdtBridgeSettingsSection,
  refreshGdtBridgeSettings,
} from "./gdt-bridge.js";
import {
  initializeDcm4cheeSettingsSection,
  refreshDcm4cheeSettings,
} from "./dcm4chee.js";
import {
  initializeExternalDeviceSettingsSection,
  refreshExternalDeviceSettings,
} from "./external-devices.js";

const noOpInitialize = () => {};
const noOpRefresh = async () => undefined;

export function defineSettingsModule(definition) {
  const requiredKeys = ["id", "label", "required", "owners"];
  if (requiredKeys.some((key) => definition[key] === undefined)) {
    throw new TypeError("Settings modules require identity, navigation, and ownership metadata.");
  }
  const ownerKeys = ["view", "api", "state", "style"];
  if (ownerKeys.some((key) => !definition.owners[key])) {
    throw new TypeError("Settings modules must declare view, API, state, and style owners.");
  }
  return Object.freeze({
    ...definition,
    owners: Object.freeze({ ...definition.owners }),
    initialize: definition.initialize || noOpInitialize,
    refresh: definition.refresh || noOpRefresh,
  });
}

const workspaceOwners = Object.freeze({
  view: "settings/workspace.js",
  api: "api/readiness.js",
  state: "settings/workspace.js",
  style: "css/views/settings.css",
});

const integrationModule = (definition) => defineSettingsModule({
  initialize: noOpInitialize,
  refresh: noOpRefresh,
  ...definition,
});

export const SETTINGS_MODULES = Object.freeze([
  defineSettingsModule({ id: "overview", label: "Overview", required: true, owners: workspaceOwners }),
  integrationModule({
    id: "medplum", label: "Medplum", required: true,
    owners: { view: "settings/medplum.js", api: "api/settings.js", state: "state/settings.js", style: "css/views/settings.css" },
    initialize: initializeMedplumSettingsSection,
    refresh: refreshMedplumSettings,
  }),
  integrationModule({
    id: "oie", label: "OIE", required: true,
    owners: { view: "settings/oie.js", api: "api/settings.js", state: "state/settings.js", style: "css/views/settings.css" },
    initialize: initializeOieSettingsSection,
    refresh: refreshOieSettings,
  }),
  integrationModule({
    id: "gdt-bridge", label: "GDT Bridge", required: false,
    owners: { view: "settings/gdt-bridge.js", api: "settings/gdt-bridge.js", state: "settings/gdt-bridge.js", style: "css/settings/gdt-bridge.css" },
    initialize: initializeGdtBridgeSettingsSection,
    refresh: refreshGdtBridgeSettings,
  }),
  integrationModule({
    id: "dcm4chee", label: "dcm4chee", required: false,
    owners: { view: "settings/dcm4chee.js", api: "settings/dcm4chee.js", state: "settings/dcm4chee.js", style: "css/settings/dcm4chee.css" },
    initialize: initializeDcm4cheeSettingsSection,
    refresh: refreshDcm4cheeSettings,
  }),
  integrationModule({
    id: "external-devices", label: "AP / External Devices", required: false,
    owners: { view: "settings/external-devices.js", api: "settings/external-devices.js", state: "settings/external-devices.js", style: "css/settings/external-devices.css" },
    initialize: initializeExternalDeviceSettingsSection,
    refresh: refreshExternalDeviceSettings,
  }),
  defineSettingsModule({
    id: "deployment", label: "Deployment & Diagnostics", required: true, owners: workspaceOwners,
  }),
]);

export const SETTINGS_SECTIONS = Object.freeze(
  SETTINGS_MODULES.map(({ id, label, required }) => Object.freeze({ id, label, required })),
);

export function sectionById(id) {
  return SETTINGS_SECTIONS.find((section) => section.id === id);
}

export function moduleById(id) {
  return SETTINGS_MODULES.find((module) => module.id === id);
}
