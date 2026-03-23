#!/usr/bin/env python3
"""
English Coach — 发货助手
收到付款后运行此脚本，选择套餐，自动生成唯一 Key 并复制到剪贴板。

用法：双击运行，或 python send_key.py
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from commercial.seller.license_keygen import choose_plan_interactive, generate_key


def copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


def build_delivery_message(*, key: str, days: int, label: str, note: str, renewal: bool) -> str:
    if renewal:
        steps = """【激活步骤】
① 打开 English Coach，点击左下角「🔑 License」
② 将上方 Key 完整复制粘贴进去，点击「激活」
③ 激活成功，有效期自动更新"""
        greeting = "感谢续费英语教练云版！您的新激活信息如下："
    else:
        steps = """【激活步骤】
① 下载并打开 English Coach（exe 文件）
② 首次运行完成基础设置（填写姓名、选择考试目标）
③ 点击左下角「🔑 License」
④ 将上方 Key 完整复制粘贴进去，点击「激活」
⑤ 激活成功后无需配置 API Key，所有 AI 功能立即可用"""
        greeting = "感谢购买英语教练！您的激活信息如下："

    note_line = f"\n【备注】{note}\n" if note else ""
    return f"""{greeting}

【License Key】
{key}

【套餐】{label}
【有效期】{days} 天（从激活时刻起计算）{note_line}
{steps}

【注意事项】
- Key 区分大小写，建议直接复制粘贴，不要手动输入
- 每个 Key 仅限一台设备激活，请勿转发给他人
- 到期后续费发送新 Key 重新激活即可，学习数据不会丢失
- 遇到任何问题随时私信我，24小时内回复

祝备考顺利！"""


def main() -> None:
    parser = argparse.ArgumentParser(description="English Coach 发货助手")
    parser.add_argument("--cli", action="store_true", help="兼容参数；当前默认即终端模式")
    _ = parser.parse_args()

    choice = choose_plan_interactive()
    days = int(choice["days"])
    label = choice["label"]
    note = choice.get("note", "")

    print("\n正在生成 Key 并注册到服务器...")
    key = generate_key(days, note)

    message = build_delivery_message(
        key=key,
        days=days,
        label=label,
        note=note,
        renewal=bool(choice.get("renewal")),
    )

    print()
    print("=" * 50)
    print(f"  套餐：{label} | 有效期：{days}天（激活时起算）")
    print("  以下内容已复制到剪贴板，直接粘贴发给买家：")
    print("=" * 50)
    print()
    print(message)
    print()
    print("=" * 50)

    copied = copy_to_clipboard(message)
    if copied:
        print("✓ 已复制到剪贴板，Ctrl+V 粘贴即可。")
    else:
        print("剪贴板复制失败，请手动复制上方内容。")

    print()
    input("按回车关闭...")


if __name__ == "__main__":
    main()
