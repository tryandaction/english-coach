# English Coach v2.0 快速开始

这份文档适用于当前本地打包出的桌面版本。

- `english-coach-opensource*` 表示 Open Source / 开源版
- `english-coach-cloud*` 表示 Cloud / 商业版

## 1. 安装或启动

你可以使用以下任一文件开始测试：

- `english-coach-opensource.exe`
- `english-coach-opensource-setup.exe`
- `english-coach-v2.0.0-opensource.zip`
- `english-coach-cloud.exe`
- `english-coach-cloud-setup.exe`
- `english-coach-v2.0.0-cloud.zip`

## 2. 第一次打开先完成 Setup

建议按这个顺序：

1. 填写用户名和目标考试
2. 如有明确考试日期，可顺手填写
3. 确认数据目录
4. 设置学习时间与提醒等级
5. 决定是否配置自己的 API Key

如果你暂时没有 API Key，也可以直接继续。

如果你拿到的是 Cloud 构建，且该构建附带激活配置，也可以在 Setup / License 中直接输入激活码。

## 3. 没有 API Key 也能测试什么

当前开源版即使不配 AI，也可以直接测试：

- Vocabulary / Word Books / SRS
- Grammar drills
- Reading 离线训练与 fallback
- Listening 内置脚本流程
- Home / Progress / History
- Practice 页面
- Mock Exam section flow
- 每日计划、测试提醒、本地复盘

Cloud 版在没有激活成功时，也应能走同样的离线主路径。

这一版还会自动累积：

- learner profile 连续性
- 词汇 `known / unsure / unknown` 状态
- review due 与高错词统计
- coach heartbeat 所需的本地记忆信号

## 4. 配置 API Key 后会多什么

如果你在 Setup 中配置自己的 API Key，可以额外测试：

- Chat
- Writing feedback
- Speaking scoring
- Reading / Writing / Speaking 的 AI 增强路径
- Chat 显式记忆入口与跨会话上下文连续性

支持的 provider：

- DeepSeek
- OpenAI
- Anthropic
- Qwen / DashScope

## 5. 这版建议重点测试什么

1. Home 是否明确告诉用户今天该做什么
2. coach 任务是否能一键进入真实训练页
3. 完成训练后，Progress / History 是否有真实变化
4. 重启后，Progress / coach 连续性是否仍然保留
5. Chat 中手动记住的目标/偏好，下一次对话是否还能读到
6. 提醒测试按钮是否可用
7. quiet hours 是否能避免打扰

## 6. 发布前自动验证

如果你要重新生成完整的本地发布物，先运行：

```bash
python build_opensource.py
```

这会同步更新：

- `releases/english-coach-opensource.exe`
- `releases/english-coach-opensource-setup.exe`
- `releases/english-coach-v2.0.0-opensource.zip`

建议发布前运行：

```bash
python scripts/smoke_test_release.py --keep-temp
```

这会真实验证：

- portable exe 启动
- setup 静默安装后的启动
- 首启是否进入 Setup
- 最小离线 Setup
- Home / Progress / History / Practice / Mock Exam 核心 API
- Chat / memory / recommendation 关键 API
- Reading / Listening 完成后是否真实回写结果
- smoke 结束后不应残留 `english-coach-opensource` 进程

## 7. 当前限制

- 这仍不是完整商业化成熟平台
- `Mock Exam` 仍不是统一作答与统分系统
- `Writing / Speaking` 的高质量反馈仍依赖 AI
- 内容覆盖与质量仍会继续优化
- 长期记忆底座已经落地，但独立的 memory 管理界面还会继续补齐
