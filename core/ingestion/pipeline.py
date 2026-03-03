"""
Document ingestion pipeline.
Parses MD/TXT files, chunks them, assigns metadata, embeds, stores in ChromaDB.
Run once: python -m core.ingestion.pipeline --source ./path/to/content
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import frontmatter


class ContentType(str, Enum):
    VOCAB = "vocab"
    READING = "reading"
    WRITING = "writing"
    SPEAKING = "speaking"
    GRAMMAR = "grammar"
    PHYSICS = "physics"
    GENERAL = "general"


CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Physics / STEM high-frequency terms (used for difficulty boosting)
STEM_TERMS = {
    "quantum", "eigenvalue", "hamiltonian", "lagrangian", "entropy", "partition",
    "divergence", "gradient", "curl", "tensor", "manifold", "eigenstate",
    "perturbation", "commutator", "wavefunction", "schrödinger", "maxwell",
    "lorentz", "relativistic", "thermodynamic", "statistical", "canonical",
    "microstate", "macrostate", "boltzmann", "fermi", "bose", "dirac",
}

# Keyword hints for content_type detection
_TYPE_HINTS: dict[ContentType, list[str]] = {
    ContentType.VOCAB: ["vocabulary", "vocab", "words", "glossary", "terms"],
    ContentType.READING: ["reading", "passage", "article", "text"],
    ContentType.WRITING: ["writing", "essay", "composition", "awa", "task2"],
    ContentType.SPEAKING: ["speaking", "task1", "task2", "task3", "task4", "oral"],
    ContentType.GRAMMAR: ["grammar", "syntax", "tense", "article", "preposition"],
    ContentType.PHYSICS: ["physics", "mechanics", "electromagnetism", "quantum",
                          "thermodynamics", "optics", "relativity", "nuclear"],
}

_EXAM_HINTS: dict[str, list[str]] = {
    "toefl": ["toefl", "ibt"],
    "gre": ["gre", "verbal", "awa", "quant"],
    "ielts": ["ielts", "band"],
    "cet": ["cet", "cet4", "cet6", "四级", "六级"],
    "general": [],
}


@dataclass
class Chunk:
    chunk_id: str
    source_file: str
    content_type: ContentType
    text: str
    difficulty: str          # A1–C2
    topic: str               # physics / academic / daily / general
    exam: str                # toefl / gre / ielts / cet / general
    language: str            # en / zh / bilingual
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _detect_language(text: str) -> str:
    zh_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    ratio = zh_chars / max(len(text), 1)
    if ratio > 0.3:
        return "zh"
    if ratio > 0.05:
        return "bilingual"
    return "en"


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:")
    if not word:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _flesch_kincaid_grade(text: str) -> float:
    words = text.split()
    if not words:
        return 8.0
    sentences = max(1, text.count(".") + text.count("?") + text.count("!"))
    syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59


def _stem_density(text: str) -> float:
    words = {w.lower().strip(".,!?;:") for w in text.split()}
    return len(words & STEM_TERMS) / max(len(words), 1)


def _grade_to_cefr(grade: float, stem_boost: float = 0.0) -> str:
    adjusted = grade + stem_boost * 3
    thresholds = [(5, "A1"), (7, "A2"), (9, "B1"), (11, "B2"), (13, "C1")]
    for threshold, level in thresholds:
        if adjusted <= threshold:
            return level
    return "C2"


def _infer_content_type(path: Path, text: str) -> ContentType:
    path_lower = str(path).lower()
    for ctype, hints in _TYPE_HINTS.items():
        if any(h in path_lower for h in hints):
            return ctype
    text_lower = text[:500].lower()
    for ctype, hints in _TYPE_HINTS.items():
        if any(h in text_lower for h in hints):
            return ctype
    return ContentType.GENERAL


def _infer_exam(path: Path) -> str:
    path_lower = str(path).lower()
    for exam, hints in _EXAM_HINTS.items():
        if any(h in path_lower for h in hints):
            return exam
    return "general"


def _infer_topic(text: str, content_type: ContentType) -> str:
    if content_type == ContentType.PHYSICS:
        return "physics"
    if _stem_density(text) > 0.02:
        return "academic"
    if content_type in (ContentType.READING, ContentType.WRITING):
        return "academic"
    return "general"


# ---------------------------------------------------------------------------
# Chunking strategies
# ---------------------------------------------------------------------------

def _chunk_by_headers(text: str) -> list[str]:
    """Split on ## or ### markdown headers."""
    parts = re.split(r"\n(?=#{1,3} )", text)
    return [p.strip() for p in parts if len(p.strip()) > 80]


def _chunk_by_paragraphs(text: str) -> list[str]:
    """Split on blank lines, keep paragraphs >= 60 chars."""
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if len(p.strip()) >= 60]


