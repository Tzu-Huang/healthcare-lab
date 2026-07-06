# Mirth Connect 4.5.2 Setup

## Purpose

[Mirth Connect 4.5.2](https://github.com/nextgenhealthcare/connect) acts as the
hospital-side open-source simulator. It uses MPL-2.0 and remains external to
this repository.

The demo requires two Mirth channels:

| Channel | Direction | Port |
| --- | --- | --- |
| `HOSPITAL_PUSH_TO_AP` | Mirth TCP Sender → AP listener | Windows `:6671` |
| `HOSPITAL_RECEIVE_ORU` | AP sender → Mirth TCP Listener | Ubuntu `:6661` |

## Start Mirth Connect with Docker

Example Ubuntu setup:

```bash
mkdir -p ~/Zack/mirth-connect/appdata

docker run --name mirth-connect \
  -d \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8443:8443 \
  -p 6661:6661 \
  -v ~/Zack/mirth-connect/appdata:/opt/connect/appdata \
  nextgenhealthcare/connect:4.5.2
```

Open the Mirth Connect Administrator through:

```text
http://<Ubuntu-IP>:8080
```

## Channel 1: Hospital Push to AP

Create:

```text
Channels
→ Channel Tasks
→ New Channel
```

Summary:

| Field | Value |
| --- | --- |
| Name | `HOSPITAL_PUSH_TO_AP` |
| Inbound Data Type | `HL7 v2.x` |
| Outbound Data Type | `HL7 v2.x` |

Source:

| Field | Value |
| --- | --- |
| Connector Type | `Channel Reader` |

Destination:

| Field | Value |
| --- | --- |
| Name | `SEND_TO_AP` |
| Connector Type | `TCP Sender` |
| Remote Address | `<Windows-IP>` |
| Remote Port | `6671` |
| Transmission Mode | `MLLP` |
| Send Timeout | `5000` ms |
| Response Timeout | `5000` ms |
| Keep Connection Open | `No` |

Save and deploy the channel.

The AP simulator must be listening on:

```text
0.0.0.0:6671
```

## Channel 2: Hospital Receive ORU

Create another channel:

```text
HOSPITAL_RECEIVE_ORU
```

Summary:

| Field | Value |
| --- | --- |
| Inbound Data Type | `HL7 v2.x` |
| Outbound Data Type | `HL7 v2.x` |

Source:

| Field | Value |
| --- | --- |
| Connector Type | `TCP Listener` |
| Mode | `Server` |
| Listener Port | `6661` |
| Transmission Mode | `MLLP` |
| Data Type | `Text` |
| Encoding | `UTF-8` |
| Respond on New Connection | `No` |

Use the default response behavior that returns an HL7 ACK on the same
connection. Save and deploy the channel.

## Connectivity Checks

From Ubuntu to the Windows AP listener:

```bash
nc -vz -w 3 <Windows-IP> 6671
```

From Windows to the Ubuntu Mirth listener:

```powershell
Test-NetConnection <Ubuntu-IP> -Port 6661
```

## Windows Firewall for AP Listener

When Ubuntu cannot connect to Windows `:6671`, run an elevated Windows
PowerShell:

```powershell
New-NetFirewallRule `
  -DisplayName "ECG AP Simulator MLLP 6671" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 6671 `
  -Action Allow `
  -Profile Any
```

Use this only in a controlled local lab network.
