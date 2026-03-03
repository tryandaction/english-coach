#!/usr/bin/env python3
"""Package English Coach for distribution - creates a proper zip with all required files."""
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

RELEASE_DIR = Path(__file__).parent / "releases"
PACKAGE_NAME = "english-coach-portable"

def create_package():
    """Create a portable zip package with all required files."""

    # Check if exe exists
    exe_path = RELEASE_DIR / "english-coach.exe"
    if not exe_path.exists():
        print(f"Error: {exe_path} not found. Build the exe first.")
        return False

    # Create temp directory for packaging
    temp_dir = RELEASE_DIR / "_package_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    print("Creating portable package...")

    # Copy exe
    print(f"  Copying english-coach.exe ({exe_path.stat().st_size // 1024 // 1024}MB)")
    shutil.copy2(exe_path, temp_dir / "english-coach.exe")

    # Copy config.yaml template (without user-specific paths)
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
    print("  Created config.yaml template")

    # Copy .env.example (not the real .env with API key)
    env_example = """# English Coach API Configuration
# Rename this file to .env and add your DeepSeek API key below

DEEPSEEK_API_KEY=sk-your-key-here
"""
    (temp_dir / ".env.example").write_text(env_example, encoding="utf-8")
    print("  Created .env.example")

    # Copy content folder if it exists
    content_src = RELEASE_DIR / "content"
    if content_src.exists():
        shutil.copytree(content_src, temp_dir / "content")
        print("  Copied content/ folder")

    # Create README
    readme = """English Coach - Portable Installation
======================================

IMPORTANT: Keep all files together!
重要：请将所有文件保持在一起！

Required Files / 必需文件:
  - english-coach.exe    - Main application / 主程序
  - .env                 - API key (you need to create this) / API密钥（需要创建）
  - config.yaml          - Settings / 配置文件
  - content/             - Learning materials / 学习材料

Quick Start / 快速开始:

1. Rename .env.example to .env
   将 .env.example 重命名为 .env

2. Edit .env and add your DeepSeek API key:
   编辑 .env 并添加您的 DeepSeek API 密钥：

   DEEPSEEK_API_KEY=sk-your-actual-key-here

3. Double-click english-coach.exe
   双击 english-coach.exe

4. Complete the setup wizard
   完成设置向导

Important Notes / 重要提示:

- DO NOT move only the .exe file - move the entire folder!
  不要只移动 .exe 文件 - 请移动整个文件夹！

- You can create a desktop shortcut to the .exe
  可以为 .exe 创建桌面快捷方式

- The app will create a "data" folder for your progress
  应用会创建 "data" 文件夹保存您的学习进度

Troubleshooting / 故障排除:

Problem: "No AI client configured"
问题："No AI client configured"

Solution: Make sure .env file exists in the same folder as the .exe
解决方案：确保 .env 文件与 .exe 在同一文件夹中

Problem: App won't start
问题：应用无法启动

Solution: Keep all files together (exe, .env, config.yaml, content/)
解决方案：将所有文件保持在一起（exe、.env、config.yaml、content/）

Support / 支持:
  GitHub: https://github.com/your-repo/english-coach
"""
    (temp_dir / "README.txt").write_text(readme, encoding="utf-8")
    print("  Created README.txt")

    # Create zip file
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_path = RELEASE_DIR / f"{PACKAGE_NAME}-{timestamp}.zip"

    print("\nCreating zip archive...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in temp_dir.rglob("*"):
            if file.is_file():
                arcname = f"english-coach/{file.relative_to(temp_dir)}"
                zf.write(file, arcname)
                print(f"  + {arcname}")

    # Cleanup
    shutil.rmtree(temp_dir)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\nPackage created: {zip_path.name} ({size_mb:.1f}MB)")
    print("\nDistribution instructions:")
    print(f"   1. Upload {zip_path.name} to GitHub releases")
    print(f"   2. Users extract the zip and get a complete 'english-coach' folder")
    print(f"   3. Users rename .env.example to .env and add their API key")
    print(f"   4. Users double-click english-coach.exe")

    return True

if __name__ == "__main__":
    create_package()
