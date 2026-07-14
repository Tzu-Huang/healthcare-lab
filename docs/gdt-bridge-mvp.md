# GDT Bridge MVP

This PoC adds a file-based GDT workflow beside the existing HL7 v2 and FHIR demos. The bridge now uses a GDT 2.1-compatible subset modeled after the qtm-api production behavior:

- inbound/intake set types: `6301` and `6302`
- result set type: `6310`
- GDT version field: `9218=02.10`
- full-message byte length field: `8100`
- record syntax: `[length3][field4][content][CRLF]`

The browser UI exposes two roles in one PoC surface:

- an OpenEMR-style ECG ordering flow that creates and tracks internal GDT orders
- an AP simulator flow that receives GDT 2.1 intake files and returns GDT 2.1 result packages

## Scope

- OpenEMR-style ECG order creation
- Shared-folder GDT 2.1 `6302` export to `inbox/`
- AP simulator `6301`/`6302` receipt by manual refresh or polling
- AP simulator display of patient, encounter, order, provider, and correlation context
- AP simulator `6310` result packaging with PDF and XML/waveform artifact references
- SQLite-backed status tracking and duplicate receipt/import prevention

Out of scope for this MVP:

- full official GDT 2.1 field coverage beyond the qtm-api-supported subset
- vendor-specific Bergfort EMR profile fields not yet represented by fixtures
- SCP-ECG or DICOM waveform generation
- embedding complete ECG waveform samples directly inside the GDT body

## Folder Contract

Bridge root defaults to `instance/gdt-bridge/`. Healthcare Lab only stores and
resolves this path; it does not create the bridge root or its subfolders. Create
the folders required by your workflow before sending or importing data.

- `inbox/`: generated GDT 2.1 `6302` files waiting for the AP/device
- `outbox/`: AP/device GDT 2.1 `6310` result files waiting for Healthcare Lab import
- `processed/`: GDT intake files parsed successfully by the AP simulator
- `error/`: GDT intake files that failed AP simulator parsing
- `reports/`: PDF and XML/waveform artifacts referenced by `6310`
- `archive/`: imported `6310` files after successful processing
- `processing/`: files claimed by Healthcare Lab while import is in progress

The GDT standards describe successful receiver processing as read-and-delete
behavior for the exchange file. Healthcare Lab defaults to archive mode for PoC
debuggability, keeping successfully imported `6310` files under `archive/` after
the raw payload is persisted. Set `GDT_BRIDGE_IMPORT_SUCCESS_MODE=delete` to use
standards-oriented exchange-folder cleanup after a successful import.

Automatic result import can be enabled from the GDT console. The watcher polls
the configured `outbox/` folder, skips `.tmp`/`.temp`/internal files, waits for
stable files, claims eligible files with a same-volume rename, and processes
them in FIFO order by creation time where available. On Docker bind mounts or
network shares where creation time is unreliable, Healthcare Lab falls back to a
deterministic timestamp and filename order.

Filename binding is configurable:

- `permissive`: accept otherwise eligible `.gdt` files for lab demos.
- `gdt21`: accept configured legacy recipient/sender filenames and numeric
  sequence-extension variants.
- `gdt35`: accept `<receiver>_<sender>_<sequence>.GDT` using configured
  receiver and sender abbreviations.

Results that only identify a patient by `3000` are preserved but not
automatically attached to the latest order. Healthcare Lab requires an
unambiguous order identifier such as the current local `6200`/`8410` values;
future GDT 3.5 work should prefer `8314` Request-UID and `8408` Study-UID when
available.

## Payload Contract

GDT files use byte-counted records:

```text
01380006302\r\n
0128100306\r\n
014921802.10\r\n
01092063\r\n
```

The first three digits are the encoded byte length of that record, including the length digits, field code, content, and trailing CRLF.

MVP intake files use this filename pattern:

```text
gdtin_{order_id}_{timestamp}.gdt
```

## Intake Fields

Outbound OpenEMR/AP intake uses GDT 2.1 `6302` for new test requests. The parser also accepts `6301` root data transfer for patient intake testing.

Core fields:

- `8000`: set type, `6301` or `6302`
- `8100`: complete file byte length
- `9218`: GDT version, `02.10`
- `9206`: charset marker
- `3000`: patient identifier / MRN
- `3101`: last name
- `3102`: first name
- `3103`: birth date as `DDMMYYYY`
- `3110`: sex, `1` male or `2` female when available
- `8410`: local order/test identifier
- `8402`: test type or exam code
- `8315`: receiver GDT ID
- `8316`: sender GDT ID
- `0102`: responsible provider/software party
- `0103`: software name
- `0132`: software version
- `6220`: text line, used here for order description or result interpretation
- `8432`: local correlation identifier for this PoC profile
- `8433`: local encounter identifier for this PoC profile

## Result Contract

The AP simulator returns a layered result package:

- GDT 2.1 `6310` for correlation, statement, summary values, and artifact metadata
- PDF for the human-readable ECG report
- XML for structured ECG content and waveform-bearing data

Result fields:

- `8000`: set type, `6310`
- `8410`: local order/test identifier used to match the originating ECG order
- `3000`, `3101`, `3102`, `3103`, `3110`: patient context
- `6220`: interpretation statement; repeated lines are allowed
- `8401` to `8405`: minimum ECG summary values for OpenEMR-facing display
- `6302`: PDF report filename under `reports/`
- `6303`: PDF content type
- `6304`: XML or waveform artifact filename under `reports/`
- `6305`: XML or waveform artifact content type

## ECG Artifact Contract

The GDT body is the transaction and summary carrier. Complete waveform content remains outside the GDT body.

Current PoC artifact behavior:

- PDF is required for a successful AP package import.
- XML is required for a successful AP package import.
- XML is treated as the structured ECG/waveform artifact for the test harness.
- The bridge validates referenced artifact presence before marking a `6310` import successful.

Future production ECG waveform work should add an explicit SCP-ECG or DICOM ECG waveform profile when a real device or vendor fixture is available.

## Run Sequence

1. Open the browser UI.
2. Choose `GDT`.
3. Create or select an ECG order.
4. Select the order and click `Write 6302`.
5. Click `Receive 6301/6302` so the AP simulator consumes the standard GDT intake file.
6. Upload one PDF and one XML/waveform artifact, then click `Package AP Result`.
7. Click `Import 6310` to parse and attach the result.
8. Inspect the selected order for summary values, PDF link, XML link, and raw standard GDT payloads.

For deterministic testing, `Mock ECG Result` still emits a synthetic PDF and XML pair automatically.

## Failure Cases

- Pipe-delimited pseudo-GDT such as `8000|GDT-IN` is rejected.
- Invalid record byte length is rejected.
- Missing or invalid `8100`, `9218`, or `8000` is rejected.
- Missing mandatory inbound patient fields marks the intake file as failed.
- Importing the same `6310` filename twice is skipped by `gdt_import_events`.
- Missing order correlation marks the import run as failed and records a bridge failure.
- Missing PDF report marks the matching order as `IMPORT_FAILED`.
- Missing XML/waveform artifact marks the matching order as `IMPORT_FAILED`.
- Packaging an AP result before GDT intake export is rejected.
