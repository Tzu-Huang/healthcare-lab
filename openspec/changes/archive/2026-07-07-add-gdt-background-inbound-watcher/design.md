## Overview

This change should turn Healthcare Lab's manual GDT `6310` bridge import into a
background-capable acquisition path. The implementation should keep the current
manual import affordance, but manual and automatic import must use the same
batch import service so file handling, parsing, matching, artifact registration,
and events stay consistent.

The watcher is an in-process lab utility, not a production daemon. It should be
small, inspectable, and easy to stop before changing the bridge folder path.

## Runtime Model

Add a `GdtBridgeInboundWatcher` owned by the Flask app extensions:

- configured with the current `GDT_BRIDGE_PATH`,
- configured with a poll interval, defaulting to a small value such as 2
  seconds,
- exposes `status()`, `start()`, `stop()`, and `configure_bridge_root()`,
- stores last run summary and last error for the console,
- runs as a daemon thread only while explicitly enabled.

Changing the GDT bridge path should be rejected while the watcher is running, or
the update should stop/reconfigure/restart the watcher explicitly. Prefer the
safer first behavior for this change.

## Import Service

Extract bridge-file import into a backend operation that can import one selected
file or all eligible files:

```text
import_gdt_bridge_files(
    bridge_root,
    filename=None,
    success_mode="archive" | "delete",
    filename_profile="permissive" | "gdt21" | "gdt35",
    receiver_id="",
    sender_id="",
)
```

Expected return shape should include:

- imported items,
- skipped filenames and reasons,
- failures with filenames, target paths, and errors,
- processed count,
- mode/config summary.

Manual `POST /api/gdt/bridge/import` can call this operation with `filename`.
The watcher calls it without `filename`.

## File Eligibility and FIFO

Eligible files:

- regular files under `inbound/`,
- `.gdt` extension case-insensitively,
- not hidden,
- not ending with `.tmp`, `.temp`, `.processing`, or similar internal suffix,
- matches configured filename binding profile,
- stable according to size and timestamp observations or age threshold.

Sort candidates FIFO by:

1. creation timestamp when available and meaningful,
2. modification timestamp as fallback,
3. filename as deterministic tie-breaker.

The implementation should document the creation-time fallback because Docker
bind mounts and network shares may not preserve creation time reliably.

## Safe Claiming

Before reading a candidate file, claim it using a same-volume rename. Acceptable
approaches:

- move `inbound/file.gdt` to `inbound/.processing/file.gdt`, or
- rename `inbound/file.gdt` to `inbound/file.gdt.processing`.

Prefer a processing subfolder if it keeps the visible inbox clean and still
works on Windows. If claim fails because the file disappeared or is locked,
record a skip/retry outcome rather than treating the whole batch as failed.

After parsing:

- success + `archive` mode: move claimed file to `archive/`,
- success + `delete` mode: delete claimed file,
- failure: move claimed file to `error/` where possible.

If moving to `archive/` or `error/` would collide, use a deterministic suffix
instead of overwriting existing diagnostic files.

## Filename Binding

Support these profiles:

- `permissive`: current lab behavior; accept any eligible `.gdt`.
- `gdt21`: accept legacy short binding such as `<Recipient><Sender>.GDT` and
  sequence-extension variants such as `.001` when configured.
- `gdt35`: accept `<recipient>_<sender>_<sequence>.GDT`, for example
  `AIS_GER_4711.GDT`.

The receiver/sender abbreviations are configuration values. The concrete IDs
are installation-specific, so the implementation should not hard-code one
vendor value beyond defaults used by the lab demo.

## Matching Policy

Keep current result matching rules for this change:

- match by unambiguous local order identifiers such as `6200` or `8410`,
- preserve patient context by `3000` when known,
- keep patient-only results unmatched or review-needed,
- do not guess the latest order for a patient.

When future GDT 3.5 fields are introduced, `8314` Request-UID and `8408`
Study-UID should take precedence over patient-only matching.

## API and UI

Add APIs:

- `GET /api/gdt/bridge/watcher/status`
- `POST /api/gdt/bridge/watcher/start`
- `POST /api/gdt/bridge/watcher/stop`

Extend bridge config/status payloads with watcher configuration and import mode
where useful. The GDT console should show automatic import state, last run
summary, last error, and controls to enable or disable automatic import.

Manual import should remain available for selected files.

## Testing Strategy

Add focused tests for:

- watcher lifecycle APIs,
- batch import uses FIFO order,
- temporary and unstable files are skipped,
- successful import archives or deletes based on configured mode,
- parse failures move files to `error/`,
- binding profiles accept and reject expected filenames,
- manual selected-file import and watcher import use consistent persistence,
- path changes are rejected while watcher is running,
- frontend exposes watcher state and controls.
