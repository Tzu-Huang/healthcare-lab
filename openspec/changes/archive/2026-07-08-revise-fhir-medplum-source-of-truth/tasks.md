## 1. Specification

- [x] 1.1 Clarify Medplum as the canonical FHIR source of truth.
- [x] 1.2 Clarify Healthcare Lab's local FHIR data as workflow ledger, retry, audit, and UI projection metadata.
- [x] 1.3 Define default live Medplum read behavior for resource inventory, patient-centered panels, and AP worklist.
- [x] 1.4 Define local intent plus Medplum-backed write behavior for Patient, Order, Task, and Result workflows.

## 2. Follow-up Alignment

- [x] 2.1 Identify how ZAC-26 Patient creation should use the boundary.
- [x] 2.2 Identify how ZAC-27 and ZAC-31 FHIR/Medplum UI pages should query and join data.
- [x] 2.3 Identify how ZAC-28, ZAC-29, and ZAC-30 should preserve retry/audit without creating a full local FHIR shadow database.

## 3. Validation

- [x] 3.1 Run OpenSpec validation for `revise-fhir-medplum-source-of-truth`.
