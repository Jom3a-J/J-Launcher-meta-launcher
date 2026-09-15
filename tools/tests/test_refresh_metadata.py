import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refresh_metadata import refresh  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class RefreshMetadataTest(unittest.TestCase):
    def test_refresh_preserves_tools_and_applies_j_owned_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            destination = root / "destination"
            upstream.mkdir()
            destination.mkdir()

            legacy_metadata = {
                "uid": "net.example",
                "version": "1.0",
                "releaseTime": "2020-01-01T00:00:00+00:00",
            }
            write_json(upstream / "net.example" / "1.0.json", legacy_metadata)
            write_json(upstream / "net.example" / "index.json", {
                "formatVersion": 1,
                "name": "Example",
                "uid": "net.example",
                "versions": [{
                    "version": "1.0",
                    "releaseTime": legacy_metadata["releaseTime"],
                    "sha256": "legacy",
                }],
            })
            write_json(upstream / "index.json", {
                "formatVersion": 1,
                "packages": [{
                    "name": "Example",
                    "uid": "net.example",
                    "sha256": "legacy-package",
                }],
            })
            (upstream / ".nojekyll").write_text("", encoding="utf-8")
            (destination / "tools").mkdir()
            (destination / "tools" / "keep.txt").write_text("keep", encoding="utf-8")

            override = {
                "formatVersion": 1,
                "uid": "net.example",
                "version": "2.0",
                "releaseTime": "2026-08-18T00:00:00+00:00",
                "type": "release",
                "recommended": True,
            }
            write_json(destination / "overrides" / "net.example" / "2.0.json", override)

            self.assertEqual(refresh(upstream, destination), 1)
            self.assertTrue((destination / "tools" / "keep.txt").is_file())
            published = destination / "net.example" / "2.0.json"
            self.assertEqual(json.loads(published.read_text(encoding="utf-8")), override)

            package_index = json.loads(
                (destination / "net.example" / "index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(package_index["versions"][0]["version"], "2.0")
            self.assertEqual(
                package_index["versions"][0]["sha256"],
                hashlib.sha256(published.read_bytes()).hexdigest(),
            )
            root_index = json.loads((destination / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(
                root_index["packages"][0]["sha256"],
                hashlib.sha256(
                    (destination / "net.example" / "index.json").read_bytes()
                ).hexdigest(),
            )

    def test_rejects_override_with_mismatched_uid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            destination = root / "destination"
            upstream.mkdir()
            destination.mkdir()
            write_json(upstream / "net.example" / "index.json", {
                "versions": [],
            })
            write_json(upstream / "index.json", {
                "packages": [{"uid": "net.example", "sha256": "unused"}],
            })
            write_json(destination / "overrides" / "net.example" / "2.0.json", {
                "uid": "net.other",
                "version": "2.0",
                "releaseTime": "2026-08-18T00:00:00+00:00",
            })
            with self.assertRaisesRegex(ValueError, "uid does not match"):
                refresh(upstream, destination)


if __name__ == "__main__":
    unittest.main()
