# AI Smoke Paths Design

## Goal

为后续可选的 `scripts/smoke_test_ai_paths.py` 固定一套轻量 AI 验证路径，覆盖：

- Writing: `prompt -> submit (SSE)`
- Speaking: `prompt -> submit (JSON)`
- Chat: `start -> message (SSE) -> end`

本轮只定义设计，不把 AI 强依赖塞进当前 release smoke。

## Scope

- 只验证 self-key AI 路径
- 不覆盖 Cloud License 激活流
- 不做浏览器级自动化
- 不验证 TTS、语音录音、桌面通知

## Environment

- 需要先完成 `Setup`
- 需要有效的 self-key API 配置
- 默认从 `.env` 或当前 `config.yaml` 读取 provider 与 key
- smoke 失败时应打印明确的 provider、endpoint 和失败阶段

## Proposed Script Shape

- 文件名：`scripts/smoke_test_ai_paths.py`
- 默认行为：只在显式传参时运行，例如 `--enable-writing --enable-speaking --enable-chat`
- 如果未传任何 `--enable-*` 参数，则直接退出并提示“AI smoke is optional”
- 每条路径独立执行、独立报错，最终输出汇总结果

## Writing Path

1. `GET /api/writing/prompt?exam=toefl&task_type=independent`
2. 断言返回 `prompt`、`task_type`、`score_max`
3. `POST /api/writing/submit`
4. 读取 SSE，至少命中这些事件：
   - `scores`
   - `overall`
   - `done`
5. 断言 session 已写入 `writing` 记录，且 `content_json` 含：
   - `result_headline`
   - `improved_point`
   - `next_step`

推荐最小 essay：

`I agree that students should take courses outside their major because it improves flexibility and helps them communicate with people from other fields.`

## Speaking Path

1. `GET /api/speaking/prompt?exam=toefl&task_type=independent`
2. 断言返回 `prompt`、`task_type`、`prep_seconds`、`speak_seconds`
3. `POST /api/speaking/submit`
4. 断言返回：
   - `overall`
   - `scores`
   - `strengths`
   - `improvements`
5. 断言 session 已写入 `speaking` 记录，且 `content_json` 含：
   - `result_headline`
   - `improved_point`
   - `next_step`

推荐最小 transcript：

`I prefer studying alone because I can control my schedule, focus on weak points, and review difficult ideas at my own pace.`

## Chat Path

1. `POST /api/chat/start`
2. 断言返回 `session_id`、`opener`、`mode_name`
3. `POST /api/chat/message/{session_id}`
4. 读取 SSE，至少命中：
   - `token`
   - `done`
5. `POST /api/chat/end/{session_id}`
6. 断言返回 `ok=true` 且 `turns >= 1`

推荐最小 message：

`Help me answer a short TOEFL speaking question about studying habits.`

## Acceptance

- 单条路径成功时，必须打印：
  - provider
  - endpoint chain
  - elapsed seconds
  - final persisted session id
- 单条路径失败时，必须打印：
  - provider
  - failed stage
  - raw error message
- 脚本退出码：
  - 全部启用路径成功：`0`
  - 任一路径失败：`1`

## Non-Goals

- 不校验具体 AI 文案质量
- 不做评分阈值断言
- 不比较不同 provider 输出差异
- 不覆盖 Cloud 版 license / verify / reactivate
