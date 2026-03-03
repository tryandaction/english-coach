# English Coach

**AI-powered English learning assistant for STEM students — TOEFL / GRE / IELTS / CET**

AI 驱动的理工科英语学习助手，支持托福 / GRE / 雅思 / 四六级

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Features / 功能

| Feature / 功能 | Description / 说明 | API Cost / API 费用 |
|---|---|---|
| 🃏 Vocabulary SRS / 词汇间隔重复 | SM-2 flashcards, offline | Free / 免费 |
| ✏️ Grammar Drills / 语法练习 | Fill-in-the-blank, 5 categories | Free / 免费 |
| 📖 Reading / 阅读理解 | Passage + AI questions, cached | ~$0.001 |
| 📝 Writing / 写作批改 | Rubric scoring + feedback | ~$0.005 |
| 💬 Chat / 对话练习 | Free conversation, error correction | ~$0.001/turn |
| 🎧 Listening / 听力练习 | Conversations + comprehension questions | ~$0.001 |
| 📚 Word Books / 单词本 | Custom vocabulary collections with SRS | Free / 免费 |

---

## Quick Start / 快速开始

### Download / 下载

**Open Source Edition (Free) / 开源版（免费）**

Download the latest release: [Releases](https://github.com/tryandaction/english-coach/releases)

下载最新版本：[Releases](https://github.com/tryandaction/english-coach/releases)

### Setup / 设置

1. **Extract the zip file / 解压 zip 文件**
   ```
   english-coach/
   ├── english-coach.exe
   ├── .env.example
   ├── config.yaml
   └── content/
   ```

2. **Get your API key / 获取 API 密钥**

   Visit [DeepSeek Platform](https://platform.deepseek.com) and register for an API key.

   访问 [DeepSeek 平台](https://platform.deepseek.com) 注册并获取 API 密钥。

   New users get ¥10 free credit! / 新用户送 ¥10 额度！

3. **Configure API key / 配置 API 密钥**

   Rename `.env.example` to `.env` and add your key:

   将 `.env.example` 重命名为 `.env` 并添加密钥：

   ```
   DEEPSEEK_API_KEY=sk-your-key-here
   ```

4. **Launch / 启动**

   Double-click `english-coach.exe` and complete the setup wizard.

   双击 `english-coach.exe` 并完成设置向导。

---

## API Cost / API 费用

DeepSeek API is very affordable:

- Reading comprehension: ~¥0.001/article
- Writing feedback: ~¥0.005/essay
- Chat practice: ~¥0.001/turn
- Vocabulary/Grammar: Free (offline)

**Estimated cost: ¥2-5/month for 1 hour daily study**

DeepSeek API 非常便宜：

- 阅读理解：约 ¥0.001/篇
- 写作批改：约 ¥0.005/篇
- 对话练习：约 ¥0.001/轮
- 词汇/语法：免费（离线）

**估算费用：每天学习 1 小时，月费用约 ¥2-5**

---

## System Requirements / 系统要求

- **OS / 操作系统**: Windows 10/11 (64-bit)
- **RAM / 内存**: 2GB minimum
- **Storage / 存储**: 200MB
- **Internet / 网络**: Required for AI features / AI 功能需要联网

---

## Development / 开发

### Prerequisites / 前置要求

- Python 3.11+
- pip

### Install / 安装

```bash
git clone https://github.com/tryandaction/english-coach.git
cd english-coach
pip install -e ".[full]"
```

### Run CLI / 运行命令行版

```bash
# Setup
english-coach setup

# Ingest content
english-coach ingest ./content

# Start learning
english-coach plan
```

### Run GUI / 运行图形界面

```bash
python -m gui.main
```

### Build executable / 构建可执行文件

```bash
python build.py
```

---

## Project Structure / 项目结构

```
english-coach/
├── ai/                 # AI client integrations
├── cli/                # Command-line interface
├── content/            # Learning materials
│   ├── listening/      # Listening passages
│   ├── reading/        # Reading passages
│   └── vocab/          # Vocabulary lists
├── core/               # Core learning engine
│   ├── knowledge_base/ # Content management
│   ├── srs/            # Spaced repetition system
│   └── user_model/     # User progress tracking
├── gui/                # GUI application
│   ├── api/            # FastAPI endpoints
│   └── static/         # Frontend (HTML/CSS/JS)
└── modes/              # Learning modes (CLI)
```

---

## License / 许可证

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**For personal learning use only. Commercial use requires authorization.**

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

**仅供个人学习使用。商业用途需获得授权。**

---

## Contributing / 贡献

Contributions are welcome! Please feel free to submit a Pull Request.

欢迎贡献！请随时提交 Pull Request。

---

## Support / 支持

- **Issues**: [GitHub Issues](https://github.com/tryandaction/english-coach/issues)
- **Documentation**: [Wiki](https://github.com/tryandaction/english-coach/wiki)

---

## Acknowledgments / 致谢

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI powered by [PyWebView](https://pywebview.flowrl.com/)
- AI powered by [DeepSeek](https://www.deepseek.com/)

---

## Roadmap / 路线图

- [ ] Support for more AI backends (OpenAI, Claude, local models)
- [ ] Mobile app (iOS/Android)
- [ ] Web version
- [ ] More exam types (SAT, ACT, etc.)
- [ ] Community content sharing

---

**Made with ❤️ for English learners**
