from __future__ import annotations

from typing import Optional

_QUESTION_LABELS = {
    "factual": "Factual",
    "inference": "Inference",
    "vocabulary": "Vocabulary",
    "negative_factual": "Negative Factual",
    "rhetorical_purpose": "Rhetorical Purpose",
    "reference": "Reference",
    "sentence_simplification": "Sentence Simplification",
    "insert_text": "Insert Text",
    "prose_summary": "Prose Summary",
    "fill_table": "Fill Table",
    "tfng": "TFNG",
    "matching_headings": "Matching Headings",
    "summary_completion": "Summary Completion",
    "matching_information": "Matching Information",
    "short_answer": "Short Answer",
    "diagram_label": "Diagram Label",
    "detail": "Detail",
    "organization": "Organization",
    "attitude": "Attitude",
    "multiple_choice": "Multiple Choice",
    "form_completion": "Form Completion",
    "matching": "Matching",
}

_WRITING_LABELS = {
    "independent": "Independent Writing",
    "integrated": "Integrated Writing",
    "task1": "Task 1",
    "task2": "Task 2",
    "issue": "Issue Essay",
    "argument": "Argument Essay",
    "essay": "Essay",
    "translation": "Translation",
    "build_sentence": "Build a Sentence",
    "write_email": "Write an Email",
    "academic_discussion": "Academic Discussion",
}

_SPEAKING_LABELS = {
    "independent": "Independent",
    "listen_repeat": "Listen & Repeat",
    "virtual_interview": "Virtual Interview",
    "part1": "Part 1",
    "part2": "Part 2",
    "part3": "Part 3",
}

_DIALOGUE_LABELS = {
    "conversation": "Conversation",
    "monologue": "Lecture",
}


def _label(value: Optional[str], mapping: dict[str, str]) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    return mapping.get(key, key.replace("_", " ").title())


def build_reading_recap(
    *,
    topic: str,
    correct: int,
    answered: int,
    requested_question_types: Optional[list[str]] = None,
    actual_question_types: Optional[list[str]] = None,
) -> dict[str, str]:
    focus = requested_question_types or actual_question_types or []
    focus_label = _label(focus[0] if focus else "", _QUESTION_LABELS)
    accuracy = round(correct * 100 / max(answered, 1))
    headline = f"阅读完成：{correct}/{answered} 题正确"
    if topic:
        headline += f" · {topic}"
    if focus_label:
        headline += f" · {focus_label}"
    if accuracy >= 80:
        improved_point = "这轮阅读命中更稳，关键信息定位已经更快。"
    elif focus_label:
        improved_point = f"{focus_label} 题已经开始成型，至少能把失分点单独看见。"
    else:
        improved_point = "这轮已经把文章主线和主要失分点暴露出来了。"
    if accuracy >= 80:
        next_step = "明天继续换一篇同考试素材，保持速度和稳定命中。"
    elif focus_label:
        next_step = f"明天优先再做 1 轮 {focus_label}，先把失分点压下来。"
    else:
        next_step = "明天继续做 1 篇短阅读，把正确率先拉稳。"
    return {"result_headline": headline, "improved_point": improved_point, "next_step": next_step}


def build_listening_recap(
    *,
    topic: str,
    correct: int,
    total: int,
    question_type: str = "",
    dialogue_type: str = "",
) -> dict[str, str]:
    accuracy = round(correct * 100 / max(total, 1))
    qtype_label = _label(question_type, _QUESTION_LABELS)
    dtype_label = _label(dialogue_type, _DIALOGUE_LABELS)
    headline = f"听力完成：{correct}/{total} 题正确"
    if topic:
        headline += f" · {topic}"
    if qtype_label:
        headline += f" · {qtype_label}"
    elif dtype_label:
        headline += f" · {dtype_label}"
    if accuracy >= 80:
        improved_point = "这轮听力主线抓得更稳，细节定位也更快了。"
    elif qtype_label:
        improved_point = f"{qtype_label} 这一类题已经能更清楚暴露漏听和误判。"
    else:
        improved_point = "这轮至少把主线理解和细节失分点分开看清了。"
    if accuracy >= 80:
        next_step = "明天继续保持同考试短听力，逐步增加长度或速度。"
    elif qtype_label:
        next_step = f"明天再做 1 组 {qtype_label} 听力，把漏听和误判单独修掉。"
    else:
        next_step = "明天再做 1 组短听力，先把主线听懂和细节定位拉稳。"
    return {"result_headline": headline, "improved_point": improved_point, "next_step": next_step}


