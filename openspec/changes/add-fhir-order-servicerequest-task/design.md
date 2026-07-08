## Context

The current Order page supports HL7 v2.3.1 and GDT ECG order creation. The FHIR option is present but disabled. The backend already has a generic FHIR workflow ledger, idempotent Medplum sync, supported resource mappings for `ServiceRequest` and `Task`, and a Medplum inventory page.

The missing workflow is a mode-aware Order create path that turns a local ECG order into FHIR resources with stable references.

## Goals / Non-Goals

**Goals:**

- Enable FHIR mode on the Order page.
- Display the full ServiceRequest-oriented FHIR order form in FHIR mode.
- Require a selected Patient that is already a synced FHIR Patient with a Medplum `Patient/<id>` reference.
- Persist a local order anchor before sync so user intent and Local Orders visibility are retained.
- Create/sync `ServiceRequest` first, then create/sync `Task` with `focus` pointing to the synced ServiceRequest.
- Surface sync status for both resources in Local Orders and Medplum inventory.

**Non-Goals:**

- Implement a full FHIR transaction Bundle in this ticket.
- Build full resource pickers for every advanced ServiceRequest reference field.
- Let FHIR order creation auto-create or auto-sync Patients.
- Expose a full manual Task form; Task is generated from the ServiceRequest order.
- Add destructive Medplum update/delete operations.

## Decisions

1. FHIR order creation requires a synced FHIR Patient.

   `ServiceRequest.subject` and `Task.for` must reference the canonical Medplum Patient. If the selected local Patient has no synced FHIR ledger reference, Order create should fail with a clear instruction to create or sync a FHIR Patient first.

2. Sync uses the existing equivalent sequential strategy.

   The implementation should create or update the local `ServiceRequest` ledger record and sync it. Once the Medplum reference is available, the implementation creates or updates the local `Task` ledger record with `focus.reference` set to `ServiceRequest/<id>` and syncs the Task. This matches the existing idempotent ledger model better than introducing a transaction Bundle now.

3. FHIR orders use a local order anchor.

   A local order record should be created for FHIR mode so Local Orders remains the user's order inventory. The local order id becomes the shared source id for the paired `ServiceRequest` and `Task` ledger records.

4. The Order page shows the full ServiceRequest form in FHIR mode.

   The user requested that all listed ServiceRequest fields appear directly on the Order page when FHIR mode is selected. Advanced fields may initially use text, multiline, comma-separated, or JSON-shaped inputs where resource pickers would be too large for this ticket.

5. Task is generated automatically.

   The generated Task should use status `requested`, intent `order`, `focus` set to the synced ServiceRequest, `for` set to the synced Patient, and an ECG worklist code. Manual Task customization stays out of scope.

## Field Handling

FHIR mode should support visible inputs for:

- `resourceType`, `id`, `identifier`
- `instantiatesCanonical`, `instantiatesUri`
- `basedOn`, `replaces`, `requisition`
- `status`, `intent`, `category`, `priority`, `doNotPerform`, `code`, `orderDetail`
- `quantity.value`, `quantity.unit`
- `subject`, `encounter`
- `occurrenceDateTime`, `asNeededBoolean` or `asNeededCodeableConcept`
- `authoredOn`, `requester`
- `performerType`, `performer`
- `locationCode`, `locationReference`
- `reasonCode`, `reasonReference`
- `insurance`, `supportingInfo`, `specimen`, `bodySite`
- `note`, `patientInstruction`, `relevantHistory`

## Risks / Trade-offs

- [Risk] The full ServiceRequest form can make the Order page dense. -> Mitigation: keep FHIR-only fields grouped but visible, with compact controls and predictable labels.
- [Risk] Sequential sync can leave ServiceRequest synced while Task fails. -> Mitigation: Local Orders and Medplum inventory must show per-resource status and allow existing retry behavior.
- [Risk] Advanced reference fields can be malformed. -> Mitigation: validate required references and preserve optional advanced values as provided where possible, returning clear validation errors for invalid JSON/reference formats.
- [Risk] Existing HL7/GDT order behavior could regress. -> Mitigation: keep mode-specific code paths and add regression tests for existing order creation.

## Open Questions

- Should advanced reference/list fields accept only FHIR references, or should display-only text values be accepted and mapped to CodeableConcept/text where appropriate?
- Should Local Orders expose a direct retry action for failed FHIR order resources, or rely on the Medplum page retry action in the first implementation?

