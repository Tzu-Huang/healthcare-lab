import struct
import unittest
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from backend.domain.ecg_waveform import (
    LeadLayoutError,
    MalformedWaveformError,
    MissingWaveformError,
    UnsupportedSOPClassError,
    UnsupportedSampleError,
    UnsupportedUnitError,
    parse_ecg_waveform,
)


TWELVE_LEAD_ECG_STORAGE = "1.2.840.10008.5.1.4.1.1.9.1.1"
GENERAL_ECG_STORAGE = "1.2.840.10008.5.1.4.1.1.9.1.2"
CANONICAL_LEADS = (
    ("I", "5.6.3-9-1"),
    ("II", "5.6.3-9-2"),
    ("III", "5.6.3-9-61"),
    ("aVR", "5.6.3-9-62"),
    ("aVL", "5.6.3-9-63"),
    ("aVF", "5.6.3-9-64"),
    ("V1", "5.6.3-9-3"),
    ("V2", "5.6.3-9-4"),
    ("V3", "5.6.3-9-5"),
    ("V4", "5.6.3-9-6"),
    ("V5", "5.6.3-9-7"),
    ("V6", "5.6.3-9-8"),
)
FIXTURE_FIRST_TIMEPOINT_MV = (
    1.115,
    0.500,
    -0.615,
    -0.807,
    0.865,
    -0.057,
    2.975,
    2.702,
    3.194,
    3.161,
    3.266,
    2.794,
)


def _coded_item(code_value, scheme="SCPECG", meaning=""):
    item = Dataset()
    item.CodeValue = code_value
    item.CodingSchemeDesignator = scheme
    item.CodeMeaning = meaning
    return item


def _channel(lead, code, *, sensitivity=1.0, correction=1.0, baseline=0.0, unit="uV"):
    channel = Dataset()
    channel.ChannelSourceSequence = Sequence([_coded_item(code, meaning=lead)])
    channel.ChannelSensitivity = sensitivity
    channel.ChannelSensitivityCorrectionFactor = correction
    channel.ChannelBaseline = baseline
    channel.ChannelSensitivityUnitsSequence = Sequence(
        [_coded_item(unit, scheme="UCUM", meaning=unit)]
    )
    return channel


def make_dataset(
    sop_class_uid=TWELVE_LEAD_ECG_STORAGE,
    *,
    leads=CANONICAL_LEADS,
    samples_by_channel=None,
    sampling_frequency=500.0,
):
    if samples_by_channel is None:
        samples_by_channel = [[index + 1, -(index + 1)] for index in range(len(leads))]

    dataset = Dataset()
    dataset.SOPClassUID = sop_class_uid
    dataset.SOPInstanceUID = "1.2.826.0.1.3680043.10.999.1"
    dataset.Modality = "ECG"
    dataset.Manufacturer = "Fixture Instruments"
    dataset.ManufacturerModelName = "Constructed ECG"
    dataset.PatientName = "Secret^Patient"
    dataset.PatientID = "MRN-SECRET"
    dataset.AccessionNumber = "ACC-SECRET"
    dataset.StudyDescription = "Sensitive study description"

    waveform = Dataset()
    waveform.NumberOfWaveformChannels = len(leads)
    waveform.NumberOfWaveformSamples = len(samples_by_channel[0])
    waveform.SamplingFrequency = sampling_frequency
    waveform.WaveformBitsAllocated = 16
    waveform.WaveformSampleInterpretation = "SS"
    waveform.ChannelDefinitionSequence = Sequence(
        [_channel(lead, code) for lead, code in leads]
    )
    multiplexed = [
        samples_by_channel[channel_index][sample_index]
        for sample_index in range(waveform.NumberOfWaveformSamples)
        for channel_index in range(waveform.NumberOfWaveformChannels)
    ]
    waveform.WaveformData = struct.pack(f"<{len(multiplexed)}h", *multiplexed)
    dataset.WaveformSequence = Sequence([waveform])
    return dataset


class EcgWaveformConstructedDatasetTest(unittest.TestCase):
    def test_both_supported_sop_classes_return_the_same_normalized_model(self):
        models = [
            parse_ecg_waveform(make_dataset(sop_class_uid))
            for sop_class_uid in (TWELVE_LEAD_ECG_STORAGE, GENERAL_ECG_STORAGE)
        ]

        self.assertIs(type(models[0]), type(models[1]))
        self.assertEqual([model.sop_class_uid for model in models], [
            TWELVE_LEAD_ECG_STORAGE,
            GENERAL_ECG_STORAGE,
        ])

    def test_shuffled_channels_are_calibrated_and_returned_in_canonical_order(self):
        shuffled = CANONICAL_LEADS[6:] + CANONICAL_LEADS[:6]
        raw = [[index + 1, index + 101] for index in range(12)]
        dataset = make_dataset(leads=shuffled, samples_by_channel=raw)
        for channel in dataset.WaveformSequence[0].ChannelDefinitionSequence:
            channel.ChannelSensitivity = 2.0
            channel.ChannelSensitivityCorrectionFactor = 0.5
            channel.ChannelBaseline = 100.0

        model = parse_ecg_waveform(dataset)

        self.assertEqual(tuple(channel.lead for channel in model.channels), tuple(
            lead for lead, _ in CANONICAL_LEADS
        ))
        self.assertEqual(tuple(channel.source_code for channel in model.channels), tuple(
            code for _, code in CANONICAL_LEADS
        ))
        # Lead I is source position six: (7 * 2 * .5 + 100) uV == .107 mV.
        self.assertAlmostEqual(model.channels[0].samples[0], 0.107)
        self.assertAlmostEqual(model.channels[0].samples[1], 0.207)
        self.assertEqual(model.unit, "mV")
        self.assertEqual(model.sampling_frequency_hz, 500.0)
        self.assertEqual(model.duration_seconds, 2 / 500.0)

    def test_millivolt_input_preserves_calibrated_offset_without_centering(self):
        dataset = make_dataset(samples_by_channel=[[2, 4] for _ in range(12)])
        channel = dataset.WaveformSequence[0].ChannelDefinitionSequence[0]
        channel.ChannelSensitivity = 3.0
        channel.ChannelSensitivityCorrectionFactor = 2.0
        channel.ChannelBaseline = 5.0
        channel.ChannelSensitivityUnitsSequence[0].CodeValue = "mV"

        model = parse_ecg_waveform(dataset)

        self.assertEqual(model.channels[0].samples, (17.0, 29.0))

    def test_metadata_is_allowlisted_and_excludes_identifying_attributes(self):
        model = parse_ecg_waveform(make_dataset())

        self.assertEqual(model.metadata["Modality"], "ECG")
        self.assertEqual(model.metadata["Manufacturer"], "Fixture Instruments")
        self.assertEqual(model.metadata["ManufacturerModelName"], "Constructed ECG")
        self.assertNotIn("PatientName", model.metadata)
        self.assertNotIn("PatientID", model.metadata)
        self.assertNotIn("AccessionNumber", model.metadata)
        self.assertNotIn("StudyDescription", model.metadata)
        self.assertFalse(
            {"Secret^Patient", "MRN-SECRET", "ACC-SECRET", "Sensitive study description"}
            & set(model.metadata.values())
        )


