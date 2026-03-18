from __future__ import annotations

import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gui.api.license import build_license_status
from gui.api.practice import _start_speaking_practice, _start_writing_practice


class LicenseStatusContractTests(unittest.TestCase):
    def test_self_key_status_is_reported_as_effective_ai_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"backend": "deepseek", "data_dir": tmpdir}
            with patch("gui.api.license._load_env", lambda _path: None), patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "sk-test"},
                clear=True,
            ):
                status = build_license_status(cfg)

        self.assertFalse(status["active"])
        self.assertTrue(status["has_self_key"])
        self.assertEqual(status["self_key_backend"], "deepseek")
        self.assertEqual(status["ai_mode"], "self_key")
        self.assertTrue(status["ai_ready"])

    def test_cloud_record_without_cloud_ai_falls_back_to_self_key_mode(self) -> None:
        fake_record = SimpleNamespace(
            format="v2",
            key="ABCD-EF12-3456-7890",
            machine_id="machine-001",
            activate_ts=int(time.time()) - 60,
            days=30,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = {"backend": "deepseek", "data_dir": tmpdir}
            with patch("gui.api.license._load_env", lambda _path: None), patch.dict(
                os.environ,
                {"DEEPSEEK_API_KEY": "sk-fallback"},
                clear=True,
            ), patch("gui.api.license.read_license_record", return_value=fake_record), patch(
                "gui.api.license.verify_license_record",
                return_value={"valid": True, "days_left": 29},
            ), patch("gui.api.license.get_license_ai_config", return_value=None):
                status = build_license_status(cfg)

        self.assertTrue(status["active"])
        self.assertFalse(status["cloud_ai_ready"])
        self.assertEqual(status["ai_mode"], "self_key")
        self.assertTrue(status["ai_ready"])


class PracticeDelegationTests(unittest.TestCase):
    def test_writing_practice_uses_prompt_endpoint_contract(self) -> None:
        req = SimpleNamespace(
            exam="ielts",
            question_types=["task2"],
            practice_mode="targeted",
            time_limit=40,
        )
        profile = SimpleNamespace(user_id="u1")
        with patch(
            "gui.api.writing.get_prompt",
            return_value={"prompt": "Test prompt", "task_type": "task2", "exam": "ielts"},
        ) as mock_get_prompt:
            result = _start_writing_practice(req, None, None, None, None, profile)

        mock_get_prompt.assert_called_once_with(exam="ielts", task_type="task2")
        self.assertEqual(result["skill"], "writing")
        self.assertTrue(result["feedback_requires_ai"])
        self.assertEqual(result["prompt"], "Test prompt")

    def test_speaking_practice_uses_prompt_endpoint_contract(self) -> None:
        req = SimpleNamespace(
            exam="toefl",
            question_types=["listen_repeat"],
            practice_mode="targeted",
            time_limit=20,
        )
        profile = SimpleNamespace(user_id="u1")
        with patch(
            "gui.api.speaking.get_speaking_prompt",
            return_value={"prompt": "Speak now", "task_type": "listen_repeat", "exam": "toefl"},
        ) as mock_get_prompt:
            result = _start_speaking_practice(req, None, None, None, None, profile)

        mock_get_prompt.assert_called_once_with(exam="toefl", task_type="listen_repeat")
        self.assertEqual(result["skill"], "speaking")
        self.assertTrue(result["feedback_requires_ai"])
        self.assertEqual(result["prompt"], "Speak now")


if __name__ == "__main__":
    unittest.main()
