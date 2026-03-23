# Private Commercial Files

这个目录用于存放商业版私有文件，但目录本身可以保留在公开仓库中作为约定入口。

公开仓库只保留本说明，不保留真实值。

建议把以下文件放到这里：

- `cloud_activation_config.json`
- `seller_cloud_config.json`
- `key_log.jsonl`
- 其他仅限本地商业打包或卖家运维使用的私有资料

当前代码会优先从这里读取：

- `build_cloud.py`
- `commercial/seller/license_keygen.py`
- `commercial/seller/send_key.py`
- `scripts/check_cloud_activation.py`

兼容性说明：

- 根目录下旧的 `cloud_activation_config.json`
- 根目录下旧的 `seller_cloud_config.json`
- 根目录下旧的 `key_log.jsonl`

仍可继续使用，但推荐逐步迁移到本目录，避免和开源公开面混在一起。
