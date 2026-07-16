# ZAC-61 Owner and Caller Inventory

This inventory records the implementation owners before ZAC-61 movement and the
approved final destinations. Compatibility paths remain only for the listed
callers and must delegate or re-export the final owner.

| Context | Responsibility | Current owner | Current callers | ZAC-61 final owner |
|---|---|---|---|---|
| Patient | validation, normalization, identifiers | `backend/domain/patient.py` | Patient repository, templates, identifier repository, compatibility delegates | unchanged |
| Patient | persistence-row presentation | `backend/domain/patient.py:project` | `backend/repositories/patients.py` | `backend/mappers/patient.py` |
| Patient | ADT/FHIR/GDT/DICOM payload construction | `backend/templates/patient.py` | composition and compatibility delegates | unchanged |
| Order | validation, normalization, identifiers | `backend/domain/order.py`, `backend/domain/fhir_order.py` | Order repository, FHIR coordination, templates, compatibility delegates | unchanged |
| Order | persistence-row presentation | `backend/domain/order.py:project` | `backend/repositories/orders.py` | `backend/mappers/order.py` |
| Order | ORM and FHIR ServiceRequest construction | `backend/templates/order.py`, `backend/templates/fhir.py` | composition and compatibility delegates | unchanged |
| FHIR | ledger validation and identifier policy | `backend/domain/fhir_ledger.py` | FHIR repository, template, protocol compatibility | unchanged |
| FHIR | workflow and attempt presentation | `backend/domain/fhir_ledger.py:project_workflow_record`, `project_sync_attempt` | FHIR repository; `backend/services/protocol_compatibility.py` retained by `DemoStore` | `backend/mappers/fhir.py` |
| GDT | parsing, encoding validation, required fields, inbound 6310 interpretation | `backend/domain/gdt_protocol.py` | GDT repository; `backend/gdt_adapter.py` and `DemoStore` compatibility paths | unchanged |
| GDT | outbound 6302 construction | `backend/templates/gdt.py` | GDT workflow/composition and `backend/gdt_adapter.py` re-export | unchanged |
| GDT | numbering and persistence preparation | `backend/domain/gdt_workflow.py` | GDT repository and `DemoStore` delegates through protocol compatibility aliases | unchanged |
| GDT | snapshots, attachments, and workbench presentation | `backend/mappers/gdt.py` | GDT repository and `DemoStore` delegates through protocol compatibility aliases | unchanged |
| dcm4chee | identifiers, reconciliation, and status policy | `backend/domain/dicom.py` | DICOM repositories, templates, services, compatibility delegates | unchanged |
| dcm4chee | ADT and MWL construction | `backend/templates/dicom.py` | DICOM services and compatibility delegates | unchanged |
| dcm4chee | Patient-sync and attempt presentation | `backend/repositories/dcm4chee_patient_sync.py` | repository and `DemoStore` delegates | `backend/mappers/dicom.py` |
| dcm4chee | MWL mapping and attempt presentation | `backend/repositories/dcm4chee_mwl.py` | repository and `DemoStore` delegates | `backend/mappers/dicom.py` |
| dcm4chee | Result and refresh-snapshot presentation | `backend/repositories/dcm4chee_results.py` | repository and `DemoStore` delegates | `backend/mappers/dicom.py` |
| Lab | server payload validation | `backend/repositories/lab.py` | Lab repository and `DemoStore` delegates | `backend/domain/lab.py` |
| Lab | server and operation presentation | `backend/repositories/lab.py` | Lab repository and `DemoStore` delegates | `backend/mappers/lab.py` |
| OIE | settings validation | `backend/repositories/oie_settings.py` | OIE settings repository and `DemoStore` composition | `backend/domain/oie.py` |
| OIE | settings and result presentation | `backend/repositories/oie_settings.py`, `backend/repositories/oie.py` | OIE repositories, workbench coordination, and `DemoStore` delegates | `backend/mappers/oie.py` |

`backend/repositories/gdt_bridge_health.py:validate_gdt_bridge_dirs` is not a
presentation or domain-validation candidate. It remains the single approved
filesystem-readiness owner, called by the GDT watcher and Lab workflow through
their existing compatibility/port paths.

The retained dcm4chee helpers on `DemoStore` are compatibility-only mechanical
delegates to `backend/domain/dicom.py`, `backend/templates/dicom.py`,
`backend/mappers/dicom.py`, the dedicated dcm4chee repositories, or the
dcm4chee workflow coordinators. They contain no projector, identifier-mapping,
payload-builder, retry/display, or response-interpretation implementation.
