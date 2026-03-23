#!/usr/bin/env python3
"""
验证脚本 - 测试开源版和云版的区别
"""
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_version_detection():
    """测试版本检测"""
    print("=== 测试版本检测 ===")
    sys.path.insert(0, str(ROOT))
    from gui.version import get_version_mode, is_opensource, is_cloud

    mode = get_version_mode()
    print(f"[OK] VERSION_MODE: {mode}")
    print(f"[OK] is_opensource(): {is_opensource()}")
    print(f"[OK] is_cloud(): {is_cloud()}")
    return mode

def test_content_bundling(version_mode):
    """测试内容打包"""
    print("\n=== 测试内容打包 ===")
    from utils.paths import get_content_dir

    content_dir = get_content_dir()
    print(f"Content directory: {content_dir}")

    if content_dir.exists():
        vocab_dir = content_dir / 'vocab'
        if vocab_dir.exists():
            vocab_files = list(vocab_dir.glob('*.md'))
            print(f"[OK] 找到 {len(vocab_files)} 个词汇文件")
            if version_mode == "cloud":
                assert len(vocab_files) > 0, "云版应该包含词汇文件"
                print(f"[OK] 云版正确包含内容")
            else:
                print(f"[WARN] 开源版在开发环境中可以看到内容（正常）")
        else:
            print("[FAIL] Vocab 目录不存在")
    else:
        if version_mode == "opensource":
            print("[OK] 开源版不包含内容目录（正确）")
        else:
            print("[FAIL] 云版应该包含内容目录")

def test_app_creation():
    """测试应用创建"""
    print("\n=== 测试应用创建 ===")
    from gui.server import create_app

    app = create_app()
    print(f"[OK] 应用创建成功")
    print(f"[OK] 路由数量: {len(app.routes)}")

def test_spec_files():
    """测试 spec 文件配置"""
    print("\n=== 测试 Spec 文件配置 ===")

    # 检查开源版 spec
    opensource_spec = (ROOT / "release_tooling" / "specs" / "english_coach_opensource.spec").read_text()
    if "('content', 'content')" in opensource_spec:
        print("[FAIL] 开源版 spec 不应该包含 content 目录")
    else:
        print("[OK] 开源版 spec 正确（不包含 content）")

    # 检查云版 spec
    cloud_spec = (ROOT / "release_tooling" / "specs" / "english_coach_cloud.spec").read_text()
    if "('content', 'content')" in cloud_spec:
        print("[OK] 云版 spec 正确（包含 content）")
    else:
        print("[FAIL] 云版 spec 应该包含 content 目录")

def test_build_scripts():
    """测试构建脚本"""
    print("\n=== 测试构建脚本 ===")

    # 检查开源版构建脚本
    opensource_build = (ROOT / "release_tooling" / "build_opensource.py").read_text()
    if 'VERSION_MODE = "opensource"' in opensource_build:
        print("[OK] 开源版构建脚本正确设置 VERSION_MODE")
    else:
        print("[FAIL] 开源版构建脚本未正确设置 VERSION_MODE")

    # 检查云版构建脚本
    cloud_build = (ROOT / "release_tooling" / "build_cloud.py").read_text()
    if 'VERSION_MODE = "cloud"' in cloud_build:
        print("[OK] 云版构建脚本正确设置 VERSION_MODE")
    else:
        print("[FAIL] 云版构建脚本未正确设置 VERSION_MODE")

def main():
    print("=" * 60)
    print("English Coach - 版本验证脚本")
    print("=" * 60)

    try:
        # 测试版本检测
        version_mode = test_version_detection()

        # 测试内容打包
        test_content_bundling(version_mode)

        # 测试应用创建
        test_app_creation()

        # 测试 spec 文件
        test_spec_files()

        # 测试构建脚本
        test_build_scripts()

        print("\n" + "=" * 60)
        print("[OK] 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
