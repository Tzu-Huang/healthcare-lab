# oe-module-gdt-ecg-poc

This is a scaffold for the OpenEMR-facing side of the `OpenEMR + GDT bridge` proof of concept.

## Purpose

- Create an encounter-linked ECG order from OpenEMR context
- Hand the order to an external GDT bridge sidecar
- Show order status, imported summary values, and returned PDF reports

## Planned Integration Boundary

- OpenEMR owns patient/encounter context, order UI, and result display
- The external bridge owns `GDT-IN` rendering, folder watching, `GDT-OUT` parsing, and import callbacks

## Current Workspace Mapping

The live PoC implementation currently runs in the Flask demo app in this repo:

- `app.py`
- `backend/lab_store.py`
- `frontend/templates/index.html`
- `frontend/static/app.js`

This scaffold documents where an OpenEMR module would plug in once a real OpenEMR codebase is available.
