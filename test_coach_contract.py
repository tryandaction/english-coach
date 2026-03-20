from __future__ import annotations

import asyncio
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from core.coach.service import CoachNotificationDispatcher, CoachService
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from core.vocab.catalog import should_include_builtin_book, sync_builtin_vocabulary
from gui.api import listening as listening_api
from gui.api.listening import _sessions as listening_sessions, start_listening
from gui.api.speaking import _rotated_choice
from gui.api.writing import _pick_task_type as _pick_writing_task_type, _rotate_prompt_list
from gui.api.speaking import _pick_task_type as _pick_speaking_task_type
from gui.server import create_app


class CoachServiceContractTests(unittest.TestCase):
    def _build_service(self, runtime: dict | None = None):
        tmpdir = tempfile.TemporaryDirectory()
        db_path = f"{tmpdir.name}/user.db"
        srs = SM2Engine(db_path)
        user_model = UserModel(db_path)
        profile = user_model.create_profile(name="Alice", target_exam="toefl")
        service = CoachService(user_model, profile, runtime or {})
        return tmpdir, srs, user_model, profile, service

    def test_due_vocab_is_first_daily_task(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service({"ai_ready": True})
        try:
            user_model._db.execute(
                """INSERT INTO srs_cards
                   (card_id, user_id, word_id, due_date)
                   VALUES (?,?,?,?)""",
                (uuid.uuid4().hex[:16], profile.user_id, "word-1", date.today().isoformat()),
            )
            user_model._db.commit()
            plan = service.sync_daily_plan()
            self.assertGreaterEqual(len(plan["tasks"]), 2)
            self.assertEqual(plan["tasks"][0]["task_key"], "vocab_review")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_notification_schedule_is_deduplicated(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service()
        try:
            service.ensure_notification_schedule()
            first_count = user_model._db.execute(
                "SELECT COUNT(*) AS count FROM coach_notification_log WHERE user_id=?",
                (profile.user_id,),
            ).fetchone()["count"]
            service.ensure_notification_schedule()
            second_count = user_model._db.execute(
                "SELECT COUNT(*) AS count FROM coach_notification_log WHERE user_id=?",
                (profile.user_id,),
            ).fetchone()["count"]
            self.assertEqual(first_count, second_count)
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_channel_capability_depends_on_tier(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service({"ai_ready": True})
        try:
            self.assertFalse(service.channel_capabilities()["bark"])
            premium = CoachService(user_model, profile, {"ai_ready": True, "cloud_ai_ready": True})
            self.assertTrue(premium.channel_capabilities()["bark"])
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_quiet_hours_suppress_non_test_notifications(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service()
        try:
            service.save_settings({
                "preferred_study_time": "20:00",
                "quiet_hours": {"start": "00:00", "end": "23:59"},
                "reminder_level": "basic",
                "desktop_enabled": True,
            })
            plan = service.sync_daily_plan()
            service._insert_notification(plan, "plan", "daily_plan", "in_app", datetime.now())  # type: ignore[attr-defined]
            service._db.commit()
            dispatcher = CoachNotificationDispatcher()
            sent = service.dispatch_due_notifications(dispatcher, now=datetime.now())
            self.assertEqual(sent, [])
            state = service._db.execute(
                "SELECT state FROM coach_notification_log WHERE user_id=? LIMIT 1",
                (profile.user_id,),
            ).fetchone()["state"]
            self.assertEqual(state, "pending")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_ai_task_prefers_less_recent_or_less_practiced_mode(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service({"ai_ready": True})
        try:
            # writing was practiced more recently than speaking
            sid1 = user_model.start_session(profile.user_id, "writing")
            user_model.end_session(sid1, 60, 1, 1.0, content_json='{"exam":"toefl","task_type":"independent","prompt":"w"}')
            sid2 = user_model.start_session(profile.user_id, "speaking")
            user_model.end_session(sid2, 60, 1, 1.0, content_json='{"exam":"toefl","task_type":"independent","prompt":"s"}')
            # force writing to be more recent
            user_model._db.execute(
                "UPDATE sessions SET ended_at=? WHERE session_id=?",
                ("2026-03-10T00:00:00", sid1),
            )
            user_model._db.execute(
                "UPDATE sessions SET ended_at=? WHERE session_id=?",
                ("2026-03-09T00:00:00", sid2),
            )
            user_model._db.commit()
            task = service._ai_task()  # type: ignore[attr-defined]
            self.assertEqual(task["mode"], "speaking")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_today_result_card_prefers_latest_session_recap(self) -> None:
        tmpdir, srs, user_model, profile, service = self._build_service()
        try:
            sid = user_model.start_session(profile.user_id, "reading")
            user_model.end_session(
                sid,
                600,
                4,
                0.75,
                content_json='{"result_headline":"阅读完成：3/4 题正确 · Factual","next_step":"明天再做 1 轮 Factual。"}',
            )
            plan = service.sync_daily_plan()
            self.assertEqual(plan["summary"]["result_card"], "阅读完成：3/4 题正确 · Factual")
            self.assertEqual(plan["summary"]["tomorrow_reason"], "明天再做 1 轮 Factual。")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_listening_start_honors_requested_question_type_when_builtin_exists(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        db_path = f"{tmpdir.name}/user.db"
        srs = SM2Engine(db_path)
        user_model = UserModel(db_path)
        profile = user_model.create_profile(name="Listener", target_exam="toefl")
        components = (None, srs, user_model, None, profile)
        try:
            with patch("gui.api.listening.get_components", return_value=components), patch(
                "gui.api.listening._synthesize_audio",
                new=AsyncMock(return_value=(None, [])),
            ), patch(
                "gui.api.listening._maybe_replenish",
                new=AsyncMock(return_value=None),
            ):
                result = asyncio.run(
                    start_listening(exam="toefl", dialogue_type="monologue", question_type="organization")
                )
            self.assertEqual(result["question_type"], "organization")
            self.assertIn("organization", result["question_types"])
            self.assertTrue(result["topic"])
        finally:
            listening_sessions.clear()
            if listening_api._pool_db is not None:
                listening_api._pool_db.close()
                listening_api._pool_db = None
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()


class BuiltinVocabVisibilityTests(unittest.TestCase):
    def test_open_source_vocab_files_are_no_longer_hidden(self) -> None:
        self.assertTrue(should_include_builtin_book("toefl_awl", {}))
        self.assertTrue(should_include_builtin_book("gre_highfreq", {}))

    def test_builtin_vocab_can_sync_without_opening_vocab_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Smoke", target_exam="toefl")
            result = sync_builtin_vocabulary([Path("content/vocab")], srs, profile)
            count = srs._db.execute("SELECT COUNT(*) AS count FROM vocabulary WHERE source != 'user'").fetchone()["count"]
            self.assertTrue(result["ok"])
            self.assertGreater(count, 0)
            user_model._db.close()
            srs._db.close()


class PromptRotationTests(unittest.TestCase):
    def test_writing_rotation_prefers_unseen_prompt(self) -> None:
        prompts = ["p1", "p2", "p3"]
        chosen = _rotate_prompt_list(prompts, {"p1", "p2"}, n=1)
        self.assertEqual(chosen, ["p3"])

    def test_speaking_rotation_prefers_unseen_prompt(self) -> None:
        choice = _rotated_choice(["a", "b", "c"], {"a", "b"})
        self.assertEqual(choice, "c")

    def test_writing_task_type_prefers_less_used(self) -> None:
        chosen = _pick_writing_task_type(
            None,
            {"task1": ["a"], "task2": ["b"]},
            {"task2": {"count": 3, "last_at": "2026-03-19T00:00:00"}},
        )
        self.assertEqual(chosen, "task1")

    def test_speaking_task_type_prefers_less_used(self) -> None:
        chosen = _pick_speaking_task_type(
            None,
            ["part1", "part2", "part3"],
            {
                "part1": {"count": 2, "last_at": "2026-03-19T00:00:00"},
                "part2": {"count": 1, "last_at": "2026-03-18T00:00:00"},
                "part3": {"count": 1, "last_at": "2026-03-19T00:00:00"},
            },
            "part1",
        )
        self.assertEqual(chosen, "part2")


class EmptyEndpointContractTests(unittest.TestCase):
    def test_coach_and_history_are_empty_instead_of_error_without_profile(self) -> None:
        components = (None, None, None, None, None)
        with patch("gui.api.coach.get_components", return_value=components), patch(
            "gui.api.history.get_components",
            return_value=components,
        ):
            client = TestClient(create_app())
            coach = client.get("/api/coach/status")
            history = client.get("/api/history/daily")

        self.assertEqual(coach.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(coach.json()["plan"]["tasks"], [])
        self.assertEqual(history.json()["days"], [])


if __name__ == "__main__":
    unittest.main()
