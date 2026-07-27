## Why

The unified Settings series now supports zero-edit Docker startup and persisted
integration configuration, but the complete fresh-install and legacy-upgrade
experience has not been verified as one operator journey. The English and
Traditional Chinese handbooks also still describe the superseded mandatory
`.env` workflow, so they cannot serve as reliable release instructions.

## What Changes

- Add a repeatable, disposable verification matrix for fresh installation,
  guided setup, restart, container recreation, and upgrade from representative
  legacy database and environment state.
- Verify failure classification and recovery guidance for Medplum, GDT,
  dcm4chee, AP, and OIE without exposing secrets, PHI, raw messages, FHIR
  bodies, or arbitrary upstream responses.
- Prove that persisted Settings remain authoritative after one-time legacy
  bootstrap and that the Settings UI cannot rewrite Compose or invoke arbitrary
  Docker operations.
- Rewrite the English and Traditional Chinese operator handbooks around one
  supported Docker start command followed by browser-based guided setup.
- Document Medplum ClientApplication creation, Settings versus Advanced
  deployment ownership, Windows GDT host/container paths, internal versus
  browser URLs, secret rotation, backup/restore implications, and activation
  semantics.
- Record synthetic, credential-free live evidence or a precise
  environment-dependent skip; route any discovered implementation defect to a
  separate linked issue rather than expanding this closure change silently.

## Capabilities

### New Capabilities

- `healthcare-lab-settings-release-verification`: Defines the disposable
  first-run and upgrade release gate, safe failure matrix, operator handbook
  contract, and evidence requirements for unified Settings.

### Modified Capabilities

None.

## Impact

The change affects disposable verification tooling and fixtures, release-gate
tests, synthetic evidence records, `README.md`, deployment guidance, and the
English and Traditional Chinese handbook sources and generated Word artifacts.
Normal product behavior changes are out of scope; reproducible defects found
during verification block closure or move to separate linked Linear issues.
