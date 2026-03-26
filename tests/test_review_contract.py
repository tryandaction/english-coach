from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.coach.context import LearnerContextBuilder
from core.coach.policy import CoachPolicyService
from core.review.service import ReviewPoolService
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from gui.server import create_app


class ReviewPoolContractTests(unittest.TestCase):
    def _build_stack(self):
        tmpdir = tempfile.TemporaryDirectory()
        db_path = f"{tmpdir.name}/user.db"
        srs = SM2Engine(db_path)
        user_model = UserModel(db_path)
        profile = user_model.create_profile(
            name="Reviewer",
            target_exam="toefl",
            study_preferences=["short_tasks"],
        )
        return tmpdir, srs, user_model, profile

    def test_review_pool_prioritizes_due_before_forgetting_only(self) -> None:
        tmpdir, srs, user_model, profile = self._build_stack()
        try:
            due_word = srs.add_word("abandon", "leave behind", source="toefl_awl", exam_type="toefl")
            fail_word = srs.add_word("mitigate", "reduce severity", source="toefl_awl", exam_type="toefl")
            srs.enroll_words(profile.user_id, [due_word, fail_word])
            card_id = srs._db.execute(
                "SELECT card_id FROM srs_cards WHERE user_id=? AND word_id=?",
                (profile.user_id, fail_word),
            ).fetchone()["card_id"]
            for _ in range(3):
                srs.review_card(card_id, 1)
            service = ReviewPoolService(user_model._db, profile)
            candidates = service.candidates(profile.user_id, limit=5)
            self.assertGreaterEqual(len(candidates), 2)
            self.assertEqual(candidates[0].word, "abandon")
            self.assertEqual(candidates[0].priority_reason, "overdue_review")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_policy_prefers_review_when_pool_is_active(self) -> None:
        tmpdir, srs, user_model, profile = self._build_stack()
        try:
            word_ids = [
                srs.add_word(f"word_{idx}", "definition", source="toefl_awl", exam_type="toefl")
                for idx in range(8)
            ]
            srs.enroll_words(profile.user_id, word_ids)
            snapshot = LearnerContextBuilder(user_model._db, profile, ai_ready=False).build(plan_status="planned")
            decision = CoachPolicyService().decide(snapshot)
            self.assertEqual(decision.action, "review_words")
            self.assertEqual(decision.skill, "vocab")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()


class PracticeRecommendationApiTests(unittest.TestCase):
    def test_practice_recommendation_returns_empty_without_profile(self) -> None:
        with patch("gui.api.practice.get_components", return_value=(None, None, None, None, None)):
            client = TestClient(create_app())
            response = client.get("/api/practice/recommendation")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["has_profile"])

    def test_vocab_targeted_uses_review_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Coach", target_exam="toefl")
            word_ids = [
                srs.add_word(f"review_{idx}", "definition", source="toefl_awl", exam_type="toefl")
                for idx in range(8)
            ]
            srs.enroll_words(profile.user_id, word_ids)
            components = (None, srs, user_model, None, profile)
            with patch("gui.api.practice.get_components", return_value=components):
                client = TestClient(create_app())
                recommend = client.get("/api/practice/recommendation")
                start = client.post(
                    "/api/practice/start-practice",
                    json={
                        "exam": "toefl",
                        "skill": "vocab",
                        "practice_mode": "targeted",
                    },
                )
            self.assertEqual(recommend.status_code, 200)
            self.assertEqual(recommend.json()["next_action"]["action"], "review_words")
            self.assertEqual(start.status_code, 200)
            self.assertEqual(start.json()["source"], "review_pool")
            self.assertGreaterEqual(start.json()["review_due_total"], 8)
            user_model._db.close()
            srs._db.close()


if __name__ == "__main__":
    unittest.main()
