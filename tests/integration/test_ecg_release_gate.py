from __future__ import annotations

from io import BytesIO
from struct import pack
from types import SimpleNamespace
from unittest.mock import patch
import socket
import urllib.error

from pydicom import dcmread

from backend.domain.ecg_waveform import (
    CANONICAL_LEADS,
    GENERAL_ECG_WAVEFORM_STORAGE,
    TWELVE_LEAD_ECG_WAVEFORM_STORAGE,
    parse_ecg_waveform,
)
from tests.integration._case_support import ApiCaseSupport
from tests.services.test_dcm4chee_ecg import dicom_bytes


class _BinaryResponse:
    def __init__(self, body: bytes, content_type: str):
        self.body = body
        self.offset = 0
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int):
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def _release_gate_dicom(sop_class_uid: str) -> bytes:
    dataset = dcmread(BytesIO(dicom_bytes(sop_class=sop_class_uid)))
    waveform = dataset.WaveformSequence[0]
    waveform.NumberOfWaveformSamples = 10_000
    waveform.SamplingFrequency = 1_000
    for definition in waveform.ChannelDefinitionSequence:
        definition.ChannelSensitivity = 1
        definition.ChannelSensitivityUnitsSequence[0].CodeValue = "uV"
    one_timepoint = tuple(1_000 + index for index in range(12))
    waveform.WaveformData = pack("<120000h", *(one_timepoint * 10_000))
    output = BytesIO()
    dataset.save_as(output, enforce_file_format=True)
    return output.getvalue()


def _multipart(payload: bytes) -> bytes:
    return (
        b"--ECGBOUND\r\nContent-Type: application/dicom\r\n"
        b"Content-Transfer-Encoding: binary\r\n\r\n"
        + payload
        + b"\r\n--ECGBOUND--\r\n"
    )


