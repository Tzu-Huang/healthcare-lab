## 1. Specification

- [ ] 1.1 Clarify Medplum as the canonical FHIR source of truth.
- [ ] 1.2 Clarify Healthcare Lab's local FHIR data as workflow ledger, retry, audit, and UI projection metadata.
- [ ] 1.3 Define default live Medplum read behavior for resource inventory, patient-centered panels, and AP worklist.
- [ ] 1.4 Define local intent plus Medplum-backed write behavior for Patient, Order, Task, and Result workflows.

## 2. Follow-up Alignment

- [ ] 2.1 Identify how ZAC-26 Patient creation should use the boundary.
- [ ] 2.2 Identify how ZAC-27 and ZAC-31 FHIR/Medplum UI pages should query and join data.
- [ ] 2.3 Identify how ZAC-28, ZAC-29, and ZAC-30 should preserve retry/audit without creating a full local FHIR shadow database.

## 3. Validation

- [ ] 3.1 Run OpenSpec validation for `revise-fhir-medplum-source-of-truth`.
