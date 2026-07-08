# AP 接端測試資訊整理

AP Integration Test Notes

## 1. 文件目的

這份文件提供 AP 工程師測試 Healthcare Lab 四個 server 串接端點時使用。

目前 AP 已經完成 Medplum、GDT、OIE、dcm4chee 四個 server 的串接入口，接下來主要測試兩件事：

1. AP 是否能接收或取得來自各 server 的 order。
2. AP 是否能將整理好的 ECG/result 資料回傳到對應 server。

這份文件不重新說明 Healthcare Lab 的完整架構，而是聚焦在測試接端時需要用到的 host、port、URL、credential、shared folder 與注意事項。

## 2. Healthcare Lab 主機資訊

Healthcare Lab server 目前架設在公司主要電腦上。

| 情境 | Host / IP | 說明 |
| --- | --- | --- |
| 同一台電腦 Same machine | `127.0.0.1` 或 `localhost` | AP 與 Healthcare Lab 跑在同一台主機 |
| 同一個內網 Same LAN | `192.168.0.145` | AP 與 Healthcare Lab 在同一個公司內網 |
| Tailscale VPN | `100.127.171.69` | AP 透過 Tailscale 連線時使用 |
| 外網 Public IP | `60.251.43.139` | AP 從外網連回公司主機時使用 |

注意：

- 如果 AP 和 Healthcare Lab 在同一台電腦，通常用 `localhost` 最簡單。
- 如果 AP 在公司內網另一台電腦，請優先使用 `192.168.0.145`。
- 如果 AP 透過 Tailscale VPN 測試，請使用 `100.127.171.69`。
- 如果 AP 從外網連線，請使用 `60.251.43.139`，但需要確認 router port forwarding、Windows firewall、Docker port mapping 都有開。
- Docker service name，例如 `medplum`、`oie`、`dcm4chee`，只適用於 Docker Compose container 內部，不適用於外部 AP。

## 3. Port / Endpoint 總表

| 系統 | 用途 | 同機 | 內網 | Tailscale | 外網 |
| --- | --- | --- | --- | --- | --- |
| Healthcare Lab UI | Lab dashboard | `http://127.0.0.1:5000` | `http://192.168.0.145:5000` | `http://100.127.171.69:5000` | `http://60.251.43.139:5000` |
| Medplum FHIR API | FHIR server | `http://127.0.0.1:8103/fhir/R4` | `http://192.168.0.145:8103/fhir/R4` | `http://100.127.171.69:8103/fhir/R4` | `http://60.251.43.139:8103/fhir/R4` |
| Medplum Web UI | Medplum admin UI | `http://127.0.0.1:3000` | `http://192.168.0.145:3000` | `http://100.127.171.69:3000` | `http://60.251.43.139:3000` |
| OIE Web UI | HL7 engine UI | `http://127.0.0.1:18080` | `http://192.168.0.145:18080` | `http://100.127.171.69:18080` | `http://60.251.43.139:18080` |
| OIE Result Listener | AP 回傳 ORU | `127.0.0.1:6661` | `192.168.0.145:6661` | `100.127.171.69:6661` | `60.251.43.139:6661` |
| OIE Order Listener | 測試 ORM input | `127.0.0.1:6663` | `192.168.0.145:6663` | `100.127.171.69:6663` | `60.251.43.139:6663` |
| dcm4chee DICOM | DIMSE / MWL / C-STORE | `127.0.0.1:11112` | `192.168.0.145:11112` | `100.127.171.69:11112` | `60.251.43.139:11112` |
| dcm4chee DICOMweb | DICOMweb API | `http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs` | `http://192.168.0.145:8082/dcm4chee-arc/aets/DCM4CHEE/rs` | `http://100.127.171.69:8082/dcm4chee-arc/aets/DCM4CHEE/rs` | `http://60.251.43.139:8082/dcm4chee-arc/aets/DCM4CHEE/rs` |
| dcm4chee Web UI | Archive UI | `http://127.0.0.1:8082/dcm4chee-arc/ui2` | `http://192.168.0.145:8082/dcm4chee-arc/ui2` | `http://100.127.171.69:8082/dcm4chee-arc/ui2` | `http://60.251.43.139:8082/dcm4chee-arc/ui2` |

## 4. Medplum FHIR 測試

AP 會直接連 Medplum FHIR API，查詢 `ServiceRequest` 作為 order 來源，並在 ECG/result 完成後寫回 FHIR resources。

### 4.1 AP 取得 Order

FHIR Base URL：

```text
同機:
http://127.0.0.1:8103/fhir/R4

內網:
http://192.168.0.145:8103/fhir/R4

Tailscale:
http://100.127.171.69:8103/fhir/R4

外網:
http://60.251.43.139:8103/fhir/R4
```

