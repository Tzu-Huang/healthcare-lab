## 1. Backend Verify Contract

- [x] 1.1 Add a focused OpenEMR/GDT backend verify helper that returns structured smoke steps.
- [x] 1.2 Include required OpenEMR HTTP reachability in the verify steps.
- [x] 1.3 Include required GDT shared-folder structure and write/read checks in the verify steps.
- [x] 1.4 Route the OpenEMR/GDT smoke/check path through the new verify helper so API responses expose the structured result.

## 2. MariaDB and OpenEMR Schema Checks

- [x] 2.1 Add a required MariaDB connection check using the existing `OpenEMRProcedureOrderSource` configuration.
- [x] 2.2 Add a required OpenEMR procedure-order schema/query readiness check.
- [x] 2.3 Classify zero matching ECG procedure orders as Degraded/WARN rather than a required failure.
- [x] 2.4 Preserve DB host, DB port, GDT path, and procedure code as runtime defaults rather than operator-facing settings.

## 3. Verification

- [x] 3.1 Add unit tests for healthy OpenEMR/GDT backend verify output.
- [x] 3.2 Add unit tests for MariaDB connection failure.
- [x] 3.3 Add unit tests for missing required OpenEMR order schema/query failure.
- [x] 3.4 Add unit tests for zero matching ECG orders producing Degraded.
- [x] 3.5 Run Healthcare Lab Python and frontend syntax checks.
