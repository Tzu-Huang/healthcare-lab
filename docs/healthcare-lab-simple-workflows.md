# Healthcare Lab Simple Workflows

These diagrams use the same structure for meeting presentation:

- Docker Container: Dashboard + integration service
- External: AP
- Arrows show payload/resource type and port
- Dashboard local database is shown only where it matters

## OIE Workflow

```mermaid
flowchart LR
    subgraph Docker["Docker Container"]
        Dashboard["Dashboard<br/>Healthcare Lab UI"]
        OIE["OIE<br/>HL7 routing engine"]
    end

    AP["AP<br/>ECG AP simulator"]

    Dashboard -->|"ORM^O01<br/>MLLP TCP<br/>oie:6600"| OIE
    OIE -->|"ORM^O01<br/>MLLP TCP<br/>AP:6671"| AP
    AP -->|"ORU^R01 / ORU^W01<br/>MLLP TCP<br/>OIE:6661"| OIE
    OIE -->|"ORU^R01 / ORU^W01<br/>MLLP TCP<br/>Dashboard:6665"| Dashboard
```

## FHIR Workflow

```mermaid
flowchart LR
    subgraph Docker["Docker Container"]
        Dashboard["Dashboard<br/>Healthcare Lab UI"]
        FHIR["FHIR<br/>Medplum FHIR R4 API"]
        DB[("Local SQLite DB<br/>workflow ledger / audit<br/>no network port")]
    end

    AP["AP<br/>ECG AP simulator"]

    Dashboard -->|"Patient / ServiceRequest<br/>FHIR R4 REST<br/>medplum:8103"| FHIR
    FHIR -->|"ServiceRequest<br/>FHIR R4 REST<br/>FHIR:8103"| AP
    AP -->|"DiagnosticReport / Observation<br/>DocumentReference / Binary<br/>FHIR R4 REST<br/>FHIR:8103"| FHIR
    FHIR -->|"DiagnosticReport / Observation<br/>FHIR R4 REST<br/>medplum:8103"| Dashboard
    Dashboard -.->|"local workflow state<br/>sync status / audit / retry"| DB
```
