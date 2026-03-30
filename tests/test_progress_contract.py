from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from gui.server import create_app


class ProgressContractTests(unittest.TestCase):
    def test_progress_returns_partial_when_coach_summary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Coach", target_exam="toefl")
            with patch("gui.api.progress.get_user_components", return_value=(user_model, profile)), patch(
                "gui.api.progress.build_coach_runtime",
                return_value={"ai_ready": False},
            ), patch(
                "gui.api.progress.CoachService.coach_summary",
                side_effect=RuntimeError("database is locked"),
            ):
                client = TestClient(create_app())
                response = client.get("/api/progress")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["partial"])
            self.assertIn("coach_summary_unavailable", body["warning_codes"])
            user_model._db.close()
            srs._db.close()

    def test_progress_returns_partial_when_runtime_fails(self) -> None:
        with patch("gui.api.progress.build_coach_runtime", side_effect=RuntimeError("bad runtime")), patch(
            "gui.api.progress.get_user_components",
            side_effect=RuntimeError("bad config"),
        ):
            client = TestClient(create_app())
            response = client.get("/api/progress")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["partial"])
        self.assertIn("runtime_status_unavailable", body["warning_codes"])
        self.assertIn("profile_load_failed", body["warning_codes"])

    def test_progress_migrates_legacy_coach_tables_before_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE coach_settings (
                    user_id TEXT PRIMARY KEY,
                    preferred_study_time TEXT
                );
                CREATE TABLE coach_daily_plan (
                    plan_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_date TEXT NOT NULL
                );
                CREATE TABLE coach_notification_log (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL
                );
                """
            )
            conn.commit()
            conn.close()

            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Coach", target_exam="toefl")
            with patch("gui.api.progress.get_user_components", return_value=(user_model, profile)), patch(
                "gui.api.progress.build_coach_runtime",
                return_value={"ai_ready": False},
            ):
                client = TestClient(create_app())
                response = client.get("/api/progress")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertFalse(body["partial"], body)
            self.assertNotIn("coach_summary_unavailable", body["warning_codes"])
            user_model._db.close()
            srs._db.close()


if __name__ == "__main__":
    unittest.main()