def build_writing_recap(*, task_type: str, overall: float, score_max: float, word_count: int) -> dict[str, str]:
    task_label = _label(task_type, _WRITING_LABELS)
    headline = f"写作完成：{overall:g}/{score_max:g}"
    if task_label:
        headline += f" · {task_label}"
    if word_count:
        headline += f" · {word_count} 词"
    if overall >= score_max * 0.7:
        improved_point = "这轮输出已经更完整，结构和展开度开始稳定。"
    else:
        improved_point = "这轮已经把最需要修的结构或语法问题暴露出来了。"
    if overall >= score_max * 0.7:
        next_step = "明天换一个任务类型或新题面，保持输出频率，不要只重复同题。"
    else:
        next_step = "明天先按这次反馈重写一个更短版本，把结构和语法先修正。"
    return {"result_headline": headline, "improved_point": improved_point, "next_step": next_step}


def build_speaking_recap(*, task_type: str, overall: float, score_max: float, word_count: int) -> dict[str, str]:
    task_label = _label(task_type, _SPEAKING_LABELS)
    headline = f"口语完成：{overall:g}/{score_max:g}"
    if task_label:
        headline += f" · {task_label}"
    if word_count:
        headline += f" · {word_count} 词"
    if overall >= score_max * 0.7:
        improved_point = "这轮表达已经更顺，展开度和流利度开始稳定。"
    else:
        improved_point = "这轮已经把高频卡壳点和结构问题单独暴露出来了。"
    if overall >= score_max * 0.7:
        next_step = "明天继续换题保持输出手感，重点维持流利度和展开度。"
    else:
        next_step = "明天先做 1 轮更短口语，把表达结构和高频卡壳点修掉。"
    return {"result_headline": headline, "improved_point": improved_point, "next_step": next_step}


def build_mock_section_recap(
    *,
    section: str,
    correct: int,
    total: int,
    overall: float = 0.0,
    score_max: float = 0.0,
) -> dict[str, str]:
    section_label = str(section or "section").replace("_", " ").title()
    if total > 0:
        accuracy = round(correct * 100 / max(total, 1))
        result_card = f"Mock {section_label} 完成：{correct}/{total}"
    else:
        accuracy = round(overall * 100 / max(score_max, 1)) if score_max > 0 else 0
        result_card = f"Mock {section_label} 完成"
        if score_max > 0:
            result_card += f"：{overall:g}/{score_max:g}"
    if accuracy >= 80:
        improved_point = f"{section_label} 这一段已经更稳，节奏和命中率都在往上走。"
    elif accuracy >= 60:
        improved_point = f"{section_label} 已经具备基本稳定性，至少把主要失分点看清了。"
    else:
        improved_point = f"{section_label} 这一段已经把最需要单独修的短板暴露出来了。"
    tomorrow_reason = f"明天先回到 {section_label} 做一次更短的专项修正，再回模考会更划算。"
    return {
        "result_card": result_card,
        "improved_point": improved_point,
        "tomorrow_reason": tomorrow_reason,
        "result_headline": result_card,
        "next_step": tomorrow_reason,
    }


def build_mock_exam_recap(*, exam: str, total_correct: int, total_questions: int, weak_areas: list[str]) -> dict[str, str]:
    exam_label = str(exam or "mock").upper()
    result_card = f"{exam_label} Mock 完成：{total_correct}/{total_questions}"
    if weak_areas:
        improved_point = "整套 section 已经跑通，当前最明显的短板已经被定位出来。"
        tomorrow_reason = f"明天先回专项训练处理 {weak_areas[0]}，再做下一轮 mock 会更有效。"
    else:
        improved_point = "整套流程已经可以完整跑通，当前更值得优化的是稳定度和时间分配。"
        tomorrow_reason = "明天继续回来做一轮更短的 section 复盘，保持整套考试手感。"
    return {
        "result_card": result_card,
        "improved_point": improved_point,
        "tomorrow_reason": tomorrow_reason,
        "result_headline": result_card,
        "next_step": tomorrow_reason,
    }
