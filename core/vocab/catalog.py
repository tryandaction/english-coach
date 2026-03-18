from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VOCAB_HEADERS = [
    "word",
    "definition_en",
    "definition_zh",
    "example",
    "part_of_speech",
    "synonyms",
    "antonyms",
    "derivatives",
    "collocations",
    "context_sentence",
    "pronunciation",
    "usage_notes",
]

BOOK_GROUP_ORDER = {
    "精选词": 1,
    "核心词": 1,
    "全面词": 2,
    "阅读高频": 3,
    "听力高频": 4,
    "写作词汇": 5,
    "口语词汇": 6,
    "学术桥接": 7,
    "学术词": 8,
    "学科词": 9,
    "高频词": 10,
    "冲刺词": 11,
    "用户自建": 99,
}

EXAM_ORDER = {
    "toefl": 1,
    "ielts": 2,
    "gre": 3,
    "cet": 4,
    "general": 5,
}

EXAM_LABELS = {
    "toefl": "TOEFL",
    "ielts": "IELTS",
    "gre": "GRE",
    "cet": "CET",
    "general": "General",
}

BOOK_BLUEPRINTS = {
    "general_vocab1000": {
        "book_key": "builtin.general.core",
        "name": "General 核心词",
        "description": "适合作为无考试用户或入门用户的基础词汇路径。",
        "exam": "general",
        "source": "content_markdown",
        "level": "B1-B2",
        "topic": "general",
        "book_group": "核心词",
        "recommended_order": 10,
        "source_label": "仓库内置 Markdown 词表（General Vocabulary 1000）",
        "source_type": "builtin_curated",
        "icon": "🧭",
        "color": "#06b6d4",
    },
    "general_oxford3000": {
        "book_key": "builtin.general.highfreq",
        "name": "General 高频词",
        "description": "面向通用英语的高频词扩展，适合在核心词之后继续提升。",
        "exam": "general",
        "source": "content_markdown",
        "level": "B1-B2",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 20,
        "source_label": "仓库内置 Markdown 词表（General Oxford 3000）",
        "source_type": "builtin_curated",
        "icon": "📈",
        "color": "#0ea5e9",
    },
    "toefl_awl": {
        "book_key": "builtin.toefl.academic",
        "name": "TOEFL 学术核心词",
        "description": "以学术阅读和讲座高频词为主，适合 TOEFL 基础阶段。",
        "exam": "toefl",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "academic",
        "book_group": "学术词",
        "recommended_order": 30,
        "source_label": "仓库内置 Markdown 词表（TOEFL Academic / AWL）",
        "source_type": "builtin_curated",
        "icon": "🎓",
        "color": "#2563eb",
    },
    "toefl_awl_academic": {
        "book_key": "builtin.toefl.academic",
        "name": "TOEFL 学术核心词",
        "description": "以学术阅读和讲座高频词为主，适合 TOEFL 基础阶段。",
        "exam": "toefl",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "academic",
        "book_group": "学术词",
        "recommended_order": 30,
        "source_label": "仓库内置 Markdown 词表（TOEFL Academic / AWL）",
        "source_type": "builtin_curated",
        "icon": "🎓",
        "color": "#2563eb",
    },
    "toefl_stem_complete": {
        "book_key": "builtin.toefl.stem",
        "name": "TOEFL 学科词",
        "description": "面向 STEM 场景的补充词汇，目前仍是小规模内置数据。",
        "exam": "toefl",
        "source": "content_markdown",
        "level": "C1",
        "topic": "stem",
        "book_group": "学科词",
        "recommended_order": 40,
        "source_label": "仓库内置 Markdown 词表（TOEFL STEM）",
        "source_type": "builtin_curated",
        "icon": "🔬",
        "color": "#3b82f6",
    },
    "ielts_academic": {
        "book_key": "builtin.ielts.academic",
        "name": "IELTS 学术核心词",
        "description": "面向 IELTS Academic 模块的学术词和写作常见词。",
        "exam": "ielts",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "academic",
        "book_group": "学术词",
        "recommended_order": 50,
        "source_label": "仓库内置 Markdown 词表（IELTS Academic）",
        "source_type": "builtin_curated",
        "icon": "📝",
        "color": "#10b981",
    },
    "ielts_academic_complete": {
        "book_key": "builtin.ielts.academic",
        "name": "IELTS 学术核心词",
        "description": "面向 IELTS Academic 模块的学术词和写作常见词。",
        "exam": "ielts",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "academic",
        "book_group": "学术词",
        "recommended_order": 50,
        "source_label": "仓库内置 Markdown 词表（IELTS Academic）",
        "source_type": "builtin_curated",
        "icon": "📝",
        "color": "#10b981",
    },
    "gre_highfreq": {
        "book_key": "builtin.gre.core",
        "name": "GRE 高频与核心词",
        "description": "适合先建立 GRE 高频识别能力，再进入更大的冲刺词库。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 60,
        "source_label": "仓库内置 Markdown 词表（GRE 高频 / Barron / Taklee 等）",
        "source_type": "builtin_curated",
        "icon": "🧠",
        "color": "#7c3aed",
    },
    "gre_baron334": {
        "book_key": "builtin.gre.core",
        "name": "GRE 高频与核心词",
        "description": "适合先建立 GRE 高频识别能力，再进入更大的冲刺词库。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 60,
        "source_label": "仓库内置 Markdown 词表（GRE 高频 / Barron / Taklee 等）",
        "source_type": "builtin_curated",
        "icon": "🧠",
        "color": "#7c3aed",
    },
    "gre_baron753": {
        "book_key": "builtin.gre.core",
        "name": "GRE 高频与核心词",
        "description": "适合先建立 GRE 高频识别能力，再进入更大的冲刺词库。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 60,
        "source_label": "仓库内置 Markdown 词表（GRE 高频 / Barron / Taklee 等）",
        "source_type": "builtin_curated",
        "icon": "🧠",
        "color": "#7c3aed",
    },
    "gre_barrons333": {
        "book_key": "builtin.gre.core",
        "name": "GRE 高频与核心词",
        "description": "适合先建立 GRE 高频识别能力，再进入更大的冲刺词库。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 60,
        "source_label": "仓库内置 Markdown 词表（GRE 高频 / Barron / Taklee 等）",
        "source_type": "builtin_curated",
        "icon": "🧠",
        "color": "#7c3aed",
    },
    "gre_taklee": {
        "book_key": "builtin.gre.core",
        "name": "GRE 高频与核心词",
        "description": "适合先建立 GRE 高频识别能力，再进入更大的冲刺词库。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "高频词",
        "recommended_order": 60,
        "source_label": "仓库内置 Markdown 词表（GRE 高频 / Barron / Taklee 等）",
        "source_type": "builtin_curated",
        "icon": "🧠",
        "color": "#7c3aed",
    },
    "gre_qitao1787": {
        "book_key": "builtin.gre.sprint",
        "name": "GRE 冲刺扩展词",
        "description": "规模更大、覆盖更广，但内部重复和定义完整度不均，适合作为冲刺补充。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "冲刺词",
        "recommended_order": 70,
        "source_label": "仓库内置 Markdown 词表（GRE 扩展 / 综合 / 冲刺）",
        "source_type": "builtin_curated",
        "icon": "🚀",
        "color": "#8b5cf6",
    },
    "gre_combined_9566": {
        "book_key": "builtin.gre.sprint",
        "name": "GRE 冲刺扩展词",
        "description": "规模更大、覆盖更广，但内部重复和定义完整度不均，适合作为冲刺补充。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "冲刺词",
        "recommended_order": 70,
        "source_label": "仓库内置 Markdown 词表（GRE 扩展 / 综合 / 冲刺）",
        "source_type": "builtin_curated",
        "icon": "🚀",
        "color": "#8b5cf6",
    },
    "gre_magoosh1000": {
        "book_key": "builtin.gre.sprint",
        "name": "GRE 冲刺扩展词",
        "description": "规模更大、覆盖更广，但内部重复和定义完整度不均，适合作为冲刺补充。",
        "exam": "gre",
        "source": "content_markdown",
        "level": "C1",
        "topic": "general",
        "book_group": "冲刺词",
        "recommended_order": 70,
        "source_label": "仓库内置 Markdown 词表（GRE 扩展 / 综合 / 冲刺）",
        "source_type": "builtin_curated",
        "icon": "🚀",
        "color": "#8b5cf6",
    },
    "cet4_core": {
        "book_key": "builtin.cet4.core",
        "name": "CET-4 核心词",
        "description": "当前是小规模内置基础集，适合作为结构验证，不足以覆盖完整 CET-4 词汇需求。",
        "exam": "cet",
        "source": "content_markdown",
        "level": "B1-B2",
        "topic": "general",
        "book_group": "核心词",
        "recommended_order": 80,
        "source_label": "仓库内置 Markdown 词表（CET-4）",
        "source_type": "builtin_curated",
        "icon": "⭐",
        "color": "#f59e0b",
    },
    "cet4_official_complete": {
        "book_key": "builtin.cet4.core",
        "name": "CET-4 核心词",
        "description": "当前是小规模内置基础集，适合作为结构验证，不足以覆盖完整 CET-4 词汇需求。",
        "exam": "cet",
        "source": "content_markdown",
        "level": "B1-B2",
        "topic": "general",
        "book_group": "核心词",
        "recommended_order": 80,
        "source_label": "仓库内置 Markdown 词表（CET-4）",
        "source_type": "builtin_curated",
        "icon": "⭐",
        "color": "#f59e0b",
    },
    "cet6_core": {
        "book_key": "builtin.cet6.core",
        "name": "CET-6 核心词",
        "description": "当前是小规模内置基础集，适合作为结构验证，不足以覆盖完整 CET-6 词汇需求。",
        "exam": "cet",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "general",
        "book_group": "核心词",
        "recommended_order": 90,
        "source_label": "仓库内置 Markdown 词表（CET-6）",
        "source_type": "builtin_curated",
        "icon": "🏁",
        "color": "#f97316",
    },
    "cet6_official_complete": {
        "book_key": "builtin.cet6.core",
        "name": "CET-6 核心词",
        "description": "当前是小规模内置基础集，适合作为结构验证，不足以覆盖完整 CET-6 词汇需求。",
        "exam": "cet",
        "source": "content_markdown",
        "level": "B2-C1",
        "topic": "general",
        "book_group": "核心词",
        "recommended_order": 90,
        "source_label": "仓库内置 Markdown 词表（CET-6）",
        "source_type": "builtin_curated",
        "icon": "🏁",
        "color": "#f97316",
    },
}

