from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from .context import LearnerSnapshot


@dataclass
class CoachActionDecision:
    action: str
    skill: str
    reason: str
    title: str
    practice_mode: str = "single"
    question_types: list[str] = field(default_factory=list)
    subject: str = ""
    time_limit: int = 0
    route_page: str = ""
    priority: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


class CoachPolicyService:
    def _weak_mode(self, snapshot: LearnerSnapshot) -> str:
        for item in snapshot.weak_areas:
            text = str(item or "")
            if text.startswith("reading"):
                return "reading"
            if text.startswith("listening"):
                return "listening"
            if text.startswith("writing"):
                return "writing"
            if text.startswith("speaking"):
                return "speaking"
            if text.startswith("vocab"):
                return "vocab"
        candidates = [(mode, score) for mode, score in snapshot.recent_mode_accuracy.items() if mode in {"reading", "listening", "writing", "speaking", "vocab"}]
        if candidates:
            return sorted(candidates, key=lambda item: item[1])[0][0]
        return "reading" if snapshot.exam in {"toefl", "gre"} else "listening"

    def _output_due_mode(self, snapshot: LearnerSnapshot) -> str:
        if not snapshot.ai_ready:
            return ""
        if not snapshot.last_output_at:
            return "writing"
        try:
            last_output_at = datetime.fromisoformat(snapshot.last_output_at)
        except ValueError:
            return "writing"
        if datetime.now() - last_output_at >= timedelta(days=2):
            return "speaking" if snapshot.last_output_mode == "writing" else "writing"
        return ""

    def decide(self, snapshot: LearnerSnapshot) -> CoachActionDecision:
        if snapshot.plan_status == "done" and snapshot.today_sessions > 0:
            return CoachActionDecision(
                action="stay_silent",
                skill="",
                reason="今天已经完成主要任务，先保持节奏，不再堆新任务。",
                title="今天先收口",
                route_page="home",
            )

        if snapshot.review_due_count >= max(snapshot.review_batch_size, 5) or snapshot.frequent_forgetting_count > 0:
            return CoachActionDecision(
                action="review_words",
                skill="vocab",
                reason="复习池已经有积压或高错词，先清复习最划算。",
                title="先清词汇复习",
                practice_mode="targeted",
                route_page="vocab",
                priority=100,
            )

        output_due_mode = self._output_due_mode(snapshot)
        if output_due_mode == "writing":
            return CoachActionDecision(
                action="write_short",
                skill="writing",
                reason="最近缺少一次高价值输出训练，先补一个短写作。",
                title="补一次短写作",
                practice_mode="single",
                route_page="writing",
                time_limit=15,
                priority=80,
            )
        if output_due_mode == "speaking":
            return CoachActionDecision(
                action="speak_short",
                skill="speaking",
                reason="最近缺少一次口语输出训练，先补一个短口语。",
                title="补一次短口语",
                practice_mode="single",
                route_page="speaking",
                time_limit=12,
                priority=80,
            )

        weak_mode = self._weak_mode(snapshot)
        if weak_mode == "reading":
            return CoachActionDecision(
                action="reading_focus",
                skill="reading",
                reason="当前更值得优先修的还是阅读理解或题型命中。",
                title="做 1 篇定向阅读",
                practice_mode="targeted",
                question_types=["inference"] if snapshot.exam in {"toefl", "gre"} else ["tfng"],
                route_page="reading",
                time_limit=15,
                priority=70,
            )
        if weak_mode == "listening":
            return CoachActionDecision(
                action="listening_focus",
                skill="listening",
                reason="当前更值得优先修的是听力命中和节奏稳定性。",
                title="做 1 组定向听力",
                practice_mode="targeted",
                question_types=["organization"] if snapshot.exam == "toefl" else ["multiple_choice"],
                route_page="listening",
                time_limit=12,
                priority=70,
            )

        if snapshot.today_sessions > 0 and snapshot.plan_status != "done":
            return CoachActionDecision(
                action="micro_test",
                skill=weak_mode if weak_mode in {"reading", "listening"} else "reading",
                reason="今天已经开始学习，适合补一个最短的定向 micro test 把结果感做出来。",
                title="补一个 micro test",
                practice_mode="targeted",
                question_types=["factual"] if snapshot.exam == "toefl" else [],
                route_page=weak_mode if weak_mode in {"reading", "listening"} else "reading",
                time_limit=8,
                priority=60,
            )

        if snapshot.deck_total < max(60, snapshot.review_batch_size * 10) or snapshot.review_due_count == 0:
            return CoachActionDecision(
                action="new_words",
                skill="vocab",
                reason="当前复习债务不重，可以补一小批新词扩充输入。",
                title="加一批新词",
                practice_mode="single",
                route_page="vocab",
                priority=50,
            )

        return CoachActionDecision(
            action="stay_silent",
            skill="",
            reason="当前没有比保持安静更高价值的下一步动作。",
            title="先保持当前节奏",
            route_page="home",
        )
