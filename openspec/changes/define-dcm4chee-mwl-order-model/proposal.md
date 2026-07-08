## Why

Healthcare Lab will integrate with dcm4chee-arc through an MWL order-first flow. The work needs a clear data contract before implementation so Healthcare Lab, dcm4chee-arc, and the AP/device simulator do not have to share one primary identifier or re-decide ownership during later tickets.

ZAC-34 defines the MWL order model, identifier strategy, and reconciliation rules. This is an order/worklist contract, not a patient master-data feature.

## What Changes

- Define dcm4chee-arc as the source of truth for PACS, MWL, DICOM study, and artifact state.
- Define Healthcare Lab as the source of truth for workflow UI intent, local order identity, generated identifiers, sync attempts, and mapping ledger records.
- Define the patient demographic attributes that Healthcare Lab includes when creating a dcm4chee MWL/order.
- Define the Scheduled Procedure Step and order attributes needed for AP MWL query and result reconciliation.
- Decide that Healthcare Lab generates sequential local order, accession, requested procedure, scheduled procedure step, and patient identifiers for the lab workflow.
- Decide that Healthcare Lab may generate `Study Instance UID` using a configured DICOM UID root plus a sequential suffix; plain integer values are not valid DICOM UIDs.
- Define reconciliation precedence for AP C-STORE results back to Healthcare Lab orders.

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Define the dcm4chee-arc MWL order-first data contract and identifier mapping.

### Modified Capabilities

- None.

## Impact

- Affected docs/specs: OpenSpec design and requirement coverage for the future dcm4chee MWL workflow.
- Affected systems: Healthcare Lab local order ledger, future dcm4chee-arc MWL/order sync, AP MWL query behavior, AP C-STORE result reconciliation.
- No runtime code, database migration, or UI change is implemented in this proposal step.
