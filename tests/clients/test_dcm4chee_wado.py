import socket
import unittest
import urllib.error
from unittest.mock import patch

from backend.clients.dcm4chee_wado import (
    WadoRsMediaTypeError,
    WadoRsMultipartError,
    WadoRsSizeError,
    WadoRsTimeoutError,
    WadoRsUpstreamHttpError,
    retrieve_dicom_instance,
)


class _Response:
    def __init__(self, body: bytes, content_type: str, *, content_length: str | None = None):
        self._body = body
        self._offset = 0
        self.read_sizes = []
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class Dcm4cheeWadoTest(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "dicomweb": {"wadoRsUrl": "https://pacs.test/archive/rs"},
            "security": {"authMode": "none", "tlsEnabled": False},
        }
        self.uids = {
            "study_instance_uid": "1.2.3",
            "series_instance_uid": "1.2.4",
            "sop_instance_uid": "1.2.5",
        }

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_retrieves_bare_dicom_from_uid_only_url(self, open_secured):
        response = _Response(b"DICM", "application/dicom")
        open_secured.return_value = response

        result = retrieve_dicom_instance(self.profile, **self.uids, max_bytes=8)

        self.assertEqual(b"DICM", result)
        request = open_secured.call_args.args[0]
        self.assertEqual(
            "https://pacs.test/archive/rs/studies/1.2.3/series/1.2.4/instances/1.2.5",
            request.full_url,
        )
        self.assertIn("application/dicom", request.get_header("Accept"))
        self.assertEqual([9, 5], response.read_sizes)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_unwraps_one_dicom_multipart_part(self, open_secured):
        body = (
            b"--BOUND\r\nContent-Type: application/dicom\r\n"
            b"Content-Transfer-Encoding: binary\r\n\r\nDICM\r\n--BOUND--\r\n"
        )
        open_secured.return_value = _Response(
            body, 'multipart/related; type="application/dicom"; boundary="BOUND"'
        )

        self.assertEqual(
            b"DICM", retrieve_dicom_instance(self.profile, **self.uids)
        )

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_rejects_multiple_multipart_parts(self, open_secured):
        body = (
            b"--B\r\nContent-Type: application/dicom\r\n\r\none\r\n"
            b"--B\r\nContent-Type: application/dicom\r\n\r\ntwo\r\n--B--\r\n"
        )
        open_secured.return_value = _Response(body, "multipart/related; boundary=B")

        with self.assertRaises(WadoRsMultipartError):
            retrieve_dicom_instance(self.profile, **self.uids)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_rejects_non_dicom_media(self, open_secured):
        open_secured.return_value = _Response(b"{}", "application/json")

        with self.assertRaises(WadoRsMediaTypeError):
            retrieve_dicom_instance(self.profile, **self.uids)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_rejects_empty_bare_and_multipart_payloads(self, open_secured):
        open_secured.return_value = _Response(b"", "application/dicom")
        with self.assertRaises(WadoRsMultipartError):
            retrieve_dicom_instance(self.profile, **self.uids)

        body = b"--B\r\nContent-Type: application/dicom\r\n\r\n\r\n--B--\r\n"
        open_secured.return_value = _Response(
            body, 'multipart/related; type="application/dicom"; boundary=B'
        )
        with self.assertRaises(WadoRsMultipartError):
            retrieve_dicom_instance(self.profile, **self.uids)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_rejects_oversized_stream_incrementally(self, open_secured):
        open_secured.return_value = _Response(b"12345", "application/dicom")

        with self.assertRaises(WadoRsSizeError):
            retrieve_dicom_instance(self.profile, **self.uids, max_bytes=4)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_rejects_oversized_declared_length_before_reading(self, open_secured):
        response = _Response(b"", "application/dicom", content_length="100")
        open_secured.return_value = response

        with self.assertRaises(WadoRsSizeError):
            retrieve_dicom_instance(self.profile, **self.uids, max_bytes=4)
        self.assertEqual([], response.read_sizes)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_maps_timeout_and_http_errors(self, open_secured):
        open_secured.side_effect = socket.timeout()
        with self.assertRaises(WadoRsTimeoutError):
            retrieve_dicom_instance(self.profile, **self.uids)

        open_secured.side_effect = urllib.error.HTTPError(
            "https://pacs.test", 503, "down", {}, None
        )
        with self.assertRaises(WadoRsUpstreamHttpError) as raised:
            retrieve_dicom_instance(self.profile, **self.uids)
        self.assertEqual(503, raised.exception.status)

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_invalid_uid_never_opens_network(self, open_secured):
        with self.assertRaises(ValueError):
            retrieve_dicom_instance(
                self.profile,
                study_instance_uid="../../admin",
                series_instance_uid="1.2.4",
                sop_instance_uid="1.2.5",
            )
        open_secured.assert_not_called()

    @patch("backend.clients.dcm4chee_wado.open_secured")
    def test_uses_profile_timeout_when_present(self, open_secured):
        profile = {**self.profile, "timeoutSeconds": 7}
        open_secured.return_value = _Response(b"DICM", "application/dicom")

        retrieve_dicom_instance(profile, **self.uids)

        self.assertEqual(7.0, open_secured.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
