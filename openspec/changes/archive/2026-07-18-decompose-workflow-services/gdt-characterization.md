# ZAC-62 GDT Workflow Characterization

The GDT decomposition must preserve these observable contracts and ownership
boundaries:

| Use case | Existing executable evidence | Locked behavior and owner boundary |
|---|---|---|
| Outbound 6302 order and export | `tests/services/test_gdt_coordination.py`, `tests/repositories/test_gdt_workflow.py`, and the GDT order/write integration cases in `tests/integration/test_app.py` | Domain validation and message construction precede persistence; context, order, message, attachment, and event rows commit atomically in the repository. Export uses a cp1252 temporary file followed by an atomic rename, then records either exported or error state. |
| Inbox discovery and manual import | Bridge batch-import integration cases plus `tests/test_gdt_adapter.py` | Internal/temp files, unsupported extensions, filename-binding mismatches, unstable files, and missing files are skipped with stable reasons. Claimed files are decoded as cp1252 and parsed before the repository receives a normalized result. |
| File disposition | Delete, archive, parse-failure, and disposition-warning integration cases | Successful imports are deleted or collision-safely archived according to configuration; invalid input moves to error; a post-persistence filesystem failure reports `imported-warning` without rolling back the committed result. |
| Candidate ordering and matching | FIFO bridge integration case and `tests/repositories/test_gdt_workflow_characterization.py` | Candidates use creation time, modification time, then filename ordering. The newest exact order identifier wins; an exact order match outranks a contradictory patient number; context-only and fully unmatched results keep their current workbench buckets. |
| Demo result | `GdtWorkflowCoordinatorTest.test_demo_result_is_deterministic_and_uses_normal_result_path` and the bridge demo integration case | Demo data is deterministic and enters through the same parse, normalize, persistence, event, and projection path as imported 6310 results. |
| Workbench and projections | Coordination read-delegate test, repository projection tests, and the bridge/workbench integration case | Patient, order, result, message, attachment, event, unmatched-result, bridge-inbox, and `resultsByOrder` projections retain their current ordering and shapes. |
| Bridge callback and watcher lifecycle | `tests/runtime/test_gdt_bridge_watcher.py` and the watcher lifecycle/path-guard integration case | The runtime watcher owns polling, stability observations, start/stop, and callback scheduling. Configuration may change only while stopped; application services receive the importer as a callback and do not own watcher threads. |
| Error and rollback behavior | Adapter rejection tests, coordination invalid-result test, repository rollback characterization, and GDT API integration cases | Invalid payloads never reach persistence. Builder or result-side failures roll back all related GDT rows and order status. HTTP mappings preserve 400/404/409/500 responses and return persisted export error state where applicable. |

The independently meaningful application use cases for the next extraction are
order access/creation, bridge inbox/import/export/configuration, watcher control,
and result/demo/workbench access. Filesystem polling remains in
`backend/runtime/gdt_bridge_watcher.py`; GDT parsing and filename rules remain in
domain/service helpers; atomic multi-table workflow mutations remain in
`backend/repositories/gdt_workflow.py`.
