## Context

The local dcm4chee result ledger already projects stable result IDs and
study/series/instance retrieve identifiers. The typed dcm4chee profile already
owns DICOMweb endpoints, authentication, TLS verification, and request timeout
settings. Separate completed capabilities parse supported DICOM ECG instances
into an allowlisted normalized model and render that model to in-memory SVG.

ZAC-94 connects those boundaries. The main constraints are that public clients
must not choose an upstream target, WADO-RS responses can be bare DICOM or
multipart, upstream bytes are untrusted and potentially large, and API errors
must remain useful without exposing PHI or integration secrets.

## Goals / Non-Goals

**Goals:**

- Resolve an ECG retrieval only from a persisted integer result ID.
- Reuse the authoritative dcm4chee profile and transport security behavior.
- Bound network time and response bytes before parsing.
- Normalize bare and single-instance multipart WADO-RS responses.
- Compose the existing parser and renderer behind stable metadata and SVG APIs.
- Provide deterministic, non-sensitive HTTP error contracts.

**Non-Goals:**

- Accepting arbitrary WADO-RS URLs, filesystem paths, or DICOM uploads.
- Returning raw DICOM datasets, arbitrary tags, or original instance bytes.
- Supporting multi-instance selection, non-ECG SOP classes, PNG, or
  diagnostic-grade display.
- Changing result refresh, reconciliation, generic viewer URLs, parser
  calibration, or renderer layout contracts.

## Decisions

### Result ID is the only public retrieval selector

Both routes use an integer `result-id`. The application service loads that row
through the result repository and constructs the WADO-RS request from the
configured base URL plus validated study, series, and instance UIDs stored in
the row. Missing or study-only rows fail before network access.

This is preferred over accepting a stored retrieve URL because reconstructing
the target from the authoritative profile prevents stale or attacker-influenced
hosts from becoming fetch targets. Caller-provided URL and path alternatives
are rejected because they introduce SSRF and path traversal boundaries.

### One bounded transport adapter owns WADO-RS behavior

A focused adapter sends an `Accept` value for DICOM instance retrieval, applies
the profile's authentication and TLS verification, and uses its controlled
timeout. It reads incrementally and aborts once a configurable application
maximum is exceeded; the entire response is never accepted unbounded.

The adapter returns one DICOM byte payload or a typed transport/content error.
Keeping HTTP and MIME handling outside the parser preserves the parser's
framework-independent dataset contract. Duplicating request code in each Flask
route or in the frontend is rejected.

### Multipart parsing is strict and media-type driven

`application/dicom` is treated as a bare instance. A
`multipart/related; type="application/dicom"; boundary=...` response is parsed
with a standards-aware MIME parser. The adapter requires a valid boundary and
exactly one non-empty DICOM part for this result-scoped request; malformed,
missing, ambiguous, or non-DICOM parts are rejected.

This avoids delimiter splitting, which is unsafe for binary payloads and
quoted boundaries. Supporting multiple returned instances is deferred because
the result row already identifies one SOP Instance.

### Application service composes retrieval, parsing, and rendering

One service returns a normalized ECG model for metadata and reuses that same
path before calling `render_ecg` for SVG. DICOM bytes are decoded with pydicom
in memory and immediately passed to `parse_ecg_waveform`; raw datasets and
bytes do not cross the service/API boundary.

The metadata response contains result identity, capability flags, normalized
technical waveform fields, and the parser's allowlisted display-safe metadata.
It excludes raw tags, patient identifiers, retrieve URLs, profile secrets, and
upstream response details.

### Routes use stable typed error translation

The API translates service errors as follows:

- `404` for an unknown result ID.
- `409` for a known row without a unique instance retrieval identity.
- `415` for unsupported response media type or ECG SOP Class.
- `422` for malformed DICOM/multipart content or invalid waveform structure.
- `502` for dcm4chee authorization, timeout, connection, HTTP, or size-limit
  failure.

Responses use stable application error codes and safe summaries. Detailed
exceptions, credentials, endpoint URLs, raw metadata, and payload fragments
remain server-side.

## Risks / Trade-offs

- [Large compressed or adversarial payload consumes resources] → Stream with a
  hard byte ceiling before pydicom receives the payload and retain parser
  structural validation.
- [MIME libraries accept ambiguous multipart shapes] → Validate the top-level
  media type, declared DICOM part type, part count, and non-empty payload after
  parsing.
- [Profile authentication behavior is accidentally duplicated] → Inject or
  reuse the canonical dcm4chee request/profile boundary and cover auth, TLS,
  and timeout propagation in adapter tests.
- [SVG rendering is CPU-heavy under concurrency] → Keep rendering
  request-scoped and resource-clean; rate limiting or asynchronous rendering is
  deferred unless operational evidence requires it.
- [HTTP mappings hide useful diagnostics] → Return stable error codes to
  clients while preserving sanitized structured server logs.

## Migration Plan

1. Add the transport and service behind new routes without changing existing
   APIs or persistence.
2. Deploy with a conservative configured response-size ceiling and the existing
   profile timeout.
3. Verify mocked bare/multipart paths and one configured dcm4chee environment.
4. Roll back by removing or disabling the new routes; no database rollback or
   stored-data conversion is required.

## Open Questions

- Select the initial response-size ceiling from fixture measurements during
  implementation and document the chosen configuration/default.
- Confirm whether dcm4chee returns a single DICOM part consistently for
  instance-level WADO-RS requests in the supported deployment.