class EcgReleaseGateTests(ApiCaseSupport):
    def _create_result(self, *, modality="ECG", sop_instance_uid="1.2.840.3"):
        profile = self.app.extensions[
            "integration_settings_service"
        ].get_effective("dcm4chee").runtime_profile()
        return self.dependencies.dcm4chee_result_repository.upsert_dcm4chee_result_record(
            {
                "study_instance_uid": "1.2.840.1",
                "series_instance_uid": "1.2.840.2",
                "sop_instance_uid": sop_instance_uid,
                "modality": modality,
                "instance_datetime": "20260728103000",
            },
            profile,
            raw_metadata={
                "PatientName": "RELEASE^GATE^SECRET",
                "Authorization": "Bearer MUST-NOT-LEAK",
            },
        )

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_both_sop_classes_cross_persisted_bare_api_and_svg_boundaries(
        self, open_secured
    ):
        for index, sop_class_uid in enumerate(
            (
                TWELVE_LEAD_ECG_WAVEFORM_STORAGE,
                GENERAL_ECG_WAVEFORM_STORAGE,
            ),
            start=3,
        ):
            with self.subTest(sop_class_uid=sop_class_uid):
                result = self._create_result(sop_instance_uid=f"1.2.840.{index}")
                payload = _release_gate_dicom(sop_class_uid)
                model = parse_ecg_waveform(dcmread(BytesIO(payload)))
                self.assertEqual(CANONICAL_LEADS, tuple(c.lead for c in model.channels))
                self.assertTrue(all(len(c.samples) == 10_000 for c in model.channels))
                self.assertEqual(1_000, model.sampling_frequency_hz)
                self.assertEqual(10, model.duration_seconds)
                self.assertEqual("mV", model.unit)
                self.assertAlmostEqual(1.0, model.channels[0].samples[0])

                open_secured.return_value = _BinaryResponse(
                    payload, "application/dicom"
                )
                metadata = self.client.get(
                    f"/api/dcm4chee/results/{result['id']}/ecg",
                    headers={"Authorization": "Bearer inbound-secret"},
                )
                self.assertEqual(200, metadata.status_code)
                waveform = metadata.get_json()["item"]["waveform"]
                self.assertEqual(list(CANONICAL_LEADS), waveform["leads"])
                self.assertEqual(12, waveform["leadCount"])
                self.assertEqual(1_000, waveform["samplingFrequencyHz"])
                self.assertEqual(10, waveform["durationSeconds"])
                self.assertEqual("mV", waveform["unit"])
                self.assertEqual(sop_class_uid, waveform["sopClassUid"])

                open_secured.return_value = _BinaryResponse(
                    payload, "application/dicom"
                )
                rendered = self.client.get(
                    f"/api/dcm4chee/results/{result['id']}/ecg/render.svg"
                )
                self.assertEqual(200, rendered.status_code)
                self.assertEqual("image/svg+xml", rendered.mimetype)
                svg = rendered.get_data(as_text=True)
                self.assertIn("<svg", svg)
                for lead in CANONICAL_LEADS:
                    self.assertIn(f"<!-- {lead} -->", svg)
                self.assertIn(
                    "For demonstration only - not for diagnostic use", svg
                )
                for forbidden in (
                    "RELEASE^GATE^SECRET",
                    "MUST-NOT-LEAK",
                    "inbound-secret",
                ):
                    self.assertNotIn(forbidden, metadata.get_data(as_text=True))
                    self.assertNotIn(forbidden, svg)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_general_ecg_multipart_crosses_persisted_api_boundary(self, open_secured):
        result = self._create_result()
        payload = _release_gate_dicom(GENERAL_ECG_WAVEFORM_STORAGE)
        open_secured.return_value = _BinaryResponse(
            _multipart(payload),
            'multipart/related; type="application/dicom"; boundary="ECGBOUND"',
        )

        response = self.client.get(f"/api/dcm4chee/results/{result['id']}/ecg")

        self.assertEqual(200, response.status_code)
        waveform = response.get_json()["item"]["waveform"]
        self.assertEqual(GENERAL_ECG_WAVEFORM_STORAGE, waveform["sopClassUid"])
        self.assertEqual(10, waveform["durationSeconds"])

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_invalid_instances_return_stable_disclosure_safe_errors(
        self, open_secured
    ):
        result = self._create_result()
        unsupported = _release_gate_dicom(TWELVE_LEAD_ECG_WAVEFORM_STORAGE)
        unsupported_dataset = dcmread(BytesIO(unsupported))
        unsupported_dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        unsupported_dataset.file_meta.MediaStorageSOPClassUID = (
            unsupported_dataset.SOPClassUID
        )
        unsupported_output = BytesIO()
        unsupported_dataset.save_as(unsupported_output, enforce_file_format=True)

        missing = dcmread(BytesIO(unsupported))
        del missing.WaveformSequence
        missing_output = BytesIO()
        missing.save_as(missing_output, enforce_file_format=True)

        wrong_unit = dcmread(BytesIO(unsupported))
        wrong_unit.WaveformSequence[0].ChannelDefinitionSequence[
            0
        ].ChannelSensitivityUnitsSequence[0].CodeValue = "mm"
        wrong_unit_output = BytesIO()
        wrong_unit.save_as(wrong_unit_output, enforce_file_format=True)

        truncated = dcmread(BytesIO(unsupported))
        truncated.WaveformSequence[0].WaveformData = (
            truncated.WaveformSequence[0].WaveformData[:-2]
        )
        truncated_output = BytesIO()
        truncated.save_as(truncated_output, enforce_file_format=True)

        cases = (
            (unsupported_output.getvalue(), "application/dicom", 415, "dcm4chee_ecg_unsupported"),
            (missing_output.getvalue(), "application/dicom", 422, "dcm4chee_ecg_invalid"),
            (wrong_unit_output.getvalue(), "application/dicom", 422, "dcm4chee_ecg_invalid"),
            (truncated_output.getvalue(), "application/dicom", 422, "dcm4chee_ecg_invalid"),
            (b"not multipart", 'multipart/related; type="application/dicom"; boundary="B"', 422, "dcm4chee_ecg_invalid"),
        )
        for body, content_type, status, code in cases:
            with self.subTest(code=code, content_type=content_type):
                open_secured.return_value = _BinaryResponse(body, content_type)
                response = self.client.get(
                    f"/api/dcm4chee/results/{result['id']}/ecg"
                )
                self.assertEqual(status, response.status_code)
                self.assertEqual(code, response.get_json()["error"]["code"])
                rendered = response.get_data(as_text=True)
                for forbidden in (
                    "RELEASE^GATE^SECRET",
                    "MUST-NOT-LEAK",
                    "WaveformSequence",
                    "mm",
                    "multipart",
                ):
                    self.assertNotIn(forbidden, rendered)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_unknown_and_upstream_failures_are_stable_and_safe(self, open_secured):
        unknown = self.client.get("/api/dcm4chee/results/999999/ecg")
        self.assertEqual(404, unknown.status_code)
        self.assertEqual(
            "dcm4chee_ecg_result_not_found",
            unknown.get_json()["error"]["code"],
        )

        result = self._create_result()
        open_secured.side_effect = socket.timeout("secret archive endpoint")
        upstream = self.client.get(
            f"/api/dcm4chee/results/{result['id']}/ecg",
            headers={"Authorization": "Bearer inbound-secret"},
        )
        self.assertEqual(502, upstream.status_code)
        self.assertEqual(
            "dcm4chee_ecg_upstream_failed",
            upstream.get_json()["error"]["code"],
        )
        response_text = upstream.get_data(as_text=True)
        for forbidden in (
            "secret archive endpoint",
            "inbound-secret",
            "RELEASE^GATE^SECRET",
            "127.0.0.1",
        ):
            self.assertNotIn(forbidden, response_text)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_unauthorized_and_unconfigured_profiles_fail_without_disclosure(
        self, open_secured
    ):
        result = self._create_result()
        open_secured.side_effect = urllib.error.HTTPError(
            "http://archive.invalid/secret-path",
            401,
            "credential rejected",
            {"Authorization": "Basic MUST-NOT-LEAK"},
            None,
        )

        unauthorized = self.client.get(
            f"/api/dcm4chee/results/{result['id']}/ecg"
        )

        self.assertEqual(502, unauthorized.status_code)
        self.assertEqual(
            "dcm4chee_ecg_upstream_failed",
            unauthorized.get_json()["error"]["code"],
        )
        for forbidden in (
            "archive.invalid",
            "secret-path",
            "credential rejected",
            "MUST-NOT-LEAK",
            "401",
        ):
            self.assertNotIn(forbidden, unauthorized.get_data(as_text=True))

        settings = self.app.extensions["integration_settings_service"]
        with patch.object(
            settings,
            "get_effective",
            return_value=SimpleNamespace(runtime_profile=lambda: {}),
        ):
            unconfigured = self.client.get(
                f"/api/dcm4chee/results/{result['id']}/ecg"
            )

        self.assertEqual(502, unconfigured.status_code)
        self.assertEqual(
            "dcm4chee_ecg_upstream_failed",
            unconfigured.get_json()["error"]["code"],
        )
        self.assertNotIn(
            "dicomweb.wadoRsUrl", unconfigured.get_data(as_text=True)
        )

    def test_viewer_summary_contract_is_stable_but_contains_no_archive_details(self):
        response = self.client.get("/viewer/ecg/42")

        self.assertEqual(200, response.status_code)
        html = response.get_data(as_text=True)
        for summary_id in (
            "ecg-viewer-leads",
            "ecg-viewer-sample-rate",
            "ecg-viewer-unit",
            "ecg-viewer-duration",
        ):
            self.assertIn(f'id="{summary_id}"', html)
        self.assertIn('id="ecg-viewer-graph"', html)
        self.assertNotIn("WADO", html)
        self.assertNotIn("Authorization", html)
