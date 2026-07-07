## Overview

This change should promote GDT from a backend-capable order/result path into a
complete Healthcare Lab console. The console should mirror the OIE page's
patient-centered structure so users can move predictably from patient context
to orders, results, artifacts, and raw payloads.

The implementation should build on existing local GDT persistence and adapter
behavior instead of introducing a separate simulator subsystem.

## UI Model

Add a sidebar `GDT` view with these panels:

- `GDT Patients`: local GDT-capable patients with MRN, GDT patient number, name,
  order count, result count, and latest activity.
- `Selected Patient`: demographic summary and patient-scoped actions.
- `GDT Orders`: local ECG orders for the selected patient with order number,
  `8402=EKG01`, status, requested time, result state, updated time, and actions.
- `Bridge Inbox`: inbound `.gdt` files discovered in the configured bridge
  inbound folder, including pending/imported/error status and import action.
- `GDT Results`: imported `6310` messages for the selected patient/order with
  match status, result status, measurement summary, attachment count, received
  time, and actions.
- `Artifacts`: PDF/DICOM/other artifact references linked to the selected
  result/order. Show format, description, reference/path/URL, role, and copy or
  open/download action where possible.
- `Preview/Detail`: selected raw `6302`, raw `6310`, canonical JSON,
  measurements, text fields, attachment details, and event trail.

The GDT console should not replace the Service Health Dashboard. The existing
OpenEMR/GDT dashboard action may navigate to the GDT console or continue to
open the existing Order flow, but the full bridge workflow should live in the
GDT console.

## Bridge Folder Behavior

Use the existing configured GDT bridge root and folder contract where possible:

- `outbox/`: generated `6302` request files.
- `inbound/`: incoming `6310` result files.
- `archive/`: imported inbound files after processing when archiving is safe.
- `error/`: files that could not be read or parsed.
- `reports/` or externally referenced paths: artifact locations referenced by
  `6305`.

`Write 6302` should write a selected order's already-generated raw GDT request
to an outbox file using a deterministic, collision-resistant filename. File
writing should use a temp file plus rename so the bridge never sees a partial
file.

`Import 6310` should read a selected inbound file, persist the raw text, parse
it through the adapter, match it when possible, register artifacts, record
events, and mark the file imported/error for visibility. Import should not fail
only because a referenced artifact path cannot be opened or verified.

## Artifact Mapping

For `6310` artifact groups, follow the GDT bridge knowledge base:

| GDT field | Meaning |
| --- | --- |
| `6302` | artifact group or artifact identifier |
| `6303` | artifact format, such as `PDF` or `DICOM` |
| `6304` | artifact description |
| `6305` | artifact reference, file path, UNC path, or URL |

Healthcare Lab should persist artifact metadata/reference records only:

- format,
- description,
- role,
- original `6305` reference,
- source file name/path when imported from a bridge file,
- linked order/message/result,
- validation/import warning details where applicable.

PDF and DICOM bytes are not copied into a managed store in this change.

## Demo Result

`Demo Result` should create deterministic `6310` content for a selected local
GDT order. It should include at least:

- order correlation,
- `3000` GDT patient number,
- `8402=EKG01`,
- result status,
- HR, PR, QRS, QT, and QTC measurements,
- result interpretation/comment/formatted text,
- a PDF artifact reference,
- a DICOM artifact reference.

The demo path may either write a file into `inbound/` and import it, or call the
same backend import operation with generated raw text. Prefer the path that
exercises shared-folder behavior if it remains simple and deterministic.

## API Shape

Prefer additive APIs around the existing GDT endpoints:

- list console/workbench data for GDT patients, orders, results, artifacts, and
  bridge inbox state,
- write/export a selected order's `6302`,
- list inbound files,
- import an inbound `6310`,
- import pasted raw `6310`,
- create/import a demo result for a selected order.

Keep `/api/gdt/orders` and `/api/gdt/results` compatible for existing tests and
callers.

## Validation and Error Handling

GDT syntax and canonical mapping still go through the adapter. Format failures
should surface as import errors, retain the raw file/text where feasible, and
record an error event/status.

Artifact reference validation is intentionally non-blocking for ZAC-24:

- missing file/reference: warning/status detail,
- unsupported artifact format: warning/status detail,
- malformed URL/path: warning/status detail,
- result import still persists the raw `6310` and canonical data when the GDT
  result itself can be parsed.

## Testing Strategy

Add focused coverage for:

- GDT console/workbench API shape.
- `Write 6302` creates an outbox file and records export state/events.
- Inbound `6310` import persists raw, parsed, canonical, match status, and
  events.
- `6302-6305` artifact groups map `6305` into artifact reference/path/URL.
- Missing artifact target records a warning without blocking result import.
- `Demo Result` produces deterministic measurements and artifact references.
- Frontend contract tests that the GDT sidebar/view, bridge inbox, order
  actions, result measurements, and artifact reference UI are present.
