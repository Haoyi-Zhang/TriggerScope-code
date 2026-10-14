"""Regression checks for consumed-byte limits on bounded local text inputs."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import androlog_adapter as adapter


class ConsumedBytes(unittest.TestCase):
    def test_session_reports_consumed_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.txt"
            payload = b"ANDROLOG METHOD=owned\n"
            path.write_bytes(payload)
            descriptor = os.open(path, os.O_RDONLY)
            with patch.object(adapter, "_open_regular_binary", return_value=(descriptor, 0)):
                trace, size = adapter._parse_session_file_with_size(
                    path, "ANDROLOG", {"METHOD=owned": 0}, max_bytes=64
                )
            self.assertEqual(trace, (0,))
            self.assertEqual(size, len(payload))

    def test_session_consumption_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.txt"
            path.write_bytes(b"unrelated\n")
            descriptor = os.open(path, os.O_RDONLY)
            with patch.object(adapter, "_open_regular_binary", return_value=(descriptor, 0)):
                with self.assertRaises(adapter.InvalidLog):
                    adapter._parse_session_file_with_size(path, "ANDROLOG", {}, max_bytes=3)

    def test_config_consumption_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_bytes(b'{"a": 1}')
            descriptor = os.open(path, os.O_RDONLY)
            with patch.object(adapter, "MAX_CONFIG_BYTES", 3), patch.object(
                adapter, "_open_regular_binary", return_value=(descriptor, 0)
            ):
                with self.assertRaises(adapter.InvalidLog):
                    adapter._load_json_object(path, "configuration")

    def test_fixed_regular_inputs_preserve_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.txt"
            payload = b"ANDROLOG METHOD=owned\r\nANDROLOG METHOD=owned\r\n"
            path.write_bytes(payload)
            trace, size = adapter._parse_session_file_with_size(
                path, "ANDROLOG", {"METHOD=owned": 0}, max_bytes=len(payload)
            )
            self.assertEqual(trace, (0, 0))
            self.assertEqual(size, len(payload))
            path = Path(directory) / "config.json"
            path.write_bytes(b'{"a": 1}')
            self.assertEqual(adapter._load_json_object(path, "configuration"), {"a": 1})

    def test_duplicate_config_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe-map.json"
            for payload in (b'{"METHOD=owned":0,"METHOD=owned":1}',
                            b'{"nested":{"x":0,"x":1}}'):
                with self.subTest(payload=payload):
                    path.write_bytes(payload)
                    with self.assertRaisesRegex(adapter.InvalidLog, "duplicate JSON key"):
                        adapter._load_json_object(path, "probe map")

    def test_distinct_probe_map_keys_remain_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe-map.json"
            path.write_bytes(b'{"METHOD=first":0,"METHOD=second":1}')
            mapping = adapter._load_json_object(path, "probe map")
            self.assertEqual(mapping, {"METHOD=first": 0, "METHOD=second": 1})
            adapter._validate_probe_map(mapping, 2)


if __name__ == "__main__":
    unittest.main()
