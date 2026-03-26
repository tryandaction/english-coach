# Coach Memory + Heartbeat Phase 1

## 当前状态

仓库原本已经有三块基础能力：

- `core/user_model/profile.py`
  - 保存用户 profile、skill score、session history
- `core/srs/engine.py`
  - 保存词汇库、SRS 卡片、复习记录
- `core/coach/service.py`
  - 生成 daily plan、提醒计划、quiet hours、recap 聚合

缺口在于长期记忆仍然分散：

- profile 里只有少量稳定字段
- session recap 只存在 `sessions.content_json`
- 没有 per-user/per-word 的结构化学习状态
- 没有独立 heartbeat 决策对象

## Phase 1 目标

只做底座，不做新 GUI 页面，不做 chat 的 “remember this” 文本意图识别。

本阶段新增能力：

- learner memory facts
- learning events
- vocab memory state
- daily memory snapshot
- simple heartbeat decision service

## 模块边界

### `core/memory/store.py`

负责 SQLite schema 和基本 CRUD：

- `learner_memory_facts`
- `learner_learning_events`
- `learner_vocab_state`
- `learner_daily_memory`

### `core/memory/service.py`

负责更高层业务接口：

- `remember_fact()`
- `record_session_completion()`
- `record_vocab_enrollment()`
- `record_vocab_review()`
- `refresh_daily_memory()`
- `review_due_list()`
- `frequent_forgetting_list()`
- `memory_summary()`

### `core/coach/heartbeat.py`

负责 heartbeat 决策，不直接依赖 GUI：

- `SILENT`
- `NUDGE_REVIEW`
- `NUDGE_NEW_WORDS`
- `MICRO_TEST`
- `ENCOURAGE_AND_WAIT`

## 数据流

### 会话完成

1. 训练模式调用 `user_model.end_session(...)`
2. `LearnerMemoryService.record_session_completion()` 写入 `learner_learning_events`
3. `refresh_daily_memory()` 生成当天快照
4. 现有 `CoachService.sync_daily_plan()` 继续更新 plan / reminder

### 词汇 enroll / review

1. `SM2Engine.enroll_words()` 写入 `srs_cards`
2. `LearnerMemoryService.record_vocab_enrollment()` 建立 `learner_vocab_state`
3. `SM2Engine.review_card()` 更新 SRS
4. `LearnerMemoryService.record_vocab_review()` 同步：
   - `status`
   - `wrong_count`
   - `success_count`
   - `last_seen_at`
   - `due_for_review`

### Coach 汇总

`CoachService.coach_summary()` 现在会合并：

- 现有 daily plan 信息
- memory summary
- heartbeat decision

## Phase 1 范围外

以下内容留到后续阶段：

- chat “remember this” 自动抽取
- GUI memory 编辑页
- weekly weak points 可视化
- 复杂 adaptive policy
- 基于 LLM 的长期记忆提炼

## 验证重点

- profile 新字段能跨重启持久化
- fact upsert 不重复
- 新 enroll 的词能进入 review due list
- 高频忘词能进入 forgetting pool
- heartbeat 能产出稳定动作
- coach summary 能暴露 memory / heartbeat 摘要
