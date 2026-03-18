# English Coach

`English Coach` 是一个面向 TOEFL / IELTS / GRE / CET / General English 的桌面英语学习应用。

当前这个 GitHub 仓库按 **Open Source / 开源版** 收口，重点保留：

- GUI + CLI 主程序
- Vocabulary / Word Books / SRS
- Grammar drills
- Reading / Listening 离线训练主路径
- Practice / Mock Exam / Progress 页面
- 自带 API key 的 AI 功能入口

默认源码运行模式是 `opensource`。Cloud 激活后端、卖家脚本、发布目录、密钥与运维材料不属于这个公开仓库的一部分。

## 当前定位

这个项目已经不是“只有 demo”的状态，但也不应夸大为大型商业备考平台。

当前更准确的定位是：

- 能稳定跑通离线学习主路径
- 能在用户自带 API key 时提供写作反馈、口语评分、Chat 等 AI 能力
- 具备词汇、阅读、听力、练习、进度等完整学习闭环
- Mock Exam 目前是连续 section flow，不是最终标准化统分系统

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

这些文件都不应提交到 Git。

## 质量说明

当前仓库已经做过一轮以“产品质量优先”为目标的收口，重点处理了：

- 首启 / Setup / Home / Progress 的状态契约统一
- Cloud / self-key / no-AI 三类状态的前后端口径统一
- Practice 入口与真实能力对齐
- Reading / Listening / Writing / Speaking / Mock Exam 的结果闭环
- 最少关键测试与语法检查补齐

当前自动验证基线：

- `python -m compileall ai core gui utils cli modes`
- `python -m unittest test_license_security.py test_quality_contract.py`
- `node --check gui/static/app.js`
- `node --check gui/static/pages/*.js`

## 仓库边界

这个公开仓库刻意不包含以下内容：

- Cloudflare 激活后端部署目录
- 卖家注册码生成与管理脚本
- 实际激活地址、token、secret
- 发布目录、打包产物、真实配置文件
- 面向商业版运维的内部文档

如果你在本地看到这些文件，那是本地私有工作材料，不属于开源发布面。

## 安全

提交前至少检查：

- `.env`
- `config.yaml`
- `data/`
- `releases/`
- `seller_cloud_config.json`
- `cloud_activation_config.json`

更详细的提交安全边界见 [SECURITY.md](SECURITY.md)。

## License

本仓库代码采用 [LICENSE](LICENSE) 中声明的许可。
