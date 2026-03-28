from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel
from gui.server import create_app


class WordbookEditContractTests(unittest.TestCase):
    def _build_stack(self):
        tmpdir = tempfile.TemporaryDirectory()
        db_path = f"{tmpdir.name}/user.db"
        srs = SM2Engine(db_path)
        user_model = UserModel(db_path)
        profile = user_model.create_profile(name="Wordbook Tester", target_exam="toefl")
        book = srs.create_word_book(profile.user_id, "My Custom Book", icon="📘")
        return tmpdir, srs, user_model, profile, book

    def test_adding_existing_word_to_book_applies_requested_updates(self) -> None:
        tmpdir, srs, user_model, profile, book = self._build_stack()
        try:
            word_id = srs.add_word("pontificate", "speak pompously", source="builtin")
            components = (None, srs, user_model, None, profile)
            with patch("gui.api.wordbooks.get_components", return_value=components):
                client = TestClient(create_app())
                response = client.post(
                    f"/api/wordbooks/{book['book_id']}/words",
                    json={
                        "word_id": word_id,
                        "definition_en": "to speak in a long, formal, self-important way",
                        "pronunciation": "/pɒnˈtɪf.ɪ.keɪt/",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["updated_existing"])
            row = srs._db.execute(
                "SELECT definition_en, pronunciation FROM vocabulary WHERE word_id=?",
                (word_id,),
            ).fetchone()
            self.assertEqual(row["definition_en"], "to speak in a long, formal, self-important way")
            self.assertEqual(row["pronunciation"], "/pɒnˈtɪf.ɪ.keɪt/")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_wordbook_put_updates_card_content_and_word_text(self) -> None:
        tmpdir, srs, user_model, profile, book = self._build_stack()
        try:
            word_id = srs.add_word(
                "abate",
                "become less intense",
                source="user",
                example="The storm began to abate.",
            )
            srs.add_word_to_book(book["book_id"], word_id)
            srs.enroll_words(profile.user_id, [word_id])
            components = (None, srs, user_model, None, profile)
            with patch("gui.api.wordbooks.get_components", return_value=components):
                client = TestClient(create_app())
                response = client.put(
                    f"/api/wordbooks/{book['book_id']}/words/{word_id}",
                    json={
                        "word": "abatement",
                        "definition_en": "a reduction in intensity or degree",
                        "definition_zh": "减轻；缓和",
                        "example": "The medicine brought a gradual abatement of the pain.",
                        "part_of_speech": "noun",
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["word"], "abatement")
            row = srs._db.execute(
                "SELECT word, definition_en, definition_zh, example, part_of_speech FROM vocabulary WHERE word_id=?",
                (word_id,),
            ).fetchone()
            self.assertEqual(row["word"], "abatement")
            self.assertEqual(row["definition_en"], "a reduction in intensity or degree")
            self.assertEqual(row["definition_zh"], "减轻；缓和")
            self.assertEqual(row["part_of_speech"], "noun")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()

    def test_vocab_add_reuses_existing_word_and_updates_fields(self) -> None:
        tmpdir, srs, user_model, profile, _book = self._build_stack()
        try:
            word_id = srs.add_word("mitigate", "make less severe", source="builtin")
            components = (None, srs, user_model, None, profile)
            with patch("gui.api.vocab.get_components", return_value=components):
                client = TestClient(create_app())
                response = client.post(
                    "/api/vocab/add",
                    json={
                        "word": "mitigate",
                        "definition_en": "to make something less harmful or severe",
                        "example": "New levees helped mitigate flood damage.",
                    },
                )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["word_id"], word_id)
            self.assertTrue(body["updated_existing"])
            enrolled = srs._db.execute(
                "SELECT 1 FROM srs_cards WHERE user_id=? AND word_id=?",
                (profile.user_id, word_id),
            ).fetchone()
            self.assertIsNotNone(enrolled)
            row = srs._db.execute(
                "SELECT definition_en, example FROM vocabulary WHERE word_id=?",
                (word_id,),
            ).fetchone()
            self.assertEqual(row["definition_en"], "to make something less harmful or severe")
            self.assertEqual(row["example"], "New levees helped mitigate flood damage.")
        finally:
            user_model._db.close()
            srs._db.close()
            tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
