"""Framework-independent parsing and normalization of DICOM ECG waveforms."""

from __future__ import annotations

from dataclasses import dataclass
from struct import iter_unpack
from types import MappingProxyType
from typing import Any, Final, Mapping

from pydicom.dataset import Dataset


TWELVE_LEAD_ECG_WAVEFORM_STORAGE: Final = "1.2.840.10008.5.1.4.1.1.9.1.1"
GENERAL_ECG_WAVEFORM_STORAGE: Final = "1.2.840.10008.5.1.4.1.1.9.1.2"
SUPPORTED_SOP_CLASS_UIDS: Final = frozenset(
    {TWELVE_LEAD_ECG_WAVEFORM_STORAGE, GENERAL_ECG_WAVEFORM_STORAGE}
)

CANONICAL_LEADS: Final = (
    "I",
    "II",
    "III",
    "aVR",
    "aVL",
    "aVF",
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
    "V6",
)
SCPECG_LEAD_CODES: Final = MappingProxyType(
    {
        "5.6.3-9-1": "I",
        "5.6.3-9-2": "II",
        "5.6.3-9-61": "III",
        "5.6.3-9-62": "aVR",
        "5.6.3-9-63": "aVL",
        "5.6.3-9-64": "aVF",
        "5.6.3-9-3": "V1",
        "5.6.3-9-4": "V2",
        "5.6.3-9-5": "V3",
        "5.6.3-9-6": "V4",
        "5.6.3-9-7": "V5",
        "5.6.3-9-8": "V6",
    }
)

# DICOM uses UCUM codes in Channel Sensitivity Units Sequence. Accept common
# ASCII and Unicode spellings while keeping the supported physical dimension
# deliberately narrow.
VOLTAGE_UNIT_TO_MV: Final = MappingProxyType(
    {
        "V": 1000.0,
        "mV": 1.0,
        "uV": 0.001,
        "\u03bcV": 0.001,
        "\u00b5V": 0.001,
        "µV": 0.001,
        "μV": 0.001,
    }
)
DISPLAY_SAFE_METADATA_FIELDS: Final = (
    "Modality",
    "Manufacturer",
    "ManufacturerModelName",
    "DeviceSerialNumber",
    "SoftwareVersions",
)


class EcgWaveformError(ValueError):
    """Base class for rejected ECG waveform datasets."""


class UnsupportedSOPClassError(EcgWaveformError):
    """The dataset is not one of the explicitly supported ECG SOP classes."""


# Backwards-compatible spelling for callers that prefer conventional title case.
UnsupportedSopClassError = UnsupportedSOPClassError


class MissingWaveformError(EcgWaveformError):
    """The dataset has no usable Waveform Sequence."""


class MalformedWaveformError(EcgWaveformError):
    """The waveform structure or byte payload is inconsistent."""


class UnsupportedSampleError(EcgWaveformError):
    """The waveform sample representation is unsupported."""


class UnsupportedUnitError(EcgWaveformError):
    """A channel does not declare a supported voltage unit."""


class LeadLayoutError(EcgWaveformError):
    """The channels cannot be resolved to one unambiguous 12-lead layout."""


@dataclass(frozen=True, slots=True)
class EcgChannel:
    """One calibrated ECG lead in canonical layout order."""

    lead: str
    source_code: str
    samples_mv: tuple[float, ...]

    @property
    def samples(self) -> tuple[float, ...]:
        """Alias for consumers where the model-level unit supplies context."""
        return self.samples_mv


@dataclass(frozen=True, slots=True)
class EcgWaveform:
    """Normalized, renderer-independent 12-lead ECG waveform."""

    channels: tuple[EcgChannel, ...]
    sampling_frequency_hz: float
    duration_seconds: float
    sop_class_uid: str
    unit: str
    display_metadata: Mapping[str, Any]

    @property
    def metadata(self) -> Mapping[str, Any]:
        """Concise alias for the explicitly display-safe metadata projection."""
        return self.display_metadata