可先測試 FHIR capability statement：

```text
GET /metadata
```

完整 URL 範例：

```text
http://192.168.0.145:8103/fhir/R4/metadata
```

AP 取得 order 時，主要查詢 resource：

```text
ServiceRequest
```

實際 query 條件可依 AP 目前實作調整，例如依狀態、病人、更新時間或 `_count` 查詢。

### 4.2 AP 回傳 Result

AP 整理完 ECG result 後，預期可寫回 Medplum FHIR resources，例如：

- `DiagnosticReport`
- `Observation`
- `DocumentReference`
- `Binary`

實際 resource 結構需依 AP 目前實作與 Healthcare Lab 測試案例確認。

### 4.3 OAuth / Client Credentials

如果 Medplum API 要求授權，AP 需要支援 OAuth client credentials flow。

AP 端可能需要：

```text
MEDPLUM_CLIENT_ID=<由 Healthcare Lab 維護者提供>
MEDPLUM_CLIENT_SECRET=<由 Healthcare Lab 維護者提供>
FHIR_BASE_URL=http://<Medplum Host>:8103/fhir/R4
TOKEN_URL=http://<Medplum Host>:8103/oauth2/token
```

範例：

```text
FHIR_BASE_URL=http://192.168.0.145:8103/fhir/R4
TOKEN_URL=http://192.168.0.145:8103/oauth2/token
```

注意：

- `Client Secret` 不要寫進 repo 或正式文件。
- 如果 AP 尚未支援 client credentials，需要補上：
  - token request
  - access token cache / refresh
  - FHIR request header: `Authorization: Bearer <access_token>`
- 如果目前 local lab 暫時允許 unauthenticated 測試，也仍建議保留 OAuth 實作計畫，避免後續切到正式環境時重工。

## 5. GDT Shared Folder 測試

GDT 不走 HTTP API，而是 shared folder 檔案交換。

### 5.1 Shared Folder 位置

Healthcare Lab Docker container 內部路徑：

```text
/data/gdt-bridge
```

公司電腦 Windows host 實際資料夾：

```text
D:\healthcare-lab\healthcare-lab\instance\gdt-bridge
```

repo root `.env` 建議設定：

```text
GDT_BRIDGE_HOST_PATH=D:\healthcare-lab\healthcare-lab\instance\gdt-bridge
```

Healthcare Lab / Docker Compose 會把 Windows host path 掛到 container 內部的 `/data/gdt-bridge`。因此：

- AP 如果跑在公司電腦上，可以直接讀寫 `D:\healthcare-lab\healthcare-lab\instance\gdt-bridge`。
- Healthcare Lab container 內部看到的是 `/data/gdt-bridge`。

### 5.2 Folder Contract

| Folder | 說明 |
| --- | --- |
| `outbox/` | Healthcare Lab 寫出 GDT order，AP 從這裡讀 |
| `inbound/` | AP 寫回 GDT result，Healthcare Lab 從這裡匯入 |
| `reports/` | AP 放 PDF / XML / waveform artifact |
| `processed/` | AP 已處理的 intake file |
| `archive/` | Healthcare Lab 成功匯入後的 result file |
| `error/` | 解析或處理失敗的 GDT file |

### 5.3 不同電腦時的注意事項

如果 AP 跟 Healthcare Lab 在同一台公司電腦，AP 可以直接讀：

```text
D:\healthcare-lab\healthcare-lab\instance\gdt-bridge
```

如果 AP 在另一台電腦，這個 local path 不能直接使用。需要改成：

- Windows shared folder
- SMB network share
- 或其他 AP 可讀寫的 shared storage

然後將 `.env` 的 `GDT_BRIDGE_HOST_PATH` 指到該 shared folder，並重啟 Healthcare Lab 相關 container。

## 6. OIE / HL7 v2 MLLP 測試

OIE 使用 HL7 v2 over MLLP TCP。

目前測試方向：

1. OIE 傳 ORM order 給 AP。
2. AP 整理 result 後回傳 ORU 給 OIE。

### 6.1 Order: OIE -> AP

AP 需要開 MLLP TCP listener 接收 ORM。

AP listener 範例：

```text
0.0.0.0:6671
```

OIE channel destination 依 AP 所在位置設定：

```text
AP 與 OIE 同機:
127.0.0.1:6671

AP 在同一內網:
<AP 內網 IP>:6671

AP 透過 Tailscale:
<AP Tailscale IP>:6671

AP 在外網:
<AP public IP or domain>:6671
```

注意：

- AP listener port 需要開 firewall。
- 如果 AP 在 NAT 後面，需要設定 port forwarding。
- MLLP 是 TCP，不是 HTTP。
- OIE 要推 ORM 給 AP 時，OIE 設定的是 AP 的位址，不是 Healthcare Lab 的位址。

