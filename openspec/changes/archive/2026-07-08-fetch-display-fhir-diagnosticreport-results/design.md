## Context

The current Medplum page already has a Patient-centered structure, supported FHIR inventory rows, live JSON preview for synced ledger records, and local submitted fallback when live preview fails. It does not yet provide a live FHIR search path for DiagnosticReports that exist in Medplum but were not created through the local ledger.

The GDT console already demonstrates the target interaction model: Patient list, expandable Patient rollup, order/result grouping, selected Patient summary, related artifact rows, and a raw payload panel.

## Goals / Non-Goals

**Goals:**

- Fetch live `DiagnosticReport` resources for a selected Medplum `Patient/<id>`.
- Narrow live results by selected `ServiceRequest/<id>` when possible.
- Keep patient-level reports visible when they do not link to a ServiceRequest.
- Display scan-friendly report rows and related FHIR references.
- Preview live Medplum JSON in the bottom raw panel.
- Distinguish live Medplum data, local submitted fallback, local-only workflow intent, fetch failed, and empty result states.
- Include DiagnosticReport fetch status in Medplum smoke/check behavior without treating an empty Bundle as an outage.

**Non-Goals:**

- Add a DiagnosticReport create, submit, sync, import, or mirror workflow.
- Persist full live DiagnosticReport resources into the local ledger.
- Build rich clinical renderers for Observation values, DocumentReference attachments, Binary payloads, or media content.
- Add destructive Medplum update/delete operations.

## Decisions

1. Patient selection auto-fetches live DiagnosticReports.

   The user decision for ZAC-43 is that selecting a FHIR Patient should immediately load that Patient's live DiagnosticReports from Medplum. This keeps the Medplum page aligned with the acceptance criteria and avoids a separate fetch action.

2. ServiceRequest selection auto-narrows live reports.

   When a ServiceRequest is selected, the backend should prefer `DiagnosticReport?based-on=ServiceRequest/<id>`. If that search is unsupported or fails in the local Medplum target, the backend should fetch by Patient and filter reports whose `basedOn[]` contains the selected ServiceRequest reference.

3. Patient-level results remain visible.

   Reports with `subject=Patient/<id>` and no matching `basedOn` link must remain visible under a patient-level result grouping. The UI should not hide these reports simply because an order is selected.

4. Related resources use lazy preview.

   The first implementation should parse and list related `Observation`, `DocumentReference`, and `Binary` references from live report data, then fetch each related resource only when selected for preview. This avoids excessive FHIR calls when a Patient has many reports.

5. Local ledger stays metadata-only for live reads.

   Live DiagnosticReport resources remain canonical in Medplum. The local ledger may be joined only for known workflow metadata such as sync status, retry error, local submitted fallback, or locally-created references.

## Backend Shape

- Add a read-only DiagnosticReport search/fetch helper.
- Support Patient search with `DiagnosticReport?subject=Patient/<id>`.
- Support ServiceRequest narrowing with `DiagnosticReport?based-on=ServiceRequest/<id>`.
- Fallback from unsupported `based-on` search to Patient search plus server-side `basedOn[]` filtering.
- Return:
  - raw FHIR Bundle JSON;
  - parsed report summaries;
  - relationship/reference lists;
  - source/status metadata for live, empty, failed, and fallback states.
- Preserve clear error classes for auth failure, upstream FHIR HTTP errors, malformed response shape, and unexpected response shape.

## Frontend Shape

- Keep Patient list as the primary navigation surface.
- Add expandable Patient rollup sections modeled on the GDT console.
- Group reports into order-linked and patient-level results.
- Show rows with report code/display, status, effective or issued date, linked order/reference, result count, and attachment/reference count.
- Selecting a report updates the bottom raw JSON panel with live Medplum JSON.
- Related Observation, DocumentReference, and Binary references appear as lightweight rows and are fetched lazily on selection.

## Risks / Trade-offs

- [Risk] Medplum search parameter support may differ by environment. -> Mitigation: prefer standards-oriented search params, implement fallback filtering, and cover both paths in tests.
- [Risk] Auto-fetch can trigger repeated requests while switching patients quickly. -> Mitigation: keep UI loading states explicit and ignore stale responses if a newer selection supersedes them.
- [Risk] Patient-level reports may confuse order-focused workflows. -> Mitigation: label patient-level results clearly and keep them separate from selected-order results.
- [Risk] Lazy related-resource preview means counts/rows may initially be reference-only. -> Mitigation: show clear labels that references are live Medplum links and fetch raw JSON when selected.

## Open Questions

- None currently. User decisions: auto-fetch on selection, lazy related-resource preview, and Patient-search fallback when `based-on` is unavailable.

