"""
PDF 툴 v3
의존성: pip install pypdf
"""

import re
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
    from pypdf import PdfReader, PdfWriter


C = {
    "bg":        "#F0F4F8",
    "card":      "#FFFFFF",
    "primary":   "#2563EB",
    "primary_h": "#1D4ED8",
    "success":   "#16A34A",
    "success_h": "#15803D",
    "danger":    "#DC2626",
    "danger_h":  "#B91C1C",
    "border":    "#E2E8F0",
    "text":      "#1E293B",
    "sub":       "#64748B",
    "badge_bg":  "#EFF6FF",
    "badge_fg":  "#1D4ED8",
    "list_sel":  "#DBEAFE",
}

FONT       = ("Malgun Gothic", 10)
FONT_B     = ("Malgun Gothic", 10, "bold")
FONT_SM    = ("Malgun Gothic", 9)
FONT_TITLE = ("Malgun Gothic", 14, "bold")


def _hover_btn(parent, text, cmd, bg, hover_bg, fg="white", **kw):
    kw.setdefault("padx", 12)
    kw.setdefault("pady", 7)
    b = tk.Button(
        parent, text=text, command=cmd,
        font=FONT_B, bg=bg, fg=fg,
        relief="flat", bd=0,
        cursor="hand2", activebackground=hover_bg, activeforeground=fg,
        **kw,
    )
    b.bind("<Enter>", lambda _: b.config(bg=hover_bg))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b


def _make_progressbar(parent) -> ttk.Progressbar:
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Blue.Horizontal.TProgressbar",
        troughcolor=C["border"], background=C["primary"],
        thickness=6, borderwidth=0,
    )
    return ttk.Progressbar(parent, mode="indeterminate", length=460,
                           style="Blue.Horizontal.TProgressbar")


def _entry(parent, var, width=42):
    return tk.Entry(
        parent, textvariable=var, width=width, font=FONT,
        relief="solid", bd=1,
        highlightthickness=1, highlightcolor=C["primary"],
        highlightbackground=C["border"],
    )


def _listbox(parent, height=8):
    lb = tk.Listbox(
        parent, font=FONT, bg=C["card"], fg=C["text"],
        relief="solid", bd=1, highlightthickness=1,
        highlightcolor=C["primary"], highlightbackground=C["border"],
        selectbackground=C["list_sel"], selectforeground=C["text"],
        height=height,
    )
    sb = ttk.Scrollbar(parent, orient="vertical", command=lb.yview)
    lb.config(yscrollcommand=sb.set)
    return lb, sb


class SectionCard(tk.Frame):
    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, bg=C["card"], relief="flat", bd=0, **kw)
        hdr = tk.Frame(self, bg=C["card"])
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(hdr, text=title, font=FONT_B,
                 bg=C["card"], fg=C["text"]).pack(side="left")
        self._body = tk.Frame(self, bg=C["card"])
        self._body.pack(fill="x", padx=16, pady=(0, 16))

    @property
    def body(self) -> tk.Frame:
        return self._body


class PDFToolApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 툴")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(540, 480)
        self.merge_files: list[str] = []
        self._show_pw  = False
        self._show_pw2 = False
        self._build_ui()
        self.update_idletasks()
        # winfo_width/height returns 1 before mainloop; use reqwidth/reqheight
        w = max(self.winfo_reqwidth(), 560)
        h = max(self.winfo_reqheight(), 540)
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ──────────────────────────────────────────────────────────
    # 전체 레이아웃
    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self, bg=C["bg"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=C["bg"])
        hdr.pack(fill="x", pady=(0, 10))
        tk.Label(hdr, text="PDF 툴", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Label(hdr, text=" v3.0 ", font=FONT_SM,
                 bg=C["badge_bg"], fg=C["badge_fg"],
                 padx=4, pady=2).pack(side="left", padx=(8, 0))

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        tabs = {
            "암호화":    tk.Frame(nb, bg=C["bg"]),
            "페이지 편집": tk.Frame(nb, bg=C["bg"]),
            "병합":      tk.Frame(nb, bg=C["bg"]),
            "나누기":    tk.Frame(nb, bg=C["bg"]),
            "압축":      tk.Frame(nb, bg=C["bg"]),
        }
        for name, frame in tabs.items():
            nb.add(frame, text=f"  {name}  ")

        self._build_encrypt_tab(tabs["암호화"])
        self._build_pages_tab(tabs["페이지 편집"])
        self._build_merge_tab(tabs["병합"])
        self._build_split_tab(tabs["나누기"])
        self._build_compress_tab(tabs["압축"])

    # ──────────────────────────────────────────────────────────
    # TAB 1 — 암호화
    # ──────────────────────────────────────────────────────────
    def _build_encrypt_tab(self, parent):
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=16)
        f.pack(fill="both", expand=True)

        # 파일
        c1 = SectionCard(f, "PDF 파일")
        c1.pack(fill="x", pady=(0, 10))
        b = c1.body
        b.columnconfigure(0, weight=1)
        self.enc_file_var = tk.StringVar()
        _entry(b, self.enc_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b, "찾아보기", self._enc_browse_file,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        # 비밀번호
        c2 = SectionCard(f, "비밀번호 설정")
        c2.pack(fill="x", pady=(0, 10))
        self._build_password_section(c2.body)

        # 알고리즘
        c3 = SectionCard(f, "암호화 강도")
        c3.pack(fill="x", pady=(0, 10))
        self.algo_var = tk.StringVar(value="AES-256")
        for i, (label, val) in enumerate([
            ("AES-256  (최고 보안 / 권장)", "AES-256"),
            ("AES-128  (표준 보안)",        "AES-128"),
            ("RC4-128  (구형 호환)",        "RC4-128"),
        ]):
            tk.Radiobutton(c3.body, text=label, variable=self.algo_var, value=val,
                           font=FONT, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"],
                           ).grid(row=i, column=0, sticky="w", pady=2)

        # 저장
        c4 = SectionCard(f, "저장 위치")
        c4.pack(fill="x", pady=(0, 14))
        b4 = c4.body
        b4.columnconfigure(0, weight=1)
        self.enc_out_var = tk.StringVar()
        _entry(b4, self.enc_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b4, "찾아보기", self._enc_browse_out,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        self.enc_pb = _make_progressbar(f)
        self.enc_pb.pack(fill="x", pady=(0, 4))
        self.enc_sv = tk.StringVar(value="파일을 선택하고 비밀번호를 입력하세요.")
        tk.Label(f, textvariable=self.enc_sv, font=FONT_SM,
                 bg=C["bg"], fg=C["sub"], anchor="w").pack(fill="x", pady=(0, 8))

        btn = _hover_btn(f, "  암호화하여 저장",
                         self._enc_start, C["success"], C["success_h"])
        btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        btn.pack(fill="x")

    def _build_password_section(self, parent):
        parent.columnconfigure(0, weight=1)
        tk.Label(parent, text="비밀번호", font=FONT_SM,
                 bg=C["card"], fg=C["sub"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
        self.pw_var = tk.StringVar()
        self._pw_entry = _entry(parent, self.pw_var)
        self._pw_entry.config(show="*")
        self._pw_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._eye1 = _hover_btn(parent, "Show", self._toggle_pw1,
                                C["border"], "#CBD5E1", C["text"])
        self._eye1.grid(row=1, column=1)

        sf = tk.Frame(parent, bg=C["card"])
        sf.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.strength_bars: list[tk.Frame] = []
        bar_row = tk.Frame(sf, bg=C["card"])
        bar_row.pack(side="left")
        for _ in range(4):
            seg = tk.Frame(bar_row, width=50, height=4, bg=C["border"])
            seg.pack_propagate(False)
            seg.pack(side="left", padx=2)
            self.strength_bars.append(seg)
        self.strength_lbl = tk.Label(sf, text="", font=FONT_SM,
                                     bg=C["card"], fg=C["sub"])
        self.strength_lbl.pack(side="left", padx=(8, 0))
        self.pw_var.trace_add("write", lambda *_: self._update_strength())

        tk.Label(parent, text="비밀번호 확인", font=FONT_SM,
                 bg=C["card"], fg=C["sub"]).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 3))
        self.pw2_var = tk.StringVar()
        self._pw2_entry = _entry(parent, self.pw2_var)
        self._pw2_entry.config(show="*")
        self._pw2_entry.grid(row=4, column=0, sticky="ew", padx=(0, 8))
        self._eye2 = _hover_btn(parent, "Show", self._toggle_pw2,
                                C["border"], "#CBD5E1", C["text"])
        self._eye2.grid(row=4, column=1)
        self.pw2_var.trace_add("write", lambda *_: self._check_match())
        self.match_lbl = tk.Label(parent, text="", font=FONT_SM,
                                   bg=C["card"], fg=C["sub"])
        self.match_lbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ──────────────────────────────────────────────────────────
    # TAB 2 — 페이지 편집
    # ──────────────────────────────────────────────────────────
    def _build_pages_tab(self, parent):
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=16)
        f.pack(fill="both", expand=True)
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

        # 파일 선택
        c1 = SectionCard(f, "PDF 파일")
        c1.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        b1 = c1.body
        b1.columnconfigure(0, weight=1)
        self.pg_file_var = tk.StringVar()
        _entry(b1, self.pg_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b1, "찾아보기", self._pg_browse_file,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)
        self.pg_info_lbl = tk.Label(b1, text="", font=FONT_SM,
                                    bg=C["card"], fg=C["sub"])
        self.pg_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 페이지 목록
        c2 = SectionCard(f, "페이지 목록  (선택 후 버튼으로 삭제·순서 변경)")
        c2.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        c2.rowconfigure(0, weight=1)
        lb_body = c2.body
        lb_body.columnconfigure(0, weight=1)
        lb_body.rowconfigure(0, weight=1)

        lf = tk.Frame(lb_body, bg=C["card"])
        lf.grid(row=0, column=0, sticky="nsew")
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        self.pg_listbox, pg_sb = _listbox(lf, height=10)
        self.pg_listbox.grid(row=0, column=0, sticky="nsew")
        pg_sb.grid(row=0, column=1, sticky="ns")

        bf = tk.Frame(lb_body, bg=C["card"])
        bf.grid(row=0, column=1, padx=(8, 0), sticky="n")
        for text, cmd in [
            ("▲ 위로",   self._pg_move_up),
            ("▼ 아래로", self._pg_move_down),
        ]:
            _hover_btn(bf, text, cmd, C["primary"], C["primary_h"],
                       padx=8, pady=6).pack(fill="x", pady=(0, 4))
        tk.Frame(bf, bg=C["card"], height=6).pack()
        _hover_btn(bf, "선택 삭제", self._pg_delete,
                   C["danger"], C["danger_h"], padx=8, pady=6).pack(fill="x", pady=(0, 4))
        _hover_btn(bf, "전체 선택", lambda: self.pg_listbox.selection_set(0, "end"),
                   C["sub"], "#475569", padx=8, pady=6).pack(fill="x", pady=(0, 4))
        _hover_btn(bf, "선택 해제", lambda: self.pg_listbox.selection_clear(0, "end"),
                   C["sub"], "#475569", padx=8, pady=6).pack(fill="x")

        # 저장
        c3 = SectionCard(f, "저장 위치")
        c3.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        b3 = c3.body
        b3.columnconfigure(0, weight=1)
        self.pg_out_var = tk.StringVar()
        _entry(b3, self.pg_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b3, "찾아보기", self._pg_browse_out,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        self.pg_pb = _make_progressbar(f)
        self.pg_pb.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self.pg_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        tk.Label(f, textvariable=self.pg_sv, font=FONT_SM,
                 bg=C["bg"], fg=C["sub"], anchor="w").grid(
            row=4, column=0, sticky="ew", pady=(0, 8))
        btn = _hover_btn(f, "  편집 결과 저장",
                         self._pg_save, C["success"], C["success_h"])
        btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        btn.grid(row=5, column=0, sticky="ew")

    # ──────────────────────────────────────────────────────────
    # TAB 3 — 병합
    # ──────────────────────────────────────────────────────────
    def _build_merge_tab(self, parent):
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=16)
        f.pack(fill="both", expand=True)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        c1 = SectionCard(f, "병합할 PDF 파일 목록")
        c1.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        c1.rowconfigure(0, weight=1)
        lb_body = c1.body
        lb_body.columnconfigure(0, weight=1)
        lb_body.rowconfigure(0, weight=1)

        lf = tk.Frame(lb_body, bg=C["card"])
        lf.grid(row=0, column=0, sticky="nsew")
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        self.mg_listbox, mg_sb = _listbox(lf, height=10)
        self.mg_listbox.grid(row=0, column=0, sticky="nsew")
        mg_sb.grid(row=0, column=1, sticky="ns")

        bf = tk.Frame(lb_body, bg=C["card"])
        bf.grid(row=0, column=1, padx=(8, 0), sticky="n")
        for text, cmd in [
            ("+ 추가",   self._mg_add),
            ("▲ 위로",   self._mg_move_up),
            ("▼ 아래로", self._mg_move_down),
        ]:
            _hover_btn(bf, text, cmd, C["primary"], C["primary_h"],
                       padx=8, pady=6).pack(fill="x", pady=(0, 4))
        tk.Frame(bf, bg=C["card"], height=6).pack()
        _hover_btn(bf, "제거",    self._mg_remove,
                   C["danger"], C["danger_h"], padx=8, pady=6).pack(fill="x", pady=(0, 4))
        _hover_btn(bf, "전체 제거", self._mg_clear,
                   C["danger"], C["danger_h"], padx=8, pady=6).pack(fill="x")

        c2 = SectionCard(f, "저장 위치")
        c2.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        b2 = c2.body
        b2.columnconfigure(0, weight=1)
        self.mg_out_var = tk.StringVar()
        _entry(b2, self.mg_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b2, "찾아보기", self._mg_browse_out,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        self.mg_pb = _make_progressbar(f)
        self.mg_pb.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.mg_sv = tk.StringVar(value="병합할 PDF 파일을 추가하세요.")
        tk.Label(f, textvariable=self.mg_sv, font=FONT_SM,
                 bg=C["bg"], fg=C["sub"], anchor="w").grid(
            row=3, column=0, sticky="ew", pady=(0, 8))
        btn = _hover_btn(f, "  PDF 병합하여 저장",
                         self._mg_start, C["success"], C["success_h"])
        btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        btn.grid(row=4, column=0, sticky="ew")

    # ──────────────────────────────────────────────────────────
    # TAB 4 — 나누기
    # ──────────────────────────────────────────────────────────
    def _build_split_tab(self, parent):
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=16)
        f.pack(fill="both", expand=True)

        c1 = SectionCard(f, "PDF 파일")
        c1.pack(fill="x", pady=(0, 10))
        b1 = c1.body
        b1.columnconfigure(0, weight=1)
        self.sp_file_var = tk.StringVar()
        _entry(b1, self.sp_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b1, "찾아보기", self._sp_browse_file,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)
        self.sp_info_lbl = tk.Label(b1, text="", font=FONT_SM,
                                    bg=C["card"], fg=C["sub"])
        self.sp_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        c2 = SectionCard(f, "나누기 방식")
        c2.pack(fill="x", pady=(0, 10))
        mb = c2.body
        self.sp_mode_var = tk.StringVar(value="each")
        modes = [
            ("each",  "모든 페이지를 개별 파일로 분리"),
            ("range", "페이지 범위 지정  (예: 1-3, 5, 7-9)"),
            ("every", "N 페이지마다 분리"),
        ]
        for i, (val, label) in enumerate(modes):
            tk.Radiobutton(mb, text=label, variable=self.sp_mode_var, value=val,
                           font=FONT, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"],
                           command=self._sp_mode_changed,
                           ).grid(row=i, column=0, sticky="w", pady=2)

        self.sp_range_frame = tk.Frame(mb, bg=C["card"])
        self.sp_range_frame.grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.sp_range_var = tk.StringVar()
        _entry(self.sp_range_frame, self.sp_range_var, width=20).pack()
        self.sp_range_frame.grid_remove()

        self.sp_every_frame = tk.Frame(mb, bg=C["card"])
        self.sp_every_frame.grid(row=2, column=1, padx=(12, 0), sticky="w")
        tk.Label(self.sp_every_frame, text="N =", font=FONT,
                 bg=C["card"], fg=C["text"]).pack(side="left")
        self.sp_every_var = tk.StringVar(value="2")
        tk.Spinbox(self.sp_every_frame, textvariable=self.sp_every_var,
                   from_=1, to=999, width=5, font=FONT,
                   relief="solid", bd=1).pack(side="left", padx=(4, 0))
        self.sp_every_frame.grid_remove()

        c3 = SectionCard(f, "저장 폴더")
        c3.pack(fill="x", pady=(0, 10))
        b3 = c3.body
        b3.columnconfigure(0, weight=1)
        self.sp_dir_var = tk.StringVar()
        _entry(b3, self.sp_dir_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b3, "폴더 선택", self._sp_browse_dir,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        self.sp_pb = _make_progressbar(f)
        self.sp_pb.pack(fill="x", pady=(0, 4))
        self.sp_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        tk.Label(f, textvariable=self.sp_sv, font=FONT_SM,
                 bg=C["bg"], fg=C["sub"], anchor="w").pack(fill="x", pady=(0, 8))
        btn = _hover_btn(f, "  PDF 나누기",
                         self._sp_start, C["success"], C["success_h"])
        btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        btn.pack(fill="x")

    # ──────────────────────────────────────────────────────────
    # TAB 5 — 압축
    # ──────────────────────────────────────────────────────────
    def _build_compress_tab(self, parent):
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=16)
        f.pack(fill="both", expand=True)

        c1 = SectionCard(f, "PDF 파일")
        c1.pack(fill="x", pady=(0, 10))
        b1 = c1.body
        b1.columnconfigure(0, weight=1)
        self.cp_file_var = tk.StringVar()
        _entry(b1, self.cp_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b1, "찾아보기", self._cp_browse_file,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)
        self.cp_info_lbl = tk.Label(b1, text="", font=FONT_SM,
                                    bg=C["card"], fg=C["sub"])
        self.cp_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        c2 = SectionCard(f, "압축 옵션")
        c2.pack(fill="x", pady=(0, 10))
        ob = c2.body

        self.cp_streams_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ob, text="콘텐츠 스트림 압축  (Deflate / zlib)",
                       variable=self.cp_streams_var,
                       font=FONT, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], selectcolor=C["card"],
                       ).grid(row=0, column=0, sticky="w", pady=2)

        self.cp_dedup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ob, text="중복 객체 제거  (identical objects)",
                       variable=self.cp_dedup_var,
                       font=FONT, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], selectcolor=C["card"],
                       ).grid(row=1, column=0, sticky="w", pady=2)

        self.cp_meta_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ob, text="메타데이터 제거",
                       variable=self.cp_meta_var,
                       font=FONT, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], selectcolor=C["card"],
                       ).grid(row=2, column=0, sticky="w", pady=2)

        level_f = tk.Frame(ob, bg=C["card"])
        level_f.grid(row=3, column=0, sticky="w", pady=(6, 0))
        tk.Label(level_f, text="압축 레벨:", font=FONT,
                 bg=C["card"], fg=C["text"]).pack(side="left")
        self.cp_level_var = tk.IntVar(value=9)
        for lvl, lbl in [(1, "빠름 (1)"), (6, "균형 (6)"), (9, "최대 (9)")]:
            tk.Radiobutton(level_f, text=lbl, variable=self.cp_level_var, value=lvl,
                           font=FONT_SM, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"],
                           ).pack(side="left", padx=(8, 0))

        c3 = SectionCard(f, "저장 위치")
        c3.pack(fill="x", pady=(0, 10))
        b3 = c3.body
        b3.columnconfigure(0, weight=1)
        self.cp_out_var = tk.StringVar()
        _entry(b3, self.cp_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        _hover_btn(b3, "찾아보기", self._cp_browse_out,
                   C["primary"], C["primary_h"]).grid(row=0, column=1)

        self.cp_pb = _make_progressbar(f)
        self.cp_pb.pack(fill="x", pady=(0, 4))
        self.cp_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        tk.Label(f, textvariable=self.cp_sv, font=FONT_SM,
                 bg=C["bg"], fg=C["sub"], anchor="w").pack(fill="x", pady=(0, 8))
        btn = _hover_btn(f, "  압축하여 저장",
                         self._cp_start, C["success"], C["success_h"])
        btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        btn.pack(fill="x")

    # ──────────────────────────────────────────────────────────
    # 암호화 핸들러
    # ──────────────────────────────────────────────────────────
    def _toggle_pw1(self):
        self._show_pw = not self._show_pw
        self._pw_entry.config(show="" if self._show_pw else "*")
        self._eye1.config(text="Hide" if self._show_pw else "Show")

    def _toggle_pw2(self):
        self._show_pw2 = not self._show_pw2
        self._pw2_entry.config(show="" if self._show_pw2 else "*")
        self._eye2.config(text="Hide" if self._show_pw2 else "Show")

    def _update_strength(self):
        pw = self.pw_var.get()
        score = sum([
            len(pw) >= 8,
            len(pw) >= 12,
            any(c.isdigit() for c in pw),
            any(c in "!@#$%^&*()" for c in pw),
        ])
        colors = ["#EF4444", "#F97316", "#EAB308", "#16A34A"]
        labels = ["취약", "보통", "강함", "매우 강함"]
        for i, bar in enumerate(self.strength_bars):
            bar.config(bg=colors[score - 1] if pw and i < score else C["border"])
        self.strength_lbl.config(
            text=labels[score - 1] if pw else "",
            fg=colors[score - 1] if pw else C["sub"],
        )

    def _check_match(self):
        p1, p2 = self.pw_var.get(), self.pw2_var.get()
        if not p2:
            self.match_lbl.config(text="")
        elif p1 == p2:
            self.match_lbl.config(text="✓ 비밀번호 일치", fg=C["success"])
        else:
            self.match_lbl.config(text="✗ 비밀번호 불일치", fg=C["danger"])

    def _enc_browse_file(self):
        p = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        if p:
            self.enc_file_var.set(p)
            base, ext = os.path.splitext(p)
            self.enc_out_var.set(base + "_encrypted" + ext)

    def _enc_browse_out(self):
        src = self.enc_file_var.get()
        init = os.path.dirname(src) if src and os.path.isfile(src) else os.path.expanduser("~")
        p = filedialog.asksaveasfilename(
            title="저장 위치 선택", initialdir=init,
            defaultextension=".pdf", filetypes=[("PDF 파일", "*.pdf")])
        if p:
            self.enc_out_var.set(p)

    def _enc_start(self):
        src = self.enc_file_var.get().strip()
        pw1, pw2 = self.pw_var.get(), self.pw2_var.get()
        out = self.enc_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not pw1:
            messagebox.showerror("오류", "비밀번호를 입력하세요."); return
        if pw1 != pw2:
            messagebox.showerror("오류", "비밀번호가 일치하지 않습니다."); return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        threading.Thread(target=self._enc_run,
                         args=(src, pw1, out, self.algo_var.get()), daemon=True).start()

    def _enc_run(self, src: str, password: str, out: str, algo: str):
        self.after(0, self.enc_pb.start, 10)
        self.after(0, self.enc_sv.set, "암호화 진행 중...")
        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            if reader.metadata:
                writer.add_metadata(dict(reader.metadata))
            writer.encrypt(user_password=password, owner_password=password, algorithm=algo)
            with open(out, "wb") as fh:
                writer.write(fh)
            name = os.path.basename(out)
            self.after(0, self.enc_pb.stop)
            self.after(0, self.enc_sv.set, f"완료 -> {name}")
            self.after(0, messagebox.showinfo, "완료",
                       f"암호화 완료!\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self.enc_pb.stop)
            self.after(0, self.enc_sv.set, "오류가 발생했습니다.")
            self.after(0, messagebox.showerror, "오류", str(e))

    # ──────────────────────────────────────────────────────────
    # 페이지 편집 핸들러
    # ──────────────────────────────────────────────────────────
    def _pg_browse_file(self):
        p = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        if not p:
            return
        self.pg_file_var.set(p)
        try:
            n = len(PdfReader(p).pages)
            self.pg_info_lbl.config(text=f"총 {n}페이지")
            self.pg_listbox.delete(0, "end")
            for i in range(n):
                self.pg_listbox.insert("end", f"  페이지 {i + 1}")
            base, ext = os.path.splitext(p)
            self.pg_out_var.set(base + "_edited" + ext)
            self.pg_sv.set("편집할 페이지를 선택하고 삭제하거나 순서를 변경하세요.")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _pg_move_up(self):
        sel = list(self.pg_listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for i in sel:
            text = self.pg_listbox.get(i)
            self.pg_listbox.delete(i)
            self.pg_listbox.insert(i - 1, text)
        self.pg_listbox.selection_clear(0, "end")
        for i in sel:
            self.pg_listbox.selection_set(i - 1)

    def _pg_move_down(self):
        sel = list(self.pg_listbox.curselection())
        if not sel or sel[-1] == self.pg_listbox.size() - 1:
            return
        for i in reversed(sel):
            text = self.pg_listbox.get(i)
            self.pg_listbox.delete(i)
            self.pg_listbox.insert(i + 1, text)
        self.pg_listbox.selection_clear(0, "end")
        for i in sel:
            self.pg_listbox.selection_set(i + 1)

    def _pg_delete(self):
        sel = list(self.pg_listbox.curselection())
        if not sel:
            messagebox.showwarning("알림", "삭제할 페이지를 선택하세요.")
            return
        for i in reversed(sel):
            self.pg_listbox.delete(i)
        self.pg_sv.set(f"{len(sel)}페이지 삭제됨. 현재 {self.pg_listbox.size()}페이지.")

    def _pg_browse_out(self):
        src = self.pg_file_var.get()
        init = os.path.dirname(src) if src and os.path.isfile(src) else os.path.expanduser("~")
        p = filedialog.asksaveasfilename(
            title="저장 위치 선택", initialdir=init,
            defaultextension=".pdf", filetypes=[("PDF 파일", "*.pdf")])
        if p:
            self.pg_out_var.set(p)

    def _pg_save(self):
        src = self.pg_file_var.get().strip()
        out = self.pg_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if self.pg_listbox.size() == 0:
            messagebox.showerror("오류", "최소 1페이지 이상 있어야 합니다."); return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        # 레이블에서 원본 페이지 번호 파싱 → 인덱스 리스트
        indices: list[int] = []
        for i in range(self.pg_listbox.size()):
            m = re.search(r"페이지\s+(\d+)", self.pg_listbox.get(i))
            if m:
                indices.append(int(m.group(1)) - 1)
        if not indices:
            messagebox.showerror("오류", "페이지 정보를 파싱할 수 없습니다."); return
        threading.Thread(target=self._pg_run,
                         args=(src, indices, out), daemon=True).start()

    def _pg_run(self, src: str, indices: list[int], out: str):
        self.after(0, self.pg_pb.start, 10)
        self.after(0, self.pg_sv.set, "저장 중...")
        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")
            writer = PdfWriter()
            for idx in indices:
                writer.add_page(reader.pages[idx])
            if reader.metadata:
                writer.add_metadata(dict(reader.metadata))
            with open(out, "wb") as fh:
                writer.write(fh)
            n = len(indices)
            self.after(0, self.pg_pb.stop)
            self.after(0, self.pg_sv.set, f"완료 -> {os.path.basename(out)}")
            self.after(0, messagebox.showinfo, "완료",
                       f"{n}페이지 저장 완료!\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self.pg_pb.stop)
            self.after(0, self.pg_sv.set, "오류가 발생했습니다.")
            self.after(0, messagebox.showerror, "오류", str(e))

    # ──────────────────────────────────────────────────────────
    # 병합 핸들러
    # ──────────────────────────────────────────────────────────
    def _mg_add(self):
        paths = filedialog.askopenfilenames(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        for p in paths:
            if p not in self.merge_files:
                self.merge_files.append(p)
                self.mg_listbox.insert("end", f"  {os.path.basename(p)}")
        self.mg_sv.set(f"{len(self.merge_files)}개 파일 준비됨.")

    def _mg_remove(self):
        sel = list(self.mg_listbox.curselection())
        for i in reversed(sel):
            self.mg_listbox.delete(i)
            del self.merge_files[i]
        self.mg_sv.set(f"{len(self.merge_files)}개 파일 준비됨.")

    def _mg_clear(self):
        self.mg_listbox.delete(0, "end")
        self.merge_files.clear()
        self.mg_sv.set("병합할 PDF 파일을 추가하세요.")

    def _mg_move_up(self):
        sel = list(self.mg_listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for i in sel:
            text = self.mg_listbox.get(i)
            self.mg_listbox.delete(i)
            self.mg_listbox.insert(i - 1, text)
            self.merge_files[i], self.merge_files[i - 1] = (
                self.merge_files[i - 1], self.merge_files[i])
        self.mg_listbox.selection_clear(0, "end")
        for i in sel:
            self.mg_listbox.selection_set(i - 1)

    def _mg_move_down(self):
        sel = list(self.mg_listbox.curselection())
        if not sel or sel[-1] == self.mg_listbox.size() - 1:
            return
        for i in reversed(sel):
            text = self.mg_listbox.get(i)
            self.mg_listbox.delete(i)
            self.mg_listbox.insert(i + 1, text)
            self.merge_files[i], self.merge_files[i + 1] = (
                self.merge_files[i + 1], self.merge_files[i])
        self.mg_listbox.selection_clear(0, "end")
        for i in sel:
            self.mg_listbox.selection_set(i + 1)

    def _mg_browse_out(self):
        p = filedialog.asksaveasfilename(
            title="저장 위치 선택", defaultextension=".pdf",
            filetypes=[("PDF 파일", "*.pdf")])
        if p:
            self.mg_out_var.set(p)

    def _mg_start(self):
        if len(self.merge_files) < 2:
            messagebox.showerror("오류", "PDF 파일을 2개 이상 추가하세요."); return
        out = self.mg_out_var.get().strip()
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        threading.Thread(target=self._mg_run,
                         args=(list(self.merge_files), out), daemon=True).start()

    def _mg_run(self, files: list[str], out: str):
        self.after(0, self.mg_pb.start, 10)
        self.after(0, self.mg_sv.set, "병합 중...")
        try:
            writer = PdfWriter()
            for path in files:
                reader = PdfReader(path)
                if reader.is_encrypted:
                    reader.decrypt("")
                for page in reader.pages:
                    writer.add_page(page)
            with open(out, "wb") as fh:
                writer.write(fh)
            self.after(0, self.mg_pb.stop)
            self.after(0, self.mg_sv.set, f"완료 -> {os.path.basename(out)}")
            self.after(0, messagebox.showinfo, "완료",
                       f"병합 완료! ({len(files)}개 파일)\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self.mg_pb.stop)
            self.after(0, self.mg_sv.set, "오류가 발생했습니다.")
            self.after(0, messagebox.showerror, "오류", str(e))

    # ──────────────────────────────────────────────────────────
    # 나누기 핸들러
    # ──────────────────────────────────────────────────────────
    def _sp_browse_file(self):
        p = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        if not p:
            return
        self.sp_file_var.set(p)
        try:
            n = len(PdfReader(p).pages)
            self.sp_info_lbl.config(text=f"총 {n}페이지")
            self.sp_dir_var.set(os.path.dirname(p))
            self.sp_sv.set(f"총 {n}페이지. 나누기 방식을 선택하세요.")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _sp_browse_dir(self):
        d = filedialog.askdirectory(title="저장 폴더 선택")
        if d:
            self.sp_dir_var.set(d)

    def _sp_mode_changed(self):
        mode = self.sp_mode_var.get()
        self.sp_range_frame.grid_remove()
        self.sp_every_frame.grid_remove()
        if mode == "range":
            self.sp_range_frame.grid()
        elif mode == "every":
            self.sp_every_frame.grid()

    @staticmethod
    def _parse_ranges(range_str: str, total: int) -> list[list[int]]:
        groups: list[list[int]] = []
        for part in range_str.split(","):
            part = part.strip()
            if not part:
                continue
            m = re.match(r"^(\d+)-(\d+)$", part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if a < 1 or b > total or a > b:
                    raise ValueError(f"잘못된 범위: {part}  (1~{total})")
                groups.append(list(range(a - 1, b)))
            elif re.match(r"^\d+$", part):
                p = int(part)
                if p < 1 or p > total:
                    raise ValueError(f"잘못된 페이지: {p}  (1~{total})")
                groups.append([p - 1])
            else:
                raise ValueError(f"파싱 오류: '{part}'")
        return groups

    def _sp_start(self):
        src = self.sp_file_var.get().strip()
        out_dir = self.sp_dir_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not out_dir or not os.path.isdir(out_dir):
            messagebox.showerror("오류", "유효한 저장 폴더를 선택하세요."); return
        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")
            total = len(reader.pages)
            mode = self.sp_mode_var.get()
            if mode == "each":
                groups = [[i] for i in range(total)]
            elif mode == "range":
                rng = self.sp_range_var.get().strip()
                if not rng:
                    messagebox.showerror("오류", "페이지 범위를 입력하세요."); return
                groups = self._parse_ranges(rng, total)
            else:
                try:
                    n = int(self.sp_every_var.get())
                    if n < 1:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("오류", "N은 1 이상의 정수여야 합니다."); return
                groups = [list(range(i, min(i + n, total)))
                          for i in range(0, total, n)]
        except Exception as e:
            messagebox.showerror("오류", str(e)); return
        threading.Thread(target=self._sp_run,
                         args=(src, groups, out_dir), daemon=True).start()

    def _sp_run(self, src: str, groups: list[list[int]], out_dir: str):
        self.after(0, self.sp_pb.start, 10)
        self.after(0, self.sp_sv.set, "나누기 진행 중...")
        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")
            base = os.path.splitext(os.path.basename(src))[0]
            pad = len(str(len(groups)))
            for idx, group in enumerate(groups):
                writer = PdfWriter()
                for pg in group:
                    writer.add_page(reader.pages[pg])
                fname = f"{base}_part{str(idx + 1).zfill(pad)}.pdf"
                with open(os.path.join(out_dir, fname), "wb") as fh:
                    writer.write(fh)
            count = len(groups)
            self.after(0, self.sp_pb.stop)
            self.after(0, self.sp_sv.set, f"완료: {count}개 파일 저장됨")
            self.after(0, messagebox.showinfo, "완료",
                       f"{count}개 파일로 분리 완료!\n\n폴더:\n{out_dir}")
        except Exception as e:
            self.after(0, self.sp_pb.stop)
            self.after(0, self.sp_sv.set, "오류가 발생했습니다.")
            self.after(0, messagebox.showerror, "오류", str(e))

    # ──────────────────────────────────────────────────────────
    # 압축 핸들러
    # ──────────────────────────────────────────────────────────
    def _cp_browse_file(self):
        p = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        if not p:
            return
        self.cp_file_var.set(p)
        size_kb = os.path.getsize(p) / 1024
        try:
            n = len(PdfReader(p).pages)
            self.cp_info_lbl.config(text=f"총 {n}페이지  /  {size_kb:.1f} KB")
        except Exception:
            self.cp_info_lbl.config(text=f"{size_kb:.1f} KB")
        base, ext = os.path.splitext(p)
        self.cp_out_var.set(base + "_compressed" + ext)
        self.cp_sv.set("압축 옵션을 선택하고 저장하세요.")

    def _cp_browse_out(self):
        src = self.cp_file_var.get()
        init = os.path.dirname(src) if src and os.path.isfile(src) else os.path.expanduser("~")
        p = filedialog.asksaveasfilename(
            title="저장 위치 선택", initialdir=init,
            defaultextension=".pdf", filetypes=[("PDF 파일", "*.pdf")])
        if p:
            self.cp_out_var.set(p)

    def _cp_start(self):
        src = self.cp_file_var.get().strip()
        out = self.cp_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        opts = {
            "compress_streams": self.cp_streams_var.get(),
            "dedup":            self.cp_dedup_var.get(),
            "remove_meta":      self.cp_meta_var.get(),
            "level":            self.cp_level_var.get(),
        }
        threading.Thread(target=self._cp_run,
                         args=(src, out, opts), daemon=True).start()

    def _cp_run(self, src: str, out: str, opts: dict):
        self.after(0, self.cp_pb.start, 10)
        self.after(0, self.cp_sv.set, "압축 중...")
        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")
            writer = PdfWriter()
            for page in reader.pages:
                if opts["compress_streams"]:
                    page.compress_content_streams(level=opts["level"])
                writer.add_page(page)
            if not opts["remove_meta"] and reader.metadata:
                writer.add_metadata(dict(reader.metadata))
            if opts["dedup"]:
                writer.compress_identical_objects(
                    remove_identicals=True, remove_orphans=True)
            with open(out, "wb") as fh:
                writer.write(fh)
            orig_kb = os.path.getsize(src) / 1024
            out_kb  = os.path.getsize(out) / 1024
            ratio   = (1 - out_kb / orig_kb) * 100 if orig_kb > 0 else 0
            summary = (
                f"압축 완료!\n\n"
                f"원본:  {orig_kb:.1f} KB\n"
                f"결과:  {out_kb:.1f} KB\n"
                f"절감:  {ratio:.1f}%\n\n"
                f"저장 위치:\n{out}"
            )
            self.after(0, self.cp_pb.stop)
            self.after(0, self.cp_sv.set,
                       f"완료: {orig_kb:.1f} KB → {out_kb:.1f} KB ({ratio:.1f}% 절감)")
            self.after(0, messagebox.showinfo, "완료", summary)
        except Exception as e:
            self.after(0, self.cp_pb.stop)
            self.after(0, self.cp_sv.set, "오류가 발생했습니다.")
            self.after(0, messagebox.showerror, "오류", str(e))


if __name__ == "__main__":
    app = PDFToolApp()
    app.mainloop()
