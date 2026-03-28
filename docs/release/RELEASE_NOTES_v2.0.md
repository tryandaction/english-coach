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
- Mock Reading 现在会优先命中更长的本地长篇素材，不再默认掉到过短 passage
- Mock Exam 现在可以明确指定先做哪个 section，而不是只能走默认顺序

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
- 商业卖家侧继续以 `python send_key.py` 作为默认入口，可直接输出买家文案

### 6. 长期私人教练底座开始落地

- learner profile 新增长期目标、学习风格、学习偏好等稳定字段
- 新增结构化 learner memory、learning events、daily memory snapshot
- 词汇状态不再只停留在 SRS 卡片，还会额外记录 `known / unsure / unknown`
- 系统会统计 review due 和 frequent forgetting，用于后续 coach 决策
- coach summary 新增 heartbeat action、memory summary、连续性相关信息
- 新增本地 `/api/memory/status` 与 `/api/memory/facts`，便于 GUI 和后续集成读取长期记忆

### 7. review pool / policy / chat 连续性进一步落地

- 新增 `review pool` 汇总与优先级排序，词汇定向练习不再只给新词
- 新增 `next_action` 策略输出，`CoachService` 和 `/api/practice/recommendation` 都能给出下一步动作
- Chat 现在可以显式记住 learner facts，而不只是临时对话
- Chat 现在可以显式标记词汇 `known / unsure / unknown`
- Chat 回复会读取 learner context、review due 和高错词，连续性更真实

### 8. 词书编辑与桌面安装体验完成一轮实修

- 用户自建词书中的已添加单词，现在在主行就能看到显式 `Edit` 按钮，不再把编辑入口藏在展开详情底部
- Add Word 弹层与词书内联编辑器统一成实时预览卡片，AI Fill、搜索复用与手工修改会同步更新卡片内容
- 已存在的词条可以继续修改 `word / definition / example / collocations / context` 等字段，并立即回写列表显示
- 词卡编辑器右侧表单布局已放宽，输入框与多行文本框会充分利用可用宽度，不再挤在窄栏里
- 桌面版新增单实例保护，重复启动不会再同时弹出多个 English Coach 窗口
- Setup 升级流程改成单一“自动覆盖旧版”选项，不再连续弹出多个业务确认框
- 旧版卸载统一走静默参数，安装后开始菜单与桌面快捷方式会重新覆盖到新安装目录
- release smoke 现在会额外校验：重复启动被拦截、开始菜单快捷方式正确、桌面快捷方式正确

## 当前适合重点测试的内容

1. 首启 Setup 是否能顺利完成
2. Home 的 coach 任务是否清晰、是否能一键进入真实训练页
3. 不配置 API key 时，Vocabulary / Grammar / Reading / Listening / History 是否都可正常使用
4. Mock Exam 选择不同 section 起点时，是否能直接进入对应 section
5. Mock Reading 的篇幅、题量和加载速度是否更像正式训练
6. 配置 API key 后，Writing / Speaking / Chat 是否正常工作
7. 完成任意训练后，Progress / History 是否立即出现真实变化
8. 关闭并重新打开应用后，词汇连续性和 coach 连续性是否仍保留
9. Chat 显式记忆写入后，下一次会话是否能延续上下文
10. 测试提醒与 quiet hours 是否按预期工作
11. 用户自建词书里，已添加单词主行是否始终可见 `Edit` 按钮，并且修改后列表会立即刷新
12. 桌面版重复启动时，是否只保留单实例窗口
13. 安装新版后，桌面 / 开始菜单快捷方式是否都指向新的安装目录

## 当前仍要保持克制的地方

- 这仍不是完整商业化成熟平台
- `Mock Exam` 仍是 section-flow，不是统一统分系统
- `Writing / Speaking` 的高质量反馈仍依赖用户自己的 API key
- 当前内容质量和覆盖率仍会继续迭代，不应夸大为最终定版
- 长期记忆与推荐已接入 Home / Progress / Chat；当前仍没有单独的 memory 管理页
