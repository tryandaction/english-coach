# Coach Review + Policy Phase 2

## 目标

把已经落地的长期记忆底座，升级成真正能驱动推荐动作的教练策略层。

本阶段新增两层：

- `core/review/`
  - 负责 review pool 汇总、候选词排序、推荐批次
- `core/coach/context.py` + `core/coach/policy.py`
  - 负责 learner snapshot 构建和 next action 决策

## 当前职责划分

### `core/memory/`

- 保存 learner facts
- 保存 learning events
- 保存 vocab memory state
- 保存 daily memory snapshot

### `core/review/service.py`

- 汇总 `review_due_count`
- 汇总 `frequent_forgetting_count`
- 输出按优先级排序的 review candidates
- 输出推荐复习批次

### `core/coach/context.py`

- 汇总 profile、today summary、mode counts、recent accuracy、review summary
- 生成统一 `LearnerSnapshot`

### `core/coach/policy.py`

- 根据 snapshot 选择一个最小但有效的下一步动作
- 当前动作集：
  - `review_words`
  - `new_words`
  - `micro_test`
  - `reading_focus`
  - `listening_focus`
  - `write_short`
  - `speak_short`
  - `stay_silent`

## chat 接入

当前 chat 已经接入显式长期记忆入口：

- `/api/chat/context/{session_id}`
  - 查看当前会话注入给模型的 learner context
- `/api/chat/remember/{session_id}`
  - 显式写入 learner fact
- `/api/chat/word-status/{session_id}`
  - 显式写入词汇掌握状态

当前 chat 仍然不做自动 LLM 抽取，只做显式写入和上下文读取。

## 当前接线点

- `CoachService.build_status()`
  - 返回 `next_action`
- `/api/coach/status`
  - 暴露 `next_action`
- `/api/practice/recommendation`
  - 暴露推荐动作和可直接复用的 practice request
- `start-practice` 的 vocab 分支
  - 在 `targeted/error_review` 下优先走 review pool，而不是只给新词

## 当前仍未覆盖

- chat 自动提取 “remember this”
- GUI 独立 memory / recommendation 可视化页
- 多动作排序与候选备选方案
- 基于 LLM 的长期记忆抽取与压缩
