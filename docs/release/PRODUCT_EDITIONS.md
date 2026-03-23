# Product Editions / 产品版本说明

当前桌面发布线同时包含 **Open Source / 开源版** 和 **Cloud / 商业版**。

## 当前版本对比

| 项目 | Open Source / 开源版 | Cloud / 商业版 |
| --- | --- | --- |
| GUI / CLI | 支持 | 支持 |
| Vocabulary / Word Books / SRS | 支持 | 支持 |
| Grammar / Reading / Listening | 支持 | 支持 |
| Practice / Progress / History | 支持 | 支持 |
| Mock Exam section flow | 支持 | 支持 |
| Chat / Writing / Speaking AI 功能 | 需要用户自带 API key | 可走 License 激活内置 AI，或改用自带 API key |
| Cloud 激活服务 | 不随开源包发放 | 正式 cloud 包默认读取本地激活配置，安装后可直接走 License 激活 |
| 无 AI 时的离线主路径 | 支持 | 支持 |
| 安装更新路径 | `%LOCALAPPDATA%\\English Coach Open Source` | `%LOCALAPPDATA%\\English Coach Cloud` |
| 桌面快捷方式 | 可选创建 | 默认创建并更新到最新 cloud 安装版 |

## 当前适合测试的重点

- 首启 Setup
- 无 AI 时的降级体验
- 离线学习主路径
- Open Source 下配置自带 API key 的 AI 能力
- Cloud 下 License / 自带 API key / 离线三种入口是否清晰
- 首页、进度页、结果页的闭环体验
- Cloud 安装后桌面/开始菜单快捷方式是否指向正式安装目录
- 旧开发配置是否会自动备份并回正

## 当前不应夸大的地方

- 这不是完整商业化备考平台
- `Mock Exam` 仍不是统一作答与统分系统
- `Speaking / Writing` 的高质量反馈仍依赖 AI
- 内容质量仍会继续迭代，不应把当前覆盖率说成最终状态

## 当前发布边界

- GitHub Release 只发布开源版三个产物
- `releases/cloud_activation_config.json` 仅用于本地商业打包，不进入开源公开发布面
- 商业版继续独立发货，不把卖家配置和激活配置放到公开附件区
- 通用产品代码、构建链、Cloud 激活实现代码可以共用一套源码
- 真正私有的内容统一收口到 `private_commercial/` 或等效私有目录