QUALITY_FIELDS = (
    "definition_zh",
    "example",
    "part_of_speech",
    "synonyms",
    "collocations",
    "context_sentence",
)

LEGACY_HIDDEN_STEMS = {
    "cet4_core",
    "cet4_official_complete",
    "cet6_core",
    "cet6_official_complete",
    "general_oxford3000",
    "general_vocab1000",
    "gre_baron334",
    "gre_baron753",
    "gre_barrons333",
    "gre_combined_9566",
    "gre_highfreq",
    "gre_magoosh1000",
    "gre_qitao1787",
    "gre_taklee",
    "ielts_academic",
    "ielts_academic_complete",
    "toefl_awl",
    "toefl_awl_academic",
    "toefl_stem_complete",
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_or(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def should_include_builtin_book(stem: str, frontmatter: dict[str, str]) -> bool:
    if _truthy(frontmatter.get("hidden")) or _truthy(frontmatter.get("catalog_hidden")):
        return False
    return stem not in LEGACY_HIDDEN_STEMS


def normalize_exam_type(value: str) -> str:
    raw = (value or "general").strip().lower()
    if raw in {"toefl", "gre", "ielts", "general"}:
        return raw
    if raw.startswith("cet"):
        return "cet"
    if raw in {"all", "both"}:
        return "both"
    return "general"


def normalize_difficulty(value: str) -> str:
    raw = (value or "B1").strip().upper()
    return raw or "B1"


def derive_subject(topic: str, source: str) -> str:
    topic_norm = (topic or "").strip().lower()
    if topic_norm and topic_norm != "general":
        return topic_norm.replace(" ", "_")
    source_norm = (source or "").strip().lower()
    if "academic" in source_norm or "awl" in source_norm:
        return "academic"
    if "stem" in source_norm:
        return "stem"
    return "general"


def normalize_word(word: str) -> str:
    return " ".join((word or "").strip().lower().split())


def parse_vocab_markdown(md_file: Path | None = None, text: str | None = None) -> tuple[dict[str, str], list[dict[str, str]]]:
    raw_text = text if text is not None else md_file.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    body = raw_text
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fm[key.strip()] = value.strip()
            body = parts[2].strip()

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or not lines[0].lower().startswith("word|definition_en|definition_zh"):
        return fm, []

    raw_headers = [part.strip() for part in lines[0].split("|")]
    header_aliases = {
        "pos": "part_of_speech",
        "partofspeech": "part_of_speech",
    }
    normalized_headers = [header_aliases.get(header.lower().replace("_", ""), header.strip()) for header in raw_headers]

    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        row = {header: (parts[idx] if idx < len(parts) else "") for idx, header in enumerate(normalized_headers)}
        word = normalize_word(row.get("word", ""))
        definition_en = row.get("definition_en", "").strip()
        if not word or not definition_en:
            continue
        parsed = {header: row.get(header, "") for header in VOCAB_HEADERS}
        parsed["word"] = word
        parsed["definition_en"] = definition_en
        rows.append(parsed)
    return fm, rows


def markdown_declared_row_count(md_file: Path | None = None, text: str | None = None) -> int:
    raw_text = text if text is not None else md_file.read_text(encoding="utf-8")
    body = raw_text
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines or not lines[0].lower().startswith("word|definition_en|definition_zh"):
        return 0
    return len(lines) - 1


def builtin_book_blueprint(stem: str, frontmatter: dict[str, str], md_file: Path | None = None) -> dict[str, Any]:
    blueprint = dict(BOOK_BLUEPRINTS.get(stem, {}))
    exam = normalize_exam_type(frontmatter.get("exam", blueprint.get("exam", stem)))
    topic = (frontmatter.get("topic") or blueprint.get("topic") or "general").strip().lower() or "general"
    difficulty = normalize_difficulty(frontmatter.get("difficulty", blueprint.get("level", "B1")))
    exam_label = EXAM_LABELS.get(exam, "General")
    group = (
        frontmatter.get("book_group")
        or blueprint.get("book_group")
        or ("学科词" if topic not in {"", "general", "academic"} else ("学术词" if topic == "academic" else "核心词"))
    )
    pretty_stem = stem.replace("_", " ").replace("-", " ").title()
    result = {
        "book_key": frontmatter.get("book_key") or blueprint.get("book_key") or f"builtin.{exam}.{stem}",
        "name": frontmatter.get("name") or blueprint.get("name") or f"{exam_label} {pretty_stem}",
        "description": frontmatter.get("description") or blueprint.get("description") or f"由内置内容目录导入的 {exam_label} 词书，来源于 {md_file.name if md_file else stem}。",
        "exam": exam,
        "source": frontmatter.get("source_kind") or blueprint.get("source") or "content_markdown",
        "level": difficulty,
        "topic": topic,
        "book_group": group,
        "recommended_order": _int_or(
            frontmatter.get("recommended_order") or blueprint.get("recommended_order"),
            500 + EXAM_ORDER.get(exam, 99),
        ),
        "source_label": frontmatter.get("source_label") or blueprint.get("source_label") or f"仓库内置 Markdown 词表（{md_file.name if md_file else stem}）",
        "source_type": frontmatter.get("source_type") or blueprint.get("source_type") or "builtin_curated",
        "icon": frontmatter.get("icon") or blueprint.get("icon") or "📘",
        "color": frontmatter.get("color") or blueprint.get("color") or "#64748b",
    }
    for extra_key in ("series", "skill_focus", "stage", "curation_note"):
        value = frontmatter.get(extra_key) or blueprint.get(extra_key)
        if value:
            result[extra_key] = value
    return result


def _level_rank(level: str) -> int:
    text = (level or "").upper()
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    scores = [order.index(item) for item in order if item in text]
    return max(scores) if scores else 0


def _merge_level(existing: str, incoming: str) -> str:
    if not existing:
        return incoming
    if not incoming:
        return existing
    return incoming if _level_rank(incoming) >= _level_rank(existing) else existing


def _coverage_payload(counts: Counter[str], total: int) -> dict[str, dict[str, int]]:
    if total <= 0:
        return {field: {"filled": 0, "pct": 0} for field in QUALITY_FIELDS}
    return {
        field: {
            "filled": int(counts.get(field, 0)),
            "pct": round(int(counts.get(field, 0)) * 100 / total),
        }
        for field in QUALITY_FIELDS
    }


def better_text(existing: Any, incoming: Any) -> str | None:
    incoming_text = str(incoming or "").strip()
    existing_text = str(existing or "").strip()
    if not incoming_text:
        return None
    if not existing_text:
        return incoming_text
    if len(incoming_text) > len(existing_text):
        return incoming_text
    return None


def merge_word_payload(existing_row: dict[str, Any] | None, incoming: dict[str, Any], *, exam_type: str, topic: str, subject_domain: str, difficulty: str, level: int, difficulty_score: int) -> dict[str, Any]:
    if existing_row and (existing_row.get("source") or "").lower() == "user":
        return {}

    updates: dict[str, Any] = {}
    for field in [
        "definition_en",
        "definition_zh",
        "example",
        "synonyms",
        "antonyms",
        "derivatives",
        "collocations",
        "context_sentence",
        "part_of_speech",
        "pronunciation",
        "usage_notes",
    ]:
        chosen = better_text((existing_row or {}).get(field), incoming.get(field))
        if chosen is not None:
            updates[field] = chosen

    existing_exam = normalize_exam_type((existing_row or {}).get("exam_type", "general"))
    if exam_type != "general":
        if existing_exam in {"general", ""}:
            updates["exam_type"] = exam_type
        elif existing_exam != exam_type:
            updates["exam_type"] = "both"

    existing_topic = (existing_row or {}).get("category", "")
    if topic and topic != "general" and existing_topic in {"", "general"}:
        updates["category"] = topic

    existing_subject = (existing_row or {}).get("subject_domain", "")
    if subject_domain and subject_domain != "general" and existing_subject in {"", "general"}:
        updates["subject_domain"] = subject_domain

    existing_diff = (existing_row or {}).get("difficulty", "")
    if difficulty and _level_rank(difficulty) >= _level_rank(existing_diff):
        updates["difficulty"] = difficulty

    existing_level = int((existing_row or {}).get("level") or 0)
    if level > existing_level:
        updates["level"] = level

    existing_score = int((existing_row or {}).get("difficulty_score") or 0)
    if difficulty_score > existing_score:
        updates["difficulty_score"] = difficulty_score

    return updates


def scan_content_library(content_dirs: list[Path]) -> dict[str, Any]:
    grouped_books: dict[str, dict[str, Any]] = {}
    global_words: dict[str, set[str]] = defaultdict(set)
    exam_words: dict[str, set[str]] = defaultdict(set)
    group_words: dict[str, set[str]] = defaultdict(set)
    file_stats: list[dict[str, Any]] = []
    total_entries = 0
    declared_entries = 0
    global_quality: Counter[str] = Counter()

    for vocab_dir in [path for path in content_dirs if path.exists()]:
        for md_file in sorted(vocab_dir.glob("*.md")):
            fm, rows = parse_vocab_markdown(md_file=md_file)
            if not should_include_builtin_book(md_file.stem, fm):
                continue
            declared_rows = markdown_declared_row_count(md_file=md_file)
            declared_entries += declared_rows
            if not rows:
                if declared_rows:
                    file_stats.append(
                        {
                            "file": md_file.name,
                            "path": md_file.as_posix(),
                            "directory": vocab_dir.name,
                            "book_key": "",
                            "book_name": "",
                            "exam": normalize_exam_type(md_file.stem),
                            "source": md_file.stem,
                            "topic": "general",
                            "difficulty": "",
                            "row_count": declared_rows,
                            "usable_rows": 0,
                            "unique_words": 0,
                            "duplicate_words": 0,
                            "incomplete_rows": declared_rows,
                        }
                    )
                continue

            stem = md_file.stem
            blueprint = builtin_book_blueprint(stem, fm, md_file)
            exam = normalize_exam_type(blueprint["exam"])
            key = blueprint["book_key"]
            group = grouped_books.setdefault(
                key,
                {
                    **blueprint,
                    "is_builtin": True,
                    "files": [],
                    "declared_word_count": 0,
                    "raw_word_count": 0,
                    "word_count": 0,
                    "duplicate_words": 0,
                    "_row_count": 0,
                    "_quality": Counter(),
                    "_words": set(),
                    "_duplicates": Counter(),
                },
            )
            group["level"] = _merge_level(group.get("level", ""), blueprint.get("level", ""))

            words_seen: list[str] = []
            local_quality: Counter[str] = Counter()
            for row in rows:
                word = normalize_word(row.get("word", ""))
                if not word:
                    continue
                total_entries += 1
                group["_row_count"] += 1
                words_seen.append(word)
                group["_duplicates"][word] += 1
                group["_words"].add(word)
                global_words[word].add(md_file.as_posix())
                exam_words[exam].add(word)
                group_words[group["book_group"]].add(word)
                for field in QUALITY_FIELDS:
                    if str(row.get(field, "")).strip():
                        local_quality[field] += 1
                        group["_quality"][field] += 1
                        global_quality[field] += 1

            local_counts = Counter(words_seen)
            file_stats.append(
                {
                    "file": md_file.name,
                    "path": md_file.as_posix(),
                    "directory": vocab_dir.name,
                    "book_key": key,
                    "book_name": blueprint["name"],
                    "exam": exam,
                    "source": fm.get("source", stem),
                    "topic": fm.get("topic", "general"),
                    "difficulty": normalize_difficulty(fm.get("difficulty", blueprint.get("level", "B1"))),
                    "row_count": declared_rows,
                    "usable_rows": len(rows),
                    "unique_words": len(set(words_seen)),
                    "duplicate_words": sum(count - 1 for count in local_counts.values() if count > 1),
                    "incomplete_rows": max(0, declared_rows - len(rows)),
                    "quality": _coverage_payload(local_quality, len(rows)),
                }
            )
            group["files"].append(
                {
                    "file": md_file.name,
                    "path": md_file.as_posix(),
                    "directory": vocab_dir.name,
                    "row_count": declared_rows,
                    "usable_rows": len(rows),
                    "unique_words": len(set(words_seen)),
                    "quality": _coverage_payload(local_quality, len(rows)),
                }
            )
            group["declared_word_count"] += declared_rows
            group["raw_word_count"] += len(rows)

    books: list[dict[str, Any]] = []
    for key, group in grouped_books.items():
        duplicate_words = sum(count - 1 for count in group["_duplicates"].values() if count > 1)
        books.append(
            {
                k: v
                for k, v in group.items()
                if not k.startswith("_")
            }
            | {
                "word_count": len(group["_words"]),
                "duplicate_words": duplicate_words,
                "quality": _coverage_payload(group["_quality"], int(group["_row_count"] or 0)),
                "files": sorted(group["files"], key=lambda item: item["path"]),
            }
        )

    books.sort(
        key=lambda item: (
            item.get("recommended_order", 999),
            EXAM_ORDER.get(item.get("exam", "general"), 99),
            BOOK_GROUP_ORDER.get(item.get("book_group", "用户自建"), 99),
            item.get("name", ""),
        )
    )

    by_exam = [
        {"exam": exam, "label": EXAM_LABELS.get(exam, exam.upper()), "word_count": len(words)}
        for exam, words in sorted(exam_words.items(), key=lambda item: EXAM_ORDER.get(item[0], 99))
    ]
    by_group = [
        {"book_group": group, "word_count": len(words)}
        for group, words in sorted(group_words.items(), key=lambda item: BOOK_GROUP_ORDER.get(item[0], 99))
    ]
    cross_file_duplicates = sum(1 for files in global_words.values() if len(files) > 1)
    recommended_path = [
        {
            "book_key": book["book_key"],
            "name": book["name"],
            "exam": book["exam"],
            "book_group": book["book_group"],
            "recommended_order": book["recommended_order"],
            "word_count": book["word_count"],
            "description": book["description"],
        }
        for book in books
    ]

    return {
        "books": books,
        "recommended_path": recommended_path,
        "stats": {
            "file_count": len(file_stats),
            "declared_entries": declared_entries,
            "total_entries": total_entries,
            "incomplete_entries": max(0, declared_entries - total_entries),
            "unique_words": len(global_words),
            "cross_file_duplicates": cross_file_duplicates,
            "quality": _coverage_payload(global_quality, total_entries),
            "by_exam": by_exam,
            "by_group": by_group,
        },
        "files": sorted(file_stats, key=lambda item: item["path"]),
    }


def _coerce_import_word(row: dict[str, Any]) -> dict[str, str]:
    return {
        "word": normalize_word(str(row.get("word", ""))),
        "definition_en": str(row.get("definition_en", "")).strip(),
        "definition_zh": str(row.get("definition_zh", "")).strip(),
        "example": str(row.get("example", "")).strip(),
        "part_of_speech": str(row.get("part_of_speech", row.get("pos", ""))).strip(),
        "synonyms": str(row.get("synonyms", "")).strip(),
        "antonyms": str(row.get("antonyms", "")).strip(),
        "derivatives": str(row.get("derivatives", "")).strip(),
        "collocations": str(row.get("collocations", "")).strip(),
        "context_sentence": str(row.get("context_sentence", "")).strip(),
        "pronunciation": str(row.get("pronunciation", "")).strip(),
        "usage_notes": str(row.get("usage_notes", "")).strip(),
    }


def detect_import_format(payload: str, format_hint: str = "auto") -> str:
    hinted = (format_hint or "auto").strip().lower()
    if hinted in {"json", "csv", "md", "markdown"}:
        return "markdown" if hinted in {"md", "markdown"} else hinted

    text = (payload or "").lstrip()
    if not text:
        return "json"
    if text.startswith("{") or text.startswith("["):
        return "json"
    if text.startswith("---") or "word|definition_en|definition_zh" in text.lower():
        return "markdown"
    return "csv"


def parse_import_payload(payload: str, format_hint: str = "auto") -> dict[str, Any]:
    fmt = detect_import_format(payload, format_hint)
    errors: list[str] = []
    warnings: list[str] = []
    book_meta: dict[str, Any] = {}
    words: list[dict[str, str]] = []

    if fmt == "json":
        data = json.loads(payload)
        if isinstance(data, dict):
            book_meta = dict(data.get("book") or {})
            raw_words = data.get("words") or data.get("entries") or []
        elif isinstance(data, list):
            raw_words = data
        else:
            raise ValueError("JSON import must be an object or an array")
        if not isinstance(raw_words, list):
            raise ValueError("JSON field 'words' must be an array")
        words = [_coerce_import_word(item or {}) for item in raw_words]
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(payload))
        if not reader.fieldnames:
            raise ValueError("CSV import requires a header row")
        normalized_headers = {name.strip().lower() for name in reader.fieldnames}
        if "word" not in normalized_headers:
            raise ValueError("CSV import requires a 'word' column")
        words = [_coerce_import_word(row) for row in reader]
    else:
        book_meta, words = parse_vocab_markdown(text=payload)

    cleaned: list[dict[str, str]] = []
    duplicates = Counter()
    for index, word in enumerate(words, start=1):
        normalized = _coerce_import_word(word)
        if not normalized["word"]:
            errors.append(f"第 {index} 行缺少 word")
            continue
        if not normalized["definition_en"]:
            errors.append(f"第 {index} 行缺少 definition_en")
            continue
        duplicates[normalized["word"]] += 1
        cleaned.append(normalized)

    duplicate_words = sorted([word for word, count in duplicates.items() if count > 1])
    if duplicate_words:
        warnings.append(f"导入内容中存在 {len(duplicate_words)} 个重复词，将按规则合并。")

    return {
        "format": fmt,
        "book": {
            "name": str(book_meta.get("name", "")).strip(),
            "description": str(book_meta.get("description", "")).strip(),
            "exam": normalize_exam_type(str(book_meta.get("exam", "general"))),
            "source": str(book_meta.get("source", "user_import")).strip() or "user_import",
            "level": normalize_difficulty(str(book_meta.get("difficulty", book_meta.get("level", "B1")))),
            "topic": str(book_meta.get("topic", "general")).strip() or "general",
        },
        "words": cleaned,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "rows": len(words),
            "valid_words": len(cleaned),
            "duplicate_words": len(duplicate_words),
            "unique_words": len({row["word"] for row in cleaned}),
        },
    }
