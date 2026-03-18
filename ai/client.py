"""
AI client — multi-backend wrapper with local response cache.
Supports: Anthropic Claude, DeepSeek, Alibaba Qwen (and any OpenAI-compatible API).
Users can supply their own API key, or use a cloud license that proxies requests
through the activation backend without exposing the upstream provider key.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Import TOEFL 2026 question generators
from ai.question_generators import (
    generate_complete_words_question,
    generate_daily_life_question,
    generate_listen_repeat_task,
    generate_virtual_interview_task,
    generate_build_sentence_task,
    generate_write_email_task,
    generate_academic_discussion_task,
)

# Import additional reading question generators
from ai.reading_question_generators import (
    generate_negative_factual_question,
    generate_rhetorical_purpose_question,
    generate_reference_question,
    generate_sentence_simplification_question,
    generate_insert_text_question,
    generate_prose_summary_question,
    generate_fill_table_question,
)


SYSTEM_PROMPT = """You are an expert English teacher specializing in academic English for Chinese STEM students preparing for TOEFL, GRE, IELTS, CET-4/6, or general academic use.

Your students are strong in physics, engineering, and mathematics but need help with English expression. They are analytical and appreciate precise, structured feedback.

Teaching principles:
- Use physics/engineering/math examples when explaining grammar or vocabulary concepts
- Be aware of common Chinese-English interference patterns: article usage (a/an/the), prepositions, subject-verb agreement, passive voice overuse
- Give feedback using the structure: strength → specific improvement → encouragement
- Always pitch explanations at the student's current CEFR level (provided in each request)
- Be concise and direct — these students value efficiency over pleasantries
- When correcting errors, always show the corrected version alongside the original

