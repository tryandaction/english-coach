#!/usr/bin/env python3
"""
Package both Cloud Edition and Open Source Edition for distribution.
"""
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

RELEASE_DIR = Path(__file__).parent / "releases"

def create_cloud_edition():
    """Create cloud edition package with license system (for commercial sales)."""
    print("\n=== Creating Cloud Edition (Commercial) ===")

    exe_path = RELEASE_DIR / "english-coach.exe"
    if not exe_path.exists():
        print(f"Error: {exe_path} not found. Build the exe first.")
        return False

    temp_dir = RELEASE_DIR / "_cloud_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    print("  Copying english-coach.exe")
    shutil.copy2(exe_path, temp_dir / "english-coach.exe")

    # Cloud edition config - no API key needed (uses license system)
    config_cloud = """api_key: ''
backend: deepseek
data_dir: data
history_retention_days: 30
language:
  teaching: en
  ui: zh
model:
  default: deepseek-chat
  writing: deepseek-chat
"""
    (temp_dir / "config.yaml").write_text(config_cloud, encoding="utf-8")
    print("  Created config.yaml")

    # Copy content folder
    content_src = RELEASE_DIR / "content"
    if content_src.exists():
        shutil.copytree(content_src, temp_dir / "content")
        print("  Copied content/ folder")

    # Cloud edition README
    readme_cloud = """English Coach - Cloud Edition / 云版
=====================================

本版本为云版（商业版），需要购买激活码使用。

Quick Start / 快速开始:
----------------------

1. 双击 english-coach.exe 启动
   Double-click english-coach.exe to start

2. 完成基础设置（姓名、考试目标）
   Complete basic setup (name, exam target)

3. 点击左下角「License」，输入购买的激活码
   Click "License" at bottom-left, enter your activation key

4. 激活成功后，所有 AI 功能立即可用，无需配置 API Key
   After activation, all AI features work immediately

Features / 功能特点:
-------------------

- 开箱即用，无需配置 API Key
  Ready to use, no API key configuration needed

- 包含 API 费用，不用担心额外开销
  API costs included, no extra charges

- 一次激活，所有 AI 功能立即可用
  One-time activation, all AI features enabled

- 本地存储，数据隐私安全
  Local storage, data privacy guaranteed

Pricing / 定价:
--------------

- 月付：¥29.9（30天）
- 年付：¥109（365天）
- 续费：¥19.9/月

Purchase / 购买方式:
-------------------

- 闲鱼/淘宝搜索"英语教练"
- 微信/QQ 联系卖家

Support / 技术支持:
------------------

购买时提供的联系方式
Contact provided at purchase

---

注意：本版本为商业版，需要激活码才能使用 AI 功能。
如需免费开源版（需自己配置 API Key），请下载 Open Source Edition。
"""
    (temp_dir / "README.txt").write_text(readme_cloud, encoding="utf-8")
    print("  Created README.txt")

    # Create zip
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_path = RELEASE_DIR / f"english-coach-cloud-{timestamp}.zip"

    print("\n  Creating zip archive...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in temp_dir.rglob("*"):
            if file.is_file():
                arcname = f"english-coach/{file.relative_to(temp_dir)}"
                zf.write(file, arcname)

    shutil.rmtree(temp_dir)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\n  Cloud Edition created: {zip_path.name} ({size_mb:.1f}MB)")
    return True


def create_opensource_edition():
    """Create open source edition package (users bring their own API key)."""
    print("\n=== Creating Open Source Edition ===")

    exe_path = RELEASE_DIR / "english-coach.exe"
    if not exe_path.exists():
        print(f"Error: {exe_path} not found. Build the exe first.")
        return False

    temp_dir = RELEASE_DIR / "_opensource_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    print("  Copying english-coach.exe")
    shutil.copy2(exe_path, temp_dir / "english-coach.exe")

    # Open source config template
    config_template = """api_key: ''
backend: deepseek
data_dir: data
history_retention_days: 30
language:
  teaching: en
  ui: zh
model:
  default: deepseek-chat
  writing: deepseek-chat
"""
    (temp_dir / "config.yaml").write_text(config_template, encoding="utf-8")
    print("  Created config.yaml")

    # .env.example for open source users
    env_example = """# English Coach API Configuration
# Rename this file to .env and add your DeepSeek API key below
# Get your API key at: https://platform.deepseek.com

DEEPSEEK_API_KEY=sk-your-key-here
"""
    (temp_dir / ".env.example").write_text(env_example, encoding="utf-8")
    print("  Created .env.example")

    # Copy content folder
    content_src = RELEASE_DIR / "content"
    if content_src.exists():
        shutil.copytree(content_src, temp_dir / "content")
        print("  Copied content/ folder")

    # Open source README
    readme_opensource = """English Coach - Open Source Edition / 开源版
===========================================

IMPORTANT: Keep all files together!
重要：请将所有文件保持在一起！

Required Files / 必需文件:
  - english-coach.exe    - Main application / 主程序
  - .env                 - API key (you need to create this) / API密钥（需要创建）
  - config.yaml          - Settings / 配置文件
  - content/             - Learning materials / 学习材料

Quick Start / 快速开始:
----------------------

1. Rename .env.example to .env
   将 .env.example 重命名为 .env

2. Get your DeepSeek API key:
   获取 DeepSeek API 密钥：

   - Visit https://platform.deepseek.com
   - Register and get your API key (new users get ¥10 free credit)
   - 访问 https://platform.deepseek.com
   - 注册并获取 API 密钥（新用户送 ¥10 额度）

3. Edit .env and add your API key:
   编辑 .env 并添加您的 API 密钥：

   DEEPSEEK_API_KEY=sk-your-actual-key-here

4. Double-click english-coach.exe
   双击 english-coach.exe

5. Complete the setup wizard
   完成设置向导

API Cost Reference / API 费用参考:
---------------------------------

DeepSeek API is very affordable:
- Reading comprehension: ~¥0.001/article
- Writing feedback: ~¥0.005/essay
- Chat practice: ~¥0.001/turn
- Vocabulary/Grammar: Free (offline)

Estimated: ¥2-5/month for 1 hour daily study
估算：每天学习 1 小时，月费用约 ¥2-5

Important Notes / 重要提示:
--------------------------

- DO NOT move only the .exe file - move the entire folder!
  不要只移动 .exe 文件 - 请移动整个文件夹！

- You can create a desktop shortcut to the .exe
  可以为 .exe 创建桌面快捷方式

- The app will create a "data" folder for your progress
  应用会创建 "data" 文件夹保存您的学习进度

Troubleshooting / 故障排除:
--------------------------

Problem: "No AI client configured"
问题："No AI client configured"

Solution: Make sure .env file exists in the same folder as the .exe
解决方案：确保 .env 文件与 .exe 在同一文件夹中

Problem: App won't start
问题：应用无法启动

Solution: Keep all files together (exe, .env, config.yaml, content/)
解决方案：将所有文件保持在一起（exe、.env、config.yaml、content/）

Support / 支持:
--------------

- GitHub: https://github.com/your-repo/english-coach
- Issues: https://github.com/your-repo/english-coach/issues
- Documentation: https://github.com/your-repo/english-coach/wiki

License / 许可证:
----------------

Open source for personal use. Commercial use requires authorization.
个人学习使用完全免费。商业用途请联系作者获取授权。
"""
    (temp_dir / "README.txt").write_text(readme_opensource, encoding="utf-8")
    print("  Created README.txt")

    # Create zip
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_path = RELEASE_DIR / f"english-coach-opensource-{timestamp}.zip"

    print("\n  Creating zip archive...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in temp_dir.rglob("*"):
            if file.is_file():
                arcname = f"english-coach/{file.relative_to(temp_dir)}"
                zf.write(file, arcname)

    shutil.rmtree(temp_dir)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\n  Open Source Edition created: {zip_path.name} ({size_mb:.1f}MB)")
    return True


if __name__ == "__main__":
    print("English Coach - Dual Edition Packager")
    print("=" * 50)

    success_cloud = create_cloud_edition()
    success_opensource = create_opensource_edition()

    if success_cloud and success_opensource:
        print("\n" + "=" * 50)
        print("SUCCESS! Both editions created:")
        print("\n  Cloud Edition (Commercial):")
        print("    - For闲鱼/淘宝 sales")
        print("    - Users buy activation key")
        print("    - API cost included")
        print("\n  Open Source Edition:")
        print("    - For GitHub releases")
        print("    - Users bring own API key")
        print("    - Free and open source")
        print("\nNext steps:")
        print("  1. Upload Cloud Edition to your sales platform")
        print("  2. Upload Open Source Edition to GitHub releases")
        print("  3. Update version documentation")