### 6.2 Result: AP -> OIE

AP 回傳 ORU 到 OIE listener。

OIE result listener：

```text
同機:
127.0.0.1:6661

內網:
192.168.0.145:6661

Tailscale:
100.127.171.69:6661

外網:
60.251.43.139:6661
```

OIE Web UI：

```text
同機:
http://127.0.0.1:18080

內網:
http://192.168.0.145:18080

Tailscale:
http://100.127.171.69:18080

外網:
http://60.251.43.139:18080
```

## 7. dcm4chee / DICOM 測試

AP 直接連 dcm4chee。此段主要提供 IP、port 與 AE Title。

### 7.1 DIMSE / MWL / C-STORE

```text
同機:
Host: 127.0.0.1
Port: 11112

內網:
Host: 192.168.0.145
Port: 11112

Tailscale:
Host: 100.127.171.69
Port: 11112

外網:
Host: 60.251.43.139
Port: 11112
```

AE Title：

```text
Called AE Title: DCM4CHEE
Calling AE Title: ECG_AP
```

`Calling AE Title` 可依 AP 實際設定調整。若 AP 已有固定 AE Title，請以 AP 實際設定為準。

### 7.2 DICOMweb

如果 AP 使用 DICOMweb：

```text
同機:
http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs

內網:
http://192.168.0.145:8082/dcm4chee-arc/aets/DCM4CHEE/rs

Tailscale:
http://100.127.171.69:8082/dcm4chee-arc/aets/DCM4CHEE/rs

外網:
http://60.251.43.139:8082/dcm4chee-arc/aets/DCM4CHEE/rs
```

dcm4chee Web UI：

```text
同機:
http://127.0.0.1:8082/dcm4chee-arc/ui2

內網:
http://192.168.0.145:8082/dcm4chee-arc/ui2

Tailscale:
http://100.127.171.69:8082/dcm4chee-arc/ui2

外網:
http://60.251.43.139:8082/dcm4chee-arc/ui2
```

目前 local lab 預設沒有啟用 production-grade auth / TLS，僅供測試環境使用。

## 8. 測試 Checklist

### Medplum

- [ ] AP 可以連到 `/fhir/R4/metadata`
- [ ] AP 可以查詢 `ServiceRequest`
- [ ] 如果需要 auth，AP 可以取得 access token
- [ ] AP 可以將 result 寫回 FHIR resources
- [ ] Healthcare Lab / Medplum UI 可以看到 AP 寫回的結果

### GDT

- [ ] AP 可以讀取 shared folder
- [ ] AP 可以從 `outbox/` 取得 GDT order
- [ ] AP 可以將 result 寫到 `inbound/`
- [ ] AP 可以將 PDF / XML artifact 放到 `reports/`
- [ ] Healthcare Lab 可以成功 import AP 寫回的 GDT result

### OIE

- [ ] AP listener 已啟動
- [ ] OIE 可以送 ORM 到 AP
- [ ] AP 可以解析 ORM
- [ ] AP 可以送 ORU 到 OIE listener `6661`
- [ ] OIE 收到 ORU 並回 ACK

### dcm4chee

- [ ] AP 可以連到 `11112`
- [ ] AP 使用正確 Called AE Title: `DCM4CHEE`
- [ ] AP 可以查詢 MWL / 傳送 DICOM
- [ ] 如果使用 DICOMweb，AP 可以連到 `8082` endpoint

## 9. Security / Network Notes

目前這些 endpoint 是 local lab / integration test 用途，不建議長期直接暴露在外網。

特別注意：

- Medplum、OIE、dcm4chee、Healthcare Lab UI 如果要外網測試，請確認只開必要 port。
- `MEDPLUM_CLIENT_SECRET` 不要放進 markdown、repo、聊天紀錄或截圖。
- 外網測試建議使用 VPN、Tailscale、reverse proxy、HTTPS 或其他受控連線方式。
- MLLP、DIMSE 多半是 raw TCP，沒有 HTTP 層的保護。若跨網路測試，請先確認 firewall 與安全邊界。
- local lab 預設 auth / TLS 設定不等於正式環境設定。

## 10. 待確認事項

以下資訊需要依實際測試狀況確認：

- AP 是否已支援 Medplum OAuth client credentials flow。
- Medplum client ID / secret 由誰提供與如何交付。
- AP 的 DICOM `Calling AE Title` 是否固定為 `ECG_AP`。
- AP 實際部署位置：同機、內網、Tailscale、或外網。
- 外網測試時哪些 port 已經完成 firewall / router port forwarding。
- AP 回寫 Medplum result 時採用的 FHIR resource payload 是否已與 Healthcare Lab 測試案例對齊。
