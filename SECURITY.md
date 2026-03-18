# Security Notes

这个仓库面向公开的开源版代码，不应包含任何真实商业配置或敏感文件。

## 不应提交的内容

永远不要提交以下内容：

- `.env`
- `config.yaml`
- `data/`
- `releases/`
- `seller_cloud_config.json`
- `cloud_activation_config.json`
- 任意真实 API key / token / secret
- 任意真实 `license.key`
- 任意卖家订单、日志或密钥生成记录

## 当前公开仓库的安全边界

公开仓库应只包含：

- Open Source 主程序源码
- 本地离线学习能力
- 用户自带 API key 的接入逻辑
- 不含真实值的占位或空默认配置

公开仓库不应包含：

- Cloud 激活后端部署目录
- 卖家注册码管理脚本
- 商业版真实激活地址与 token
- 内部运维文档

## 提交前自检

在 `git add` 之前，先检查：

```bash
git status --short
git diff --cached
```

并特别确认没有出现：

- `sk-...`
- `Bearer ...`
- `CLIENT_TOKEN`
- `ADMIN_TOKEN`
- `WORKER_SECRET`
- `SESSION_TOKEN_SECRET`

## 设计原则

商业版安全不应依赖“仓库里藏着某个值看不见”。

真正的安全边界应该来自：

- 服务端验证
- 权限分离
- 受限代理 token
- 密钥不落客户端
- 公开仓库不携带真实部署配置
