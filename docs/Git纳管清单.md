# English Coach Git 纳管清单

这份清单只回答三件事：

1. 哪些文件应该纳入公开仓库
2. 哪些文件必须继续私有
3. 你以后应该怎么操作

## 一、应该纳入公开仓库的内容

当前这版结构下，下面这些应作为公开仓库内容纳管：

- 共享代码目录
  - `ai/`
  - `cli/`
  - `content/`
  - `core/`
  - `gui/`
  - `modes/`
  - `utils/`
- 商业可公开维护目录
  - `commercial/`
- 发布工具目录
  - `release_tooling/`
- 通用脚本与手工脚本目录
  - `scripts/`
- 测试目录
  - `tests/`
- 发布文档目录
  - `docs/`
- 根目录元文件与便捷入口
  - `.gitignore`
  - `.mailmap`
  - `LICENSE`
  - `README.md`
  - `SECURITY.md`
  - `pyproject.toml`
  - `操作中心.pyw`
  - `build_cloud.py`
  - `build_opensource.py`
  - `license_keygen.py`
  - `send_key.py`

## 二、必须继续私有的内容

下面这些不要进入公开仓库：

- `private_commercial/` 下的真实配置和日志
  - `private_commercial/cloud_activation_config.json`
  - `private_commercial/seller_cloud_config.json`
  - `private_commercial/key_log.jsonl`
- `.env`
- `config.yaml`
- `data/`
- `releases/`
- 任意真实 token、secret、license 文件

说明：

- `private_commercial/README.md` 可以公开
- `private_commercial/` 里的真实文件必须继续被 ignore

## 三、当前 git status 里这些变化是什么意思

当前状态里常见的几类变化：

- `M`
  - 代表已有跟踪文件被修改
  - 这类一般应纳入本轮公开更新
- `D`
  - 代表旧位置文件被删除
  - 当前主要是因为文件搬家到了新目录
  - 例如：
    - `README.txt` -> `docs/release/README.txt`
    - `test_*.py` -> `tests/`
- `??`
  - 代表新文件或新目录尚未纳管
  - 当前大多是本轮整理后新增的公开目录
  - 例如：
    - `commercial/`
    - `release_tooling/`
    - `docs/`
    - `tests/`
    - 根目录 4 个便捷入口壳

## 四、你以后最简单的操作方式

如果你准备把“公开仓库该纳管的内容”正式纳入 Git，建议按下面顺序：

### 1. 先确认私有文件仍被忽略

```bash
git check-ignore -v private_commercial/cloud_activation_config.json
git check-ignore -v private_commercial/seller_cloud_config.json
git check-ignore -v private_commercial/key_log.jsonl
git check-ignore -v .env
git check-ignore -v config.yaml
```

### 2. 查看当前改动

```bash
git status --short
```

### 3. 纳管本轮公开文件

最直接：

```bash
git add .gitignore README.md SECURITY.md pyproject.toml LICENSE .mailmap
git add ai cli commercial content core docs gui modes release_tooling scripts tests utils
git add build_cloud.py build_opensource.py license_keygen.py send_key.py
```

### 4. 再检查一次暂存区

```bash
git diff --cached --stat
git diff --cached
```

重点确认：

- 没有 `private_commercial/` 里的真实文件
- 没有 `.env`
- 没有 `config.yaml`
- 没有 `data/`
- 没有 `releases/` 里的二进制产物

## 五、直接 `git add .` 是否安全

结论：

- 可以
- 前提是继续保持当前 `.gitignore` 不被破坏

当前已经实测：

- `git add -n .` 预演结果里，没有出现真实私有文件
- `git status --ignored` 明确显示以下文件被 ignore：
  - `private_commercial/cloud_activation_config.json`
  - `private_commercial/seller_cloud_config.json`
  - `private_commercial/key_log.jsonl`
  - `.env`
  - `config.yaml`
  - `data/`
  - `releases/`

也就是说：

- 你平时可以直接 `git add .`
- 但第一次正式纳管结构调整时，仍建议先看一眼 `git diff --cached`
- `private_commercial/README.md` 这种说明文件如果被 add，是正常的；真实私有文件不会被 add

## 六、你平时日常操作只要记住这些

### 默认优先

直接双击：

```text
操作中心.pyw
```

如果你不想记命令，优先用这个。

### 开源版发包

```bash
python build_opensource.py
python scripts/smoke_test_release.py --keep-temp
```

### 商业版发包

```bash
python scripts/check_cloud_activation.py
python build_cloud.py
python scripts/smoke_test_release.py --expected-version-mode cloud --portable-exe releases/english-coach-cloud.exe --installer-exe releases/english-coach-cloud-setup.exe --keep-temp
```

### 发激活码

```bash
python send_key.py
```

### 查 key / 撤销 key

```bash
python license_keygen.py --inspect XXXX-XXXX-XXXX-XXXX
python license_keygen.py --revoke XXXX-XXXX-XXXX-XXXX
```

## 七、当前建议

当前最稳妥的做法是：

1. 继续把 `private_commercial/` 当成私有区
2. 把本轮整理后的 `commercial/`、`release_tooling/`、`docs/`、`tests/` 纳入公开仓库
3. 不要把 `releases/`、`.env`、`config.yaml`、`data/` 推到公开面
