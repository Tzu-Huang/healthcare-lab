# ECG Viewer Verification Guide

This guide defines the bounded operator check for the Healthcare Lab ECG
Viewer. It is an executable acceptance checklist, not evidence that a live
environment has already passed. Record the date, commit, fixture manifest
entry, and outcome when the checklist is run.

> **Safety classification:** The ECG Viewer is demonstration-only and
> non-diagnostic. Do not use its waveform, measurements, or summary for patient
> care or clinical decisions.

## Supported input contract

The viewer accepts only these DICOM ECG Waveform Storage SOP Classes:

| Format | SOP Class UID |
| --- | --- |
| Twelve-lead ECG Waveform Storage | `1.2.840.10008.5.1.4.1.1.9.1.1` |
| General ECG Waveform Storage | `1.2.840.10008.5.1.4.1.1.9.1.2` |

The current parser requires one waveform sequence with 12 unambiguous SCPECG
leads, signed 16-bit samples, and UCUM voltage units. It normalizes supported
voltage units to `mV`. The release fixtures are expected to contain 10,000
samples per channel at 1,000 Hz (10 seconds); those values describe the bounded
release fixture contract, not every DICOM object in either SOP Class.

## Fixture safety policy

Only a sanitized synthetic fixture listed in the repository's machine-readable
fixture manifest may be used. Before use, verify its recorded hash and confirm
that the de-identification check passes without printing attribute values.

- Keep source or unresolved DICOM files outside the repository and outside
  shared storage.
- Do not upload real patient data or copy raw DICOM metadata into screenshots,
  test output, tickets, or logs.
- If provenance, identity review, or hash validation is missing, stop and mark
  the fixture **blocked**. Do not continue with that file.
- Store acceptance evidence as bounded pass/fail observations and identifiers;
  never attach the DICOM payload.

## Configuration and dependencies

Configure the active typed dcm4chee profile in **Settings > dcm4chee**. The
profile must identify the archive and provide a WADO-RS base URL. For local
host execution with dcm4chee in Compose, use the published archive address
(`http://127.0.0.1:8082/.../aets/DCM4CHEE/rs`). Inside the `lab-app` container,
keep the service address:

```text
DCM4CHEE_WADO_RS_URL=http://dcm4chee:8080/dcm4chee-arc/aets/DCM4CHEE/rs
```

Do not put credentials or tokens in verification evidence. Authentication and
TLS settings belong to the typed dcm4chee profile or its configured secret
files.

The supported host installation path is:

```powershell
python -m pip install -r requirements.txt
python app.py
```

`requirements.txt` declares `pydicom>=3.0,<4.0` for parsing and
`matplotlib>=3.11,<3.12` for SVG rendering. The supported container path is to
build or use the repository image; its `Dockerfile` installs the same
`requirements.txt`. No package should be installed manually inside a running
container:

```powershell
docker compose -f deploy/docker-compose.yml build lab-app
.\deploy\lab.ps1 restart all
```

## Bounded manual acceptance checklist

Run the checklist once for each supported SOP Class. Evidence status is
**pending / environment-dependent** until an operator records an actual result.

| Field | Operator record |
| --- | --- |
| Date and tested commit | Pending |
| Environment/profile name | Pending |
| Fixture manifest identifier and hash status | Pending |
| Twelve-lead ECG outcome | Pending |
| General ECG outcome | Pending |

For each sanitized synthetic fixture:

1. Store the fixture in dcm4chee through the controlled lab ingestion path,
   then open Healthcare Lab and refresh dcm4chee results.
2. Confirm the expected study, series, and instance reconcile under the intended
   result without exposing patient attributes in the evidence.
3. Confirm the ECG instance offers **View ECG Graph**, select it, and verify the
   viewer finishes loading without an error panel.
4. Confirm the graph labels appear in canonical order (`I`, `II`, `III`, `aVR`,
   `aVL`, `aVF`, `V1`-`V6`) and the summary shows 12 leads, `1000 Hz`, `mV`,
   and `10 seconds`.
5. Confirm the page visibly states that the viewer is demonstration-only and
   non-diagnostic. Record pass/fail and a disclosure-safe failure category.

This checklist deliberately does not assert waveform morphology or diagnostic
accuracy. Automated fixture validation owns exact channel count, sample count,
timing, calibration, and safe error regressions.

## Troubleshooting and recovery

Use only the stable category shown to the user; do not paste upstream bodies,
credentials, internal paths, raw metadata, or DICOM content into evidence.

| Symptom/category | Safe recovery |
| --- | --- |
| Result not found | Refresh dcm4chee results and confirm the persisted result still exists. |
| Incomplete instance identifiers | Reconcile the result and confirm it identifies one study, series, and SOP instance. |
| Unsupported ECG | Confirm the SOP Class UID is one of the two supported values above. |
| Invalid ECG | Re-run the fixture manifest/invariant validator; replace a corrupt or contract-incompatible synthetic fixture. |
| Retrieval/upstream failure | Run bounded dcm4chee diagnostics, verify the active profile and WADO-RS reachability, then retry. |
| Summary loads but graph fails | Retry once; if repeatable, record the commit, result ID, browser console category, and no payload details. |

An unconfigured or unauthorized profile must be corrected in Settings by an
authorized operator. Never work around it by embedding a secret in a URL,
command, screenshot, or ticket.

## Display limitations and deferred scope

The viewer renders a fixed application-generated SVG and a small display
summary. It is not a diagnostic workstation and does not provide validated
measurement tools, diagnostic interpretation, morphology verification, or a
clinical report.

Zoom, calipers, annotations, print layout, and export are explicitly deferred
follow-up scope. Create separate Linear issues for those capabilities when they
are prioritized; do not add them to this verification change. No follow-up
issues are created by this guide.

