from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from core.coach.heartbeat import HeartbeatAction, HeartbeatDecisionService, HeartbeatSignals
from core.coach.service import CoachService
from core.memory.service import LearnerMemoryService
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from gui.server import create_app


class MemoryContractTests(unittest.TestCase):
    def _build_stack(self):
        tmpdir = tempfile.TemporaryDirectory()
        db_path = f"{tmpdir.name}/user.db"
        srs = SM2Engine(db_path)
        user_model = UserModel(db_path)
        profile = user_model.create_profile(
            name="Alice",
            target_exam="toefl",
            preferred_style="direct",
            long_term_goal="TOEFL 100",
            study_preferences=["short_tasks", "review_first"],
        )
        memory = LearnerMemoryService(user_model._db, profile)
        return tmpdir, srs, user_model, profile, memory

    def test_profile_fields_persist_across_restart(self) -> None:
        tmpdir, srs, user_model, profile, _ = self._build_stack()
        try:
            user_model._db.close()
            srs._db.close()

            reopened = UserModel(f"{tmpdir.name}/user.db")
            loaded = reopened.get_profile(profile.user_id)
            self.assertEqual(loaded.preferred_style, "direct")
            self.assertEqual(loaded.long_term_goal, "TOEFL 100")
            self.assertEqual(loaded.study_preferences, ["short_tasks", "review_first"])
            reopened._db.close()
        finally:
            tmpdir.cleanup()

    def test_remember_fact_is_upserted(self) -> None:
        tmpdir, srs, user_model, profile, memory = self._build_stack()
        try:
            memory.remember_fact("preference", "preferred_style", {"style": "direct"})
            memory.remember_fact("preference", "preferred_style", {"style": "concise"})
            facts = memory.facts("preference")
            self.assertEqual(len(facts), 1)
            self.assertEqual(facts[0].value["style"], "concise")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_enrolled_words_appear_in_review_due_list(self) -> None:
        tmpdir, srs, user_model, profile, memory = self._build_stack()
        try:
            word_id = srs.add_word(
                "abandon",
                "to leave behind",
                topic="academic",
                difficulty="B2",
                source="toefl_awl",
                exam_type="toefl",
                subject_domain="academic",
            )
            srs.enroll_words(profile.user_id, [word_id])
            due = memory.review_due_list()
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0].word, "abandon")
            self.assertEqual(due[0].status, "unknown")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_frequent_forgetting_pool_tracks_repeated_failures(self) -> None:
        tmpdir, srs, user_model, profile, memory = self._build_stack()
        try:
            word_id = srs.add_word(
                "mitigate",
                "to make less severe",
                topic="academic",
                difficulty="B2",
                source="toefl_awl",
                exam_type="toefl",
                subject_domain="academic",
            )
            srs.enroll_words(profile.user_id, [word_id])
            card_id = srs._db.execute(
                "SELECT card_id FROM srs_cards WHERE user_id=? AND word_id=?",
                (profile.user_id, word_id),
            ).fetchone()["card_id"]
            for _ in range(3):
                srs.review_card(card_id, 1)
                srs._db.execute(
                    "UPDATE srs_cards SET due_date=date('now','localtime') WHERE card_id=?",
                    (card_id,),
                )
                srs._db.commit()
            frequent = memory.frequent_forgetting_list()
            self.assertEqual(len(frequent), 1)
            self.assertEqual(frequent[0].word, "mitigate")
            self.assertGreaterEqual(frequent[0].wrong_count, 3)
            self.assertEqual(frequent[0].status, "unknown")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_coach_summary_includes_memory_and_heartbeat(self) -> None:
        tmpdir, srs, user_model, profile, memory = self._build_stack()
        try:
            word_ids = []
            for idx in range(8):
                word_ids.append(
                    srs.add_word(
                        f"retention_{idx}",
                        "the ability to keep something",
                        topic="academic",
                        difficulty="B2",
                        source="toefl_awl",
                        exam_type="toefl",
                        subject_domain="academic",
                    )
                )
            srs.enroll_words(profile.user_id, word_ids)
            memory.remember_fact("goal", "target_score", {"toefl": 100})
            coach = CoachService(user_model, profile, {"ai_ready": True})
            coach.save_settings(
                {
                    "preferred_study_time": "20:00",
                    "quiet_hours": {"start": "00:00", "end": "00:01"},
                    "reminder_level": "basic",
                    "desktop_enabled": False,
                    "bark_enabled": False,
                    "webhook_enabled": False,
                }
            )
            summary = coach.coach_summary()
            self.assertIn("heartbeat_action", summary)
            self.assertIn("frequent_forgetting_count", summary)
            self.assertIn("memory_last_event_at", summary)
            self.assertEqual(summary["review_due_today"], 8)
            self.assertEqual(summary["heartbeat_action"], "NUDGE_REVIEW")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()


