from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

DEFAULT_PREFERRED_STUDY_TIME = "20:00"
DEFAULT_QUIET_HOURS = {"start": "22:30", "end": "08:00"}
VALID_REMINDER_LEVELS = {"off", "basic", "coach"}
RECOVERY_WINDOW_HOURS = 6


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        parsed = json.loads(value)
    except Exception:
        return default
    return parsed if parsed is not None else default


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _safe_time(raw: Any, fallback: str) -> str:
    for candidate in (str(raw or "").strip(), fallback):
        try:
            datetime.strptime(candidate, "%H:%M")
            return candidate
        except ValueError:
            continue
    return fallback


def _parse_time(raw: Any, fallback: str) -> time:
    return datetime.strptime(_safe_time(raw, fallback), "%H:%M").time()


def _combine(day: date, raw_time: Any, fallback: str) -> datetime:
    return datetime.combine(day, _parse_time(raw_time, fallback))


def _is_quiet_hours(now: datetime, quiet_hours: dict[str, Any]) -> bool:
    start = _parse_time(quiet_hours.get("start"), DEFAULT_QUIET_HOURS["start"])
    end = _parse_time(quiet_hours.get("end"), DEFAULT_QUIET_HOURS["end"])
    current = now.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _mode_key(mode: str | None) -> str:
    text = str(mode or "").strip().lower()
    if text.startswith("mock_"):
        return "mock"
    return text or "other"


