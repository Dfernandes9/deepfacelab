"""Read-only tests for the independent AERO LAB project manifest."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from aero_lab.project_loader import ManifestError, validate

class ProjectLoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "clip.mp4"
        self.video.write_bytes(b"synthetic test video placeholder")
        self.digest = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.manifest = {
            "schema_version": "0.1", "job_id": "job-001",
            "identities": [{"id": "subject-a", "head_swap_authorized": True,
                            "authorization_record": "consent-record-001"}],
            "assets": [{"id": "clip-a", "kind": "video", "path": "clip.mp4", "sha256": self.digest}],
            "source_identity_id": "subject-a", "target_asset_id": "clip-a",
            "target_use_authorized": True, "target_authorization_record": "video-license-001",
            "mode": "head", "pipeline_profile": "quality",
            "voice": {"enabled": False},
            "output": {"preserve_original": True, "synthetic_content_label": True},
        }

    def test_valid_project_does_not_modify_file(self):
        before = self.video.read_bytes()
        result = validate(self.manifest, self.root)
        self.assertEqual(result["status"], "VALIDATED_NOT_RENDERED")
        self.assertEqual(before, self.video.read_bytes())

    def test_multiple_independent_assets(self):
        other = self.root / "other.mov"
        other.write_bytes(b"second synthetic video placeholder")
        self.manifest["assets"].append({
            "id": "clip-b", "kind": "video", "path": "other.mov",
            "sha256": hashlib.sha256(other.read_bytes()).hexdigest()
        })
        self.manifest["identities"].append({
            "id": "subject-b", "head_swap_authorized": True,
            "authorization_record": "consent-record-002"})
        self.manifest["source_identity_id"] = "subject-b"
        self.manifest["target_asset_id"] = "clip-b"
        result = validate(self.manifest, self.root)
        self.assertEqual(result["identity_count"], 2)
        self.assertEqual(result["asset_count"], 2)

    def test_bad_hash(self):
        self.manifest["assets"][0]["sha256"] = "0" * 64
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

    def test_missing_consent(self):
        self.manifest["identities"][0]["head_swap_authorized"] = False
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

    def test_unimplemented_voice(self):
        self.manifest["voice"]["enabled"] = True
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

    def test_traversal(self):
        self.manifest["assets"][0]["path"] = "../clip.mp4"
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

    def test_duplicate_id(self):
        self.manifest["assets"].append(dict(self.manifest["assets"][0]))
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

    def test_output_protections_required(self):
        self.manifest["output"]["preserve_original"] = False
        with self.assertRaises(ManifestError):
            validate(self.manifest, self.root)

if __name__ == "__main__":
    unittest.main()
