# Healthcare Lab Project Boundary

This project owns the local interoperability lab control plane.

## Primary Scope

- Server Health Dashboard
- service health checks for OIE, Medplum, OpenEMR/GDT, and dcm4chee
- Docker Compose runtime and service operation controls
- dashboard resource usage and event summaries
- lab service registry and operation history
- local dashboard-created GDT ECG order creation and status display

## Source Areas To Keep Here

- `deploy/`
- dashboard and lab server APIs:
  - `/api/dashboard/*`
  - `/api/lab/servers/*`
- backend modules in `backend/`
- dashboard service grouping and resource snapshots in `backend/dashboard_services.py`
- dashboard UI:
  - `lab-console-view`
  - dashboard resource usage
  - dashboard event log
- frontend assets in `frontend/`
- Docker operation adapters in `backend/lab_operations.py`
- runtime smoke checks
- local GDT ECG order APIs:
  - `/api/gdt/orders`

## Out Of Scope

Move protocol workflow features to the ECG AP Simulator project:

- AP MLLP listener and raw HL7 sender
- ECG JSON/PDF/aECG/DICOM result packaging
- integration queue
- HL7 ORU result generation
- FHIR selected-order result submission
- GDT Hospital/AP workflow UI

Healthcare Lab may still create local dashboard-originated GDT ECG orders for
the lab control-plane workflow. Full GDT hospital/device simulation and result
packaging remain in the ECG AP Simulator boundary.

## Current Migration State

This folder now owns the Healthcare Lab dashboard and lab control plane only.
The Flask app imports its persistence layer from `backend/lab_store.py`; legacy
ECG AP Simulator backend modules have been removed from `backend/`.
