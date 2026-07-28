"""Application service for result-scoped dcm4chee ECG retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable, Mapping

from pydicom import dcmread
from pydicom.errors import InvalidDicomError

from backend.domain.ecg_waveform import (
    EcgWaveform,
    EcgWaveformError,
    UnsupportedSOPClassError,
    parse_ecg_waveform,
)
from backend.presentation.ecg_renderer import EcgRenderConfig, RenderedEcg, render_ecg


@dataclass(frozen=True, slots=True)
class RetrieveInstanceIdentifiers:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str


class Dcm4cheeEcgServiceError(RuntimeError):
    """Disclosure-safe application error suitable for HTTP translation."""

    def __init__(self, code: str, summary: str, *, http_status: int) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary
        self.http_status = http_status


class Dcm4cheeEcgNotFoundError(Dcm4cheeEcgServiceError):
    def __init__(self) -> None:
        super().__init__("dcm4chee_ecg_result_not_found", "ECG result was not found.", http_status=404)


class Dcm4cheeEcgConflictError(Dcm4cheeEcgServiceError):
    def __init__(self) -> None:
        super().__init__(
            "dcm4chee_ecg_instance_incomplete",
            "ECG result does not identify one retrievable instance.",
            http_status=409,
        )


class Dcm4cheeEcgUnsupportedError(Dcm4cheeEcgServiceError):
    def __init__(self) -> None:
        super().__init__(
            "dcm4chee_ecg_unsupported",
            "The retrieved instance is not a supported ECG.",
            http_status=415,
        )


class Dcm4cheeEcgInvalidError(Dcm4cheeEcgServiceError):
    def __init__(self) -> None:
        super().__init__(
            "dcm4chee_ecg_invalid",
            "The retrieved ECG instance is invalid.",
            http_status=422,
        )


class Dcm4cheeEcgUpstreamError(Dcm4cheeEcgServiceError):
    def __init__(self) -> None:
        super().__init__(
            "dcm4chee_ecg_upstream_failed",
            "The ECG instance could not be retrieved.",
            http_status=502,
        )


ResultGetter = Callable[[int], Mapping[str, Any]]
ProfileGetter = Callable[[str], Mapping[str, Any]]
InstanceRetriever = Callable[[Mapping[str, Any], RetrieveInstanceIdentifiers], bytes]


class Dcm4cheeEcgService:
    def __init__(
        self,
        *,
        result_getter: ResultGetter,
        profile_getter: ProfileGetter,
        retriever: InstanceRetriever,
    ) -> None:
        self._get_result = result_getter
        self._get_profile = profile_getter
        self._retrieve = retriever

    def load_waveform(self, result_id: int) -> tuple[Mapping[str, Any], EcgWaveform]:
        result = self._load_result(result_id)
        identifiers = self._identifiers(result)
        profile_name = str(result.get("profileName") or "").strip()
        if not profile_name:
            raise Dcm4cheeEcgConflictError()
        profile = self._get_profile(profile_name)
        try:
            payload = self._retrieve(profile, identifiers)
        except Dcm4cheeEcgServiceError:
            raise
        except Exception as exc:
            translated = _translate_typed_upstream_error(exc)
            raise translated from exc

        try:
            dataset = dcmread(BytesIO(payload), force=False)
            waveform = parse_ecg_waveform(dataset)
        except UnsupportedSOPClassError as exc:
            raise Dcm4cheeEcgUnsupportedError() from exc
        except (InvalidDicomError, EcgWaveformError, TypeError, ValueError) as exc:
            raise Dcm4cheeEcgInvalidError() from exc
        return result, waveform

    def metadata(self, result_id: int) -> dict[str, Any]:
        result, waveform = self.load_waveform(result_id)
        return {
            "result": {
                "id": int(result["id"]),
                "modality": str(result.get("modality") or ""),
                "instanceDateTime": str(result.get("instanceDateTime") or ""),
            },
            "capabilities": {"metadata": True, "renderSvg": True},
            "waveform": {
                "leadCount": len(waveform.channels),
                "leads": [channel.lead for channel in waveform.channels],
                "samplingFrequencyHz": waveform.sampling_frequency_hz,
                "durationSeconds": waveform.duration_seconds,
                "unit": waveform.unit,
                "sopClassUid": waveform.sop_class_uid,
            },
            "displayMetadata": dict(waveform.display_metadata),
        }

    def render(
        self, result_id: int, config: EcgRenderConfig = EcgRenderConfig()
    ) -> RenderedEcg:
        _, waveform = self.load_waveform(result_id)
        return render_ecg(waveform, config)

    def _load_result(self, result_id: int) -> Mapping[str, Any]:
        try:
            return self._get_result(int(result_id))
        except KeyError as exc:
            raise Dcm4cheeEcgNotFoundError() from exc

    @staticmethod
    def _identifiers(result: Mapping[str, Any]) -> RetrieveInstanceIdentifiers:
        values = tuple(
            str(result.get(key) or "").strip()
            for key in ("studyInstanceUid", "seriesInstanceUid", "sopInstanceUid")
        )
        if not all(values):
            raise Dcm4cheeEcgConflictError()
        return RetrieveInstanceIdentifiers(*values)


def _translate_typed_upstream_error(exc: Exception) -> Dcm4cheeEcgServiceError:
    status = getattr(exc, "http_status", None)
    category = str(getattr(exc, "category", "") or "").lower()
    if category in {"upstream", "timeout", "size"}:
        return Dcm4cheeEcgUpstreamError()
    if status == 415 or category in {"media-type", "unsupported-media"}:
        return Dcm4cheeEcgUnsupportedError()
    if status == 422 or category in {"content", "multipart", "malformed"}:
        return Dcm4cheeEcgInvalidError()
    return Dcm4cheeEcgUpstreamError()
