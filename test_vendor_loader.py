"""Windows용 동봉 바이너리의 대상과 import 경로를 검증합니다."""
import base64
import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from vendor_loader import configure_vendor


class VendorTests(unittest.TestCase):
    def test_bundled_files_match_original_wheel_records(self):
        folder = Path(__file__).parent / "vendor" / "windows-cp311-amd64"
        for record in folder.glob("*.dist-info/RECORD"):
            with record.open(encoding="utf-8", newline="") as f:
                for name, checksum, size in csv.reader(f):
                    if not checksum:
                        continue
                    algorithm, expected = checksum.split("=", 1)
                    data = (folder / name).read_bytes()
                    actual = base64.urlsafe_b64encode(hashlib.new(algorithm, data).digest()).decode().rstrip("=")
                    self.assertEqual(actual, expected, name)
                    self.assertEqual(len(data), int(size), name)

    def test_windows_311_prefers_bundled_packages(self):
        with patch.object(sys, "platform", "win32"), \
             patch.object(sys, "version_info", (3, 11, 0)), \
             patch.object(sys, "maxsize", 2**63 - 1), \
             patch.object(sys, "path", sys.path.copy()), \
             patch("sysconfig.get_platform", return_value="win-amd64"):
            folder = configure_vendor()
            self.assertEqual(sys.path[0], str(folder))
            configure_vendor()
            self.assertEqual(sys.path.count(str(folder)), 1)
            for name in ("numpy", "pygame"):
                self.assertTrue((folder / name / "__init__.py").is_file())

    def test_incompatible_windows_rejected(self):
        for version, maximum, platform in (((3, 12, 0), 2**63-1, "win-amd64"),
                                           ((3, 11, 0), 2**31-1, "win32"),
                                           ((3, 11, 0), 2**63-1, "win-arm64")):
            with patch.object(sys, "platform", "win32"), \
                 patch.object(sys, "version_info", version), \
                 patch.object(sys, "maxsize", maximum), \
                 patch("sysconfig.get_platform", return_value=platform):
                with self.assertRaises(RuntimeError):
                    configure_vendor()

    def test_non_windows_keeps_existing_import_path(self):
        with patch.object(sys, "platform", "linux"):
            before = sys.path.copy()
            self.assertIsNone(configure_vendor())
            self.assertEqual(sys.path, before)

    def test_distributions_match_windows_311_and_preserve_licenses(self):
        root = Path(__file__).parent / "vendor"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["python"], "CPython 3.11")
        folder = root / "windows-cp311-amd64"
        for source in manifest["sources"]:
            name, version = source["package"], source["version"]
            info = folder / f"{name}-{version}.dist-info"
            self.assertIn("Tag: cp311-cp311-win_amd64", (info / "WHEEL").read_text())
            self.assertIn(f"Version: {version}", (info / "METADATA").read_text(encoding="utf-8"))
            self.assertEqual(len(source["sha256"]), 64)
            if name == "numpy":
                self.assertTrue((info / "LICENSE.txt").is_file())
            else:
                self.assertTrue((folder / "pygame" / "docs" / "generated" / "LGPL.txt").is_file())
            extensions = list((folder / name).rglob("*.pyd"))
            self.assertTrue(extensions)
            for binary in extensions:
                with binary.open("rb") as f:
                    self.assertEqual(f.read(2), b"MZ")
        self.assertTrue(list((folder / "numpy.libs").glob("*.dll")))
        self.assertTrue(list((folder / "pygame").glob("*.dll")))


if __name__ == "__main__":
    unittest.main()
