import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import joint_records


class JointRecordTests(unittest.TestCase):
    def test_new_records_do_not_overwrite_legacy_or_existing_operations(self):
        name = joint_records.next_record_name(
            ("joint_type", "operation_0001", "operation_0003", "other")
        )
        self.assertEqual(name, "operation_0002")

    def test_record_keeps_endpoint_and_operation_data(self):
        encoded = joint_records.encode_record(
            {
                "joint_type": "miter_trim",
                "endpoint_index": 1,
                "extension_mm": 12.5,
            }
        )
        record = joint_records.decode_record("operation_0007", encoded)
        self.assertIsNotNone(record)
        self.assertEqual(record.name, "operation_0007")
        self.assertEqual(record.payload["endpoint_index"], 1)
        self.assertEqual(record.payload["extension_mm"], 12.5)
        self.assertEqual(
            record.payload["schema_version"],
            joint_records.RECORD_SCHEMA_VERSION,
        )

    def test_legacy_attributes_are_ignored_as_records(self):
        self.assertIsNone(
            joint_records.decode_record("joint_type", "straight_trim")
        )


if __name__ == "__main__":
    unittest.main()