def parse_ecg_waveform(dataset: Dataset) -> EcgWaveform:
    """Validate and normalize a pydicom ECG waveform dataset."""
    sop_class_uid = str(getattr(dataset, "SOPClassUID", ""))
    if sop_class_uid not in SUPPORTED_SOP_CLASS_UIDS:
        raise UnsupportedSOPClassError(
            f"Unsupported ECG Waveform SOP Class UID: {sop_class_uid or '<missing>'}"
        )

    waveform_sequence = getattr(dataset, "WaveformSequence", None)
    if not waveform_sequence:
        raise MissingWaveformError("Waveform Sequence is missing or empty")
    if len(waveform_sequence) != 1:
        raise MalformedWaveformError("Exactly one Waveform Sequence item is required")
    waveform = waveform_sequence[0]

    channel_count = _positive_int(waveform, "NumberOfWaveformChannels")
    sample_count = _positive_int(waveform, "NumberOfWaveformSamples")
    if channel_count != len(CANONICAL_LEADS):
        raise LeadLayoutError(
            f"Expected {len(CANONICAL_LEADS)} waveform channels, got {channel_count}"
        )
    sampling_frequency = _positive_float(waveform, "SamplingFrequency")

    bits_allocated = _positive_int(waveform, "WaveformBitsAllocated")
    interpretation = str(getattr(waveform, "WaveformSampleInterpretation", ""))
    if bits_allocated != 16 or interpretation != "SS":
        raise UnsupportedSampleError(
            "Only signed 16-bit (SS) waveform samples are supported"
        )

    definitions = getattr(waveform, "ChannelDefinitionSequence", None)
    if definitions is None or len(definitions) != channel_count:
        raise MalformedWaveformError(
            "Channel Definition Sequence length must match waveform channel count"
        )

    payload = getattr(waveform, "WaveformData", None)
    if not isinstance(payload, (bytes, bytearray)):
        raise MalformedWaveformError("Waveform Data is missing or is not bytes")
    expected_length = channel_count * sample_count * 2
    if len(payload) != expected_length:
        raise MalformedWaveformError(
            f"Waveform Data is {len(payload)} bytes; expected {expected_length}"
        )

    byte_order = "<" if _is_little_endian(dataset) else ">"
    raw_flat = tuple(value[0] for value in iter_unpack(f"{byte_order}h", payload))
    resolved: dict[str, EcgChannel] = {}
    for channel_index, definition in enumerate(definitions):
        lead, source_code = _resolve_lead(definition)
        if lead in resolved:
            raise LeadLayoutError(f"Duplicate SCPECG lead definition: {lead}")
        factor = _calibration_factor_mv(definition)
        baseline = _optional_float(definition, "ChannelBaseline", 0.0)
        sensitivity = _required_float(definition, "ChannelSensitivity")
        correction = _optional_float(
            definition, "ChannelSensitivityCorrectionFactor", 1.0
        )
        samples = tuple(
            (raw_flat[offset] * sensitivity * correction + baseline) * factor
            for offset in range(channel_index, len(raw_flat), channel_count)
        )
        resolved[lead] = EcgChannel(lead, source_code, samples)

    missing = tuple(lead for lead in CANONICAL_LEADS if lead not in resolved)
    if missing:
        raise LeadLayoutError(f"Missing required SCPECG leads: {', '.join(missing)}")

    metadata: dict[str, Any] = {
        "SOPClassUID": sop_class_uid,
        "NumberOfWaveformChannels": channel_count,
        "NumberOfWaveformSamples": sample_count,
        "SamplingFrequency": sampling_frequency,
        "DurationSeconds": sample_count / sampling_frequency,
        "WaveformBitsAllocated": bits_allocated,
        "WaveformSampleInterpretation": interpretation,
    }
    originality = getattr(waveform, "WaveformOriginality", None)
    if originality is not None:
        metadata["WaveformOriginality"] = _metadata_value(originality)
    for field in DISPLAY_SAFE_METADATA_FIELDS:
        value = getattr(dataset, field, None)
        if value is not None:
            metadata[field] = _metadata_value(value)

    return EcgWaveform(
        channels=tuple(resolved[lead] for lead in CANONICAL_LEADS),
        sampling_frequency_hz=sampling_frequency,
        duration_seconds=sample_count / sampling_frequency,
        sop_class_uid=sop_class_uid,
        unit="mV",
        display_metadata=MappingProxyType(metadata),
    )


def _positive_int(dataset: Dataset, field: str) -> int:
    try:
        value = int(getattr(dataset, field))
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise MalformedWaveformError(f"{field} must be a positive integer") from exc
    if value <= 0:
        raise MalformedWaveformError(f"{field} must be a positive integer")
    return value


def _positive_float(dataset: Dataset, field: str) -> float:
    value = _required_float(dataset, field)
    if value <= 0:
        raise MalformedWaveformError(f"{field} must be positive")
    return value


def _required_float(dataset: Dataset, field: str) -> float:
    try:
        return float(getattr(dataset, field))
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise MalformedWaveformError(f"{field} must be numeric") from exc


def _optional_float(dataset: Dataset, field: str, default: float) -> float:
    if not hasattr(dataset, field):
        return default
    return _required_float(dataset, field)


def _resolve_lead(definition: Dataset) -> tuple[str, str]:
    sources = getattr(definition, "ChannelSourceSequence", None)
    if not sources or len(sources) != 1:
        raise LeadLayoutError("Each channel requires exactly one source definition")
    source = sources[0]
    scheme = str(getattr(source, "CodingSchemeDesignator", ""))
    code = str(getattr(source, "CodeValue", ""))
    if scheme != "SCPECG" or code not in SCPECG_LEAD_CODES:
        raise LeadLayoutError(
            f"Unknown or unsupported channel source: {scheme or '<missing>'} "
            f"{code or '<missing>'}"
        )
    return SCPECG_LEAD_CODES[code], code


def _calibration_factor_mv(definition: Dataset) -> float:
    units = getattr(definition, "ChannelSensitivityUnitsSequence", None)
    if not units or len(units) != 1:
        raise UnsupportedUnitError(
            "Each channel requires exactly one sensitivity voltage unit"
        )
    unit = units[0]
    scheme = str(getattr(unit, "CodingSchemeDesignator", ""))
    code = str(getattr(unit, "CodeValue", ""))
    if scheme != "UCUM" or code not in VOLTAGE_UNIT_TO_MV:
        raise UnsupportedUnitError(
            f"Unsupported channel sensitivity unit: {scheme or '<missing>'} "
            f"{code or '<missing>'}"
        )
    return VOLTAGE_UNIT_TO_MV[code]


def _is_little_endian(dataset: Dataset) -> bool:
    transfer_syntax = getattr(getattr(dataset, "file_meta", None), "TransferSyntaxUID", None)
    if transfer_syntax is not None:
        try:
            return bool(transfer_syntax.is_little_endian)
        except AttributeError:
            pass
    legacy_byte_order = getattr(dataset, "is_little_endian", None)
    return True if legacy_byte_order is None else bool(legacy_byte_order)


def _metadata_value(value: Any) -> Any:
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_metadata_value(item) for item in value)
    return str(value)
