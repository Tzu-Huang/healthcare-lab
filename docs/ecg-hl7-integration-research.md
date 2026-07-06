# ECG Hospital Integration Research Report

## 1. Objective

This report evaluates the expected data exchange workflow between a hospital
system and an application platform (AP) that integrates hospital data with ECG
medical-device data.

The AP must support two hospital environments:

1. Hospitals with PACS support.
2. Hospitals without PACS that exchange data through HL7 interfaces.

The report focuses on:

- Whether the AP normally receives hospital HL7 data through Push or Pull.
- Which formats should be used when the AP sends integrated ECG data back to
  the hospital.
- Which improvements are needed in the current HL7 simulation UI.

## 2. System Context

The target workflow is bidirectional:

```text
Hospital HIS / EMR
        |
        | Patient and ECG order context
        v
Application Platform (AP)
        |
        +-- Receive hospital data
        +-- Associate patient and ECG-device data
        +-- Integrate ECG measurements, interpretation, and report
        |
        | Return integrated result
        v
Hospital PACS, HIS, or EMR
```

The AP cannot assume that every hospital supports the same transport protocol
or message profile. The hospital interface specification remains the source of
truth for production integration.

## 3. Receiving Hospital Data: Push or Pull?

### 3.1 Recommended Primary Model: Push

The AP should primarily support hospitals actively pushing HL7 v2 messages to
the AP.

```text
Hospital HIS
        |
        | ADT / ORM over MLLP-TCP
        v
AP MLLP Listener
        |
        | ACK
        v
Hospital HIS
```

Common messages include:

| Message | Purpose |
|---|---|
| `ADT^A01` | Patient admission |
| `ADT^A03` | Patient discharge |
| `ADT^A04` | Patient registration |
| `ADT^A08` | Patient demographic or visit update |
| `ORM^O01` | ECG examination order creation or update |

This event-driven model is common because the AP receives patient and order
updates when hospital-side events occur.

### 3.2 Supplemental Model: Pull

The AP may also need to query hospital systems when information is missing.

```text
AP
        |
        | Patient or order query
        v
Hospital System
        |
        | Query response
        v
AP
```

Possible use cases:

- An emergency or unscheduled ECG examination.
- Missing patient demographics.
- Recovering data after downtime.
- Manually searching for a patient before ECG acquisition.

Possible implementations:

| Hospital Capability | Possible Query Method |
|---|---|
| Traditional HL7 v2 | Hospital-specific HL7 query and response messages |
| FHIR API | REST queries such as `GET /Patient?identifier=...` |
| DICOM environment | Modality Worklist query when supported |

Pull support should not be assumed. It must be confirmed with each hospital.

### 3.3 Conclusion

The AP should support both models, with the following priority:

```text
Primary:    Hospital Push → AP Listener
Secondary:  AP Pull Query → Hospital System
```

## 4. Returning Integrated ECG Data to the Hospital

The result format depends on whether the hospital has PACS support.

### 4.1 Hospitals with PACS: Prefer DICOM

For hospitals with PACS:

```text
AP
        |
        | DICOM ECG Waveform and report
        v
Hospital PACS
```

Relevant DICOM formats include:

- `12-lead ECG Waveform Storage`
- `General ECG Waveform Storage`
- DICOM Structured Report for ECG measurements and interpretations

DICOM is preferred for ECG waveforms because it is designed to represent
digitized ECG signals, patient context, study metadata, and waveform data.

### 4.2 Hospitals without PACS: Use HL7 ORU^R01

If the hospital only accepts HL7 interfaces, the AP should normally return
integrated ECG results using:

```text
HL7 v2 ORU^R01 over MLLP-TCP
```

Typical segments:

| Segment | Purpose |
|---|---|
| `MSH` | Sender, receiver, timestamp, and message control ID |
| `PID` | Patient identifier |
| `PV1` | Patient visit or location context |
| `OBR` | ECG report or observation-group context |
| `OBX` | Individual measurements, interpretations, or report attachments |

Example:

```hl7
MSH|^~\&|ECG_AP|QT_MEDICAL|HOSPITAL|EMR|20260602120000||ORU^R01|MSG001|P|2.5.1
PID|||PATIENT123
PV1||O
OBR|1|||ECG^Electrocardiogram
OBX|1|NM|8867-4^Heart rate^LN||72|/min
OBX|2|TX|ECG-INTERPRETATION^ECG Interpretation||Normal sinus rhythm
OBX|3|ED|ECG-REPORT^ECG Report||PDF^Base64EncodedContent
```

The hospital must confirm:

- Accepted HL7 version.
- Required segments and fields.
- Patient identifier namespace.
- Observation codes, such as LOINC or hospital-defined codes.
- Unit requirements.
- Whether PDF reports are accepted in `OBX` attachments.
- ACK, retry, deduplication, and correction rules.

### 4.3 Recommended Decision Model