def _chunk_vocab_entries(text: str) -> list[str]:
    """
    Vocab files: each entry starts with a bold word or a numbered item.
    Pattern: **word** or `word` or '1. word'
    """
    entries = re.split(r"\n(?=\*\*|\`|\d+\.)", text)
    return [e.strip() for e in entries if len(e.strip()) > 20]


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------

class IngestionPipeline:
    """
    Parse source files → chunk → assign metadata → return Chunk list.
    Embedding and storage are handled by KnowledgeBase.
    """

    def ingest_file(self, path: Path) -> list[Chunk]:
        suffix = path.suffix.lower()
        if suffix in (".md", ".txt"):
            return self._ingest_markdown(path)
        if suffix == ".pdf":
            return self._ingest_pdf(path)
        if suffix in (".docx", ".doc"):
            return self._ingest_docx(path)
        return []

    def ingest_directory(self, directory: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        supported = {".md", ".txt", ".pdf", ".docx"}
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in supported:
                chunks.extend(self.ingest_file(path))
        return chunks

    # ------------------------------------------------------------------

    def _ingest_pdf(self, path: Path) -> list[Chunk]:
        try:
            import pypdf
        except ImportError:
            return []

        try:
            reader = pypdf.PdfReader(str(path))
        except Exception:
            return []

        # Extract text page by page, then chunk
        pages_text = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                pages_text.append(t)

        full_text = "\n\n".join(pages_text)
        if not full_text.strip():
            return []

        return self._text_to_chunks(full_text, path, meta={})

    def _ingest_docx(self, path: Path) -> list[Chunk]:
        try:
            import docx
        except ImportError:
            return []

        try:
            doc = docx.Document(str(path))
        except Exception:
            return []

        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        if not full_text.strip():
            return []

        return self._text_to_chunks(full_text, path, meta={})

    def _text_to_chunks(self, text: str, path: Path, meta: dict) -> list[Chunk]:
        """Shared chunking logic for PDF/DOCX extracted text."""
        content_type = _infer_content_type(path, text)
        exam = _infer_exam(path)
        language = _detect_language(text)

        if content_type == ContentType.VOCAB:
            raw_chunks = _chunk_vocab_entries(text)
        elif content_type in (ContentType.READING, ContentType.WRITING):
            raw_chunks = _chunk_by_paragraphs(text)
        else:
            raw_chunks = _chunk_by_headers(text) or _chunk_by_paragraphs(text)

        chunks: list[Chunk] = []
        for chunk_text in raw_chunks:
            grade = _flesch_kincaid_grade(chunk_text)
            stem = _stem_density(chunk_text)
            difficulty = meta.get("difficulty") or _grade_to_cefr(grade, stem)
            topic = meta.get("topic") or _infer_topic(chunk_text, content_type)

            chunk = Chunk(
                chunk_id=_sha256(str(path) + chunk_text[:50]),
                source_file=str(path),
                content_type=content_type,
                text=chunk_text,
                difficulty=difficulty,
                topic=topic,
                exam=exam,
                language=language,
                metadata={"fk_grade": round(grade, 1), "stem_density": round(stem, 3), **meta},
            )
            chunks.append(chunk)

        return chunks

    # ------------------------------------------------------------------

    def _ingest_markdown(self, path: Path) -> list[Chunk]:
        raw = path.read_text(encoding="utf-8", errors="ignore")

        # Parse YAML front-matter if present
        try:
            post = frontmatter.loads(raw)
            text = post.content
            meta = dict(post.metadata)
        except Exception:
            text = raw
            meta = {}

        content_type = ContentType(meta.get("content_type", "")) \
            if meta.get("content_type") in ContentType._value2member_map_ \
            else _infer_content_type(path, text)

        exam = meta.get("exam", _infer_exam(path))
        language = _detect_language(text)

        # Choose chunking strategy
        if content_type == ContentType.VOCAB:
            raw_chunks = _chunk_vocab_entries(text)
        elif content_type in (ContentType.READING, ContentType.WRITING):
            raw_chunks = _chunk_by_paragraphs(text)
        else:
            raw_chunks = _chunk_by_headers(text) or _chunk_by_paragraphs(text)

        chunks: list[Chunk] = []
        for chunk_text in raw_chunks:
            grade = _flesch_kincaid_grade(chunk_text)
            stem = _stem_density(chunk_text)
            difficulty = meta.get("difficulty") or _grade_to_cefr(grade, stem)
            topic = meta.get("topic") or _infer_topic(chunk_text, content_type)

            chunk = Chunk(
                chunk_id=_sha256(str(path) + chunk_text[:50]),
                source_file=str(path),
                content_type=content_type,
                text=chunk_text,
                difficulty=difficulty,
                topic=topic,
                exam=exam,
                language=language,
                metadata={
                    "fk_grade": round(grade, 1),
                    "stem_density": round(stem, 3),
                    **meta,
                },
            )
            chunks.append(chunk)

        return chunks
