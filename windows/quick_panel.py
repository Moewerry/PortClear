from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.actions import kill_record, record_action_hint
from core.inspector import inspect_ports
from core.models import PortRecord
from core.privilege import get_privilege_info


class QuickPanel:
    """Small tray-launched panel for the most common port cleanup workflow."""

    def __init__(self, master: tk.Misc, open_main_window=None, elevate=None) -> None:
        self.master = master
        self.open_main_window = open_main_window
        self.elevate = elevate
        self.window: tk.Toplevel | None = None
        self.records: list[PortRecord] = []
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.query_button: ttk.Button | None = None
        self.kill_button: ttk.Button | None = None
        self.hint_button: ttk.Button | None = None

    def show(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.master)
        self.window.title("PortClear 快速清理")
        self.window.geometry("520x420")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        privilege = get_privilege_info()
        self.status_var.set(f"当前权限: {privilege.label}")

        container = ttk.Frame(self.window, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="PortClear 快速清理", font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        ttk.Label(container, textvariable=self.status_var, foreground="#b45309").pack(anchor="w", pady=(4, 12))

        form = ttk.Frame(container)
        form.pack(fill="x")
        ttk.Label(form, text="端口号").pack(side="left")
        entry = ttk.Entry(form, textvariable=self.port_var, width=18)
        entry.pack(side="left", padx=(8, 8))
        entry.bind("<Return>", lambda _event: self.query())
        self.query_button = ttk.Button(form, text="查询", command=self.query)
        self.query_button.pack(side="left")

        columns = ("pid", "process", "state", "type")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=8)
        for name, title, width in [
            ("pid", "PID", 80),
            ("process", "进程", 150),
            ("state", "状态", 100),
            ("type", "类型", 130),
        ]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, anchor="center")
        self.tree.pack(fill="x", pady=(12, 8))

        actions = ttk.Frame(container)
        actions.pack(fill="x")
        self.kill_button = ttk.Button(actions, text="终止选中进程", command=self.kill_selected)
        self.kill_button.pack(side="left")
        self.hint_button = ttk.Button(actions, text="诊断建议", command=self.show_hint)
        self.hint_button.pack(side="left", padx=(8, 0))
        if self.open_main_window is not None:
            ttk.Button(actions, text="打开主窗口", command=self.open_main_window).pack(side="left", padx=(8, 0))
        if self.elevate is not None and not privilege.is_elevated:
            ttk.Button(actions, text="以管理员身份运行", command=self.elevate).pack(side="left", padx=(8, 0))

        ttk.Label(container, text="提示").pack(anchor="w", pady=(14, 2))
        self.log = tk.Text(container, height=6, wrap="word")
        self.log.pack(fill="both", expand=True)
        self._append_log("输入端口号后点击查询。")
        if privilege.limitations:
            self._append_log("当前为普通用户，部分进程可能无法终止。")

        entry.focus_set()

    def hide(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def query(self) -> None:
        port_text = self.port_var.get().strip()
        try:
            port = int(port_text)
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效端口号。", parent=self.window)
            return
        if port < 1 or port > 65535:
            messagebox.showerror("输入错误", "端口范围必须在 1-65535。", parent=self.window)
            return

        self._set_query_enabled(False)
        self._append_log(f"正在查询端口 {port}...")
        threading.Thread(target=self._query_worker, args=(port,), daemon=True).start()

    def kill_selected(self) -> None:
        record = self._selected_record()
        if record is None:
            messagebox.showinfo("提示", "请先选择一条记录。", parent=self.window)
            return
        if not record.pid:
            messagebox.showwarning("无法终止", "当前记录没有可终止的 PID。", parent=self.window)
            return
        if not messagebox.askyesno("确认终止", f"确认终止 PID {record.pid} ({record.process_name or '未知进程'})？", parent=self.window):
            return

        ok, message = kill_record(record)
        self._append_log(message)
        if ok:
            self.query()
        else:
            messagebox.showwarning("终止失败", message, parent=self.window)

    def show_hint(self) -> None:
        record = self._selected_record()
        if record is None:
            messagebox.showinfo("提示", "请先选择一条记录。", parent=self.window)
            return
        hint = record_action_hint(record)
        self._append_log(hint)
        messagebox.showinfo("诊断建议", hint, parent=self.window)

    def _query_worker(self, port: int) -> None:
        try:
            records = inspect_ports([port])
        except Exception as exc:  # pragma: no cover
            self.master.after(0, lambda: self._query_failed(port, str(exc)))
            return
        self.master.after(0, lambda: self._render_records(port, records))

    def _render_records(self, port: int, records: list[PortRecord]) -> None:
        self.records = records
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not records:
            self._append_log(f"端口 {port} 当前未发现占用。")
            self._set_query_enabled(True)
            return

        for index, record in enumerate(records):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    record.pid or "-",
                    record.process_name or "-",
                    record.state,
                    record.occupancy_type.value,
                ),
            )
        self.tree.selection_set("0")
        self.tree.focus("0")
        self.tree.see("0")
        self.tree.focus_set()
        self._append_log(f"端口 {port} 查询完成，发现 {len(records)} 条记录。")
        self._set_query_enabled(True)

    def _query_failed(self, port: int, error: str) -> None:
        self._append_log(f"端口 {port} 查询失败: {error}")
        self._set_query_enabled(True)
        messagebox.showerror("查询失败", error, parent=self.window)

    def _selected_record(self) -> PortRecord | None:
        selection = self.tree.selection()
        if not selection:
            return None
        index = int(selection[0])
        if 0 <= index < len(self.records):
            return self.records[index]
        return None

    def _append_log(self, message: str) -> None:
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def _set_query_enabled(self, enabled: bool) -> None:
        if self.query_button is not None:
            self.query_button.configure(text="查询" if enabled else "查询中...", state="normal" if enabled else "disabled")
