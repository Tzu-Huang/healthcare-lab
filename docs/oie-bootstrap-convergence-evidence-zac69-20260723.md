# ZAC-69 OIE bootstrap convergence evidence

This report records an isolated, synthetic-data-only verification of the
Healthcare Lab bootstrap contract against OIE 4.5.2. No credentials,
authorization headers, raw Channel XML, HL7 payloads, or patient data were
captured.

## Run ownership

| Field | Evidence |
| --- | --- |
| Window | 2026-07-23 11:27-11:41 +08:00 |
| Tested product commit | `50f3fa21b2be864aa6fbe05836da28eae8b464e7` |
| Compose project / network | `zac69verify` / `zac69verify-lab` |
| Application image | Local image `healthcare-lab:zac69-50f3fa2`, built from the tested commit |
| OIE image | `nextgenhealthcare/connect:4.5.2@sha256:4afa295cfe7c5ffd596efee69594157fea87202e33d66bb4a98a52db4598f836` |
| Isolated host ports | HLAB `15069`; OIE MLLP `16069`/`16669`; OIE HTTP/HTTPS `18069`/`18469` |
| Local state target | Docker volume `zac69verify_lab-app-instance` mounted at `/app/instance` |
| OIE state target | Docker volume `zac69verify_oie-appdata` mounted at `/opt/connect/appdata` |
| Destructive-test boundary | Only the two exact `zac69verify` volumes above; both labels resolved to project `zac69verify` before removal |
| Competing stack | The existing `interoperability-lab` project, ports, network, containers, and volumes were not stopped, restarted, or reset |

The isolated override also replaced the GDT bind mount with
`zac69verify_lab-gdt-bridge`. Docker Compose 5.1.3 created all isolated
resources.

## Scenario ledger

| Scenario | Result | Bounded evidence |
| --- | --- | --- |
| Delayed readiness | PASS | HLAB started without OIE. Run `8ccb9a5b3d0234cd00fa7129` completed after 3 attempts and the configured 8-second bound with `connection` / `timeout`; both logical types were unavailable/timeout and Retry was eligible. |
| Explicit Retry | PASS | After OIE reported 4.5.2 started, Retry run `1f5240f32ca39554149828f5` completed in one attempt. Both missing logical types were created and `STARTED`. |
| Clean startup | PASS | The combined-reset rerun at the tested commit produced run `f914ea4f7b155f0cf4ffb505`: one attempt, exactly two missing/success outcomes, both `STARTED`, with no duplicate managed names or IDs. |
| Retained restart | PASS | Run `fe1d11443f47cbab9cf6ddcd` returned two unchanged/no-op outcomes. IDs and revisions remained `cdf4905f-be47-40cd-981b-564cd75b8c38`/1 and `93fd9b78-2deb-4505-817a-a52975a887c8`/1. |
| One Channel missing | PASS | Guarded preview/delete removed only `HLAB_ORM_TO_AP`. Startup run `f07b01901ed3ff8dcaeb3988` recreated it once; peer `93fd9b78-2deb-4505-817a-a52975a887c8` remained revision 1 and `STARTED`. |
| Local-settings-only reset | PASS | At the tested commit, run `d7f0d7bb596f3a02b393ad5c` recovered both retained OIE identities in one attempt. IDs `35456c7e-c7d7-457f-a1a1-916007d3ce36` and `f779233b-1afb-428d-a4f5-3250fbb617cb` remained revision 1 and `STARTED`. |
| OIE-appdata-only reset | PASS after bounded fix | The first run exposed a persisted-ID replacement defect: two new Channels remained `UNDEPLOYED` and status evidence degraded to generic failure. Commit `50f3fa2` binds only the exact ID returned by the guarded create operation using a mapping CAS. Rerun `3895f8cf04d6caea87f61685` completed in one attempt with both missing/success outcomes and both new Channels `STARTED`. |
| Both state targets reset | PASS | After exact-target removal and re-resolution, run `f914ea4f7b155f0cf4ffb505` converged from clean state to exactly two revision-1 `STARTED` Channels. |
| Read-only surfaces | PASS | Three rounds of bootstrap status GET, Settings GET, diagnostics GET, and managed inventory GET produced no change to either final Channel ID, revision, status, or count. |
| Evidence safety | PASS | Evidence contains only allowlisted operational state, synthetic identifiers, image/commit identity, timestamps, and isolated resource names. |

## Focused fix verification

The live failure was reproduced only inside the disposable project. The fix
uses the Channel ID returned by the successful create call as the sole
read-back exception to the normal mapped-ID contradiction guard, then
atomically replaces the exact previously observed mapping identity and
revision. It does not adopt an unrelated pre-existing marker. The bootstrap
evidence allowlist also accepts the lifecycle service's bounded
`audit-failure` category.

Focused domain, lifecycle, bootstrap, coordinator, and bootstrap repository
verification passed: 69 tests. The live OIE-appdata-only and combined-reset
reruns passed against the committed image.

Overall ZAC-69 live gate: **PASS**.
