## 2026-07-03 Apply

ZAC-18 scope implemented as a local HL7 v2.3.1 Order MVP:

- Reuse local Patient records as the source for `PID` and patient context.
- Create local 12-lead ECG orders with generated `ORM^O01` payloads.
- Persist orders and raw ORM payloads in SQLite.
- Show orders in both Order and OIE views.
- Send one selected order to a configurable OIE MLLP endpoint and store ACK or transport result.

Patient MVP persistence already stores visit numbers and account numbers. Order creation reuses the patient visit number when present. If account number is blank, the order stores a stable generated `ACC-ORD-######` account value; if visit number were absent, the order path would use a stable generated `VISIT-ORD-######` value. The generated ORM payload is stored with the order so later patient changes do not mutate sent-message history.

## Code Review

Review file: `openspec/changes/order-hl7-orm-mvp/review/2026-07-03_codex-review.md`

Verdict: no blocking findings. Residual risks are live OIE MLLP channel verification and browser-level interaction coverage, both outside the automated local review scope.
