## Context

ZAC-34 defined the dcm4chee MWL/order contract and identifier precedence for result reconciliation. ZAC-36 implemented runtime dcm4chee MWL creation and stores creation attempts in `local_dcm4chee_mwl_attempts`.

ZAC-37 should turn that attempt-level persistence into a reliable local PACS/MWL ledger. The ledger is the canonical cross-system mapping: one Healthcare Lab order maps to the dcm4chee MWL/study identifiers that APs and later results will use.

## Goals / Non-Goals

**Goals:**

- Store one canonical dcm4chee PACS/MWL mapping per Healthcare Lab order.
- Store Healthcare Lab local order identity and AP-facing identifiers.
- Store dcm4chee identifiers once known, whether they were prefilled by Healthcare Lab or read back from dcm4chee.
- Keep every create/read-back attempt as audit history with raw request/response payloads.
- Add retry/idempotency behavior that avoids duplicate dcm4chee MWL orders for the same Healthcare Lab order.
- Add local lookup helpers for future result reconciliation by Study Instance UID, Accession Number, Requested Procedure ID, and Scheduled Procedure Step ID.
- Keep local orders available when dcm4chee creation or read-back fails.

**Non-Goals:**

- Implement full AP C-STORE result polling, import, display, or viewer-link workflows.
- Implement production dcm4chee auth/TLS beyond the existing profile settings.
- Replace dcm4chee as the source of truth for PACS, MWL, DICOM study, or artifact state.
- Delete local Healthcare Lab orders when dcm4chee sync fails.

## Decisions

1. Separate canonical mapping from attempt audit.

   `local_dcm4chee_mwl_attempts` remains useful as an audit trail, but reconciliation needs one authoritative mapping row per Healthcare Lab order/profile/server identity. The implementation should either add a dedicated mapping table or a clearly separated canonical mapping shape while keeping historical attempts.

2. Healthcare Lab pre-fills required workflow fields only.

   Healthcare Lab should continue providing patient/order data required to create the MWL item and any required AP-facing identifiers that the local workflow owns. It should not assume all dcm4chee identifiers are final until dcm4chee has accepted and, where practical, been read back.

3. Read-back stores dcm4chee's actual identifiers.

   After creation succeeds, Healthcare Lab should parse identifiers from the response when available and/or query dcm4chee using the strongest known identifiers. The canonical mapping should record which values are confirmed from dcm4chee and keep read-back failures visible without deleting the local order.

4. Idempotent retry uses the canonical mapping first.

   If a canonical mapping for a local order is already successfully created/confirmed, retry should not POST a new MWL item. If the previous attempt failed, retry should reuse stable local identifiers from the mapping. If the previous attempt timed out or is ambiguous, Healthcare Lab should attempt read-back before creating another dcm4chee item.

5. Local reconciliation lookup follows identifier strength.

   The lookup path should match by Study Instance UID first, then Accession Number within dcm4chee server/profile namespace, then Requested Procedure ID plus Scheduled Procedure Step ID. Weak patient/time-window matching should remain ambiguous unless exactly one active candidate exists.

## Data Model Direction

The canonical mapping should include:

- local Healthcare Lab order record id and local dcm4chee order number
- profile name, dcm4chee server identity, MWL AE title, Scheduled Station AE Title
- Patient ID and Issuer of Patient ID
- Accession Number
- Requested Procedure ID
- Scheduled Procedure Step ID
- Study Instance UID
- Worklist Label
- sync status, last sync time, retry count, last error type/text/payload
- raw or summarized latest create/read-back request and response references when appropriate
- created/updated timestamps

Attempt audit records should remain append-only enough for debugging and should include operation type such as create, read-back, retry, or reconcile lookup when the implementation needs to distinguish them.

## Risks / Trade-offs

- [Risk] dcm4chee REST response payloads may not include all generated identifiers. -> Mitigation: support response parsing where available and a separate read-back query path.
- [Risk] Ambiguous timeout handling can still duplicate MWL items. -> Mitigation: check the canonical mapping and attempt dcm4chee read-back before retrying POST.
- [Risk] Separate mapping and attempt tables add schema complexity. -> Mitigation: keep the canonical row small and optimized for reconciliation, while attempts retain verbose audit details.
- [Risk] Full result reconciliation may need more dcm4chee study query behavior than this ticket can safely complete. -> Mitigation: deliver local mapping and lookup support first, then connect AP result ingestion in a follow-up if needed.

## Open Questions

- Which dcm4chee endpoint reliably returns MWL items by Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, or Patient ID in the local Docker runtime?
- Should Worklist Label be treated as a reconciliation identifier, or only as AP-facing context?
- Should ambiguous timeout/read-back failures remain `Pending sync` for manual retry, or move to a distinct `Needs verification` status?
