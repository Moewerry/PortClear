from __future__ import annotations

import threading
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from core.actions import kill_record
from core.inspector import inspect_ports
from core.models import OccupancyType, PortRecord
from core.privilege import get_privilege_info


class PortClearApp:
    # ---- 配色系统（提取自截图） ----
    BG = "#f3f4f6"          # 窗口背景
    CARD = "#ffffff"        # 卡片背景
    BORDER = "#e5e7eb"      # 卡片/输入框边框
    TEXT = "#111827"        # 主文字
    MUTED = "#6b7280"       # 次要文字
    BLUE = "#3b82f6"        # 主按钮
    BLUE_HOVER = "#2563eb"
    GREEN = "#10b981"       # 成功/监听
    AMBER = "#f59e0b"       # 警告
    RED = "#ef4444"         # 终止/错误
    ORANGE = "#ea580c"      # 等待关闭

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("端口占用查询工具")
        self.root.geometry("1200x880")
        self.root.minsize(1000, 780)
        self.root.configure(fg_color=self.BG)

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.privilege = get_privilege_info()
        self.records: list[PortRecord] = []
        self.log_rows: list[tuple[str, str, str, str]] = []

        self.port_var = ctk.StringVar(value="80")
        self.result_title_var = ctk.StringVar(value="查询结果（端口：80）")
        self.count_var = ctk.StringVar(value="共 0 条记录")
        self.privilege_var = ctk.StringVar(value=self._privilege_text())

        self._build_ui()

    # ==================== UI 构建 ====================

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self.root, fg_color=self.BG, corner_radius=0)
        container.pack(fill="both", expand=True, padx=24, pady=20)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=3)
        container.grid_rowconfigure(3, weight=2)

        self._build_header(container).grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._build_privilege_banner(container).grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self._build_query_card(container).grid(row=2, column=0, sticky="nsew", pady=(0, 16))
        self._build_log_card(container).grid(row=3, column=0, sticky="nsew", pady=(0, 8))

        tip = ctk.CTkLabel(
            container,
            text="提示：系统进程、HTTP.sys 与部分连接状态无法直接终止，请确认后再操作。",
            text_color=self.MUTED,
            font=("Microsoft YaHei UI", 11),
        )
        tip.grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _build_header(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        frame.grid_columnconfigure(1, weight=1)

        # 图标
        icon = ctk.CTkCanvas(frame, width=40, height=40, bg=self.BG, highlightthickness=0)
        icon.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self._draw_app_icon(icon)

        # 标题
        ctk.CTkLabel(
            frame, text="端口占用查询工具", font=("Microsoft YaHei UI", 20, "bold"), text_color=self.TEXT
        ).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(
            frame,
            text="快速定位端口占用、识别系统服务，并安全释放应用进程。",
            font=("Microsoft YaHei UI", 12),
            text_color=self.MUTED,
        ).grid(row=1, column=1, sticky="nw", pady=(2, 0))

        # 权限 Pill
        pill_color = self.GREEN if self.privilege.is_elevated else self.AMBER
        pill_text = "管理员权限" if self.privilege.is_elevated else "普通权限"
        pill = ctk.CTkFrame(frame, fg_color=self.CARD, corner_radius=16, border_width=1, border_color=self.BORDER)
        pill.grid(row=0, column=2, rowspan=2, sticky="e")

        dot = ctk.CTkCanvas(pill, width=14, height=14, bg=self.CARD, highlightthickness=0)
        dot.pack(side="left", padx=(12, 6), pady=8)
        dot.create_oval(3, 3, 11, 11, fill=pill_color, outline=pill_color)

        ctk.CTkLabel(
            pill, text=pill_text, font=("Microsoft YaHei UI", 11, "bold"), text_color="#334155"
        ).pack(side="left", padx=(0, 12))

        return frame

    def _build_privilege_banner(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        bg = "#ecfdf5" if self.privilege.is_elevated else "#fff7ed"
        border = "#bbf7d0" if self.privilege.is_elevated else "#fed7aa"
        color = self.GREEN if self.privilege.is_elevated else self.AMBER

        banner = ctk.CTkFrame(parent, fg_color=bg, corner_radius=10, border_width=1, border_color=border)
        banner.grid_columnconfigure(1, weight=1)

        icon = ctk.CTkCanvas(banner, width=28, height=28, bg=bg, highlightthickness=0)
        icon.grid(row=0, column=0, padx=(16, 10), pady=12)
        self._draw_shield(icon, color, bg)

        ctk.CTkLabel(
            banner,
            textvariable=self.privilege_var,
            font=("Microsoft YaHei UI", 13, "bold"),
            text_color=color,
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            banner,
            text="完整诊断与清理能力已启用" if self.privilege.is_elevated else "建议以管理员身份运行以获得完整清理能力",
            font=("Microsoft YaHei UI", 11),
            text_color="#475569",
        ).grid(row=0, column=2, sticky="w", padx=(12, 16))

        return banner

    def _build_query_card(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        card = self._card(parent)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)

        # ---- 标题区 ----
        top = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 0))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="端口查询", font=("Microsoft YaHei UI", 16, "bold"), text_color=self.TEXT).grid(
            row=0, column=0, sticky="w"
        )
        self._chip(top, self.count_var).grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            top,
            text="输入端口号后查询当前监听、连接与系统占用状态。",
            font=("Microsoft YaHei UI", 11),
            text_color=self.MUTED,
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # ---- 搜索栏 ----
        form = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        form.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 8))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="端口号", font=("Microsoft YaHei UI", 12), text_color=self.TEXT).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )

        self.entry = ctk.CTkEntry(
            form,
            textvariable=self.port_var,
            placeholder_text="请输入端口号（如：80）",
            font=("Microsoft YaHei UI", 12),
            height=42,
            corner_radius=8,
            border_width=1,
            border_color=self.BORDER,
            fg_color="#f9fafb",
        )
        self.entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.entry.bind("<Return>", lambda _e: self.query_port())

        self.query_btn = ctk.CTkButton(
            form,
            text="查询",
            command=self.query_port,
            font=("Microsoft YaHei UI", 12, "bold"),
            height=42,
            corner_radius=8,
            fg_color=self.BLUE,
            hover_color=self.BLUE_HOVER,
            text_color="#ffffff",
        )
        self.query_btn.grid(row=0, column=2, sticky="e")

        # 快捷端口
        quick = ctk.CTkFrame(form, fg_color="transparent", corner_radius=0)
        quick.grid(row=1, column=1, sticky="w", pady=(10, 0))
        for port in ("80", "443", "3306", "5432", "6379", "8080"):
            self._quick_port_button(quick, port).pack(side="left", padx=(0, 8))

        # ---- 结果标题 ----
        result_meta = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        result_meta.grid(row=2, column=0, sticky="ew", padx=20, pady=(14, 8))
        result_meta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            result_meta,
            textvariable=self.result_title_var,
            font=("Microsoft YaHei UI", 15, "bold"),
            text_color=self.TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            result_meta,
            text="点击操作列可释放应用进程",
            font=("Microsoft YaHei UI", 11),
            text_color=self.MUTED,
        ).grid(row=0, column=1, sticky="e")

        # ---- 结果表格 ----
        self.result_container = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        self.result_container.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.result_container.grid_columnconfigure(0, weight=1)
        self.result_container.grid_rowconfigure(1, weight=1)

        # 表头
        headers = [("协议", 90), ("状态", 170), ("PID", 100), ("进程名", 280), ("占用类型", 150), ("操作", 120)]
        result_header_wrap = ctk.CTkFrame(self.result_container, fg_color="transparent", corner_radius=0)
        result_header_wrap.grid(row=0, column=0, sticky="ew")
        result_header_wrap.grid_columnconfigure(0, weight=1)
        self.result_header = self._table_header(result_header_wrap, headers)
        self.result_header.grid(row=0, column=0, sticky="ew")
        self._scrollbar_header_spacer(result_header_wrap).grid(row=0, column=1, sticky="ns")

        # 滚动区域
        self.result_scroll = ctk.CTkScrollableFrame(
            self.result_container, fg_color="transparent", corner_radius=0, scrollbar_button_color="#d1d5db"
        )
        self.result_scroll.grid(row=1, column=0, sticky="nsew")
        self.result_scroll.grid_columnconfigure(0, weight=1)

        self._render_empty_result()

        # ---- 底部提示 ----
        bottom = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        bottom.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 16))
        ctk.CTkLabel(
            bottom,
            text="系统服务、连接状态和权限受限项会显示为不可操作。",
            font=("Microsoft YaHei UI", 11),
            text_color=self.MUTED,
        ).pack(side="left")

        return card

    def _build_log_card(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        card = self._card(parent)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 12))
        ctk.CTkLabel(top, text="操作日志", font=("Microsoft YaHei UI", 16, "bold"), text_color=self.TEXT).pack(
            side="left"
        )
        self._chip(top, ctk.StringVar(value="最近 80 条")).pack(side="right")

        # 表格
        self.log_container = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        self.log_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 18))
        self.log_container.grid_columnconfigure(0, weight=1)
        self.log_container.grid_rowconfigure(1, weight=1)

        headers = [("时间", 185), ("级别", 100), ("操作", 145), ("详情", 560)]
        log_header_wrap = ctk.CTkFrame(self.log_container, fg_color="transparent", corner_radius=0)
        log_header_wrap.grid(row=0, column=0, sticky="ew")
        log_header_wrap.grid_columnconfigure(0, weight=1)
        self.log_header = self._table_header(log_header_wrap, headers)
        self.log_header.grid(row=0, column=0, sticky="ew")
        self._scrollbar_header_spacer(log_header_wrap).grid(row=0, column=1, sticky="ns")

        self.log_scroll = ctk.CTkScrollableFrame(
            self.log_container, fg_color="transparent", corner_radius=0, scrollbar_button_color="#d1d5db"
        )
        self.log_scroll.grid(row=1, column=0, sticky="nsew")
        self.log_scroll.grid_columnconfigure(0, weight=1)

        self._render_empty_log()
        return card

    # ==================== 表格组件 ====================

    def _table_header(self, parent: ctk.CTkFrame, columns: list[tuple[str, int]]) -> ctk.CTkFrame:
        header = ctk.CTkFrame(parent, fg_color="#f9fafb", corner_radius=0, height=44)
        header.grid_propagate(False)
        for i, (title, width) in enumerate(columns):
            header.grid_columnconfigure(i, minsize=width, weight=1 if i == 3 else 0)
            pad = 16 if i == 0 else 12
            ctk.CTkLabel(
                header, text=title, font=("Microsoft YaHei UI", 11, "bold"), text_color="#374151"
            ).grid(row=0, column=i, sticky="w", padx=pad, pady=10)
        return header

    def _render_result_row(self, index: int, record: PortRecord) -> None:
        bg = "#ffffff" if index % 2 == 0 else "#f8fafc"
        row = ctk.CTkFrame(self.result_scroll, fg_color=bg, corner_radius=0, height=56, border_width=1, border_color="#f3f4f6")
        row.grid_propagate(False)
        row.pack(fill="x", pady=(0, 1))
        self._configure_grid_columns(row, self._result_columns())

        # 协议
        ctk.CTkLabel(row, text=self._display_protocol(record), font=("Microsoft YaHei UI", 11), text_color="#334155").grid(
            row=0, column=0, sticky="w", padx=16, pady=14
        )

        # 状态（带圆点）
        self._status_badge(row, self._display_state(record), *self._state_colors(record), bg).grid(
            row=0, column=1, sticky="w", padx=12, pady=10
        )

        # PID
        ctk.CTkLabel(row, text=str(record.pid or "-"), font=("Microsoft YaHei UI", 11), text_color="#334155").grid(
            row=0, column=2, sticky="w", padx=12, pady=14
        )

        # 进程名（带提示）
        proc_frame = ctk.CTkFrame(row, fg_color=bg, corner_radius=0)
        proc_frame.grid(row=0, column=3, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(
            proc_frame,
            text=self._display_process(record),
            font=("Microsoft YaHei UI", 11, "bold"),
            text_color=self.TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            proc_frame,
            text=self._process_hint(record),
            font=("Microsoft YaHei UI", 9),
            text_color="#94a3b8",
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        # 占用类型
        self._badge(row, self._display_kind(record), *self._kind_colors(record), bg).grid(
            row=0, column=4, sticky="w", padx=12, pady=12
        )

        # 操作
        if self._can_show_kill(record):
            btn = ctk.CTkButton(
                row,
                text="终止进程",
                command=lambda idx=index: self.kill_record_by_index(idx),
                font=("Microsoft YaHei UI", 10, "bold"),
                height=32,
                width=90,
                corner_radius=6,
                fg_color="#fef2f2",
                hover_color="#fee2e2",
                text_color=self.RED,
                border_width=1,
                border_color="#fecaca",
            )
            btn.grid(row=0, column=5, sticky="w", padx=12, pady=10)
        else:
            self._badge(row, "不可终止", "#f3f4f6", "#9ca3af", bg).grid(
                row=0, column=5, sticky="w", padx=12, pady=14
            )

    def _render_log_row(self, index: int, item: tuple[str, str, str, str]) -> None:
        time_text, level, action, detail = item
        bg = "#ffffff" if index % 2 == 0 else "#f8fafc"
        row = ctk.CTkFrame(self.log_scroll, fg_color=bg, corner_radius=0, height=44, border_width=1, border_color="#f3f4f6")
        row.grid_propagate(False)
        row.pack(fill="x", pady=(0, 1))
        self._configure_grid_columns(row, self._log_columns())

        ctk.CTkLabel(row, text=time_text, font=("Microsoft YaHei UI", 10), text_color="#475569").grid(
            row=0, column=0, sticky="w", padx=14, pady=10
        )

        level_bg, level_fg = {
            "信息": ("#eff6ff", "#2563eb"),
            "成功": ("#ecfdf5", self.GREEN),
            "错误": ("#fef2f2", self.RED),
        }.get(level, ("#f3f4f6", "#475569"))

        self._badge(row, level, level_bg, level_fg, bg).grid(row=0, column=1, sticky="w", padx=10, pady=8)
        ctk.CTkLabel(row, text=action, font=("Microsoft YaHei UI", 10, "bold"), text_color=self.TEXT).grid(
            row=0, column=2, sticky="w", padx=10, pady=10
        )
        ctk.CTkLabel(row, text=detail, font=("Microsoft YaHei UI", 10), text_color="#334155").grid(
            row=0, column=3, sticky="ew", padx=10, pady=10
        )

    def _render_empty_result(self, text: str = "输入端口号后开始查询") -> None:
        self._clear_scroll(self.result_scroll)
        empty = ctk.CTkFrame(self.result_scroll, fg_color=self.CARD, height=160, corner_radius=0)
        empty.pack(fill="x")
        empty.pack_propagate(False)
        ctk.CTkLabel(
            empty, text="暂无查询结果", font=("Microsoft YaHei UI", 14, "bold"), text_color=self.TEXT
        ).pack(pady=(50, 6))
        ctk.CTkLabel(empty, text=text, font=("Microsoft YaHei UI", 11), text_color=self.MUTED).pack()

    def _render_empty_log(self) -> None:
        self._clear_scroll(self.log_scroll)
        empty = ctk.CTkFrame(self.log_scroll, fg_color=self.CARD, height=120, corner_radius=0)
        empty.pack(fill="x")
        empty.pack_propagate(False)
        ctk.CTkLabel(
            empty, text="暂无操作日志", font=("Microsoft YaHei UI", 13, "bold"), text_color=self.TEXT
        ).pack(pady=(40, 4))
        ctk.CTkLabel(
            empty, text="查询、终止和异常信息会显示在这里", font=("Microsoft YaHei UI", 10), text_color=self.MUTED
        ).pack()

    # ==================== 辅助组件 ====================

    def _card(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent,
            fg_color=self.CARD,
            corner_radius=12,
            border_width=1,
            border_color=self.BORDER,
        )

    def _chip(self, parent: ctk.CTkFrame, textvariable: ctk.StringVar) -> ctk.CTkFrame:
        chip = ctk.CTkFrame(parent, fg_color="#f3f4f6", corner_radius=12, border_width=1, border_color="#e5e7eb")
        ctk.CTkLabel(
            chip,
            textvariable=textvariable,
            font=("Microsoft YaHei UI", 10, "bold"),
            text_color="#475569",
        ).pack(padx=10, pady=4)
        return chip

    def _scrollbar_header_spacer(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, width=18, height=44, fg_color="#f9fafb", corner_radius=0)

    def _badge(self, parent: ctk.CTkFrame, text: str, bg_color: str, fg_color: str, row_bg: str) -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color=row_bg, corner_radius=0)
        inner = ctk.CTkFrame(wrap, fg_color=bg_color, corner_radius=4)
        inner.pack()
        ctk.CTkLabel(
            inner, text=text, font=("Microsoft YaHei UI", 9, "bold"), text_color=fg_color
        ).pack(padx=10, pady=4)
        return wrap

    def _status_badge(self, parent: ctk.CTkFrame, text: str, bg_color: str, fg_color: str, row_bg: str) -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color=row_bg, corner_radius=0)
        inner = ctk.CTkFrame(wrap, fg_color=bg_color, corner_radius=4)
        inner.pack()

        dot = ctk.CTkCanvas(inner, width=10, height=10, bg=bg_color, highlightthickness=0)
        dot.pack(side="left", padx=(8, 4), pady=6)
        dot.create_oval(2, 2, 8, 8, fill=fg_color, outline=fg_color)

        ctk.CTkLabel(
            inner, text=text, font=("Microsoft YaHei UI", 9, "bold"), text_color=fg_color
        ).pack(side="left", padx=(0, 8), pady=4)
        return wrap

    def _quick_port_button(self, parent: ctk.CTkFrame, port: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=port,
            command=lambda p=port: self._choose_quick_port(p),
            font=("Microsoft YaHei UI", 10),
            height=28,
            width=50,
            corner_radius=6,
            fg_color="#f3f4f6",
            hover_color="#e5e7eb",
            text_color="#475569",
            border_width=1,
            border_color="#e5e7eb",
        )

    def _configure_grid_columns(self, frame: ctk.CTkFrame, columns: list[tuple[str, int]]) -> None:
        stretch_index = 3
        for i, (_, width) in enumerate(columns):
            frame.grid_columnconfigure(i, minsize=width, weight=1 if i == stretch_index else 0)

    def _result_columns(self) -> list[tuple[str, int]]:
        return [("协议", 90), ("状态", 170), ("PID", 100), ("进程名", 280), ("占用类型", 150), ("操作", 120)]

    def _log_columns(self) -> list[tuple[str, int]]:
        return [("时间", 185), ("级别", 100), ("操作", 145), ("详情", 560)]

    def _clear_scroll(self, scroll: ctk.CTkScrollableFrame) -> None:
        for child in scroll.winfo_children():
            child.destroy()

    # ==================== 业务逻辑（保持原样） ====================

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

        self.result_title_var.set(f"正在查询端口 {port}...")
        self._set_query_state(False)
        self._append_log("信息", "查询端口", f"查询端口 {port}")
        worker = threading.Thread(target=self._query_port_worker, args=(port,), daemon=True)
        worker.start()

    def _query_port_worker(self, port: int) -> None:
        try:
            records = inspect_ports([port])
        except Exception as exc:
            self.root.after(0, lambda: self._handle_query_error(port, str(exc)))
            return
        self.root.after(0, lambda: self._render_query_result(port, records))

    def _render_query_result(self, port: int, records: list[PortRecord]) -> None:
        self.records = records
        self._clear_scroll(self.result_scroll)

        if not records:
            self._render_empty_result(f"端口 {port} 当前未发现占用")
        else:
            for index, record in enumerate(records):
                self._render_result_row(index, record)

        self.count_var.set(f"共 {len(records)} 条记录")
        self.result_title_var.set(f"查询结果：端口 {port}")
        self._append_log("信息", "查询完成", f"找到 {len(records)} 条占用记录")
        if not records:
            self._append_log("信息", "查询结果", f"端口 {port} 当前未发现占用")
        self._set_query_state(True)

    def _handle_query_error(self, port: int, error: str) -> None:
        self.result_title_var.set(f"查询失败：端口 {port}")
        self._append_log("错误", "查询失败", f"端口 {port} 查询失败：{error}")
        self._set_query_state(True)
        messagebox.showerror("查询失败", error)

    def kill_record_by_index(self, index: int) -> None:
        if not (0 <= index < len(self.records)):
            return
        record = self.records[index]
        if not self._can_show_kill(record):
            return

        process = self._display_process(record)
        if not messagebox.askyesno("确认终止", f"确认终止 PID {record.pid}（{process}）？"):
            return

        self._append_log("信息", "终止进程", f"尝试终止 PID {record.pid}（{process}）")
        ok, message = kill_record(record)
        if ok:
            self._append_log("成功", "终止成功", f"已成功终止 PID {record.pid}（{process}）")
            self.query_port()
        else:
            self._append_log("错误", "终止失败", message)
            messagebox.showwarning("终止失败", message)

    def _append_log(self, level: str, action: str, detail: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = (now, level, action, detail)
        self.log_rows.append(item)
        if len(self.log_rows) > 80:
            self.log_rows = self.log_rows[-80:]

        self._clear_scroll(self.log_scroll)
        for index, row in enumerate(self.log_rows):
            self._render_log_row(index, row)
        # 滚动到底部
        if hasattr(self.log_scroll, "_parent_canvas"):
            self.log_scroll._parent_canvas.yview_moveto(1.0)

    def _choose_quick_port(self, port: str) -> None:
        self.port_var.set(port)
        self.query_port()

    def _set_query_state(self, enabled: bool) -> None:
        self.query_btn.configure(
            text="查询" if enabled else "查询中...",
            state="normal" if enabled else "disabled",
            fg_color=self.BLUE if enabled else "#9ca3af",
            hover_color=self.BLUE_HOVER if enabled else "#9ca3af",
        )

    # ==================== 数据展示（保持原样） ====================

    def _display_protocol(self, record: PortRecord) -> str:
        if record.occupancy_type == OccupancyType.HTTP_SYS:
            return "HTTP"
        return record.protocol or "-"

    def _display_state(self, record: PortRecord) -> str:
        state = (record.state or "").upper()
        labels = {
            "LISTEN": "监听中",
            "LISTENING": "监听中",
            "ESTABLISHED": "已建立连接",
            "TIME_WAIT": "等待关闭",
            "CLOSE_WAIT": "等待关闭",
            "BOUND": "已绑定",
        }
        return labels.get(state, state or "-")

    def _display_process(self, record: PortRecord) -> str:
        if record.occupancy_type == OccupancyType.HTTP_SYS:
            return "System (HTTP.sys)"
        return record.process_name or record.command or "--"

    def _process_hint(self, record: PortRecord) -> str:
        if record.occupancy_type == OccupancyType.HTTP_SYS:
            return "系统级 HTTP 服务，需进一步诊断"
        if record.occupancy_type == OccupancyType.TIME_WAIT:
            return "TCP 回收状态，通常等待系统自动释放"
        if record.occupancy_type == OccupancyType.PERMISSION_LIMITED:
            return "当前权限不足，可能无法查看完整进程"
        if record.occupancy_type == OccupancyType.CLOSE_WAIT:
            return "应用未正常关闭连接，建议检查进程"
        if record.pid:
            return f"PID {record.pid}，可按需终止释放端口"
        return "暂无可操作进程信息"

    def _display_kind(self, record: PortRecord) -> str:
        labels = {
            OccupancyType.USER_PROCESS: "应用程序",
            OccupancyType.HTTP_SYS: "系统服务",
            OccupancyType.TIME_WAIT: "连接状态",
            OccupancyType.CLOSE_WAIT: "应用异常",
            OccupancyType.PERMISSION_LIMITED: "权限受限",
            OccupancyType.UNKNOWN: "未知",
        }
        return labels.get(record.occupancy_type, "未知")

    def _state_colors(self, record: PortRecord) -> tuple[str, str]:
        state = (record.state or "").upper()
        if state in {"LISTEN", "LISTENING", "BOUND"}:
            return "#d1fae5", self.GREEN
        if state == "ESTABLISHED":
            return "#dbeafe", "#2563eb"
        if state in {"TIME_WAIT", "CLOSE_WAIT"}:
            return "#ffedd5", self.ORANGE
        return "#f3f4f6", "#475569"

    def _kind_colors(self, record: PortRecord) -> tuple[str, str]:
        colors = {
            OccupancyType.USER_PROCESS: ("#dbeafe", "#2563eb"),
            OccupancyType.HTTP_SYS: ("#f3f4f6", "#475569"),
            OccupancyType.TIME_WAIT: ("#ffedd5", self.ORANGE),
            OccupancyType.CLOSE_WAIT: ("#fee2e2", self.RED),
            OccupancyType.PERMISSION_LIMITED: ("#ffedd5", "#b45309"),
            OccupancyType.UNKNOWN: ("#f3f4f6", "#475569"),
        }
        return colors.get(record.occupancy_type, ("#f3f4f6", "#475569"))

    def _can_show_kill(self, record: PortRecord) -> bool:
        blocked_types = {OccupancyType.HTTP_SYS, OccupancyType.TIME_WAIT, OccupancyType.PERMISSION_LIMITED}
        return bool(record.pid and record.occupancy_type not in blocked_types)

    def _privilege_text(self) -> str:
        if self.privilege.is_elevated:
            return "当前已是管理员权限"
        return "当前不是管理员权限"

    def _draw_app_icon(self, canvas: ctk.CTkCanvas) -> None:
        canvas.create_oval(1, 1, 39, 39, fill="#dbeafe", outline="#bfdbfe")
        canvas.create_polygon(20, 8, 31, 12, 30, 23, 20, 34, 10, 23, 9, 12, fill=self.BLUE, outline=self.BLUE)
        canvas.create_polygon(15, 20, 19, 24, 26, 15, fill="#ffffff", outline="#ffffff")

    def _draw_shield(self, canvas: ctk.CTkCanvas, fill: str, bg: str) -> None:
        canvas.delete("all")
        canvas.create_polygon(14, 2, 25, 6, 24, 16, 14, 27, 4, 16, 3, 6, fill=fill, outline=fill)
        canvas.create_polygon(9, 13, 13, 17, 20, 9, fill=bg, outline=bg)


def run_gui() -> None:
    root = ctk.CTk()
    PortClearApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
