from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.memory.service import LearnerMemoryService
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from gui.api import chat as chat_api
from gui.server import create_app


class _FakeAI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, messages, cefr_level: str, correct_errors: bool = True) -> str:
        self.calls.append(
            {
                "messages": messages,
                "cefr_level": cefr_level,
                "correct_errors": correct_errors,
            }
        )
        return "stub-reply"


class ChatContractTests(unittest.TestCase):
    def test_chat_remember_and_word_status_write_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(name="Coach", target_exam="toefl")
            fake_ai = _FakeAI()
            components = (None, srs, user_model, fake_ai, profile)
            with patch("gui.api.chat.get_components", return_value=components), patch(
                "gui.api.chat.load_config",
                return_value={"backend": "openai"},
            ):
                client = TestClient(create_app())
                start = client.post("/api/chat/start?exam=toefl")
                self.assertEqual(start.status_code, 200)
                sid = start.json()["session_id"]

                remember = client.post(
                    f"/api/chat/remember/{sid}",
                    json={
                        "fact_type": "goal",
                        "fact_key": "target_score",
                        "value": {"toefl": 105},
                    },
                )
                self.assertEqual(remember.status_code, 200)

                mark = client.post(
                    f"/api/chat/word-status/{sid}",
                    json={
                        "word": "mitigate",
                        "status": "unknown",
                        "definition_en": "to reduce severity",
                        "tags": ["toefl"],
                    },
                )
                self.assertEqual(mark.status_code, 200)
                self.assertEqual(mark.json()["status"], "unknown")

                memory = LearnerMemoryService(user_model._db, profile)
                facts = memory.facts("goal")
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0].fact_key, "target_score")
                review_due = memory.review_due_list(limit=10)
                self.assertTrue(any(item.word == "mitigate" for item in review_due))
            chat_api._sessions.clear()
            user_model._db.close()
            srs._db.close()

    def test_chat_message_includes_memory_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/user.db"
            srs = SM2Engine(db_path)
            user_model = UserModel(db_path)
            profile = user_model.create_profile(
                name="Coach",
                target_exam="toefl",
                long_term_goal="TOEFL 100",
                study_preferences=["short_tasks"],
            )
            fake_ai = _FakeAI()
            components = (None, srs, user_model, fake_ai, profile)
            with patch("gui.api.chat.get_components", return_value=components), patch(
                "gui.api.chat.load_config",
                return_value={"backend": "openai"},
            ):
                client = TestClient(create_app())
                start = client.post("/api/chat/start?exam=toefl")
                sid = start.json()["session_id"]
                client.post(
                    f"/api/chat/remember/{sid}",
                    json={
                        "fact_type": "preference",
                        "fact_key": "style",
                        "value": {"style": "direct"},
                    },
                )
                response = client.post(
                    f"/api/chat/message/{sid}",
                    json={"message": "Help me practice today."},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("stub-reply", response.text)
                self.assertTrue(fake_ai.calls)
                first_message = fake_ai.calls[0]["messages"][0]
                self.assertEqual(first_message["role"], "system")
                self.assertIn("Long-term goal: TOEFL 100", first_message["content"])
                self.assertIn("Known learner facts:", first_message["content"])
            chat_api._sessions.clear()
            user_model._db.close()
            srs._db.close()


if __name__ == "__main__":
    unittest.main()