class EcgWaveformTypedErrorTest(unittest.TestCase):
    def test_rejects_unsupported_sop_class(self):
        with self.assertRaises(UnsupportedSOPClassError):
            parse_ecg_waveform(make_dataset("1.2.840.10008.5.1.4.1.1.2"))

    def test_rejects_missing_and_empty_waveform_sequences(self):
        missing = make_dataset()
        del missing.WaveformSequence
        empty = make_dataset()
        empty.WaveformSequence = Sequence([])

        for dataset in (missing, empty):
            with self.subTest(has_sequence="WaveformSequence" in dataset):
                with self.assertRaises(MissingWaveformError):
                    parse_ecg_waveform(dataset)

    def test_rejects_inconsistent_waveform_data_length(self):
        dataset = make_dataset()
        dataset.WaveformSequence[0].WaveformData = b"\x00\x01"

        with self.assertRaises(MalformedWaveformError):
            parse_ecg_waveform(dataset)

    def test_rejects_unsupported_sample_interpretation(self):
        dataset = make_dataset()
        dataset.WaveformSequence[0].WaveformSampleInterpretation = "US"

        with self.assertRaises(UnsupportedSampleError):
            parse_ecg_waveform(dataset)

    def test_rejects_unknown_or_missing_voltage_unit(self):
        unknown = make_dataset()
        unknown.WaveformSequence[0].ChannelDefinitionSequence[
            0
        ].ChannelSensitivityUnitsSequence[0].CodeValue = "nV"
        missing = make_dataset()
        del missing.WaveformSequence[0].ChannelDefinitionSequence[
            0
        ].ChannelSensitivityUnitsSequence

        for dataset in (unknown, missing):
            with self.subTest(missing_unit=not hasattr(
                dataset.WaveformSequence[0].ChannelDefinitionSequence[0],
                "ChannelSensitivityUnitsSequence",
            )):
                with self.assertRaises(UnsupportedUnitError):
                    parse_ecg_waveform(dataset)

    def test_rejects_missing_duplicate_and_unknown_leads(self):
        layouts = {
            "missing": CANONICAL_LEADS[:-1],
            "duplicate": CANONICAL_LEADS[:-1] + (CANONICAL_LEADS[0],),
            "unknown": CANONICAL_LEADS[:-1] + (("X", "unknown"),),
        }

        for name, leads in layouts.items():
            with self.subTest(layout=name):
                with self.assertRaises(LeadLayoutError):
                    parse_ecg_waveform(make_dataset(leads=leads))


class PhilipsEcgFixtureCompatibilityTest(unittest.TestCase):
    FIXTURE_DIR = Path(__file__).resolve().parents[2] / "dicom-formats"
    FIXTURES = ("12lead_ecg_waveform.dcm", "general_ecg_waveform.dcm")

    def test_optional_philips_fixtures_have_expected_normalized_shape(self):
        missing = [name for name in self.FIXTURES if not (self.FIXTURE_DIR / name).is_file()]
        if missing:
            self.skipTest(
                "local-only Philips DICOM fixtures are unavailable: " + ", ".join(missing)
            )

        for name in self.FIXTURES:
            with self.subTest(fixture=name):
                dataset = pydicom.dcmread(self.FIXTURE_DIR / name)
                model = parse_ecg_waveform(dataset)

                self.assertEqual(len(model.channels), 12)
                self.assertTrue(all(len(channel.samples) == 10_000 for channel in model.channels))
                self.assertEqual(model.sampling_frequency_hz, 1_000.0)
                self.assertEqual(model.duration_seconds, 10.0)
                self.assertEqual(model.unit, "mV")
                self.assertEqual(
                    tuple(channel.lead for channel in model.channels),
                    tuple(lead for lead, _ in CANONICAL_LEADS),
                )
                self.assertEqual(
                    tuple(channel.samples[0] for channel in model.channels),
                    FIXTURE_FIRST_TIMEPOINT_MV,
                )


if __name__ == "__main__":
    unittest.main()
