# Security Notes

这个仓库面向公开的开源版代码，不应包含任何真实商业配置或敏感文件。

## 不应提交的内容

永远不要提交以下内容：

- `.env`
- `config.yaml`
- `data/`
- `releases/`
- `private_commercial/` 下的真实文件
- `seller_cloud_config.json`
- `cloud_activation_config.json`
- 任意真实 API key / token / secret
- 任意真实 `license.key`
- 任意卖家订单、日志或密钥生成记录

## 当前公开仓库的安全边界

公开仓库应只包含：

- Open Source 主程序源码
- Cloud / 商业版共享代码
- Cloudflare 激活服务实现代码
- `commercial/` 目录下的卖家工具脚本本身
- 本地离线学习能力
- 用户自带 API key 的接入逻辑
- 不含真实值的占位或空默认配置

公开仓库不应包含：

- `private_commercial/` 中的真实配置与日志
- 商业版真实激活地址与 token
- 任意真实卖家配置、订单、发货记录
- 发布目录中的真实商业配置文件

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
- 私有配置集中放在 `private_commercial/`
