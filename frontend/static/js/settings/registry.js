export const SETTINGS_SECTIONS = Object.freeze([
  { id: "overview", label: "Overview", required: true },
  { id: "medplum", label: "Medplum", required: true },
  { id: "oie", label: "OIE", required: true },
  { id: "gdt-bridge", label: "GDT Bridge", required: false },
  { id: "dcm4chee", label: "dcm4chee", required: false },
  { id: "external-devices", label: "AP / External Devices", required: false },
  { id: "deployment", label: "Deployment & Diagnostics", required: true },
]);

export function sectionById(id) {
  return SETTINGS_SECTIONS.find((section) => section.id === id);
}
