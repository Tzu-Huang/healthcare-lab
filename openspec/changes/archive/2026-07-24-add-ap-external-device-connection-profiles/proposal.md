## Why

AP identity and endpoint values are currently duplicated across OIE managed Channels, GDT Bridge settings, dcm4chee settings, and deployment defaults. Operators need one reusable, validated AP or external-device profile so every enabled protocol path resolves the same device identity without weakening existing guarded activation workflows.

## What Changes

- Add persisted AP/external-device profiles with unique names, enabled state, environment, supported transports, safe descriptive metadata, and exactly one default per environment.
- Add protocol-specific HL7/MLLP, GDT, and DICOM subprofiles with conditional completeness and identity validation.
- Add application services that resolve one effective AP profile and project its values into OIE desired configuration, GDT Bridge workflows, and dcm4chee workflows.
- Report OIE endpoint drift as `apply-required` without automatically previewing, applying, deploying, or redeploying a managed Channel.
- Add bounded protocol-aware connectivity checks and a PHI-safe last-observed-interaction projection containing metadata only.
- Replace the AP / External Devices Settings placeholder with profile management, diagnostics, activation guidance, and Settings Overview readiness.

## Capabilities

### New Capabilities

- `healthcare-lab-ap-device-profiles`: Defines multi-profile AP/external-device persistence, validation, default selection, effective resolution, diagnostics, and safe interaction metadata.

### Modified Capabilities

- `healthcare-lab-typed-integration-settings`: Defines the ownership boundary between multi-record AP profiles and existing single-record integration profiles.
- `healthcare-lab-settings-workspace`: Adds an integration-owned AP / External Devices workspace, readiness, and diagnostics.
- `healthcare-lab-oie-managed-channel-lifecycle`: Projects effective AP HL7 endpoints into desired state while preserving guarded preview/apply behavior.
- `healthcare-lab-gdt-bridge-settings`: Associates AP GDT identity with the selected GDT Bridge profile.
- `healthcare-lab-dcm4chee-connection-profile`: Uses effective AP DICOM identity for MWL and result-delivery roles without conflating archive and device endpoints.

## Impact

- Adds AP profile schema, repository, application services, APIs, validation, diagnostics, readiness composition, and modular frontend ownership.
- Changes effective configuration composition for OIE ORM-to-AP desired state, GDT identity, dcm4chee MWL station identity, and DICOM result delivery.
- Adds migration, domain, repository, service, API, lifecycle-drift, workflow, readiness, diagnostics, privacy, and frontend tests.
- Does not automatically mutate OIE, expose raw HL7/GDT/DICOM payloads, or change deployment-owned port publication and container topology.
