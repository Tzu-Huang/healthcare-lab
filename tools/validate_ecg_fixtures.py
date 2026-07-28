"""Validate local ECG fixtures without emitting identifying DICOM values."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.ecg_waveform import parse_ecg_waveform


DEFAULT_MANIFEST = ROOT / "dicom-formats" / "ecg-fixtures.manifest.json"


def validate_manifest(manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    """Return disclosure-safe contract errors; an empty list means success."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checklist = tuple(manifest["policy"]["identity_checklist"])
    errors: list[str] = []
    base = manifest_path.parent

    for entry in manifest["fixtures"]:
        name = Path(entry["path"]).name
        path = base / name
        if not path.is_file():
            errors.append(f"{name}: missing local-only fixture")
            continue

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            errors.append(f"{name}: content hash drift")
            continue

        dataset = pydicom.dcmread(path)
        present = sorted(field for field in checklist if _has_value(dataset, field))
        expected_present = sorted(
            entry["deidentification"]["identity_attributes_present"]
        )
        if present != expected_present:
            errors.append(f"{name}: identity attribute presence drift")

        deident = entry["deidentification"]
        handling = entry["handling"]
        if present:
            synthetic_confirmed = (
                deident["status"] == "synthetic-confirmed"
                and deident.get("contains_real_patient_data") is False
                and bool(deident.get("confirmation_source"))
                and handling["classification"] == "synthetic-local-test"
            )
            unresolved_local_only = (
                deident["status"] == "unresolved"
                and handling["classification"] == "local-only"
            )
            if (
                not (synthetic_confirmed or unresolved_local_only)
                or not handling["excluded_from_source_control"]
            ):
                errors.append(f"{name}: unsafe fixture handling classification")
        if bool(getattr(dataset, "PatientIdentityRemoved", "")) != bool(
            deident["patient_identity_removed"]
        ):
            errors.append(f"{name}: PatientIdentityRemoved declaration drift")
        if bool(getattr(dataset, "DeidentificationMethod", "")) != bool(
            deident["method_documented"]
        ):
            errors.append(f"{name}: de-identification method declaration drift")

        errors.extend(_invariant_errors(name, dataset, entry["invariants"]))

    return errors


def _invariant_errors(name: str, dataset: Any, expected: dict[str, Any]) -> list[str]:
    waveform = dataset.WaveformSequence[0]
    actual = {
        "sop_class_uid": str(dataset.SOPClassUID),
        "channels": int(waveform.NumberOfWaveformChannels),
        "samples_per_channel": int(waveform.NumberOfWaveformSamples),
        "sampling_frequency_hz": float(waveform.SamplingFrequency),
        "duration_seconds": (
            int(waveform.NumberOfWaveformSamples) / float(waveform.SamplingFrequency)
        ),
        "waveform_bits_allocated": int(waveform.WaveformBitsAllocated),
        "waveform_sample_interpretation": str(
            waveform.WaveformSampleInterpretation
        ),
        "waveform_data_bytes": len(waveform.WaveformData),
    }
    errors = [
        f"{name}: {key} invariant drift"
        for key, value in actual.items()
        if value != expected[key]
    ]
    try:
        model = parse_ecg_waveform(dataset)
        normalized = {
            "normalized_unit": model.unit,
            "canonical_leads": [channel.lead for channel in model.channels],
        }
        errors.extend(
            f"{name}: {key} invariant drift"
            for key, value in normalized.items()
            if value != expected[key]
        )
    except Exception:
        errors.append(f"{name}: normalized waveform contract rejected")
    return errors


def _has_value(dataset: Any, field: str) -> bool:
    value = getattr(dataset, field, None)
    return value is not None and str(value) != ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    errors = validate_manifest(args.manifest)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("ECG fixture contract valid (2 synthetic local-test fixtures; values suppressed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
