from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

import gui.license as license_mod


class LicenseSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_worker_url = license_mod.WORKER_URL
        license_mod.WORKER_URL = "https://license.example.test"

    def tearDown(self) -> None:
        license_mod.WORKER_URL = self.original_worker_url

    def _make_record_text(self, days: int = 30, payload: str = "session.token.example") -> str:
        key = "ABCD-EF12-3456-7890"
        machine_id = "machine-001"
        activate_ts = int(time.time()) - 60
        payload_hex = license_mod.encrypt_local_payload(key, machine_id, payload)
        return license_mod.make_license_record(
            key=key,
            machine_id=machine_id,
            activate_ts=activate_ts,
            days=days,
            payload_kind="proxy_token",
            payload_hex=payload_hex,
        )

    def test_v2_record_detects_days_tampering(self) -> None:
        original = self._make_record_text(days=30)
        record = license_mod.parse_license_record(original)
        self.assertTrue(license_mod.verify_license_record(record)["valid"])

        parts = original.split("|")
        parts[4] = "3650"
        tampered = "|".join(parts)
        tampered_record = license_mod.parse_license_record(tampered)
        result = license_mod.verify_license_record(tampered_record)
        self.assertFalse(result["valid"])
        self.assertIn("篡改", result["error"])

    def test_v2_record_returns_proxy_config(self) -> None:
        record_text = self._make_record_text(payload="session.token.example")
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "license.key").write_text(record_text, encoding="utf-8")
            cfg = license_mod.get_license_ai_config(tmpdir)

        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(cfg["mode"], "proxy_token")
        self.assertEqual(cfg["api_key"], "session.token.example")
        self.assertEqual(cfg["base_url"], "https://license.example.test/v1")


if __name__ == "__main__":
    unittest.main()
