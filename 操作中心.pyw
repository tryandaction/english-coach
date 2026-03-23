from __future__ import annotations

import contextlib
import io
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from commercial.seller.license_keygen import (
    generate_key,
    get_plan_options,
    inspect_key,
    revoke_key,
)
from commercial.seller.send_key import build_delivery_message


def _npx_cmd() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


class OpsCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("English Coach 操作中心")
        self.geometry("980x760")
        self.minsize(920, 700)

        self._queue: queue.Queue[tuple[str, str | bool]] = queue.Queue()
        self._busy = False
        self._buttons: list[ttk.Button] = []

        self._plan_options = get_plan_options()
        self._build_ui()
        self.after(120, self._drain_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            root,
            text="English Coach 操作中心",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            root,
            text="默认双击这个文件即可，不需要你记一堆命令。",
        )
        subtitle.pack(anchor="w", pady=(4, 12))

        seller = ttk.LabelFrame(root, text="卖家操作", padding=12)
        seller.pack(fill=tk.X, pady=(0, 12))

        plan_row = ttk.Frame(seller)
        plan_row.pack(fill=tk.X)
        ttk.Label(plan_row, text="套餐").pack(side=tk.LEFT)
        self.plan_var = tk.StringVar(value=next(iter(self._plan_options.keys())))
        plan_values = [
            f"{key} · {item['label']}" for key, item in self._plan_options.items()
        ] + ["custom · 自定义天数"]
        self.plan_combo = ttk.Combobox(
            plan_row,
            textvariable=self.plan_var,
            values=plan_values,
            state="readonly",
            width=34,
        )
        self.plan_combo.current(0)
        self.plan_combo.pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(plan_row, text="自定义天数").pack(side=tk.LEFT)
        self.custom_days_var = tk.StringVar()
        ttk.Entry(plan_row, textvariable=self.custom_days_var, width=10).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(plan_row, text="备注").pack(side=tk.LEFT)
        self.note_var = tk.StringVar()
        ttk.Entry(plan_row, textvariable=self.note_var, width=28).pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        seller_btns = ttk.Frame(seller)
        seller_btns.pack(fill=tk.X, pady=(10, 0))
        self._add_button(seller_btns, "生成发货文案", self._on_generate_delivery).pack(side=tk.LEFT)
        ttk.Label(seller_btns, text="Key").pack(side=tk.LEFT, padx=(18, 6))
        self.key_var = tk.StringVar()
        ttk.Entry(seller_btns, textvariable=self.key_var, width=26).pack(side=tk.LEFT)
        self._add_button(seller_btns, "查 Key", self._on_inspect_key).pack(side=tk.LEFT, padx=(8, 0))
        self._add_button(seller_btns, "撤销 Key", self._on_revoke_key).pack(side=tk.LEFT, padx=(8, 0))

        release = ttk.LabelFrame(root, text="构建与部署", padding=12)
        release.pack(fill=tk.X, pady=(0, 12))
        row1 = ttk.Frame(release)
        row1.pack(fill=tk.X)
        self._add_button(row1, "开源版完整发布验证", self._run_opensource_full).pack(side=tk.LEFT)
        self._add_button(row1, "商业版完整发布验证", self._run_cloud_full).pack(side=tk.LEFT, padx=(10, 0))
        row2 = ttk.Frame(release)
        row2.pack(fill=tk.X, pady=(10, 0))
        self._add_button(row2, "仅检查商业激活", self._run_cloud_check).pack(side=tk.LEFT)
        self._add_button(row2, "重新部署商业后端", self._run_pages_deploy).pack(side=tk.LEFT, padx=(10, 0))
        self._add_button(row2, "清空输出", self._clear_output).pack(side=tk.LEFT, padx=(10, 0))

        tips = ttk.LabelFrame(root, text="你以后怎么操作", padding=12)
        tips.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(
            tips,
            text=(
                "日常最常用：双击本文件。\n"
                "发码：选套餐 -> 点“生成发货文案”。\n"
                "发开源版：点“开源版完整发布验证”。\n"
                "发商业版：点“商业版完整发布验证”。\n"
                "重发商业后端：点“重新部署商业后端”。"
            ),
            justify=tk.LEFT,
        ).pack(anchor="w")

        out_frame = ttk.LabelFrame(root, text="输出", padding=8)
        out_frame.pack(fill=tk.BOTH, expand=True)
        self.output = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            height=22,
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self._append("操作中心已就绪。\n")

    def _add_button(self, parent: ttk.Frame, text: str, command) -> ttk.Button:
        btn = ttk.Button(parent, text=text, command=command)
        self._buttons.append(btn)
        return btn

    def _append(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        state = tk.DISABLED if value else tk.NORMAL
        for btn in self._buttons:
            if btn["text"] == "清空输出":
                continue
            btn.configure(state=state)

    def _start_task(self, title: str, fn) -> None:
        if self._busy:
            messagebox.showinfo("忙碌中", "当前已有任务在执行，请等待完成。")
            return
        self._set_busy(True)
        self._append(f"\n=== {title} ===\n")
        threading.Thread(target=self._run_task, args=(fn,), daemon=True).start()

    def _run_task(self, fn) -> None:
        try:
            fn()
            self._queue.put(("done", True))
        except Exception:
            self._queue.put(("line", traceback.format_exc() + "\n"))
            self._queue.put(("done", False))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "line":
                    self._append(str(payload))
                elif kind == "clipboard":
                    self.clipboard_clear()
                    self.clipboard_append(str(payload))
                elif kind == "done":
                    self._set_busy(False)
                    if payload:
                        self._append("\n[完成]\n")
                    else:
                        self._append("\n[失败]\n")
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def _capture_callable(self, fn) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn()
        return buf.getvalue()

    def _run_commands(self, steps: list[tuple[str, Path, list[str]]]) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for title, cwd, cmd in steps:
            self._queue.put(("line", f"\n>>> {title}\n$ {' '.join(cmd)}\n"))
            process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._queue.put(("line", line))
            code = process.wait()
            if code != 0:
                raise RuntimeError(f"{title} 失败，退出码 {code}")

    def _resolve_choice(self) -> tuple[int, str, str, bool]:
        raw = self.plan_combo.get().strip()
        note = self.note_var.get().strip()
        if raw.startswith("custom"):
            days_text = self.custom_days_var.get().strip()
            if not days_text.isdigit() or int(days_text) <= 0:
                raise ValueError("自定义天数必须是正整数。")
            days = int(days_text)
            label = f"自定义 {days}天"
            return days, label, note, False
        plan_key = raw.split("·", 1)[0].strip()
        item = self._plan_options[plan_key]
        return int(item["days"]), str(item["label"]), note or str(item.get("note", "")), bool(item.get("renewal"))

    def _on_generate_delivery(self) -> None:
        def task() -> None:
            days, label, note, renewal = self._resolve_choice()
            output = self._capture_callable(lambda: generate_key(days, note))
            key = ""
            for line in output.splitlines():
                if line.startswith("Key"):
                    key = line.split(":", 1)[1].strip()
            if not key:
                raise RuntimeError("生成成功但未解析出 Key。")
            message = build_delivery_message(
                key=key,
                days=days,
                label=label,
                note=note,
                renewal=renewal,
            )
            self._queue.put(("line", output + "\n" + message + "\n"))
            self._queue.put(("clipboard", message))
            self._queue.put(("line", "\n已复制发货文案到剪贴板。\n"))

        self._start_task("生成发货文案", task)

    def _on_inspect_key(self) -> None:
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("缺少 Key", "先输入要查询的 Key。")
            return

        def task() -> None:
            output = self._capture_callable(lambda: inspect_key(key))
            self._queue.put(("line", output + "\n"))

        self._start_task("查询 Key", task)

    def _on_revoke_key(self) -> None:
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("缺少 Key", "先输入要撤销的 Key。")
            return
        if not messagebox.askyesno("确认撤销", f"确认撤销这个 Key？\n\n{key}"):
            return

        def task() -> None:
            output = self._capture_callable(lambda: revoke_key(key))
            self._queue.put(("line", output + "\n"))

        self._start_task("撤销 Key", task)

    def _run_opensource_full(self) -> None:
        steps = [
            ("构建开源版", ROOT, [sys.executable, str(ROOT / "build_opensource.py")]),
            ("开源版 smoke", ROOT, [sys.executable, str(ROOT / "scripts" / "smoke_test_release.py"), "--keep-temp"]),
        ]
        self._start_task("开源版完整发布验证", lambda: self._run_commands(steps))

    def _run_cloud_full(self) -> None:
        steps = [
            ("检查商业激活", ROOT, [sys.executable, str(ROOT / "scripts" / "check_cloud_activation.py")]),
            ("构建商业版", ROOT, [sys.executable, str(ROOT / "build_cloud.py")]),
            (
                "商业版 smoke",
                ROOT,
                [
                    sys.executable,
                    str(ROOT / "scripts" / "smoke_test_release.py"),
                    "--expected-version-mode",
                    "cloud",
                    "--portable-exe",
                    "releases/english-coach-cloud.exe",
                    "--installer-exe",
                    "releases/english-coach-cloud-setup.exe",
                    "--keep-temp",
                ],
            ),
        ]
        self._start_task("商业版完整发布验证", lambda: self._run_commands(steps))

    def _run_cloud_check(self) -> None:
        steps = [
            ("检查商业激活", ROOT, [sys.executable, str(ROOT / "scripts" / "check_cloud_activation.py")]),
        ]
        self._start_task("仅检查商业激活", lambda: self._run_commands(steps))

    def _run_pages_deploy(self) -> None:
        steps = [
            (
                "重新部署商业后端",
                ROOT / "commercial" / "deploy" / "pages",
                [
                    _npx_cmd(),
                    "wrangler",
                    "pages",
                    "deploy",
                    ".",
                    "--project-name",
                    "english-coach-license",
                    "--branch",
                    "main",
                    "--commit-dirty=true",
                ],
            ),
            ("部署后检查商业激活", ROOT, [sys.executable, str(ROOT / "scripts" / "check_cloud_activation.py")]),
        ]
        self._start_task("重新部署商业后端", lambda: self._run_commands(steps))

    def _clear_output(self) -> None:
        if self._busy:
            return
        self.output.delete("1.0", tk.END)
        self._append("输出已清空。\n")


def main() -> None:
    app = OpsCenter()
    app.mainloop()


if __name__ == "__main__":
    main()