class CoachNotificationDispatcher:
    def __init__(self) -> None:
        self._desktop_supported: Optional[bool] = None

    def desktop_supported(self) -> bool:
        if self._desktop_supported is not None:
            return self._desktop_supported
        try:
            import desktop_notifier  # noqa: F401

            self._desktop_supported = True
        except Exception:
            self._desktop_supported = False
        return self._desktop_supported

    def send(self, channel: str, title: str, body: str, settings: dict[str, Any], payload: dict[str, Any]) -> bool:
        if channel == "in_app":
            return True
        if channel == "desktop":
            return self._send_desktop(title, body)
        if channel == "bark":
            return self._send_bark(title, body, settings)
        if channel == "webhook":
            return self._send_webhook(title, body, settings, payload)
        return False

    def _send_desktop(self, title: str, body: str) -> bool:
        if not self.desktop_supported():
            return False
        try:
            from desktop_notifier import DesktopNotifier

            notifier = DesktopNotifier(app_name="English Coach")
            asyncio.run(notifier.send(title=title, message=body))
            return True
        except Exception:
            return False

    def _send_bark(self, title: str, body: str, settings: dict[str, Any]) -> bool:
        bark_key = str(settings.get("bark_key", "") or "").strip()
        if not bark_key:
            return False
        try:
            if bark_key.startswith("http://") or bark_key.startswith("https://"):
                req = urllib.request.Request(
                    bark_key,
                    data=json.dumps({"title": title, "body": body, "group": "English Coach"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
            else:
                req = urllib.request.Request(
                    f"https://api.day.app/{bark_key}/{urllib.parse.quote(title, safe='')}/{urllib.parse.quote(body, safe='')}?group=English%20Coach",
                    method="GET",
                )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    def _send_webhook(self, title: str, body: str, settings: dict[str, Any], payload: dict[str, Any]) -> bool:
        webhook_url = str(settings.get("webhook_url", "") or "").strip()
        if not webhook_url:
            return False
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps({"title": title, "body": body, "source": "english-coach", "payload": payload}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False


class CoachService:
    def __init__(self, user_model, profile, runtime: Optional[dict[str, Any]] = None) -> None:
        self.user_model = user_model
        self.profile = profile
        self.runtime = runtime or {}
        self._db = user_model._db

    def tier(self) -> str:
        if self.runtime.get("cloud_ai_ready"):
            return "premium"
        if self.runtime.get("ai_ready"):
            return "self_key"
        return "free"

    def _default_settings(self) -> dict[str, Any]:
        return {
            "preferred_study_time": DEFAULT_PREFERRED_STUDY_TIME,
            "quiet_hours": dict(DEFAULT_QUIET_HOURS),
            "reminder_level": "basic",
            "desktop_enabled": True,
            "bark_enabled": False,
            "webhook_enabled": False,
            "bark_key": "",
            "webhook_url": "",
        }

    def get_settings(self) -> dict[str, Any]:
        if not self.profile:
            return self._default_settings()
        row = self._db.execute(
            """SELECT preferred_study_time, quiet_hours_json, reminder_level,
                      desktop_enabled, bark_enabled, webhook_enabled,
                      bark_key, webhook_url, updated_at
               FROM coach_settings WHERE user_id=?""",
            (self.profile.user_id,),
        ).fetchone()
        if not row:
            settings = self._default_settings()
            self._db.execute(
                """INSERT INTO coach_settings
                   (user_id, preferred_study_time, quiet_hours_json, reminder_level,
                    desktop_enabled, bark_enabled, webhook_enabled, bark_key, webhook_url, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.profile.user_id,
                    settings["preferred_study_time"],
                    json.dumps(settings["quiet_hours"], ensure_ascii=True),
                    settings["reminder_level"],
                    1,
                    0,
                    0,
                    "",
                    "",
                    _iso(datetime.now()),
                ),
            )
            self._db.commit()
            settings["updated_at"] = _iso(datetime.now())
            return settings
        return {
            "preferred_study_time": _safe_time(row["preferred_study_time"], DEFAULT_PREFERRED_STUDY_TIME),
            "quiet_hours": _loads(row["quiet_hours_json"], dict(DEFAULT_QUIET_HOURS)),
            "reminder_level": row["reminder_level"] if row["reminder_level"] in VALID_REMINDER_LEVELS else "basic",
            "desktop_enabled": bool(row["desktop_enabled"]),
            "bark_enabled": bool(row["bark_enabled"]),
            "webhook_enabled": bool(row["webhook_enabled"]),
            "bark_key": row["bark_key"] or "",
            "webhook_url": row["webhook_url"] or "",
            "updated_at": row["updated_at"] or "",
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.get_settings()
        quiet = payload.get("quiet_hours") or {}
        settings["preferred_study_time"] = _safe_time(payload.get("preferred_study_time"), settings["preferred_study_time"])
        settings["quiet_hours"] = {
            "start": _safe_time(quiet.get("start"), settings["quiet_hours"].get("start", DEFAULT_QUIET_HOURS["start"])),
            "end": _safe_time(quiet.get("end"), settings["quiet_hours"].get("end", DEFAULT_QUIET_HOURS["end"])),
        }
        reminder_level = str(payload.get("reminder_level", settings["reminder_level"]) or "").strip().lower()
        settings["reminder_level"] = reminder_level if reminder_level in VALID_REMINDER_LEVELS else settings["reminder_level"]
        settings["desktop_enabled"] = _truthy(payload.get("desktop_enabled"), settings["desktop_enabled"])
        settings["bark_enabled"] = _truthy(payload.get("bark_enabled"), settings["bark_enabled"])
        settings["webhook_enabled"] = _truthy(payload.get("webhook_enabled"), settings["webhook_enabled"])
        settings["bark_key"] = str(payload.get("bark_key", settings["bark_key"]) or "").strip()
        settings["webhook_url"] = str(payload.get("webhook_url", settings["webhook_url"]) or "").strip()
        settings["updated_at"] = _iso(datetime.now())
        self._db.execute(
            """INSERT INTO coach_settings
               (user_id, preferred_study_time, quiet_hours_json, reminder_level,
                desktop_enabled, bark_enabled, webhook_enabled, bark_key, webhook_url, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 preferred_study_time=excluded.preferred_study_time,
                 quiet_hours_json=excluded.quiet_hours_json,
                 reminder_level=excluded.reminder_level,
                 desktop_enabled=excluded.desktop_enabled,
                 bark_enabled=excluded.bark_enabled,
                 webhook_enabled=excluded.webhook_enabled,
                 bark_key=excluded.bark_key,
                 webhook_url=excluded.webhook_url,
                 updated_at=excluded.updated_at""",
            (
                self.profile.user_id,
                settings["preferred_study_time"],
                json.dumps(settings["quiet_hours"], ensure_ascii=True),
                settings["reminder_level"],
                1 if settings["desktop_enabled"] else 0,
                1 if settings["bark_enabled"] else 0,
                1 if settings["webhook_enabled"] else 0,
                settings["bark_key"],
                settings["webhook_url"],
                settings["updated_at"],
            ),
        )
        self._db.commit()
        return settings

    def channel_capabilities(self) -> dict[str, bool]:
        tier = self.tier()
        return {"desktop": True, "bark": tier == "premium", "webhook": tier == "premium"}

    def _due_today(self) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) AS count FROM srs_cards WHERE user_id=? AND due_date<=?",
            (self.profile.user_id, date.today().isoformat()),
        ).fetchone()
        return int(row["count"] or 0)

    def _today_rows(self, day: Optional[date] = None) -> list[Any]:
        return self._db.execute(
            """SELECT mode, duration_sec, items_done, accuracy, started_at, ended_at
               FROM sessions
               WHERE user_id=? AND date(COALESCE(ended_at, started_at))=?
               ORDER BY COALESCE(ended_at, started_at) DESC""",
            (self.profile.user_id, (day or date.today()).isoformat()),
        ).fetchall()

    def _today_modes(self, day: Optional[date] = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._today_rows(day):
            key = _mode_key(row["mode"])
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _today_summary(self, day: Optional[date] = None) -> dict[str, int]:
        rows = self._today_rows(day)
        return {
            "sessions": len(rows),
            "minutes": int(sum(int(row["duration_sec"] or 0) for row in rows) // 60),
            "items": int(sum(int(row["items_done"] or 0) for row in rows)),
        }

    def _last_session_at(self) -> Optional[datetime]:
        row = self._db.execute(
            """SELECT COALESCE(ended_at, started_at) AS ts
               FROM sessions
               WHERE user_id=? AND COALESCE(ended_at, started_at) IS NOT NULL
               ORDER BY COALESCE(ended_at, started_at) DESC LIMIT 1""",
            (self.profile.user_id,),
        ).fetchone()
        if not row or not row["ts"]:
            return None
        try:
            return datetime.fromisoformat(row["ts"])
        except ValueError:
            return None

    def _mode_totals(self) -> dict[str, int]:
        rows = self._db.execute(
            "SELECT mode, COUNT(*) AS count FROM sessions WHERE user_id=? GROUP BY mode",
            (self.profile.user_id,),
        ).fetchall()
        totals: dict[str, int] = {}
        for row in rows:
            key = _mode_key(row["mode"])
            totals[key] = totals.get(key, 0) + int(row["count"] or 0)
        return totals

    def _recent_mode_stats(self) -> dict[str, dict[str, float]]:
        rows = self._db.execute(
            """SELECT mode, accuracy FROM sessions
               WHERE user_id=? AND ended_at IS NOT NULL
               ORDER BY ended_at DESC LIMIT 50""",
            (self.profile.user_id,),
        ).fetchall()
        buckets: dict[str, list[float]] = {}
        for row in rows:
            key = _mode_key(row["mode"])
            if key in {"chat", "other"}:
                continue
            if len(buckets.setdefault(key, [])) < 5:
                buckets[key].append(float(row["accuracy"] or 0))
        stats: dict[str, dict[str, float]] = {}
        for key, values in buckets.items():
            if values:
                stats[key] = {
                    "count": len(values),
                    "avg_accuracy": sum(values) / len(values),
                    "all_below_threshold": 1 if len(values) >= 2 and all(v < 0.65 for v in values) else 0,
                }
        return stats

    def _stage(self) -> str:
        exam_date_text = str(getattr(self.profile, "target_exam_date", "") or "").strip()
        if exam_date_text:
            try:
                days_left = (date.fromisoformat(exam_date_text) - date.today()).days
                if 0 <= days_left <= 30:
                    return "sprint"
            except ValueError:
                pass
        return "core" if int(getattr(self.profile, "total_sessions", 0) or 0) < 3 else "growth"

    def _task_for_mode(self, mode: str, category: str, reason: str) -> dict[str, Any]:
        catalog = {
            "vocab": ("vocab_review", "vocab", "先清今天的词汇复习", "先用最短路径把到期复习清掉，连续学习更稳。", "如果今天不处理复习债务，明天会继续累积。", 8),
            "grammar": ("grammar_quick_win", "grammar", "做一个 grammar quick win", "先用短练习把正确率拉回来，适合快速进入状态。", "如果今天不修正语法短板，后续写作和阅读会持续受影响。", 10),
            "reading": ("reading_focus", "reading", "完成 1 篇定向阅读", "围绕目标考试完成一篇可见结果的阅读任务。", "如果今天跳过阅读，弱项修复会继续拖延。", 15),
            "listening": ("listening_focus", "listening", "完成 1 组听力微任务", "优先做一组短听力，保持考试场景的输入节奏。", "如果今天跳过听力，考试场景的连续输入会变钝。", 12),
            "writing": ("writing_feedback", "writing", "完成 1 次带反馈的写作", "用一次短写作拿到可执行反馈，形成结果感。", "如果今天不做输出训练，AI 反馈闭环会持续空缺。", 18),
            "speaking": ("speaking_feedback", "speaking", "完成 1 次带评分的口语", "做一次短口语，把表达问题尽早暴露出来。", "如果今天不练口语，输出肌肉会继续退化。", 12),
            "mock": ("mock_section", "mock-exam", "做 1 个 mock section", "只做一个 section，保持冲刺手感，不强迫整套模考。", "如果冲刺期一直不碰 section，考试节奏感会下降。", 25),
        }
        task_key, route_page, title, desc, risk, minutes = catalog.get(mode, catalog["reading"])
        task_type = self._task_type_for_mode(mode, category)
        task_type_label = self._task_type_label(mode, task_type)
        task = {
            "task_key": task_key,
            "mode": "mock" if mode == "mock" else mode,
            "route_page": route_page,
            "category": category,
            "title": f"{title}（{task_type_label}）" if task_type_label else title,
            "description": desc,
            "risk_text": risk,
            "expected_minutes": minutes,
            "reason": f"{reason} 当前优先形态：{task_type_label}。" if task_type_label else reason,
        }
        task["exam"] = str(self.profile.target_exam or "general").lower()
        task["task_type"] = task_type
        if mode == "mock":
            task["recommended_section"] = self._recommended_mock_section()
        return task

    def _task_type_label(self, mode: str, task_type: str) -> str:
        labels = {
            "reading": {
                "factual": "Factual",
                "inference": "Inference",
                "tfng": "TFNG",
                "matching_headings": "Matching Headings",
            },
            "listening": {
                "detail": "Detail",
                "organization": "Organization",
                "multiple_choice": "Multiple Choice",
                "form_completion": "Form Completion",
                "inference": "Inference",
            },
            "writing": {
                "independent": "Independent Writing",
                "task2": "Task 2",
                "issue": "Issue Essay",
                "essay": "Essay",
            },
            "speaking": {
                "independent": "Independent",
                "part1": "Part 1",
            },
        }
        return labels.get(mode, {}).get(task_type, "")

    def _task_type_for_mode(self, mode: str, category: str) -> str:
        exam = str(self.profile.target_exam or "general").lower()
        odd_day = datetime.now().toordinal() % 2 == 1
        if mode == "writing":
            return {
                "toefl": "independent",
                "ielts": "task2",
                "gre": "issue",
                "cet": "essay",
                "general": "essay",
            }.get(exam, "essay")
        if mode == "speaking":
            return {
                "toefl": "independent",
                "ielts": "part1",
                "gre": "",
                "cet": "",
                "general": "",
            }.get(exam, "")
        if mode == "reading":
            if exam == "toefl":
                return "inference" if category != "core" or odd_day else "factual"
            if exam == "ielts":
                return "matching_headings" if category != "core" or odd_day else "tfng"
            if exam == "gre":
                return "inference"
            if exam == "cet":
                return "main_idea"
            return "factual"
        if mode == "listening":
            if exam == "toefl":
                return "organization" if category == "sprint" else "detail"
            if exam == "ielts":
                return "multiple_choice"
            if exam == "cet":
                return "detail"
            if exam == "gre":
                return "inference"
            return "detail"
        return ""

    def _recommended_mock_section(self) -> str:
        weak_areas = list(self.profile.weak_areas or [])
        if weak_areas:
            first = weak_areas[0]
            if first.startswith("reading"):
                return "reading"
            if first.startswith("listening"):
                return "listening"
            if first.startswith("writing"):
                return "writing"
            if first.startswith("speaking"):
                return "speaking"
        stats = self._recent_mode_stats()
        section_candidates = [item for item in stats.items() if item[0] in {"reading", "listening", "writing", "speaking"}]
        if section_candidates:
            return sorted(section_candidates, key=lambda item: item[1]["avg_accuracy"])[0][0]
        exam = str(self.profile.target_exam or "toefl").lower()
        return "reading" if exam in {"toefl", "gre"} else "listening"

    def _weak_task(self) -> Optional[dict[str, Any]]:
        stats = self._recent_mode_stats()
        weak_recent = [item for item in stats.items() if item[1]["all_below_threshold"]]
        if weak_recent:
            mode = sorted(weak_recent, key=lambda item: item[1]["avg_accuracy"])[0][0]
            return self._task_for_mode(mode, "growth", "最近 5 次相关训练的正确率持续偏低。")
        weak_areas = list(self.profile.weak_areas or [])
        if not weak_areas:
            return None
        text = weak_areas[0]
        if text.startswith("grammar"):
            return self._task_for_mode("grammar", "growth", "你的近期薄弱项集中在语法。")
        if text.startswith("reading"):
            return self._task_for_mode("reading", "growth", "你的近期薄弱项集中在阅读理解。")
        if text.startswith("writing"):
            return self._task_for_mode("writing", "growth", "你的近期薄弱项集中在写作表达。")
        if text.startswith("speaking"):
            return self._task_for_mode("speaking", "growth", "你的近期薄弱项集中在口语组织。")
        if text.startswith("vocab"):
            return self._task_for_mode("vocab", "growth", "你的近期薄弱项集中在词汇记忆。")
        return None

    def _exam_task(self) -> dict[str, Any]:
        exam = str(self.profile.target_exam or "general").strip().lower()
        totals = self._mode_totals()
        if exam in {"toefl", "ielts"}:
            mode = "reading" if totals.get("reading", 0) <= totals.get("listening", 0) else "listening"
        elif exam == "gre":
            mode = "reading"
        elif exam == "cet":
            mode = "listening" if totals.get("listening", 0) <= totals.get("reading", 0) else "reading"
        else:
            mode = "reading" if date.today().day % 2 else "listening"
        category = "core" if self._stage() == "core" else "growth"
        label = exam.upper() if exam != "general" else "General English"
        return self._task_for_mode(mode, category, f"当前目标考试是 {label}，系统优先给你最该补的一项。")

    def _ai_task(self) -> Optional[dict[str, Any]]:
        if not self.runtime.get("ai_ready"):
            return None
        cutoff = (datetime.now() - timedelta(days=2)).isoformat()
        rows = self._db.execute(
            """SELECT mode, MAX(COALESCE(ended_at, started_at)) AS ts
               FROM sessions
               WHERE user_id=? AND mode IN ('writing', 'speaking')
               GROUP BY mode""",
            (self.profile.user_id,),
        ).fetchall()
        by_mode = {row["mode"]: row["ts"] for row in rows}
        stale = [mode for mode in ("writing", "speaking") if not by_mode.get(mode) or str(by_mode.get(mode)) < cutoff]
        if not stale:
            return None
        mode_counts = self._mode_totals()
        ranked = sorted(
            stale,
            key=lambda mode: (
                0 if not by_mode.get(mode) else 1,
                str(by_mode.get(mode) or ""),
                mode_counts.get(mode, 0),
                mode,
            ),
        )
        return self._task_for_mode(ranked[0], "ai_enhanced", "过去 2 天还没有形成 AI 输出反馈，今天补一次最值钱。")

    def _task_state(self, task: dict[str, Any], today_modes: dict[str, int], due_now: int) -> str:
        if task["task_key"] == "vocab_review":
            baseline = int(task.get("baseline_due", 0) or 0)
            if baseline <= 0 or due_now <= 0:
                return "done"
            if due_now < baseline or today_modes.get("vocab", 0) > 0:
                return "in_progress"
            return "pending"
        if task["mode"] == "mock":
            return "done" if today_modes.get("mock", 0) > 0 else "pending"
        return "done" if today_modes.get(task["mode"], 0) > 0 else "pending"

    def _latest_session_recap(self, day: Optional[date] = None) -> dict[str, str]:
        row = self._db.execute(
            """SELECT content_json
               FROM sessions
               WHERE user_id=? AND ended_at IS NOT NULL
                 AND date(COALESCE(ended_at, started_at))=?
               ORDER BY ended_at DESC, started_at DESC
               LIMIT 1""",
            (self.profile.user_id, (day or date.today()).isoformat()),
        ).fetchone()
        payload = _loads(row["content_json"], {}) if row else {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "result_headline": str(payload.get("result_headline", "") or "").strip(),
            "next_step": str(payload.get("next_step", "") or "").strip(),
        }

    def _result_card(self, plan_status: str, summary: dict[str, int], completed: int, due_now: int, latest_result_headline: str = "") -> str:
        if latest_result_headline:
            return latest_result_headline
        if plan_status == "done":
            return f"今天计划已完成，你已经做了 {summary['sessions']} 次训练。"
        if summary["sessions"] > 0:
            return f"今天已经完成 {completed} 个任务，继续推进剩余任务会更轻松。"
        if due_now > 0:
            return f"今天还有 {due_now} 张词汇待复习，先清 8 分钟最划算。"
        return "今天还没开始，先完成一个最短任务把状态拉起来。"

    def _tomorrow_reason(self, plan_status: str, due_now: int, latest_next_step: str = "") -> str:
        if latest_next_step:
            return latest_next_step
        if plan_status == "done":
            return "明天系统会根据你今天的完成情况自动刷新更合适的任务。"
        if self._stage() == "sprint":
            return "明天还会继续收紧冲刺节奏，保持 section 手感。"
        if due_now > 0:
            return "明天继续回来清理复习债务，连续学习会更稳。"
        return "明天回来后，系统会根据你的弱项和完成度重新排任务。"

    def _if_skip(self, sessions: int, due_now: int) -> str:
        if sessions > 0:
            return "今天已经启动了学习，最好把结果感补完整。"
        if due_now > 0:
            return "如果今天不学，复习债务会继续累积，连续学习也会断掉。"
        return "如果今天不学，明天的启动成本会更高。"

    def _build_tasks(self) -> list[dict[str, Any]]:
        due_now = self._due_today()
        tasks: list[dict[str, Any]] = []
        seen: set[str] = set()

        def push(task: Optional[dict[str, Any]]) -> None:
            if not task or task["task_key"] in seen:
                return
            seen.add(task["task_key"])
            tasks.append(task)

        if due_now > 0:
            task = self._task_for_mode("vocab", "core", f"今天还有 {due_now} 张到期复习，先把最稳的基础任务完成。")
            task["baseline_due"] = due_now
            push(task)
        push(self._weak_task())
        push(self._ai_task())
        push(self._exam_task())
        if self._stage() == "sprint":
            push(self._task_for_mode("mock", "sprint", "你已经进入冲刺窗口，今天只做一个 section 保持手感。"))
        if len(tasks) < 2:
            push(self._task_for_mode("grammar", "core", "先用一个短 grammar 任务把学习状态拉起来。"))
        if len(tasks) < 3 and due_now <= 0:
            push(self._task_for_mode("reading", "core", "今天至少完成一篇可见结果的阅读，建立日完成感。"))
        return tasks[:4]

    def expire_old_plans(self) -> None:
        today = date.today().isoformat()
        self._db.execute(
            "UPDATE coach_daily_plan SET status='expired' WHERE user_id=? AND plan_date<? AND status IN ('planned','in_progress')",
            (self.profile.user_id, today),
        )
        self._db.execute(
            "UPDATE coach_notification_log SET state='expired' WHERE user_id=? AND state='pending' AND scheduled_for<?",
            (self.profile.user_id, _iso(datetime.now() - timedelta(hours=RECOVERY_WINDOW_HOURS))),
        )
        self._db.commit()

    def sync_daily_plan(self, plan_day: Optional[date] = None) -> dict[str, Any]:
        if not self.profile:
            return {}
        self.expire_old_plans()
        plan_day = plan_day or date.today()
        plan_date = plan_day.isoformat()
        row = self._db.execute(
            "SELECT plan_id, stage, plan_json, generated_at FROM coach_daily_plan WHERE user_id=? AND plan_date=?",
            (self.profile.user_id, plan_date),
        ).fetchone()
        if row:
            plan = _loads(row["plan_json"], {})
            plan.setdefault("plan_id", row["plan_id"])
            plan.setdefault("plan_date", plan_date)
            plan.setdefault("stage", row["stage"])
            plan.setdefault("generated_at", row["generated_at"] or _iso(datetime.now()))
        else:
            plan = {
                "plan_id": uuid.uuid4().hex[:12],
                "plan_date": plan_date,
                "stage": self._stage(),
                "generated_at": _iso(datetime.now()),
                "tier": self.tier(),
                "meta": {
                    "due_at_start": self._due_today(),
                    "target_exam": self.profile.target_exam,
                    "target_exam_date": getattr(self.profile, "target_exam_date", "") or "",
                },
                "tasks": self._build_tasks(),
            }

        today_modes = self._today_modes(plan_day)
        today_summary = self._today_summary(plan_day)
        latest_recap = self._latest_session_recap(plan_day)
        due_now = self._due_today() if plan_day == date.today() else int(plan.get("meta", {}).get("due_at_start", 0) or 0)
        completed = 0
        in_progress = 0
        for task in plan.get("tasks", []):
            task["state"] = self._task_state(task, today_modes, due_now)
            if task["state"] == "done":
                completed += 1
            elif task["state"] == "in_progress":
                in_progress += 1
        status = "done" if plan.get("tasks") and completed == len(plan["tasks"]) else "in_progress" if (completed or in_progress) else "planned"
        summary = {
            "tasks_total": len(plan.get("tasks", [])),
            "tasks_done": completed,
            "tasks_in_progress": in_progress,
            "completion_rate": round(completed * 100 / max(len(plan.get("tasks", [])), 1)) if plan.get("tasks") else 0,
            "due_at_start": int(plan.get("meta", {}).get("due_at_start", 0) or 0),
            "due_now": due_now,
            "today_sessions": today_summary["sessions"],
            "today_minutes": today_summary["minutes"],
            "today_items": today_summary["items"],
            "today_modes": today_modes,
            "result_card": self._result_card(status, today_summary, completed, due_now, latest_recap.get("result_headline", "")),
            "tomorrow_reason": self._tomorrow_reason(status, due_now, latest_recap.get("next_step", "")),
            "if_skip": self._if_skip(today_summary["sessions"], due_now),
        }
        plan["status"] = status
        plan["summary"] = summary
        plan["completed_at"] = _iso(datetime.now()) if status == "done" else ""
        self._db.execute(
            """INSERT INTO coach_daily_plan
               (plan_id, user_id, plan_date, stage, status, plan_json, summary_json, generated_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id, plan_date) DO UPDATE SET
                 stage=excluded.stage,
                 status=excluded.status,
                 plan_json=excluded.plan_json,
                 summary_json=excluded.summary_json,
                 generated_at=excluded.generated_at,
                 completed_at=excluded.completed_at""",
            (
                plan["plan_id"],
                self.profile.user_id,
                plan_date,
                plan["stage"],
                plan["status"],
                json.dumps({k: v for k, v in plan.items() if k != "summary"}, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
                plan["generated_at"],
                plan["completed_at"],
            ),
        )
        self._db.commit()
        return plan

    def _channels(self, settings: dict[str, Any]) -> list[str]:
        channels = ["in_app"]
        if settings.get("desktop_enabled"):
            channels.append("desktop")
        if self.tier() == "premium" and settings.get("bark_enabled") and settings.get("bark_key"):
            channels.append("bark")
        if self.tier() == "premium" and settings.get("webhook_enabled") and settings.get("webhook_url"):
            channels.append("webhook")
        return channels

    def _compose_notification(self, event_type: str, plan: dict[str, Any], task_key: str) -> dict[str, str]:
        summary = plan.get("summary", {})
        first_pending = next((task for task in plan.get("tasks", []) if task.get("state") != "done"), None)
        if event_type == "daily_plan":
            return {"title": "English Coach 今日计划", "body": (first_pending or {}).get("description") or summary.get("result_card", "")}
        if event_type == "review_due":
            due_now = int(summary.get("due_now", 0) or 0)
            return {"title": "复习到期提醒", "body": f"今天还有 {due_now} 张词汇待复习，先清 8 分钟，连续学习就保住了。"}
        if event_type == "streak_risk":
            return {"title": "连续学习即将中断", "body": "你昨天断了节奏，今天先做 1 篇阅读把状态拉回来。"}
        if event_type == "idle_overdue":
            return {"title": "该回来学习了", "body": "你已经有一段时间没打开 English Coach，今天先做一个最短任务恢复手感。"}
        if event_type == "day_recap":
            return {"title": "今日复盘提醒", "body": "今天任务已完成，花 2 分钟看复盘，明天会更轻松。"}
        if event_type == "test":
            return {"title": "English Coach 测试提醒", "body": "这是一条测试提醒，用来确认本地监督通道可用。"}
        task = next((item for item in plan.get("tasks", []) if item["task_key"] == task_key), None) or first_pending
        return {"title": "English Coach 提醒", "body": (task or {}).get("description") or summary.get("result_card", "")}

    def _insert_notification(self, plan: dict[str, Any], task_key: str, event_type: str, channel: str, scheduled_for: datetime) -> None:
        payload = self._compose_notification(event_type, plan, task_key)
        payload.update({"task_key": task_key, "event_type": event_type})
        dedupe_key = f"{self.profile.user_id}|{plan['plan_date']}|{event_type}|{task_key}|{channel}"
        self._db.execute(
            """INSERT OR IGNORE INTO coach_notification_log
               (event_id, user_id, plan_id, task_key, event_type, channel,
                scheduled_for, fired_at, state, dedupe_key, payload_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                uuid.uuid4().hex[:16],
                self.profile.user_id,
                plan["plan_id"],
                task_key,
                event_type,
                channel,
                _iso(scheduled_for),
                "",
                "pending",
                dedupe_key,
                json.dumps(payload, ensure_ascii=False),
                _iso(datetime.now()),
            ),
        )

    def ensure_notification_schedule(self, now: Optional[datetime] = None) -> dict[str, Any]:
        if not self.profile:
            return {"scheduled": 0, "channels": []}
        now = now or datetime.now()
        settings = self.get_settings()
        if settings["reminder_level"] == "off":
            self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE user_id=? AND state='pending'", (self.profile.user_id,))
            self._db.commit()
            return {"scheduled": 0, "channels": []}
        plan = self.sync_daily_plan(now.date())
        summary = plan.get("summary", {})
        today_sessions = int(summary.get("today_sessions", 0) or 0)
        due_now = int(summary.get("due_now", 0) or 0)
        channels = self._channels(settings)
        quiet = settings.get("quiet_hours") or dict(DEFAULT_QUIET_HOURS)
        preferred_dt = _combine(now.date(), settings["preferred_study_time"], DEFAULT_PREFERRED_STUDY_TIME)
        quiet_start = _combine(now.date(), quiet.get("start"), DEFAULT_QUIET_HOURS["start"])
        specs: list[tuple[str, str, datetime]] = []
        if today_sessions == 0:
            specs.append(("daily_plan", "plan", preferred_dt))
        if due_now >= 10:
            specs.append(("review_due", "vocab_review", preferred_dt + timedelta(minutes=45)))
        if settings["reminder_level"] == "coach":
            if today_sessions == 0:
                specs.append(("streak_risk", "streak", quiet_start - timedelta(minutes=90)))
            if today_sessions > 0:
                specs.append(("day_recap", "recap", quiet_start - timedelta(minutes=30)))
            last_session = self._last_session_at()
            if last_session:
                for hours in (48, 72):
                    threshold = last_session + timedelta(hours=hours)
                    if now >= threshold:
                        specs.append(("idle_overdue", f"{hours}h", threshold))
        for event_type, task_key, scheduled_for in specs:
            for channel in channels:
                self._insert_notification(plan, task_key, event_type, channel, scheduled_for)
        self._db.commit()
        return {"scheduled": len(specs), "channels": channels}

    def dispatch_due_notifications(self, dispatcher: CoachNotificationDispatcher, now: Optional[datetime] = None) -> list[dict[str, Any]]:
        if not self.profile:
            return []
        now = now or datetime.now()
        settings = self.get_settings()
        quiet_hours = settings.get("quiet_hours") or dict(DEFAULT_QUIET_HOURS)
        plan = self.sync_daily_plan(now.date())
        summary = plan.get("summary", {})
        rows = self._db.execute(
            """SELECT event_id, event_type, task_key, channel, scheduled_for, payload_json
               FROM coach_notification_log
               WHERE user_id=? AND state='pending' AND scheduled_for<=?
               ORDER BY scheduled_for ASC""",
            (self.profile.user_id, _iso(now)),
        ).fetchall()
        results = []
        for row in rows:
            scheduled_for = datetime.fromisoformat(row["scheduled_for"])
            if now - scheduled_for > timedelta(hours=RECOVERY_WINDOW_HOURS):
                self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                continue
            if row["event_type"] != "test" and _is_quiet_hours(now, quiet_hours):
                continue
            if row["event_type"] == "daily_plan" and int(summary.get("today_sessions", 0) or 0) > 0:
                self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                continue
            if row["event_type"] == "review_due" and int(summary.get("due_now", 0) or 0) < 10:
                self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                continue
            if row["event_type"] == "streak_risk" and int(summary.get("today_sessions", 0) or 0) > 0:
                self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                continue
            if row["event_type"] == "day_recap" and int(summary.get("today_sessions", 0) or 0) == 0:
                self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                continue
            if row["event_type"] == "idle_overdue":
                last_session = self._last_session_at()
                required_hours = int(str(row["task_key"]).replace("h", "") or 0)
                if last_session and now - last_session < timedelta(hours=required_hours):
                    self._db.execute("UPDATE coach_notification_log SET state='expired' WHERE event_id=?", (row["event_id"],))
                    continue
            payload = _loads(row["payload_json"], {})
            dispatcher.send(row["channel"], payload.get("title", "English Coach"), payload.get("body", ""), settings, payload)
            self._db.execute("UPDATE coach_notification_log SET state='sent', fired_at=? WHERE event_id=?", (_iso(now), row["event_id"]))
            results.append(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "task_key": row["task_key"],
                    "channel": row["channel"],
                    "title": payload.get("title", ""),
                    "body": payload.get("body", ""),
                }
            )
        self._db.commit()
        return results

    def recent_notifications(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self._db.execute(
            """SELECT event_id, task_key, event_type, channel, scheduled_for, fired_at, state, payload_json
               FROM coach_notification_log WHERE user_id=?
               ORDER BY COALESCE(fired_at, scheduled_for) DESC LIMIT ?""",
            (self.profile.user_id, limit),
        ).fetchall()
        items = []
        for row in rows:
            payload = _loads(row["payload_json"], {})
            items.append(
                {
                    "event_id": row["event_id"],
                    "task_key": row["task_key"],
                    "event_type": row["event_type"],
                    "channel": row["channel"],
                    "scheduled_for": row["scheduled_for"],
                    "fired_at": row["fired_at"],
                    "state": row["state"],
                    "title": payload.get("title", ""),
                    "body": payload.get("body", ""),
                }
            )
        return items

    def next_notification(self) -> Optional[dict[str, Any]]:
        row = self._db.execute(
            """SELECT event_id, task_key, event_type, channel, scheduled_for, payload_json
               FROM coach_notification_log
               WHERE user_id=? AND state='pending'
               ORDER BY scheduled_for ASC LIMIT 1""",
            (self.profile.user_id,),
        ).fetchone()
        if not row:
            return None
        payload = _loads(row["payload_json"], {})
        return {
            "event_id": row["event_id"],
            "task_key": row["task_key"],
            "event_type": row["event_type"],
            "channel": row["channel"],
            "scheduled_for": row["scheduled_for"],
            "title": payload.get("title", ""),
            "body": payload.get("body", ""),
        }

    def coach_summary(self) -> dict[str, Any]:
        plan = self.sync_daily_plan()
        rows = self._db.execute(
            "SELECT summary_json FROM coach_daily_plan WHERE user_id=? ORDER BY plan_date DESC LIMIT 7",
            (self.profile.user_id,),
        ).fetchall()
        completion_rates = []
        due_trend = []
        consistency = 0
        for row in rows:
            summary = _loads(row["summary_json"], {})
            completion_rates.append(int(summary.get("completion_rate", 0) or 0))
            due_trend.append(int(summary.get("due_now", 0) or 0))
            if int(summary.get("today_sessions", 0) or 0) > 0:
                consistency += 1
        weak_done = any(task.get("category") == "growth" and task.get("state") == "done" for task in plan.get("tasks", []))
        return {
            "plan_completion_rate_7d": round(sum(completion_rates) / max(len(completion_rates), 1)) if completion_rates else 0,
            "study_consistency_7d": round(consistency * 100 / max(len(rows), 1)) if rows else 0,
            "review_due_today": int(plan.get("summary", {}).get("due_now", 0) or 0),
            "review_due_trend": due_trend,
            "weak_area_progress": {"current": list(self.profile.weak_areas or []), "today_focused": weak_done},
            "today_result_card": plan.get("summary", {}).get("result_card", ""),
            "tomorrow_reason": plan.get("summary", {}).get("tomorrow_reason", ""),
            "plan_stage": plan.get("stage", "growth"),
            "tier": self.tier(),
        }

    def catch_up_message(self) -> str:
        plan = self.sync_daily_plan()
        preferred_dt = _combine(date.today(), self.get_settings()["preferred_study_time"], DEFAULT_PREFERRED_STUDY_TIME)
        if int(plan.get("summary", {}).get("today_sessions", 0) or 0) == 0 and datetime.now() - preferred_dt > timedelta(hours=RECOVERY_WINDOW_HOURS):
            return "你已经错过了今天的主提醒窗口，但现在补一个最短任务，仍然能把节奏拉回来。"
        return ""

    def build_status(self) -> dict[str, Any]:
        plan = self.sync_daily_plan()
        self.ensure_notification_schedule()
        return {
            "tier": self.tier(),
            "stage": plan.get("stage", "growth"),
            "settings": self.get_settings(),
            "plan": plan,
            "coach_summary": self.coach_summary(),
            "recent_notifications": self.recent_notifications(),
            "next_notification": self.next_notification(),
            "catch_up": self.catch_up_message(),
            "channel_capabilities": self.channel_capabilities(),
        }

    def dismiss_notification(self, event_id: str) -> bool:
        self._db.execute("UPDATE coach_notification_log SET state='dismissed' WHERE event_id=? AND user_id=?", (event_id, self.profile.user_id))
        self._db.commit()
        return bool(self._db.execute("SELECT changes()").fetchone()[0])

    def test_notification(self, dispatcher: CoachNotificationDispatcher) -> list[dict[str, Any]]:
        plan = self.sync_daily_plan()
        now = datetime.now()
        for channel in self._channels(self.get_settings()):
            self._insert_notification(plan, "test", "test", channel, now)
        self._db.commit()
        return self.dispatch_due_notifications(dispatcher, now=now)
