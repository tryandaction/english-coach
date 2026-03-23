# English Coach v2.0 Release Notes

**发布日期**: 2026-03-19  
**当前打包对象**: Desktop editions / 桌面版本线

## 这一轮主要变化

### 1. 从练习工具升级到 coach 产品骨架

- Home 不再只是统计页，而是“今天该做什么”的 coach 面板
- Daily plan 会固定按优先级生成任务：
  - 到期复习
  - 弱项修复
  - 考试目标任务
  - 冲刺任务
- 首页 coach 任务可以直接进入真实训练页

### 2. 留存与监督体验增强

- Setup 支持学习时间、quiet hours、本地提醒与测试提醒
- quiet hours 内不会发送普通提醒
- Progress 会显示计划完成率、稳定度、复习债务趋势
- History 会按天复盘，而不只是 session 列表
- History 支持“再做一次”直接返回真实任务

### 3. 内容与任务质量增强

- 开源词表会在有 profile 后自动同步进内置词书与词汇库
- Writing / Speaking prompt 会尽量避免近 7 天重复
- Writing / Speaking 默认任务类型会优先选择最近更少练的类型
- Mock coach 任务会默认预选一个推荐 section，而不是默认整套
- Listening 新增高命中离线素材，优先覆盖 TOEFL `detail` / `organization` 与 IELTS `multiple_choice` / `form_completion`
- Reading 新增高命中离线题型元数据，优先覆盖 TOEFL `factual` / `inference` 与 IELTS `tfng` / `matching_headings`

### 4. 学习结果闭环更完整

- Reading 会写回 topic / question types / passage preview
- Listening 会写回 topic / dialogue type / question type / correct count
- Writing / Speaking 会写回 prompt 摘要、字数、时长、分数与简短 recap
- Progress / History 的结果感更接近真实教练复盘
- Home / Progress / History / Mock Exam 现在统一展示“这次做了什么 / 哪一点进步了 / 明天为什么回来”

### 5. 发布验证从人工 checklist 升级到真实 smoke

- GUI 启动支持无 WebView smoke 模式，便于真实验证打包产物
- 可以对 `english-coach-opensource.exe` 做 portable 启动验证
- 可以对 `english-coach-opensource-setup.exe` 做静默安装与启动验证
- 也可以对 `english-coach-cloud.exe` / `english-coach-cloud-setup.exe` 做同样的 smoke 验证
- smoke 会自动完成最小离线 Setup，并验证 Reading / Listening 后的结果回写
- `python build_opensource.py` 会一次生成 exe、setup 和 zip，减少手工发布步骤
- `python build_cloud.py` 也会一次生成 exe、setup 和 zip，减少商业版手工发布步骤

## 当前适合重点测试的内容

1. 首启 Setup 是否能顺利完成
2. Home 的 coach 任务是否清晰、是否能一键进入真实训练页
3. 不配置 API key 时，Vocabulary / Grammar / Reading / Listening / History 是否都可正常使用
4. 配置 API key 后，Writing / Speaking / Chat 是否正常工作
5. 完成任意训练后，Progress / History 是否立即出现真实变化
6. 测试提醒与 quiet hours 是否按预期工作

## 当前仍要保持克制的地方

- 这仍不是完整商业化成熟平台
- `Mock Exam` 仍是 section-flow，不是统一统分系统
- `Writing / Speaking` 的高质量反馈仍依赖用户自己的 API key
- 当前内容质量和覆盖率仍会继续迭代，不应夸大为最终定版
