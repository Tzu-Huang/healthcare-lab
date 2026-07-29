# Contributing to Healthcare Lab

Thanks for helping make healthcare interoperability testing easier to reproduce.
Contributions to documentation, protocol fixtures, platform support, tests, and
operator experience are welcome.

## Before You Start

- Use synthetic data only. Never commit protected health information, real
  credentials, private endpoints, or identifiable DICOM metadata.
- Search existing issues before opening a new one.
- For a substantial behavior or architecture change, open an issue first so the
  scope and interoperability assumptions can be discussed.
- Keep changes focused. Separate unrelated protocol or infrastructure changes.

## Development Setup

Python 3.10 or newer is required for direct host development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>.

The supported end-user runtime uses Docker Compose:

```powershell
.\deploy\lab.ps1 start
.\deploy\lab.ps1 status
```

See [Deployment runtime](deploy/README.md) for service configuration and
operations.

## Validation

Run the full product test suite:

```powershell
python -m unittest discover -s tests -v
```

Also run the smallest relevant test module while developing. If your change
affects an external protocol workflow, document the environment, synthetic test
identifiers, expected result, and actual result in the pull request.

## Pull Requests

A useful pull request:

- explains the user or interoperability problem;
- identifies the affected protocol and system boundary;
- includes tests or explains why automated coverage is not practical;
- updates operator-facing documentation when behavior changes;
- preserves raw protocol evidence and stable identifiers where applicable; and
- contains no patient data, credentials, or environment-specific secrets.

Read [Architecture and boundaries](docs/architecture.md) and
[Project boundary](PROJECT_BOUNDARY.md) before moving responsibilities between
layers.

## Good First Contributions

Good starting points include sample HL7 message fixtures, Linux/macOS wrapper
improvements, ARM64 investigation, documentation screenshots, and repeatable
demo automation. Look for issues labeled `good first issue` or `help wanted`.
