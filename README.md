# English Coach

`English Coach` 是一个面向 TOEFL / IELTS / GRE / CET / General English 的桌面英语学习应用。

当前仓库是 **Open Source / 开源版主仓库**，重点不是“云端大平台”，而是一个：

- 能稳定跑通本地学习闭环的桌面产品
- 有词汇 / 阅读 / 听力 / 语法 / 写作 / 口语 / Mock Exam 主路径
- 支持用户自带 API key 的 AI 反馈能力
- 已经开始具备“每日计划、提醒、复盘、留存”的 coach 能力

源码默认运行模式是 `opensource`。Cloud 激活后端、卖家运维脚本、真实密钥与发布运维材料不属于这个公开仓库。

## 当前定位

当前更准确的定位是：

- 不是“演示 demo”
- 也不是“已经做完的大型商业化平台”
- 而是一个正在向“持续陪伴式英语教练产品”推进的可运行产品底座

当前已具备：

- 本地词汇学习与 SRS 复习
- 内置词书 / 自建词书 / 自动同步开源词表
- Reading / Listening 离线训练与 fallback
- TOEFL / IELTS 重点题型的离线优先命中
- Writing / Speaking / Chat 的自带 key AI 路径
- Practice / Mock Exam / Progress / History 的完整主界面
- Daily coach plan / reminder / recap 的第一版骨架

## 本地运行

### 1. 安装依赖

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
```

如需完整可选能力：

```bash
pip install -e .[full]
```

### 2. 启动 GUI

```bash
python -m gui.main
```

### 3. 启动 CLI

```bash
english-coach --help
```

## 本地打包发布

如果你要重建当前 Open Source 桌面发布物，直接运行：

```bash
python build_opensource.py
```

这会在 `releases/` 下同步生成：

- `english-coach-opensource.exe`
- `english-coach-opensource-setup.exe`
- `english-coach-v2.0.0-opensource.zip`

发布前建议再运行：

```bash
python scripts/smoke_test_release.py --keep-temp
```

## AI 配置

Open Source 版本默认不附带任何商业激活配置。

你可以直接在 Setup 中配置自己的 API key，支持：

- `DeepSeek`
- `OpenAI`
- `Anthropic`
- `Qwen / DashScope`

如果没有 API key，以下能力仍然可用：

- Vocabulary / Word Books / SRS
- Grammar
- Reading 离线训练与 fallback
- Listening 内置脚本流程
- Progress / History / 基础 Practice 页面
- 每日计划、基础提醒与本地复盘

## Coach 能力（当前版本）

当前仓库已经开始具备英语教练产品的第一版能力：

- 首页会生成“今天该做什么”
- 计划优先级固定：到期复习 → 弱项修复 → 考试目标任务 → 冲刺任务
- 首页 coach 任务可直接进入真实训练页
- Progress 会显示计划完成率、稳定度、复习债务趋势
- History 会按天复盘，而不只是 session 列表
- 四类任务完成后会写回简短结果 recap，供 Home / Progress / History 复用
- Home / Progress / History / Mock Exam 会统一展示“这次做了什么 / 哪一点进步了 / 明天为什么回来”
- Setup 支持设置学习时间、quiet hours、本地提醒
- 有 profile 后会自动同步开源词表到内置词书与词汇库
- 写作 / 口语 prompt 会尽量避免近 7 天重复
- Listening 已开始支持按题型优先命中内置素材，而不是只按 conversation / monologue 粗分

当前提醒策略是：

- 以本地提醒为主
- 支持测试提醒
- quiet hours 内不发送普通提醒
- 支持 Bark / Webhook 扩展入口
- 默认不做高频骚扰

## 数据目录

默认用户数据目录由运行模式决定：

- 源码运行：项目目录下的 `data/`
- 打包运行：用户本地可写目录

数据里通常包含：

- `user.db`
- `teaching.db`
- 学习历史
- 自建词书
- 本地配置
- `license.key`（若存在 cloud 版本本地记录）

这些文件都不应提交到 Git。

## 当前验证基线

当前自动验证基线：

- `python -m compileall ai core gui utils cli modes commercial release_tooling build_cloud.py build_opensource.py scripts tests`
- `python -m unittest tests.test_license_security tests.test_quality_contract tests.test_coach_contract tests.test_gui_smoke`
- `node --check gui/static/app.js`
- `node --check gui/static/pages/*.js`

当前发布验证基线：

- `python build_opensource.py`
- `python scripts/smoke_test_release.py --keep-temp`
- 会真实验证 portable exe、setup 安装版、首启 Setup、最小离线主流程，以及 Reading / Listening 完成后的结果回写

## 仓库边界

当前推荐边界是：

- 通用产品代码、构建脚本、测试脚本、Cloud 激活实现代码都可以保留在公开仓库
- 商业专用卖家工具与部署资料集中在 `commercial/`
- 发布说明与发包文档集中在 `docs/release/`
- 真实商业配置、卖家运维资料、本地发货日志统一放到 `private_commercial/`
- `private_commercial/` 目录本身可以存在，但公开仓库只保留说明文件，不保留真实值
- `releases/`、`.env`、`config.yaml`、用户数据仍不进入公开提交面

也就是说，真正需要私有化的是“配置与运营资料”，而不是整套商业代码。

## 当前目录结构

建议按下面理解这个仓库：

- `ai/` `core/` `gui/` `cli/` `modes/` `utils/`
  - 共享产品代码
- `content/`
  - 内置学习内容
- `scripts/`
  - 通用脚本、验证脚本、手工工具脚本
- `release_tooling/`
  - 桌面构建脚本、spec、installer、runtime hook
- `tests/`
  - 自动化测试
- `commercial/`
  - 商业版专用但可公开维护的卖家工具、部署目录、配置样例
- `docs/release/`
  - 跟随发布物同步到 `releases/` 的说明文档
- `private_commercial/`
  - 真实商业配置、发货日志、本地运维资料
- `releases/`
  - 本地构建产物

## 你以后怎么操作

最常用的日常命令已经整理到：

- `docs/操作速查.md`

## 安全

提交前至少检查：

- `.env`
- `config.yaml`
- `data/`
- `releases/`
- `private_commercial/`
- `seller_cloud_config.json`
- `cloud_activation_config.json`

更详细的提交安全边界见 [SECURITY.md](SECURITY.md)。

## License

本仓库代码采用 [LICENSE](LICENSE) 中声明的许可。