Respond in English unless the student writes in Chinese, in which case you may mix languages for clarity."""

# Known OpenAI-compatible backend base URLs
_BACKENDS = {
    "anthropic": "https://api.anthropic.com/v1",
    "deepseek":  "https://api.deepseek.com/v1",
    "qwen":      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai":    "https://api.openai.com/v1",
}

# Default models per backend
_DEFAULT_MODELS = {
    "anthropic": ("claude-haiku-4-5",   "claude-sonnet-4-5"),
    "deepseek":  ("deepseek-chat",       "deepseek-chat"),
    "qwen":      ("qwen-turbo",          "qwen-plus"),
    "openai":    ("gpt-4o-mini",         "gpt-4o"),
}



class AIClient:
    """
    Multi-backend AI client.
    Works with Claude (Anthropic), DeepSeek, Qwen, or any OpenAI-compatible API.
    1. Local SQLite response cache (avoid re-generating same content)
    2. Per-session token tracking
    3. Configurable model per task type
    """

    def __init__(
        self,
        api_key: str,
        cache_db_path: str | Path,
        default_model: str = "deepseek-chat",
        writing_model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
    ):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._default_model = default_model
        self._writing_model = writing_model
        self._cache_db = sqlite3.connect(str(cache_db_path), check_same_thread=False)
        self._init_cache_schema()
        self.session_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_cache_schema(self) -> None:
        self._cache_db.executescript("""
            CREATE TABLE IF NOT EXISTS response_cache (
                cache_key   TEXT PRIMARY KEY,
                response    TEXT,
                model       TEXT,
                created_at  TEXT,
                expires_at  TEXT
            );
        """)
        self._cache_db.commit()

    # ------------------------------------------------------------------
    # Public API tasks
    # ------------------------------------------------------------------

    def generate_writing_prompt(
        self,
        cefr_level: str,
        exam: str = "general",
    ) -> str:
        """
        Generate a writing prompt for the given exam and CEFR level.
        Cached 7 days. Returns prompt string or empty string on failure.
        """
        import random
        _styles = {
            "toefl":   "an independent TOEFL writing task (agree/disagree or preference)",
            "ielts":   "an IELTS Task 2 essay question (discuss both views or opinion)",
            "gre":     "a GRE Issue essay prompt (take a position on a broad claim)",
            "cet":     "a CET-4/6 essay topic (social or campus issue)",
            "general": "a general academic essay question",
        }
        style = _styles.get(exam, _styles["general"])
        seed = random.randint(1, 9999)
        cache_key = self._key(f"wprompt|{cefr_level}|{exam}|{seed // 20}")
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        prompt = (
            f"Write one original {style} for a {cefr_level} English learner. "
            f"The topic should be fresh and thought-provoking. "
            f"Return only the prompt text, no labels or extra commentary."
        )
        result = self._call(prompt, model=self._default_model, max_tokens=200).strip()
        if result:
            self._set_cache(cache_key, result, ttl_days=7)
        return result

    def generate_reading_passage(
        self,
        cefr_level: str,
        exam: str = "general",
        topic: str = "",
    ) -> dict:
        """
        Generate a reading passage when no KB content is available.
        Returns {passage, topic, difficulty, word_count}.
        Cached 7 days per cefr+exam+topic combo.
        """
        import random
        _topics = {
            "toefl": ["climate change", "ancient civilizations", "neuroscience", "space exploration", "economics"],
            "ielts": ["urban planning", "renewable energy", "social media", "biodiversity", "technology"],
            "gre":   ["philosophy of mind", "evolutionary biology", "political theory", "linguistics", "art history"],
            "cet":   ["campus life", "environmental protection", "career development", "cultural exchange", "health"],
            "general": ["artificial intelligence", "ocean ecosystems", "human psychology", "architecture", "music"],
        }
        if not topic:
            topic = random.choice(_topics.get(exam, _topics["general"]))

        cache_key = self._key(f"passage|{cefr_level}|{exam}|{topic}")
        cached = self._get_cache(cache_key)
        if cached:
            import json as _j
            return _j.loads(cached)

        default_targets = {"A1": 80, "A2": 120, "B1": 180, "B2": 250, "C1": 320, "C2": 400}
        exam_targets = {
            "toefl": {"A1": 120, "A2": 180, "B1": 320, "B2": 680, "C1": 720, "C2": 760},
            "ielts": {"A1": 120, "A2": 180, "B1": 420, "B2": 820, "C1": 860, "C2": 900},
            "gre": {"A1": 120, "A2": 180, "B1": 260, "B2": 340, "C1": 430, "C2": 500},
            "cet": {"A1": 120, "A2": 160, "B1": 240, "B2": 320, "C1": 380, "C2": 420},
        }
        words = exam_targets.get(exam, default_targets).get(cefr_level, default_targets.get(cefr_level, 200))
        style_hint = {
            "toefl": "Use an academic expository style similar to a TOEFL reading passage, with 6-8 coherent paragraphs and clear development of ideas.",
            "ielts": "Use an IELTS Academic reading style with substantial detail, 6-8 coherent paragraphs, and a neutral informative tone.",
            "gre": "Use a dense academic style similar to GRE reading passages, with nuanced reasoning and compact paragraph structure.",
            "cet": "Use a Chinese university English exam style passage with clear structure and practical academic vocabulary.",
            "general": "Use a polished academic English article style with clear paragraph transitions.",
        }.get(exam, "Use a polished academic English article style with clear paragraph transitions.")

        prompt = (
            f"Write one reading passage about '{topic}' for a {cefr_level} English learner "
            f"preparing for {exam.upper()}. Target length: about {words} words. "
            f"{style_hint} Use vocabulary and sentence complexity appropriate for {cefr_level}. "
            f"Do not add a title, bullets, questions, markdown, or explanations. Return only the passage text."
        )
        passage = self._call(prompt, model=self._default_model, max_tokens=600).strip()

        result = {"passage": passage, "topic": topic, "difficulty": cefr_level, "word_count": len(passage.split())}
        import json as _j
        self._set_cache(cache_key, _j.dumps(result, ensure_ascii=False), ttl_days=7)
        return result

    def generate_comprehension_questions(
        self,
        passage: str,
        cefr_level: str,
        num_questions: int = 5,
        exam: str = "general",
        question_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Generate reading comprehension questions matching official exam formats.
        TOEFL/CET/general: 4-option MC. IELTS: MC + T/F/NG. GRE: 5-option MC.
        Cached 30 days — same passage won't cost twice.
        Returns list of {question, type, options, answer, explanation}.

        If question_type is specified, generates only that specific type (e.g., "complete_words", "daily_life").
        """
        cache_key = self._key(f"compq2|{passage[:120]}|{cefr_level}|{exam}|{num_questions}|{question_type or 'mixed'}")
        cached = self._get_cache(cache_key)
        if cached:
            return json.loads(cached)

        # Exam-specific format instructions
        _fmt = {
            "toefl": (
                f"Generate exactly {num_questions} TOEFL-style reading questions. "
                "Use these types: factual information (What does the author say about...?), "
                "negative factual (According to the passage, which is NOT true?), "
                "inference (What can be inferred about...?), vocabulary (The word X in paragraph Y is closest in meaning to...), "
                "rhetorical purpose (Why does the author mention...?). "
                "Each question has exactly 4 options (A/B/C/D). "
                'Return ONLY a JSON array: [{"question":"...","type":"factual|negative_factual|inference|vocabulary|rhetorical","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            ),
            "ielts": (
                f"Generate exactly {num_questions} IELTS Academic Reading questions using mixed formats. "
                "Include at least 2 True/False/Not Given questions and at least 2 multiple-choice questions. "
                "For T/F/NG: options must be exactly [\"True\",\"False\",\"Not Given\"]. "
                "For MC: 4 options (A/B/C/D). "
                'Return ONLY a JSON array: [{"question":"...","type":"tfng|mc","options":["...","...","..."],"answer":"True|False|Not Given|A","explanation":"..."}]'
            ),
            "gre": (
                f"Generate exactly {num_questions} GRE Verbal Reading Comprehension questions. "
                "Use these types: inference, author's purpose, strengthen/weaken argument, vocabulary-in-context. "
                "Each question has exactly 5 options (A/B/C/D/E). "
                'Return ONLY a JSON array: [{"question":"...","type":"inference|purpose|argument|vocabulary","options":["A. ...","B. ...","C. ...","D. ...","E. ..."],"answer":"A","explanation":"..."}]'
            ),
            "cet": (
                f"Generate exactly {num_questions} CET-4/6 style reading comprehension questions. "
                "Use factual, inference, and main idea question types. "
                "Each question has exactly 4 options (A/B/C/D). "
                'Return ONLY a JSON array: [{"question":"...","type":"factual|inference|main_idea","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            ),
            "general": (
                f"Generate exactly {num_questions} reading comprehension questions. "
                "Mix factual recall, inference, and vocabulary-in-context types. "
                "Each question has exactly 4 options (A/B/C/D). "
                'Return ONLY a JSON array: [{"question":"...","type":"factual|inference|vocabulary","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            ),
        }
        fmt = _fmt.get(exam, _fmt["general"])

        prompt = (
            f"Student CEFR level: {cefr_level}. Exam: {exam.upper()}.\n\n"
            f"PASSAGE:\n{passage}\n\n"
            f"{fmt}"
        )

        response = self._call(prompt, model=self._default_model, max_tokens=900)
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        result_json = text[start:end] if start != -1 else "[]"

        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            result = []

        if result:
            self._set_cache(cache_key, json.dumps(result, ensure_ascii=False), ttl_days=30)
        return result

    # ------------------------------------------------------------------
    # TOEFL 2026 New Question Types
    # ------------------------------------------------------------------

    def generate_complete_words_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 2026 'Complete the Words' question."""
        return generate_complete_words_question(passage, cefr_level, self)

    def generate_daily_life_question(self, cefr_level: str, text_type: str = "email") -> dict:
        """Generate TOEFL 2026 'Read in Daily Life' question."""
        return generate_daily_life_question(cefr_level, self, text_type)

    def generate_listen_repeat_task(self, cefr_level: str, num_sentences: int = 7) -> dict:
        """Generate TOEFL 2026 'Listen & Repeat' speaking task."""
        return generate_listen_repeat_task(cefr_level, self, num_sentences)

    def generate_virtual_interview_task(self, cefr_level: str, num_questions: int = 5) -> dict:
        """Generate TOEFL 2026 'Virtual Interview' speaking task."""
        return generate_virtual_interview_task(cefr_level, self, num_questions)

    def generate_build_sentence_task(self, cefr_level: str, num_items: int = 5) -> dict:
        """Generate TOEFL 2026 'Build a Sentence' writing task."""
        return generate_build_sentence_task(cefr_level, self, num_items)

    def generate_write_email_task(self, cefr_level: str) -> dict:
        """Generate TOEFL 2026 'Write an Email' writing task."""
        return generate_write_email_task(cefr_level, self)

    def generate_academic_discussion_task(self, cefr_level: str) -> dict:
        """Generate TOEFL 2026 'Academic Discussion' writing task."""
        return generate_academic_discussion_task(cefr_level, self)

    # ------------------------------------------------------------------
    # Additional TOEFL Reading Question Types
    # ------------------------------------------------------------------

    def generate_negative_factual_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Negative Factual Information' question."""
        return generate_negative_factual_question(passage, cefr_level, self)

    def generate_rhetorical_purpose_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Rhetorical Purpose' question."""
        return generate_rhetorical_purpose_question(passage, cefr_level, self)

    def generate_reference_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Reference' question."""
        return generate_reference_question(passage, cefr_level, self)

    def generate_sentence_simplification_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Sentence Simplification' question."""
        return generate_sentence_simplification_question(passage, cefr_level, self)

    def generate_insert_text_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Insert Text' question."""
        return generate_insert_text_question(passage, cefr_level, self)

    def generate_prose_summary_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Prose Summary' question."""
        return generate_prose_summary_question(passage, cefr_level, self)

    def generate_fill_table_question(self, passage: str, cefr_level: str) -> dict:
        """Generate TOEFL 'Fill in a Table' question."""
        return generate_fill_table_question(passage, cefr_level, self)

    def evaluate_writing(
        self,
        essay: str,
        prompt: str,
        cefr_level: str,
        exam: str = "toefl",
    ) -> dict:
        """
        Score and give feedback on a writing sample.
        Uses the stronger writing model. Not cached (each essay is unique).
        Returns {scores, strengths, improvements, revised_intro}.
        """
        rubric = _WRITING_RUBRICS.get(exam, _WRITING_RUBRICS["general"])

        ai_prompt = (
            f"Student CEFR level: {cefr_level}. Task: {prompt}. Exam: {exam}.\n\n"
            f"SCORING RUBRIC:\n{rubric}\n\n"
            f"STUDENT ESSAY:\n{essay}\n\n"
            f"Provide feedback as JSON (no other text):\n"
            f'{{"scores":{{"task_achievement":0,"coherence":0,"lexical_resource":0,"grammar_accuracy":0}},'
            f'"overall":0,'
            f'"strengths":["..."],'
            f'"improvements":[{{"issue":"...","original":"...","correction":"...","explanation":"..."}}],'
            f'"revised_intro":"..."}}'
        )

        response = self._call(ai_prompt, model=self._writing_model, max_tokens=1200)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        result_json = text[start:end] if start != -1 else "{}"
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            return {"error": "Could not parse feedback", "raw": text}

    def evaluate_speaking(
        self,
        transcript: str,
        task_type: str,
        cefr_level: str,
        sample_response: Optional[str] = None,
    ) -> dict:
        """
        Score a speaking transcript (text-based simulation).
        Returns {scores, strengths, improvements, key_phrases_to_add}.
        """
        sample_section = (
            f"\nHIGH-SCORE SAMPLE RESPONSE FOR REFERENCE:\n{sample_response}\n"
            if sample_response
            else ""
        )

        prompt = (
            f"Student CEFR level: {cefr_level}. Speaking task: {task_type}.\n"
            f"{sample_section}\n"
            f"STUDENT RESPONSE:\n{transcript}\n\n"
            f"Score on ETS TOEFL Speaking rubric (0-4 each dimension). Return JSON only:\n"
            f'{{"scores":{{"delivery":0,"language_use":0,"topic_development":0}},'
            f'"overall":0,'
            f'"strengths":["..."],'
            f'"improvements":["..."],'
            f'"key_phrases_to_add":["..."]}}'
        )

        response = self._call(prompt, model=self._default_model, max_tokens=700)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        result_json = text[start:end] if start != -1 else "{}"
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            return {"error": "Could not parse feedback", "raw": text}

    def enrich_word(self, word: str, cefr_level: str = "B2", exam: str = "general") -> dict:
        """
        Return a full vocabulary card for a word.
        Cached for 90 days — same word won't cost twice.
        Returns dict with all enrichment fields.
        """
        cache_key = self._key(f"enrich|{word}|{cefr_level}")
        cached = self._get_cache(cache_key)
        if cached:
            return json.loads(cached)

        prompt = (
            f"Give a complete vocabulary entry for the English word '{word}' "
            f"for a CEFR {cefr_level} student targeting {exam.upper()}.\n"
            f"Return ONLY a JSON object, no other text:\n"
            f'{{"definition_en":"...","definition_zh":"...","part_of_speech":"noun/verb/adj/adv/...",'
            f'"example":"...one natural example sentence...","context_sentence":"...one longer academic sentence using the word in context...",'
            f'"synonyms":"word1, word2, word3","antonyms":"word1, word2",'
            f'"derivatives":"noun form, verb form, adj form etc",'
            f'"collocations":"common phrase1; common phrase2; common phrase3",'
            f'"pronunciation":"/phonetic spelling/"}}'
        )

        response = self._call(prompt, model=self._default_model, max_tokens=500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        result_json = text[start:end] if start != -1 else "{}"
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            result = {}

        if result:
            self._set_cache(cache_key, json.dumps(result), ttl_days=90)
        return result

    def generate_listening_dialogue(
        self,
        cefr_level: str,
        exam: str = "general",
        dialogue_type: str = "conversation",
        question_types: Optional[list[str]] = None,
    ) -> dict:
        """
        Generate a listening comprehension script with questions.
        dialogue_type: 'conversation' (two speakers) or 'monologue' (one speaker).
        question_types: Optional list of specific question types to generate (e.g., ['gist_content', 'detail', 'function'])
        Cached 7 days per cefr+exam+type combo.
        Returns {type, topic, script:[{speaker,text}], questions:[{question,options,answer,explanation}]}.
        """
        import random
        _topics = {
            "toefl":   ["campus library", "professor office hours", "biology lecture", "study group planning", "campus event"],
            "ielts":   ["job interview", "travel booking", "university enrollment", "health clinic", "community meeting"],
            "gre":     ["academic seminar", "research discussion", "conference presentation", "thesis defense", "lab meeting"],
            "cet":     ["dormitory life", "canteen conversation", "class registration", "club activity", "internship"],
            "general": ["coffee shop", "airport check-in", "hotel reception", "doctor appointment", "phone call"],
        }
        topic = random.choice(_topics.get(exam, _topics["general"]))

        cache_key = self._key(f"listening|{cefr_level}|{exam}|{dialogue_type}|{topic}|{','.join(question_types or [])}")
        cached = self._get_cache(cache_key)
        if cached:
            return json.loads(cached)

        if dialogue_type == "conversation":
            script_instruction = (
                "Write a natural conversation between Speaker A and Speaker B (8-12 exchanges total). "
                "Format each line as: A: <text> or B: <text>"
            )
        else:
            script_instruction = (
                "Write a monologue or short lecture (10-14 sentences). "
                "Format each line as: A: <text>"
            )

        # Exam-specific question format instructions
        if exam == "toefl" and question_types:
            # Generate specific TOEFL question types
            type_descriptions = {
                "gist_content": "gist-content (What is the main topic?)",
                "gist_purpose": "gist-purpose (Why does the student visit the professor?)",
                "detail": "detail (According to the professor, what is X?)",
                "function": "function (Why does the speaker say this: [specific quote]?)",
                "attitude": "attitude (What is the speaker's attitude toward X?)",
                "organization": "organization (How does the professor organize the information?)",
                "connecting": "connecting content (What is the relationship between X and Y?)",
                "inference": "inference (What can be inferred about X?)",
            }
            type_list = ", ".join([type_descriptions.get(qt, qt) for qt in question_types])
            q_fmt = (
                f"Write exactly {len(question_types)} TOEFL Listening questions. "
                f"Include these types: {type_list}. "
                "Each has 4 options (A/B/C/D). "
                'questions format: [{"question":"...","type":"gist_content|gist_purpose|detail|function|attitude|organization|connecting|inference","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            )
        else:
            _q_fmt = {
                "toefl": (
                    "Write exactly 5 TOEFL Listening questions. "
                    "Include: gist-content (What is the main topic?), detail, function (Why does the speaker say...?), "
                    "attitude (What is the speaker's attitude toward...?), and inference. "
                    "Each has 4 options (A/B/C/D). "
                    'questions format: [{"question":"...","type":"gist_content|detail|function|attitude|inference","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
                ),
            "ielts": (
                "Write exactly 5 IELTS Listening questions using mixed formats. "
                "Include at least 2 multiple-choice (4 options A/B/C/D) and at least 2 form/note completion (fill-in-blank, answer is 1-3 words from the audio). "
                "For fill-in-blank, set options to [] and answer to the exact word(s). "
                'questions format: [{"question":"...","type":"mc|fill","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A or word","explanation":"..."}]'
            ),
            "gre": (
                "Write exactly 5 GRE-style listening/lecture comprehension questions. "
                "Focus on inference, author's purpose, and argument structure. "
                "Each has 5 options (A/B/C/D/E). "
                'questions format: [{"question":"...","type":"inference|purpose|argument","options":["A. ...","B. ...","C. ...","D. ...","E. ..."],"answer":"A","explanation":"..."}]'
            ),
            "cet": (
                "Write exactly 5 CET-4/6 listening questions. "
                "Include main idea, detail, and inference types. Each has 4 options (A/B/C/D). "
                'questions format: [{"question":"...","type":"main_idea|detail|inference","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            ),
            "general": (
                "Write exactly 4 multiple-choice listening comprehension questions. "
                "Each has 4 options (A/B/C/D). "
                'questions format: [{"question":"...","type":"detail|inference|main_idea","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]'
            ),
            }
            q_fmt = _q_fmt.get(exam, _q_fmt["general"])

        prompt = (
            f"Create a listening comprehension exercise for a {cefr_level} English learner targeting {exam.upper()}.\n"
            f"Topic: {topic}\n\n"
            f"{script_instruction}\n\n"
            f"{q_fmt}\n\n"
            f"Return ONLY a JSON object, no other text:\n"
            f'{{"type":"{dialogue_type}","topic":"{topic}",'
            f'"script":[{{"speaker":"A","text":"..."}}],'
            f'"questions":[{{"question":"...","type":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}}]}}'
        )

        response = self._call(prompt, model=self._default_model, max_tokens=1500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        result_json = text[start:end] if start != -1 else "{}"
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            result = {"type": dialogue_type, "topic": topic, "script": [], "questions": []}

        if result.get("script"):
            self._set_cache(cache_key, json.dumps(result, ensure_ascii=False), ttl_days=7)
        return result

    def complete(self, prompt: str, cache_key: Optional[str] = None, max_tokens: int = 500) -> str:
        """
        Generic completion — used by notebook and other modes for freeform prompts.
        Optionally cached by cache_key.
        """
        if cache_key:
            cached = self._get_cache(cache_key)
            if cached:
                return cached

        result = self._call(prompt, model=self._default_model, max_tokens=max_tokens)

        if cache_key:
            self._set_cache(cache_key, result, ttl_days=7)
        return result

    def explain_grammar(
        self,
        error_sentence: str,
        correction: str,
        cefr_level: str,
    ) -> str:
        """
        Explain a grammar error with a STEM-context example.
        Cached by error pattern.
        """
        cache_key = self._key(f"grammar|{error_sentence[:80]}|{cefr_level}")
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        prompt = (
            f"Student CEFR level: {cefr_level}.\n"
            f"Error: \"{error_sentence}\"\n"
            f"Correction: \"{correction}\"\n\n"
            f"Explain the grammar rule in 2-3 sentences. "
            f"Then give one example sentence using a physics or engineering context. "
            f"Be concise."
        )

        result = self._call(prompt, model=self._default_model, max_tokens=250)
        self._set_cache(cache_key, result, ttl_days=90)
        return result

    def chat(
        self,
        messages: list[dict],
        cefr_level: str,
        correct_errors: bool = True,
    ) -> str:
        """
        Free conversation mode. Responds at user's CEFR level.
        messages: list of {role: user|assistant, content: str}
        """
        level_instruction = (
            f"The student's CEFR level is {cefr_level}. "
            f"Respond using vocabulary and sentence structures appropriate for this level. "
        )
        correction_instruction = (
            "If the student's message contains grammar errors, gently note them "
            "at the end of your response with: 'Note: [correction]'"
            if correct_errors else ""
        )

        augmented = messages.copy()
        if augmented and augmented[-1]["role"] == "user":
            augmented[-1] = {
                "role": "user",
                "content": augmented[-1]["content"]
                + f"\n\n[{level_instruction} {correction_instruction}]",
            }

        response = self._client.chat.completions.create(
            model=self._default_model,
            max_tokens=800,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + augmented,
        )
        self._track(response.usage)
        return response.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    def usage_summary(self) -> str:
        u = self.session_usage
        return (
            f"API usage this session -- "
            f"input: {u['input']:,} | output: {u['output']:,}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(self, user_prompt: str, model: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        self._track(response.usage)
        return response.choices[0].message.content or ""

    def _track(self, usage) -> None:
        self.session_usage["input"]  += getattr(usage, "prompt_tokens", 0)
        self.session_usage["output"] += getattr(usage, "completion_tokens", 0)

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[str]:
        now = datetime.now().isoformat()
        row = self._cache_db.execute(
            "SELECT response FROM response_cache WHERE cache_key=? AND expires_at > ?",
            (key, now),
        ).fetchone()
        return row[0] if row else None

    def _set_cache(self, key: str, value: str, ttl_days: int = 30) -> None:
        expires = (datetime.now() + timedelta(days=ttl_days)).isoformat()
        self._cache_db.execute(
            "INSERT OR REPLACE INTO response_cache (cache_key, response, created_at, expires_at) "
            "VALUES (?,?,?,?)",
            (key, value, datetime.now().isoformat(), expires),
        )
        self._cache_db.commit()


# ------------------------------------------------------------------
# Writing rubrics (local, no API cost)
# ------------------------------------------------------------------

_WRITING_RUBRICS = {
    "toefl": """TOEFL Writing Rubric (0-5 scale):
- Task Achievement: Does the response address the prompt fully?
- Coherence & Cohesion: Is the essay logically organized with clear transitions?
- Lexical Resource: Is vocabulary varied, precise, and appropriate?
- Grammar Accuracy: Are sentences grammatically correct and varied in structure?""",

    "ielts": """IELTS Writing Rubric (0-9 band):
- Task Achievement/Response: Addresses all parts of the task
- Coherence & Cohesion: Logical progression, paragraphing, linking
- Lexical Resource: Range, accuracy, and appropriacy of vocabulary
- Grammatical Range & Accuracy: Variety and correctness of structures""",

    "gre": """GRE AWA Rubric (0-6 scale):
- Critical Thinking: Quality of analysis and reasoning
- Organization: Clear structure with introduction, body, conclusion
- Language Use: Precise vocabulary, varied sentence structure
- Grammar & Mechanics: Correct grammar, spelling, punctuation""",

    "general": """General Writing Rubric:
- Content: Relevant, well-developed ideas
- Organization: Clear structure and logical flow
- Vocabulary: Appropriate and varied word choice
- Grammar: Accurate and varied sentence structures""",
}


def load_client(config: dict, data_dir: Path) -> Optional["AIClient"]:
    """
    Load AIClient from cloud license proxy config or local .env settings.
    Priority: License activation > .env file
    Returns None if no API key found.
    """
    # 1. Check cloud license first
    try:
        from gui.license import get_license_ai_config

        license_cfg = get_license_ai_config(data_dir)
        if license_cfg:
            return AIClient(
                api_key=license_cfg["api_key"],
                cache_db_path=data_dir / "ai_cache.db",
                default_model="deepseek-chat",
                writing_model="deepseek-chat",
                base_url=license_cfg["base_url"],
            )
    except Exception:
        pass  # License not available or not activated

    # 2. Fall back to .env file (opensource version)
    env_file = data_dir.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    backend = config.get("backend", "").lower()

    _ENV_KEYS = {
        "deepseek":  "DEEPSEEK_API_KEY",
        "qwen":      "DASHSCOPE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
    }

    if not backend:
        # Auto-detect: pick first backend that has a key in env
        for b, env_var in _ENV_KEYS.items():
            if os.environ.get(env_var):
                backend = b
                break

    if not backend:
        return None

    api_key = (
        config.get("api_key")
        or os.environ.get(_ENV_KEYS.get(backend, ""), "")
    )
    if not api_key:
        return None

    base_url = _BACKENDS.get(backend, _BACKENDS["deepseek"])
    default_m, writing_m = _DEFAULT_MODELS.get(backend, _DEFAULT_MODELS["deepseek"])

    return AIClient(
        api_key=api_key,
        cache_db_path=data_dir / "ai_cache.db",
        default_model=config.get("model", {}).get("default", default_m),
        writing_model=config.get("model", {}).get("writing", writing_m),
        base_url=base_url,
    )
