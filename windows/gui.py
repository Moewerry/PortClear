from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.actions import kill_record, record_action_hint, time_wait_tuning_advice
from core.inspector import inspect_ports
from core.models import PortRecord
from core.privilege import get_privilege_info

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None


class PortClearApp:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.title("PortClear")
        self.root.geometry("980x640")

        self.privilege = get_privilege_info()
        self.records: list[PortRecord] = []

        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value=f"当前权限: {self.privilege.label}")
        self.detail_var = tk.StringVar(value=self._build_limit_text())
        self.query_button: ttk.Button | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="PortClear 端口占用清理工具", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(header, textvariable=self.status_var, foreground="#b45309").pack(anchor="w", pady=(8, 0))
        ttk.Label(header, textvariable=self.detail_var, foreground="#475569").pack(anchor="w", pady=(2, 12))

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="端口").pack(side="left")
        ttk.Entry(controls, textvariable=self.port_var, width=16).pack(side="left", padx=(8, 12))
        self.query_button = ttk.Button(controls, text="查询", command=self.query_port)
        self.query_button.pack(side="left")
        ttk.Button(controls, text="终止进程", command=self.kill_selected).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="HTTP.sys 诊断", command=self.show_hint).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="TIME_WAIT 建议", command=self.show_tuning).pack(side="left", padx=(8, 0))

        columns = ("port", "protocol", "state", "pid", "process", "kind")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=16)
        for name, title, width in [
            ("port", "端口", 80),
            ("protocol", "协议", 80),
            ("state", "状态", 120),
            ("pid", "PID", 90),
            ("process", "进程", 220),
            ("kind", "分类", 160),
        ]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)

        log_frame = ttk.Frame(container)
        log_frame.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(log_frame, text="操作日志").pack(anchor="w")
        self.log = tk.Text(log_frame, height=10, wrap="word")
        self.log.pack(fill="both", expand=True)
        self._append_log("工具已启动。")

    def query_port(self) -> None:
        port_text = self.port_var.get().strip()
        try:
            port = int(port_text)
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效端口号。")
            return
        if port < 1 or port > 65535:
            messagebox.showerror("输入错误", "端口范围必须在 1-65535。")
            return

        self._set_query_state(False)
        self._append_log(f"开始查询端口 {port}...")
        worker = threading.Thread(target=self._query_port_worker, args=(port,), daemon=True)
        worker.start()

    def _query_port_worker(self, port: int) -> None:
        try:
            records = inspect_ports([port])
        except Exception as exc:  # pragma: no cover
            self.root.after(0, lambda: self._handle_query_error(port, str(exc)))
            return
        self.root.after(0, lambda: self._render_query_result(port, records))

    def _render_query_result(self, port: int, records: list[PortRecord]) -> None:
        self.records = records
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.records:
            self._append_log(f"端口 {port} 当前未发现占用。")
            self._set_query_state(True)
            return

        for index, record in enumerate(self.records):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    record.local_port,
                    record.protocol,
                    record.state,
                    record.pid or "-",
                    record.process_name or "-",
                    record.occupancy_type.value,
                ),
            )
            self._append_log(
                f"发现端口 {record.local_port} 占用: PID={record.pid or '-'} "
                f"状态={record.state} 分类={record.occupancy_type.value}"
            )
        self._set_query_state(True)

    def _handle_query_error(self, port: int, error: str) -> None:
        self._append_log(f"查询端口 {port} 失败: {error}")
        self._set_query_state(True)
        messagebox.showerror("查询失败", error)

    def kill_selected(self) -> None:
        record = self._selected_record()
        if not record:
            messagebox.showinfo("提示", "请先选中一条记录。")
            return
        ok, message = kill_record(record)
        self._append_log(message)
        if ok:
            messagebox.showinfo("完成", message)
            self.query_port()
        else:
            messagebox.showwarning("失败", message)

    def show_hint(self) -> None:
        record = self._selected_record()
        if not record:
            messagebox.showinfo("提示", "请先选中一条记录。")
            return
        hint = record_action_hint(record)
        self._append_log(hint)
        self._show_large_message("诊断信息", hint)

    def show_tuning(self) -> None:
        hint = time_wait_tuning_advice()
        self._append_log(hint)
        self._show_large_message("TIME_WAIT 建议", hint)

    def _selected_record(self) -> PortRecord | None:
        selection = self.tree.selection()
        if not selection:
            return None
        index = int(selection[0])
        if 0 <= index < len(self.records):
            return self.records[index]
        return None

    def _build_limit_text(self) -> str:
        if not self.privilege.limitations:
            return "当前拥有完整诊断与清理能力。"
        return "；".join(self.privilege.limitations)

    def _append_log(self, message: str) -> None:
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def _set_query_state(self, enabled: bool) -> None:
        if self.query_button is not None:
            self.query_button.configure(text="查询" if enabled else "查询中...", state="normal" if enabled else "disabled")

    def _show_large_message(self, title: str, content: str) -> None:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("760x520")
        text = tk.Text(window, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", content)
        text.configure(state="disabled")


def run_gui() -> None:
    if ctk is not None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
    root = ctk.CTk() if ctk is not None else tk.Tk()
    app = PortClearApp(root)
    root.mainloop()