class HeartbeatDecisionTests(unittest.TestCase):
    def test_quiet_hours_stay_silent(self) -> None:
        decision = HeartbeatDecisionService().decide(HeartbeatSignals(now=datetime.now(), quiet_now=True))
        self.assertEqual(decision.action, HeartbeatAction.SILENT)

    def test_review_due_prefers_review_nudge(self) -> None:
        decision = HeartbeatDecisionService().decide(
            HeartbeatSignals(now=datetime.now(), review_due_count=8)
        )
        self.assertEqual(decision.action, HeartbeatAction.NUDGE_REVIEW)

    def test_inactivity_prefers_new_words(self) -> None:
        decision = HeartbeatDecisionService().decide(
            HeartbeatSignals(now=datetime.now(), last_interaction_at=datetime.now() - timedelta(hours=25))
        )
        self.assertEqual(decision.action, HeartbeatAction.NUDGE_NEW_WORDS)

    def test_recent_progress_prefers_micro_test(self) -> None:
        decision = HeartbeatDecisionService().decide(
            HeartbeatSignals(
                now=datetime.now(),
                last_interaction_at=datetime.now() - timedelta(hours=1),
                today_sessions=1,
                plan_status="in_progress",
            )
        )
        self.assertEqual(decision.action, HeartbeatAction.MICRO_TEST)

    def test_completed_day_prefers_encourage_and_wait(self) -> None:
        decision = HeartbeatDecisionService().decide(
            HeartbeatSignals(
                now=datetime.now(),
                last_interaction_at=datetime.now() - timedelta(hours=2),
                today_sessions=1,
                plan_status="done",
            )
        )
        self.assertEqual(decision.action, HeartbeatAction.ENCOURAGE_AND_WAIT)


class MemoryApiContractTests(unittest.TestCase):
    def test_memory_status_is_empty_without_profile(self) -> None:
        with patch("gui.api.memory.get_user_components", return_value=(None, None)):
            client = TestClient(create_app())
            response = client.get("/api/memory/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["has_profile"])
        self.assertEqual(body["facts"], [])

    def test_memory_api_can_write_and_read_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Coach", target_exam="toefl")
            with patch("gui.api.memory.get_user_components", return_value=(user_model, profile)), patch(
                "gui.api.progress.get_user_components",
                return_value=(user_model, profile),
            ), patch(
                "gui.api.progress.build_coach_runtime",
                return_value={"ai_ready": False},
            ):
                client = TestClient(create_app())
                save_resp = client.post(
                    "/api/memory/facts",
                    json={
                        "fact_type": "goal",
                        "fact_key": "target_score",
                        "value": {"toefl": 105},
                        "source": "api_test",
                        "confidence": 0.9,
                    },
                )
                self.assertEqual(save_resp.status_code, 200)
                facts_resp = client.get("/api/memory/facts?fact_type=goal")
                status_resp = client.get("/api/memory/status")
                progress_resp = client.get("/api/progress")
            self.assertEqual(facts_resp.status_code, 200)
            facts = facts_resp.json()["facts"]
            self.assertEqual(len(facts), 1)
            self.assertEqual(facts[0]["fact_key"], "target_score")
            self.assertEqual(status_resp.status_code, 200)
            self.assertGreaterEqual(status_resp.json()["summary"]["facts_count"], 1)
            self.assertEqual(progress_resp.status_code, 200)
            self.assertIn("memory_summary", progress_resp.json())
            self.assertGreaterEqual(progress_resp.json()["memory_summary"]["facts_count"], 1)
            user_model._db.close()
            srs._db.close()


if __name__ == "__main__":
    unittest.main()
