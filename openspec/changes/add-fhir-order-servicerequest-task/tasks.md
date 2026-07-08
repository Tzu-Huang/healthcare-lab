## 1. FHIR Order Resource Mapping

- [ ] 1.1 Add backend builders for FHIR `ServiceRequest` from an Order-page FHIR payload.
- [ ] 1.2 Add backend builder for generated ECG AP/worklist `Task` from the local order, synced Patient reference, and synced ServiceRequest reference.
- [ ] 1.3 Validate FHIR order creation requires a local Patient with synced FHIR `Patient/<id>` reference.
- [ ] 1.4 Preserve deterministic identifiers for both `ServiceRequest` and `Task`.

## 2. Local Create And Medplum Sync

- [ ] 2.1 Persist a local order anchor for FHIR mode before Medplum sync.
- [ ] 2.2 Create or update the paired `ServiceRequest` FHIR workflow ledger record for the local order.
- [ ] 2.3 Sync `ServiceRequest` first through the existing idempotent Medplum sync path.
- [ ] 2.4 Create or update the paired `Task` FHIR workflow ledger record after the ServiceRequest reference is known.
- [ ] 2.5 Sync `Task` and preserve failed/pending state independently from the ServiceRequest.
- [ ] 2.6 Return order response metadata containing ServiceRequest and Task ledger ids, sync statuses, Medplum references, and errors.

## 3. Order UI

- [ ] 3.1 Enable the Order page FHIR option.
- [ ] 3.2 Add a FHIR ECG Order Demo Preset.
- [ ] 3.3 Show the full ServiceRequest field set in FHIR mode.
- [ ] 3.4 Render a ServiceRequest JSON preview for FHIR mode.
- [ ] 3.5 Submit FHIR mode orders through the FHIR order creation path.
- [ ] 3.6 Display FHIR order ServiceRequest and Task sync status in Local Orders.
- [ ] 3.7 Keep existing HL7 v2.3.1 and GDT order flows working.

## 4. Medplum Inventory

- [ ] 4.1 Ensure created ServiceRequest and Task records appear in Medplum inventory.
- [ ] 4.2 Ensure patient filtering includes ServiceRequest via `subject` and Task via `for`.
- [ ] 4.3 Ensure previews show live Medplum JSON when synced and local submitted JSON fallback when live fetch fails.

## 5. Verification

- [ ] 5.1 Add store tests for ServiceRequest mapping, Task mapping, deterministic identifiers, and Patient precondition validation.
- [ ] 5.2 Add app tests for successful FHIR order create-and-sync, ServiceRequest/Task reference correctness, and partial sync failure preservation.
- [ ] 5.3 Add frontend/API regression coverage for FHIR mode enablement, full form visibility, preview, and Local Orders sync display.
- [ ] 5.4 Run OpenSpec validation and the Healthcare Lab Python test suite.

