# English Coach Deployment Checklist

## Shared Baseline

- [ ] `python -m unittest tests.test_license_security tests.test_quality_contract tests.test_chat_contract tests.test_review_contract tests.test_memory_contract tests.test_coach_contract tests.test_gui_smoke`
- [ ] `python -m compileall ai core gui utils cli modes commercial release_tooling build_cloud.py build_opensource.py scripts tests`
- [ ] `node --check gui/static/app.js`
- [ ] `node --check gui/static/pages/*.js`
- [ ] 确认没有把真实 `.env`、真实用户数据、卖家配置误打进公开包

## Open Source Release

- [ ] 运行 `python build_opensource.py`
- [ ] 不要与 `python build_cloud.py` 并行执行（两者共用 `build/`）
- [ ] 确认生成：
  - [ ] `releases/english-coach-opensource.exe`
  - [ ] `releases/english-coach-opensource-setup.exe`
  - [ ] `releases/english-coach-v2.0.0-opensource.zip`
- [ ] 运行 `python scripts/smoke_test_release.py --keep-temp`
- [ ] 确认 portable + installer 都通过
- [ ] 确认重复启动被单实例保护拦截，不会同时弹出多个桌面窗口
- [ ] 确认桌面快捷方式指向最新安装目录
- [ ] 确认开始菜单快捷方式指向最新安装目录
- [ ] 确认 smoke 结束后无 `english-coach-opensource` 残留进程

## Cloud Release

- [ ] 确认本地有效激活配置已就位：
  - [ ] 优先使用 `private_commercial/cloud_activation_config.json`
  - [ ] 兼容旧路径：`cloud_activation_config.json` 或 `releases/cloud_activation_config.json`
  - [ ] 若设置了 `EC_WORKER_URL / EC_WORKER_CLIENT_TOKEN`，两者必须同时设置
- [ ] 运行 `python scripts/check_cloud_activation.py`
- [ ] 确认 `runtime-info -> register -> activate -> verify -> proxy -> inspect -> revoke` 全通过
- [ ] 运行 `python build_cloud.py`
- [ ] 不要与 `python build_opensource.py` 并行执行（两者共用 `build/`）
- [ ] 确认生成：
  - [ ] `releases/english-coach-cloud.exe`
  - [ ] `releases/english-coach-cloud-setup.exe`
  - [ ] `releases/english-coach-v2.0.0-cloud.zip`
- [ ] 运行：
  - [ ] `python scripts/smoke_test_release.py --expected-version-mode cloud --portable-exe releases/english-coach-cloud.exe --installer-exe releases/english-coach-cloud-setup.exe --keep-temp`
- [ ] 确认 portable + installer 都通过
- [ ] 确认 cloud smoke 已覆盖 chat `remember / word-status / context`
- [ ] 确认 smoke 结束后无 `english-coach-cloud` 残留进程
- [ ] 手工安装 `releases/english-coach-cloud-setup.exe` 后确认：
  - [ ] 默认目录为 `%LOCALAPPDATA%\English Coach Cloud`
  - [ ] 桌面快捷方式指向 `%LOCALAPPDATA%\English Coach Cloud\english-coach-cloud.exe`
  - [ ] 开始菜单快捷方式指向 `%LOCALAPPDATA%\English Coach Cloud\english-coach-cloud.exe`
  - [ ] 旧开发配置会备份为 `config.dev-backup.yaml` 并自动回正

## Product Acceptance

- [ ] Home / Progress / History / Mock Exam 结果感一致
- [ ] Reading / Listening 重点离线题型命中正常
- [ ] `/api/memory/status` 与 `/api/practice/recommendation` 返回正常
- [ ] Open Source 版不要求在线激活
- [ ] Open Source 版输出目录没有残留 `cloud_activation_config.json`
- [ ] Cloud 版可走 License 激活链
- [ ] 文档与实际发布物名称一致
- [ ] `gui/cloud_license_defaults.py` 仍保持源码空默认值
- [ ] 商业私有文件已集中放入 `private_commercial/` 或其他私有位置
- [ ] 开源公开面不暴露 `releases/cloud_activation_config.json`

## No-Go Conditions

- [ ] 任一 smoke 失败
- [ ] 任一版本 build 失败
- [ ] 发布物缺失 exe/setup/zip 任一项
- [ ] Cloud 激活检查失败
- [ ] 包内仍包含错误或过时文档口径
- [ ] cloud 包安装后桌面快捷方式未更新到正式安装路径
