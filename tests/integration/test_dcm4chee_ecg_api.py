from __future__ import annotations

from unittest.mock import patch

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


class Dcm4cheeEcgEndToEndTests(ApiCaseSupport):
    def create_result(self):
        profile = self.app.extensions[
            "integration_settings_service"
        ].get_effective("dcm4chee").runtime_profile()
        return self.dependencies.dcm4chee_result_repository.upsert_dcm4chee_result_record(
            {
                "study_instance_uid": "1.2.840.1",
                "series_instance_uid": "1.2.840.2",
                "sop_instance_uid": "1.2.840.3",
                "modality": "ECG",
                "instance_datetime": "20260728103000",
            },
            profile,
            raw_metadata={"PatientName": "MUST^NOT^LEAK"},
        )

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_bare_dicom_metadata_is_retrieved_end_to_end(self, open_secured):
        result = self.create_result()
        open_secured.return_value = _BinaryResponse(
            dicom_bytes(), "application/dicom"
        )

        response = self.client.get(f"/api/dcm4chee/results/{result['id']}/ecg")

        self.assertEqual(200, response.status_code)
        item = response.get_json()["item"]
        self.assertEqual(result["id"], item["result"]["id"])
        self.assertEqual(12, item["waveform"]["leadCount"])
        self.assertNotIn("MUST", response.get_data(as_text=True))

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_multipart_dicom_renders_svg_end_to_end(self, open_secured):
        result = self.create_result()
        payload = dicom_bytes()
        multipart = (
            b"--BOUND\r\nContent-Type: application/dicom\r\n"
            b"Content-Transfer-Encoding: binary\r\n\r\n"
            + payload
            + b"\r\n--BOUND--\r\n"
        )
        open_secured.return_value = _BinaryResponse(
            multipart,
            'multipart/related; type="application/dicom"; boundary="BOUND"',
        )

        response = self.client.get(
            f"/api/dcm4chee/results/{result['id']}/ecg/render.svg"
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("image/svg+xml", response.mimetype)
        self.assertIn(b"<svg", response.data)
