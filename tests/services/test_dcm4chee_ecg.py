from __future__ import annotations

from io import BytesIO
from struct import pack
import unittest

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from backend.domain.ecg_waveform import (
    CANONICAL_LEADS,
    SCPECG_LEAD_CODES,
    TWELVE_LEAD_ECG_WAVEFORM_STORAGE,
)
from backend.services.dcm4chee_ecg import (
    Dcm4cheeEcgConflictError,
    Dcm4cheeEcgInvalidError,
    Dcm4cheeEcgNotFoundError,
    Dcm4cheeEcgService,
    Dcm4cheeEcgUnsupportedError,
    Dcm4cheeEcgUpstreamError,
    RetrieveInstanceIdentifiers,
)
from backend.clients.dcm4chee_wado import WadoRsUpstreamHttpError


def dicom_bytes(*, sop_class=TWELVE_LEAD_ECG_WAVEFORM_STORAGE, waveform=True):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = sop_class
    ds.SOPInstanceUID = "1.2.3.4"
    ds.Modality = "ECG"
    ds.Manufacturer = "Safe Device"
    ds.PatientName = "MUST^NOT^LEAK"
    if waveform:
        item = Dataset()
        item.NumberOfWaveformChannels = 12
        item.NumberOfWaveformSamples = 2
        item.SamplingFrequency = 500
        item.WaveformBitsAllocated = 16
        item.WaveformSampleInterpretation = "SS"
        item.WaveformData = pack("<24h", *range(24))
        definitions = []
        by_lead = {lead: code for code, lead in SCPECG_LEAD_CODES.items()}
        for lead in CANONICAL_LEADS:
            definition = Dataset()
            definition.ChannelSensitivity = 1
            source = Dataset()
            source.CodingSchemeDesignator = "SCPECG"
            source.CodeValue = by_lead[lead]
            definition.ChannelSourceSequence = [source]
            unit = Dataset()
            unit.CodingSchemeDesignator = "UCUM"
            unit.CodeValue = "mV"
            definition.ChannelSensitivityUnitsSequence = [unit]
            definitions.append(definition)
        item.ChannelDefinitionSequence = definitions
        ds.WaveformSequence = [item]
    output = BytesIO()
    ds.save_as(output, enforce_file_format=True)
    return output.getvalue()


class TypedTransportError(RuntimeError):
    def __init__(self, *, http_status=None, category=""):
        self.http_status = http_status
        self.category = category


class Dcm4cheeEcgServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.result = {
            "id": 7,
            "profileName": "archive",
            "studyInstanceUid": " 1.2.1 ",
            "seriesInstanceUid": "1.2.2",
            "sopInstanceUid": "1.2.3",
            "modality": "ECG",
            "instanceDateTime": "20260728103000",
            "patientId": "SECRET",
            "instanceRetrieveUrl": "http://secret/",
            "rawMetadata": {"PatientName": "SECRET"},
        }

    def service(self, payload=None, result=None, error=None):
        def retrieve(profile, identifiers):
            self.calls.append((profile, identifiers))
            if error:
                raise error
            return payload if payload is not None else dicom_bytes()

        return Dcm4cheeEcgService(
            result_getter=lambda result_id: self.result if result is None else result,
            profile_getter=lambda name: {"name": name, "secret": "credential"},
            retriever=retrieve,
        )

    def test_metadata_uses_normalized_identifiers_and_safe_projection(self):
        metadata = self.service().metadata(7)
        self.assertEqual(
            RetrieveInstanceIdentifiers("1.2.1", "1.2.2", "1.2.3"),
            self.calls[0][1],
        )
        self.assertEqual(12, metadata["waveform"]["leadCount"])
        self.assertEqual(
            TWELVE_LEAD_ECG_WAVEFORM_STORAGE,
            metadata["waveform"]["sopClassUid"],
        )
        self.assertEqual("Safe Device", metadata["displayMetadata"]["Manufacturer"])
        rendered = repr(metadata)
        for forbidden in ("SECRET", "http://", "PatientName", "credential"):
            self.assertNotIn(forbidden, rendered)

    def test_unknown_and_incomplete_results_do_not_retrieve(self):
        service = Dcm4cheeEcgService(
            result_getter=lambda _: (_ for _ in ()).throw(KeyError(9)),
            profile_getter=lambda _: {},
            retriever=lambda *_: self.fail("retrieval must not run"),
        )
        with self.assertRaises(Dcm4cheeEcgNotFoundError):
            service.metadata(9)
        with self.assertRaises(Dcm4cheeEcgConflictError):
            self.service(result={**self.result, "seriesInstanceUid": ""}).metadata(7)
        self.assertEqual([], self.calls)

    def test_unsupported_sop_and_invalid_dicom_are_typed(self):
        with self.assertRaises(Dcm4cheeEcgUnsupportedError):
            self.service(payload=dicom_bytes(sop_class="1.2.3.999")).metadata(7)
        with self.assertRaises(Dcm4cheeEcgInvalidError):
            self.service(payload=b"not dicom").metadata(7)
        with self.assertRaises(Dcm4cheeEcgInvalidError):
            self.service(payload=dicom_bytes(waveform=False)).metadata(7)

    def test_typed_transport_errors_are_safely_mapped(self):
        cases = (
            (TypedTransportError(http_status=415), Dcm4cheeEcgUnsupportedError),
            (TypedTransportError(category="multipart"), Dcm4cheeEcgInvalidError),
            (TypedTransportError(category="timeout"), Dcm4cheeEcgUpstreamError),
            (WadoRsUpstreamHttpError(415), Dcm4cheeEcgUpstreamError),
        )
        for error, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(expected):
                    self.service(error=error).metadata(7)

    def test_valid_instance_renders_svg(self):
        rendered = self.service().render(7)
        self.assertEqual("image/svg+xml", rendered.media_type)
        self.assertIn(b"<svg", rendered.svg_bytes)


if __name__ == "__main__":
    unittest.main()
