## Context

Healthcare Lab currently seeds dcm4chee as a generic lab server and runs a shallow HTTP smoke check. That is enough for dashboard reachability, but it is not enough for dcm4chee workflow features because MWL order creation, AP MWL query expectations, DICOMweb lookup, viewer links, and C-STORE reconciliation need a shared set of dcm4chee-specific values.

ZAC-34 already established the order/worklist model and reconciliation identifiers. ZAC-35 provides the environment profile that those future workflows depend on.

## Goals / Non-Goals

**Goals:**

- Add a named dcm4chee connection profile that Healthcare Lab can load by key.
- Make local lab defaults explicit and validated.
- Keep DIMSE, MWL, DICOMweb, viewer, auth, and TLS settings in one profile shape.
- Provide diagnostic output that tells the operator what is missing or invalid.
- Preserve the existing dashboard server registry as a health/operations surface.

**Non-Goals:**

- Implement dcm4chee MWL create/update APIs.
- Implement AP MWL query behavior.
- Implement C-STORE receive, parsing, or reconciliation.
- Add production credential management or certificate provisioning.
- Treat Healthcare Lab as a PACS or DICOM object store.

## Decisions

1. Use a dedicated dcm4chee profile shape.

   The generic lab-server registry should remain useful for dashboard health and operations, but the dcm4chee workflow needs structured DICOM values that do not fit cleanly into generic `host`, `port`, `baseUrl`, and `checkConfig` fields.

2. Ship one default local Docker profile.

   The default profile is `local-dcm4chee` and targets the current Docker defaults: Web UI on `127.0.0.1:8082`, DIMSE on `127.0.0.1:11112`, and DICOMweb under `/dcm4chee-arc/aets/DCM4CHEE/rs`.

3. Keep AE titles explicit.

   The initial AE title defaults are:

   | Field | Default |
   | --- | --- |
   | Called AE Title | `DCM4CHEE` |
   | Healthcare Lab Calling AE Title | `HEALTHCARE_LAB` |
   | MWL AE Title | `DCM4CHEE` |
   | Default Scheduled Station AE Title | `ECG_AP` |

4. Predefine DICOMweb endpoint fields.

   The profile should expose a base DICOMweb URL plus derived or explicit endpoint values for query/retrieve/store integrations. The implementation may initially validate and return these values without using them for live DICOMweb requests.

5. Auth and TLS are explicit but disabled for local lab.

   The local profile uses `authMode: none` and `tlsEnabled: false`. The profile should still reserve fields for future auth mode, username/client identity references, token endpoint, TLS verification behavior, certificate/key paths, and notes about unsupported production security.

## Profile Shape

Minimum profile fields:

- `profileName`
- `displayName`
- `environmentName`
- `webUiUrl`
- `dimse.host`
- `dimse.port`
- `dimse.calledAETitle`
- `dimse.callingAETitle`
- `mwl.aeTitle`
- `mwl.defaultScheduledStationAETitle`
- `dicomweb.baseUrl`
- `dicomweb.qidoRsUrl`
- `dicomweb.wadoRsUrl`
- `dicomweb.stowRsUrl`
- `viewer.studyUrlTemplate`
- `security.authMode`
- `security.tlsEnabled`
- `security.tlsVerify`
- `security.username`
- `security.tokenUrl`
- `security.certificatePath`
- `security.privateKeyPath`

## Validation

Validation should report:

- missing profile name, display name, or environment name;
- invalid Web UI or DICOMweb URLs;
- missing DIMSE host or invalid DIMSE port;
- missing called, calling, MWL, or default station AE titles;
- unsupported auth mode;
- inconsistent TLS settings, such as certificate paths without TLS enabled.

The diagnostic endpoint should return a machine-readable list of checks and a human-readable summary so the dashboard or future dcm4chee pages can display useful errors.

## Risks / Trade-offs

- [Risk] Duplicating server identity between lab-server registry and dcm4chee profile can drift. -> Mitigation: keep profile as workflow configuration and server registry as operations metadata; validation can include both when needed.
- [Risk] dcm4chee endpoint paths may vary by deployment. -> Mitigation: allow explicit endpoint overrides rather than deriving all URLs permanently from one base.
- [Risk] Security placeholders can look production-ready. -> Mitigation: label local defaults as unauthenticated lab settings and make unsupported production security explicit.
