## Why

Healthcare Lab can already write GDT `6302` order files and import selected
`6310` result files from the shared-folder bridge. That current import path is
operator-triggered: a user must refresh the inbox and choose a file to import.

GDT file exchange standards describe a more automatic AIS/EDP behavior for
shared-folder result acquisition. The receiver should process available result
files in FIFO order, avoid partial files, and remove successfully processed
files from the exchange folder. Healthcare Lab should model that background
acquisition behavior while preserving lab-grade observability for demos and
debugging.

## What Changes

- Add a background GDT bridge inbound watcher that can be started, stopped, and
  inspected from backend APIs and the GDT console.
- Add a shared batch import service used by both manual selected-file import
  and the watcher.
- Process inbound result files in FIFO order based on creation time when
  available, with deterministic fallback ordering for platforms where creation
  time is unreliable.
- Skip temporary or unstable files so Healthcare Lab does not read a device
  result while it is still being written.
- Claim files before import by renaming or moving them into a processing state,
  then route them to delete/archive/error handling after processing.
- Support configurable post-success behavior:
  - standards-oriented delete mode,
  - lab/debug archive mode with clear documentation that it is a PoC deviation.
- Add configurable filename binding checks for GDT 2.1 legacy, GDT 3.5 binding,
  and permissive lab mode.
- Preserve the current safe matching behavior: do not attach a `6310` result to
  the latest order by patient number alone.
- Extend docs/tests for automatic import, FIFO behavior, temporary-file safety,
  post-success delete/archive behavior, binding filters, and watcher status.

## Non-Goals

- No OS-specific filesystem event watcher requirement; polling is acceptable
  and preferred for Docker bind mounts, Windows folders, and network shares.
- No production Windows service, daemon installer, or process supervisor.
- No full GDT 3.5 object model parser.
- No automatic patient-only order matching for ambiguous results.
- No artifact byte ingestion, PDF parsing, DICOM parsing, or PACS send.
- No changes to HL7, FHIR, OIE, Medplum, or dcm4chee workflows.

## Key Decisions

- Polling first: use a small background polling worker rather than relying on
  filesystem events because shared folders and Docker mounts are less reliable
  with native watcher APIs.
- One import path: manual import and background import must share the same
  backend batch-import operation.
- FIFO interpretation: prefer creation time for GDT conformance, fall back to
  modification time plus filename where the platform cannot provide a reliable
  creation timestamp.
- File safety: ignore `.tmp`, `.temp`, hidden, and processing files; require a
  file to be stable before importing; claim the file before parsing.
- Delete/archive mode: default lab behavior may archive for observability, but
  standards-oriented mode must delete successfully processed exchange files.
- Matching safety: future GDT 3.5 `8314` Request-UID and `8408` Study-UID
  support may improve matching, but patient-only matching must remain
  non-automatic unless a user explicitly resolves it.

## Capabilities

### Modified Capabilities

- `healthcare-lab-gdt-bridge-console`: Add automatic inbound result acquisition,
  watcher lifecycle controls/status, FIFO batch import, safe file claiming, and
  configurable post-success delete/archive behavior.

## Impact

- Affected code: Flask GDT bridge APIs, GDT bridge file helpers, import
  service code, watcher lifecycle object, frontend GDT console controls/status,
  and tests.
- Affected runtime: local Flask process owns an in-process polling worker while
  the app is running.
- Affected files: configured `inbound/`, optional processing state, `archive/`,
  and `error/` folders under the GDT bridge root.
- Affected docs/tests: update GDT bridge documentation to distinguish standard
  delete behavior from PoC archive behavior and add regression coverage for
  automatic import edge cases.
