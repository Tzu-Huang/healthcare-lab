# End-to-End Demo Walkthrough

## Goal

Demonstrate the main AP workflow:

```text
Mirth hospital Push
-> Hospital -> AP Listener :6671
-> AP queue waits for ECG
-> ECG JSON upload matches by MRN
-> AP -> Hospital Result Endpoint :6661
-> Mirth hospital listener returns ACK
```

## Prerequisites

- Mirth Connect channels from [mirth-connect-setup.md](mirth-connect-setup.md)
- Windows firewall permits local lab traffic to TCP `6671`
- Virtual data only

Example addresses used below:

| System | Address |
| --- | --- |
| Windows AP simulator | `192.168.30.52` |
| Ubuntu Mirth Connect | `192.168.30.177` |

Replace them with the current lab addresses.

## 1. Start the UI

In Windows PowerShell:

```powershell
cd C:\path\to\Intern
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 2. Start the AP Listener

In **Step 1 - Listen for Hospital HL7**:

| Field | Value |
| --- | --- |
| Bind Host | `0.0.0.0` |
| Listener Port | `6671` |
| Encoding | `utf-8` |

Select **Start AP Listener**.

Expected status:

```text
Listening 0.0.0.0:6671
```

## 3. Push Hospital Context from Mirth

In Mirth Administrator:

```text
Channels
-> HOSPITAL_PUSH_TO_AP
-> Send Message
```

Send:

```hl7
MSH|^~\&|HOSPITAL||ECG_AP||20260602150000||ADT^A04|ADT002|P|2.5.1
PID|1||QT_Athlete_003_Borderline2||Brooks^Caleb||20100228|M
```

In **Step 2 - Review Incoming Queue**, confirm:

```text
MRN:    QT_Athlete_003_Borderline2
HL7:    ADT^A04
ECG:    Waiting
Status: WAITING_FOR_ECG
```

## 4. Upload ECG JSON

In **Step 3 - Upload ECG JSON**, select:

```text
examples/ecg-sample.json
```

Select **Upload ECG JSON**.

The queue should update:

```text
MRN:    QT_Athlete_003_Borderline2
HL7:    ADT^A04
ECG:    Uploaded
Status: READY_TO_SEND
```

## 5. Configure the Hospital Result Endpoint

In **Step 4 - Return ECG Result to Hospital**:

| Field | Value |
| --- | --- |
| Hospital Host | `<Ubuntu-IP>` |
| Hospital Port | `6661` |
| Timeout (ms) | `5000` |
| Encoding | `utf-8` |

Select **Test Hospital Endpoint**.

Expected status:

```text
TCP reachable
```

## 6. Generate ORU Result

Still in **Step 4 - Return ECG Result to Hospital**:

1. Select the `READY_TO_SEND` queue row.
2. Choose `ORU^W01` for waveform OBX return or `ORU^R01` for aECG XML return.
   For `ORU^W01`, choose MA timepoint-major or NA channel-major waveform array
   layout.
3. Select **Generate HL7 Result**.
4. Expand **Advanced Tools** only if you need to review or edit the raw ORU.

Expected structure:

```hl7
MSH|...||ORU^W01|...|2.5.1
PID|||QT_Athlete_003_Borderline2|...
OBR|1|||ECG^Electrocardiogram
OBX|1|TS|TIM^Time Channel^99ECG||...
OBX|2|CE|CHN^Channel Definition^99ECG||...
OBX|3|NA|WAV^Waveform Samples^99ECG||...
```

For `ORU^R01`, the JSON waveform is carried as a minimal aECG XML document in
an inline `OBX|ED`:

```hl7
MSH|...||ORU^R01|...|2.5.1
PID|||QT_Athlete_003_Borderline2|...
OBR|1|||ECG^Electrocardiogram
OBX|1|ED|93000^Annotated ECG^LN||AP_SIMULATOR^Application^XML^Base64^...
```

## 7. Send ORU Result

Select:

```text
Send ORU to Hospital
```

Expected queue status:

```text
ACCEPTED
```

In **Step 5 - Inspect Selected Record**, review the ACK and outbound attempt:

```json
{
  "status": "ACCEPTED",
  "ackCode": "AA"
}
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Mirth TCP Sender reports `Connect timed out` | AP listener is started on `0.0.0.0:6671`; Windows firewall allows TCP `6671`; Mirth destination uses the Windows LAN IP |
| AP raw sender reports `TCP failed` for `6671` | Restart the AP listener after restarting `python app.py` |
| Queue remains `WAITING_FOR_ECG` | ECG JSON `patient.mrn` must equal inbound HL7 `PID-3` |
| Queue remains `WAITING_FOR_HL7` | Push a matching inbound `ADT^A04`, `ADT^A08`, or `ORM^O01` |
| ORU sender reports failure | Confirm Mirth `HOSPITAL_RECEIVE_ORU` is deployed and listening on `6661` |
| ACK is `AE` or `AR` | Inspect the AP selected record and Mirth message detail |

## Local Loopback Troubleshooting

Expand **Advanced Tools** only when you need to test the AP listener without
Mirth. The page clearly labels this path:

```text
AP Simulator Raw Sender -> 127.0.0.1:6671 -> AP Simulator Listener
```

Select **Generate Local Test ADT**, then **Send to This AP Listener**. This is
an AP-to-itself test and is not the hospital production flow. The Advanced
Tools section also exposes ACK failure simulation through `AA`, `AE`, and
`AR`.

## Optional Pull Demo

After storing a demo patient, expand **Advanced Tools** and use
**Mock Patient Pull Extension**:

```text
MRN: QT_Athlete_003_Borderline2
-> Lookup Patient
```

This demonstrates a future query extension. It is not a production FHIR
endpoint.
