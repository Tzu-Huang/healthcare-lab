## Context

Healthcare Lab will create an order, create a corresponding dcm4chee-arc MWL/order, let the AP query that order from dcm4chee-arc, and then reconcile AP C-STORE results after the exam is performed.

The key design risk is identifier ownership. Healthcare Lab, dcm4chee-arc, and the AP must not be forced to use the same primary key. Instead, Healthcare Lab needs a mapping ledger that records the identifiers it generated, the identifiers accepted or returned by dcm4chee-arc, and the identifiers observed on returned DICOM studies.

## Goals / Non-Goals

**Goals:**

- Define the MWL order-first data contract before implementation.
- Make clear that this is a worklist/order feature, while patient demographics are required order payload attributes.
- Define the source-of-truth boundary between Healthcare Lab and dcm4chee-arc.
- Define generated identifiers and reconciliation keys.
- Support multiple dcm4chee servers, APs, and identifier namespaces without assuming a shared primary ID.

**Non-Goals:**

- Implement dcm4chee API calls, DIMSE behavior, or database schema changes in this change.
- Build AP-side MWL query or C-STORE result packaging.
- Treat Healthcare Lab as a PACS, DICOM object store, or patient master index.
- Parse, render, or validate DICOM object bytes in Healthcare Lab.

## Decisions

1. dcm4chee-arc owns PACS/MWL/DICOM artifact state.

   Once an MWL/order is accepted by dcm4chee-arc, dcm4chee-arc is authoritative for the worklist item as exposed to APs and for returned DICOM study/artifact state. Healthcare Lab stores workflow intent and mapping metadata, not a shadow PACS.

2. Healthcare Lab owns workflow identity and the mapping ledger.

   Healthcare Lab generates stable local workflow identifiers, records create/sync attempts, stores the dcm4chee server identity, and records the cross-system identifiers used to reconcile results.

3. ZAC-34 models MWL order creation, not patient master creation.

   Patient attributes are included because DICOM MWL requires patient context. This does not introduce a separate dcm4chee patient master lifecycle in Healthcare Lab.

4. Healthcare Lab uses sequential readable IDs for lab workflow identifiers.

   The default generated identifiers are:

   | Identifier | Owner | Example | Purpose |
   | --- | --- | --- | --- |
   | Local order ID | Healthcare Lab | `LAB-ORD-000001` | Local UI/order anchor |
   | Patient ID | Healthcare Lab namespace | `P-000001` | DICOM `00100020` patient identifier in the selected issuer namespace |
   | Accession Number | Healthcare Lab | `ACC-000001` | DICOM `00080050`; primary human/order reconciliation key |
   | Requested Procedure ID | Healthcare Lab | `RP-000001` | DICOM `00401001`; requested procedure identity |
   | Scheduled Procedure Step ID | Healthcare Lab | `SPS-000001` | DICOM `00400009`; AP worklist step identity |

5. Patient ID issuer is always explicit.

   Healthcare Lab sends `00100021 Issuer of Patient ID` and does not assume that `P-000001` is globally meaningful without its issuer. The default demo issuer can be `HEALTHCARE_LAB`, with future configuration per dcm4chee server or hospital namespace.

6. Study Instance UID is a DICOM UID, not a plain sequential integer.

   Healthcare Lab may generate `0020000D Study Instance UID` when the workflow needs deterministic pre-allocation. The UID must use a configured DICOM UID root plus a unique suffix, for example `<uid-root>.<date>.<sequence>`. If a later implementation lets dcm4chee-arc or AP generate the Study Instance UID, Healthcare Lab must record the returned or observed UID in the mapping ledger.

7. Reconciliation uses strongest available keys first.

   When AP C-STORE results arrive in dcm4chee-arc, Healthcare Lab should match results to local orders in this order:

   1. `Study Instance UID (0020000D)` when present in both the mapping ledger and returned study.
   2. `Accession Number (00080050)` within the configured dcm4chee server namespace.
   3. `Requested Procedure ID (00401001)` and `Scheduled Procedure Step ID (00400009)`.
   4. Patient ID plus issuer, Scheduled Station AE Title, modality/time window, and order status as a weak fallback that requires ambiguity handling.

## Field Contract

Healthcare Lab order creation for dcm4chee MWL/order should include these patient fields:

| DICOM tag | Name | Source |
| --- | --- | --- |
| `00100010` | Patient's Name | Selected Healthcare Lab patient/order form |
| `00100020` | Patient ID | Generated or selected patient identifier |
| `00100021` | Issuer of Patient ID | Configured issuer namespace |
| `00100030` | Patient's Birth Date | Selected Healthcare Lab patient/order form |
| `00100040` | Patient's Sex | Selected Healthcare Lab patient/order form |

Healthcare Lab order creation should include these order/Scheduled Procedure Step fields:

| DICOM tag | Name | Source |
| --- | --- | --- |
| `00400001` | Scheduled Station AE Title | Selected AP/station target |
| `00400009` | Scheduled Procedure Step ID | Generated `SPS-*` identifier |
| `0020000D` | Study Instance UID | Healthcare Lab generated DICOM UID or later recorded external UID |
| `00080050` | Accession Number | Generated `ACC-*` identifier |
| `00401001` | Requested Procedure ID | Generated `RP-*` identifier |
| `00741202` | Worklist Label | Human-readable label for the order/worklist item |

## Ledger Shape

Future implementation tickets should preserve at least:

- Healthcare Lab local order ID.
- dcm4chee server key/base identity.
- Patient ID and issuer used for the MWL/order.
- Accession Number, Requested Procedure ID, Scheduled Procedure Step ID.
- Study Instance UID generation status and value when known.
- Scheduled Station AE Title.
- dcm4chee create/sync status and response details.
- Result reconciliation status, matched study identifiers, and ambiguity/error details.

## Risks / Trade-offs

- [Risk] Sequential IDs can collide across environments. -> Mitigation: scope them by dcm4chee server, issuer namespace, and local database; use explicit issuer and server keys in mappings.
- [Risk] Pre-generating Study Instance UID can conflict with AP behavior. -> Mitigation: make UID ownership explicit per workflow and record externally generated/observed UIDs when Healthcare Lab does not pre-generate.
- [Risk] Accession Number alone may not be globally unique. -> Mitigation: match within dcm4chee server namespace and prefer Study Instance UID when available.
- [Risk] Weak fallback matching can attach results incorrectly. -> Mitigation: treat weak fallback matches as ambiguous unless exactly one active candidate exists.
