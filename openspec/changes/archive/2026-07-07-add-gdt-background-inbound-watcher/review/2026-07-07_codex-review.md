## Findings

### P2 - Post-persistence cleanup failures are reported as import failures after the result is already committed

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:877)

`import_gdt_bridge_files()` persists the `6310` result with `store.record_gdt_result()` before deleting or archiving the claimed file. If `processing_path.unlink()` or `processing_path.replace(target_path)` then raises an `OSError`, the broad `except (SimulatorValidationError, UnicodeDecodeError, OSError)` path moves the file to `error/` and reports the import as a failure. At that point the database already contains the imported message, attachments, events, and possibly an updated order status. This creates an inconsistent operator view: the API/watcher says the file failed and places it in `error/`, while the result is already clinically attached. On flaky shared folders or permission changes, this can lead to duplicate investigation or manual reprocessing of an already-imported result.

Recommendation: split parse/persist failures from post-persistence file-disposition failures. Once persistence succeeds, report the result as imported with a warning/disposition error, and keep the file in `processing/` or move it to a separate diagnostic location without classifying the GDT import itself as failed.

### P2 - Manual inbox listing hides GDT 2.1 numeric-extension files even when the backend supports them

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:1894)

The new binding helper supports GDT 2.1 sequence-extension variants such as `.001`, and `/api/gdt/bridge/import` can accept them when `GDT_BRIDGE_FILENAME_PROFILE=gdt21`. However, `list_gdt_bridge_inbox_items()` still uses `glob("*.gdt")` for pending, archived, and error files. In GDT 2.1 profile, valid files like `EDV1EKG1.001` are eligible for automatic import but will not appear in the Bridge Inbox UI for manual selected-file import or status visibility. This weakens the fallback/debug flow that the proposal explicitly keeps.

Recommendation: make inbox listing use the same eligibility/profile helper as import discovery, or include `.001`-style files when the configured filename profile is `gdt21`.

## Open Questions

- Should post-success file disposition failures be visible as watcher warnings in `lastResult`, separate from parse/persist failures?
- Should archive/error listing apply binding filters, or should it show all diagnostic files regardless of the current filename profile?

## Tests Reviewed

- `python -m unittest discover -s tests -v`
- `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`
- `node --check frontend\static\app.js`
- `openspec validate add-gdt-background-inbound-watcher --strict`

## Residual Risk

The automated tests cover normal archive/delete behavior, parse failure routing, binding filters, FIFO ordering, watcher lifecycle, and UI contract presence. They do not currently cover file-disposition failures after successful database persistence or GDT 2.1 `.001` inbox listing behavior.