```text
Does the hospital support PACS?
        |
        +-- Yes → Send DICOM ECG Waveform and Structured Report to PACS
        |
        +-- No  → Send HL7 v2 ORU^R01 result message to HIS / EMR
```

## 5. Current Simulation UI Assessment

### 5.1 Current Capability

The current local UI supports:

```text
Local UI
        |
        | HL7 ADT^A01 over MLLP-TCP
        v
Mirth Connect TCP Listener
        |
        | ACK
        v
Local UI
```

This is useful for:

- TCP reachability checks.
- MLLP framing validation.
- Sending a virtual HL7 message.
- Receiving and displaying ACK responses.

However, it only tests a client sending data to a server. It does not yet
simulate the complete ECG workflow.

### 5.2 Required Improvements

The UI should support four test modes.

| Mode | Purpose | Priority |
|---|---|---|
| Hospital Push Simulator | Generate and push hospital `ADT` and `ORM` messages to the AP | Required |
| AP Listener Inspector | Receive hospital Push messages, display raw HL7, and return ACK | Required |
| AP Result Sender | Generate and send ECG `ORU^R01` messages back to a hospital endpoint | Required |
| Patient Query Simulator | Simulate patient Pull queries and responses | Phase 2 |

### 5.3 Suggested UI Layout

```text
[Hospital → AP]
Generate ADT
Generate ORM
Push Message
Inspect ACK

[AP Listener]
Start / Stop Listener
Display Received HL7
Return AA / AE / AR

[AP → Hospital]
Generate ECG ORU
Attach PDF Report
Send Result
Inspect ACK

[Query]
Search Patient
Display Query Response
```

### 5.4 Suggested Test Data

The ECG result form should support:

- Patient identifier.
- Encounter or visit identifier.
- ECG device identifier.
- Acquisition timestamp.
- Heart rate.
- PR interval.
- QRS duration.
- QT and QTc intervals.
- Interpretation text.
- Optional PDF report attachment.

### 5.5 Suggested Reliability Tests

The UI should simulate:

- `AA`: accepted ACK.
- `AE`: application error.
- `AR`: application reject.
- ACK timeout.
- Duplicate message control IDs.
- Retry behavior.
- Invalid MLLP framing.
- Invalid patient identifiers.
- Corrected or updated ECG results.

## 6. Recommended Implementation Scope

### Phase 1: HL7 Push and Result Return

Implement:

```text
Hospital ADT / ORM Push
→ AP Listener
→ AP sends ACK

AP ECG ORU^R01 Push
→ Hospital Listener
→ Hospital sends ACK
```

This is the minimum useful simulation for the HL7-only hospital workflow.

### Phase 2: Pull Queries

Add patient and order query simulations after confirming which query protocol
target hospitals support.

### Phase 3: PACS and DICOM

Evaluate DICOM ECG Waveform Storage, Structured Reports, and PACS integration as
a separate workstream. DICOM simulation should not be mixed into the first HL7
UI iteration.

## 7. Open Questions for Hospitals

Before production integration, ask each hospital:

1. Will patient and ECG order data be pushed to the AP?
2. Which `ADT` events and order-message types will be provided?
3. Does the hospital support patient or order queries?
4. Does the hospital provide a FHIR API, HL7 v2 query interface, or DICOM
   Modality Worklist?
5. Does the hospital have PACS support for ECG waveform storage?
6. Which DICOM ECG SOP Classes are accepted?
7. If PACS is unavailable, does the hospital accept `ORU^R01`?
8. Which HL7 version, segments, codes, and units are required?
9. How should PDF ECG reports be attached or referenced?
10. What are the ACK, retry, deduplication, update, and correction rules?

## 8. Conclusion

For HL7-only integrations, the recommended first design is:

```text
Hospital Pushes ADT and ORM
→ AP receives and associates patient context with ECG-device data
→ AP returns integrated ECG results as ORU^R01
→ Hospital returns ACK
```

For hospitals with PACS, DICOM ECG Waveform Storage and Structured Reports
should be preferred for waveform and report delivery.

The current simulation UI is suitable for basic MLLP and ACK verification, but
it should be extended with listener mode, `ADT`, `ORM`, and `ORU` templates,
ECG-specific fields, and ACK failure simulations.

## 9. References

- HL7 v2 ADT transaction set:
  https://www.hl7.eu/HL7v2x/v22/std22/HL7CHP3.html
- HL7 v2 ORU observation reporting:
  https://hl7.eu/HL7v2x/v24/std24/ch07.htm
- IHE Resting ECG Workflow:
  https://wiki.ihe.net/index.php/Resting_ECG_Workflow
- DICOM 12-Lead ECG IOD:
  https://dicom.nema.org/medical/Dicom/2016e/output/chtml/part03/sect_A.34.3.html
- DICOM ECG SOP Classes:
  https://dicom.nema.org/medical/dicom/2016e/output/chtml/part04/sect_B.5.html
