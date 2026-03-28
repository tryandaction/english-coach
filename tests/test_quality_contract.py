from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gui.cloud_license_defaults as cloud_defaults
import gui.deps as deps_mod
from gui.api.setup import _normalize_supplied_data_dir
from gui.api.license import build_license_status
from gui.api.practice import _start_speaking_practice, _start_writing_practice
from utils import private_paths

ROOT = Path(__file__).resolve().parents[1]


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


class PackagingContractTests(unittest.TestCase):
    def test_gitignore_protects_private_and_local_runtime_files(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "data/",
            "config.yaml",
            ".env",
            "releases/",
            "/private_commercial/**",
            "!/private_commercial/README.md",
        ):
            self.assertIn(pattern, text)

    def test_cloud_license_source_defaults_are_empty(self) -> None:
        self.assertEqual(cloud_defaults.WORKER_URL, "")
        self.assertEqual(cloud_defaults.CLIENT_TOKEN, "")

    def test_private_commercial_candidates_are_preferred(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            activation_candidates = private_paths.cloud_activation_config_candidates()
            seller_candidates = private_paths.seller_config_candidates()
        self.assertTrue(str(activation_candidates[0]).replace("\\", "/").endswith("private_commercial/cloud_activation_config.json"))
        self.assertTrue(str(seller_candidates[0]).replace("\\", "/").endswith("private_commercial/seller_cloud_config.json"))
        self.assertFalse(any(str(path).replace("\\", "/").endswith("releases/cloud_activation_config.json") for path in activation_candidates))

    def test_opensource_spec_has_no_machine_specific_site_packages_path(self) -> None:
        spec_text = (ROOT / "release_tooling" / "specs" / "english_coach_opensource.spec").read_text(encoding="utf-8")
        lowered = spec_text.lower()
        self.assertNotIn("appdata\\roaming\\python", lowered)
        self.assertNotIn("site-packages", lowered)

    def test_cloud_spec_has_no_machine_specific_site_packages_path(self) -> None:
        spec_text = (ROOT / "release_tooling" / "specs" / "english_coach_cloud.spec").read_text(encoding="utf-8")
        lowered = spec_text.lower()
        self.assertNotIn("appdata\\roaming\\python", lowered)
        self.assertNotIn("site-packages", lowered)

    def test_installers_write_valid_empty_yaml_defaults(self) -> None:
        for path in (
            ROOT / "release_tooling" / "installers" / "installer_cloud.iss",
            ROOT / "release_tooling" / "installers" / "installer_opensource.iss",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn('backend: ""', text, path.name)
            self.assertIn('api_key: ""', text, path.name)
            self.assertIn('target_exam_date: ""', text, path.name)

    def test_installers_include_previous_version_removal_flow(self) -> None:
        for path in (
            ROOT / "release_tooling" / "installers" / "installer_cloud.iss",
            ROOT / "release_tooling" / "installers" / "installer_opensource.iss",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("PrepareToInstall", text, path.name)
            self.assertIn("UninstallPreviousInstall", text, path.name)
            self.assertIn("taskkill.exe", text, path.name)
            self.assertIn("CreateInputOptionPage", text, path.name)
            self.assertIn("ShouldReplaceExistingInstall", text, path.name)
            self.assertIn("NormalizeSilentUninstallParams", text, path.name)
            self.assertIn("/NOCANCEL", text, path.name)
            self.assertNotIn("MsgBox(Prompt", text, path.name)

    def test_installers_use_streamlined_wizard_pages(self) -> None:
        for path in (
            ROOT / "release_tooling" / "installers" / "installer_cloud.iss",
            ROOT / "release_tooling" / "installers" / "installer_opensource.iss",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("DisableWelcomePage=yes", text, path.name)
            self.assertIn("DisableDirPage=yes", text, path.name)
            self.assertNotIn('Name: "desktopicon"', text, path.name)

    def test_frozen_config_reset_targets_temp_smoke_data_dir(self) -> None:
        cfg = {"data_dir": r"C:\Users\me\AppData\Local\Temp\english_coach_release_smoke_abcd\smoke-data"}
        self.assertTrue(deps_mod._should_reset_frozen_user_config(cfg))

    def test_frozen_config_reset_allows_smoke_data_dir_when_override_enabled(self) -> None:
        cfg = {"data_dir": r"C:\Users\me\AppData\Local\Temp\english_coach_release_smoke_abcd\smoke-data"}
        with patch.dict(os.environ, {"ENGLISH_COACH_ALLOW_DEV_MACHINE_PATH": "1"}, clear=False):
            self.assertFalse(deps_mod._should_reset_frozen_user_config(cfg))

    def test_frozen_config_reset_does_not_block_user_chosen_absolute_dir(self) -> None:
        cfg = {"data_dir": r"D:\EnglishCoachData"}
        self.assertFalse(deps_mod._should_reset_frozen_user_config(cfg))

    def test_frozen_config_allows_user_chosen_absolute_data_dir(self) -> None:
        cfg = {"data_dir": r"C:\Users\me\Documents\EnglishCoachData"}
        self.assertFalse(deps_mod._should_reset_frozen_user_config(cfg))

    def test_frozen_config_parse_failure_is_reset_to_default_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.yaml"
            cfg_path.write_text(
                "backend: '\n"
                "api_key: '\n"
                "data_dir: data\n"
                "history_retention_days: 30\n"
                "user:\n"
                "  name: '\n"
                "  target_exam: '\n"
                "  target_exam_date: '\n",
                encoding="utf-8",
            )
            original_path = deps_mod._CONFIG_PATH
            original_frozen = getattr(deps_mod.sys, "frozen", False)
            try:
                deps_mod._CONFIG_PATH = cfg_path
                setattr(deps_mod.sys, "frozen", True)
                changed = deps_mod.sanitize_frozen_user_config()
                loaded = deps_mod.load_config()
            finally:
                deps_mod._CONFIG_PATH = original_path
                setattr(deps_mod.sys, "frozen", original_frozen)

        self.assertTrue(changed)
        self.assertEqual(loaded["data_dir"], "data")
        self.assertEqual(loaded["user"]["target_exam_date"], "")

    def test_setup_accepts_user_db_file_path_and_normalizes_to_parent_dir(self) -> None:
        normalized = _normalize_supplied_data_dir(r'C:\Users\me\AppData\Roaming\EnglishCoach\data\user.db')
        self.assertEqual(str(normalized), r'C:\Users\me\AppData\Roaming\EnglishCoach\data')


if __name__ == "__main__":
    unittest.main()
