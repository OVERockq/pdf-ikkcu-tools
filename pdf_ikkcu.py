"""PDF ikkcu — Freeware PDF Tool v1.0"""
from __future__ import annotations
import re, os, sys, threading, webbrowser, tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

# ── auto-install (skipped when frozen by PyInstaller) ────────
def _pip(*pkgs: str) -> None:
    import subprocess, sys
    if getattr(sys, "frozen", False):
        return          # deps are bundled; never call sys.executable = EXE
    _MOD = {"pymupdf": "fitz"}   # package name → importable module name
    for pkg in pkgs:
        mod = _MOD.get(pkg.split(">=")[0], pkg.split(">=")[0].replace("-", "_"))
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_pip("pypdf", "pymupdf", "Pillow")

from pypdf import PdfReader, PdfWriter   # type: ignore
import fitz                               # type: ignore  (pymupdf)
from PIL import Image, ImageTk            # type: ignore

# ── tokens ───────────────────────────────────────────────────
C = {
    "bg":      "#EEF1F4", "card":    "#FFFFFF", "card_hdr": "#F7F8FA",
    "primary": "#1F6FEB", "pri_h":   "#1557C0", "pri_t":    "#EAF2FF",
    "success": "#0E9F6E", "suc_h":   "#057A55",
    "danger":  "#E11D48", "dan_h":   "#BE123C",
    "border":  "#D8DEE7", "text":    "#111827",
    "sub":     "#5B6472", "muted":   "#8A94A3",
    "sel":     "#DCEBFF", "badge_bg":"#EAF2FF", "badge_fg":"#1557C0",
    "chrome":  "#FFFFFF", "chrome_sub": "#6B7280",
}

def _ui_family() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("Apple SD Gothic Neo",)
    if os.name == "nt":
        return ("Segoe UI", "Malgun Gothic")
    return ("Noto Sans CJK KR", "Noto Sans")

MG = _ui_family()

def _font_sizes() -> tuple[int, int, int, int]:
    return (13, 12, 18, 14) if sys.platform == "darwin" else (10, 9, 15, 11)

FS, FS_SM, FS_TTL, FS_BTN = _font_sizes()
F      = (*MG, FS)
F_B    = (*MG, FS, "bold")
F_SM   = (*MG, FS_SM)
F_TTL  = (*MG, FS_TTL, "bold")

def _display_scaling_target() -> float:
    return 2.0 if sys.platform == "darwin" else 1.10

def apply_display_scaling(root: tk.Tk) -> None:
    try:
        current = float(root.tk.call("tk", "scaling"))
        root.tk.call("tk", "scaling", max(current, _display_scaling_target()))
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=MG[0], size=FS)
        tkfont.nametofont("TkSmallCaptionFont").configure(family=MG[0], size=FS_SM)
    except tk.TclError:
        pass

# ── helpers ──────────────────────────────────────────────────
def hbtn(parent, text, cmd, bg, bgh, fg="white", **kw) -> tk.Button:
    kw.setdefault("padx", 14); kw.setdefault("pady", 8)
    b = tk.Button(parent, text=text, command=cmd, font=F_B,
                  bg=bg, fg=fg, relief="flat", bd=0, cursor="hand2",
                  activebackground=bgh, activeforeground=fg, **kw)
    b.bind("<Enter>", lambda _: b.config(bg=bgh))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b

def centry(parent, var, width=44) -> tk.Entry:
    return tk.Entry(parent, textvariable=var, width=width, font=F,
                    relief="solid", bd=1, highlightthickness=1,
                    highlightcolor=C["primary"], highlightbackground=C["border"])

def mkpb(parent) -> ttk.Progressbar:
    s = ttk.Style()
    s.configure("A.Horizontal.TProgressbar", troughcolor=C["border"],
                background=C["primary"], thickness=4, borderwidth=0)
    return ttk.Progressbar(parent, mode="indeterminate",
                           style="A.Horizontal.TProgressbar")


# ── SectionCard ──────────────────────────────────────────────
class SectionCard(tk.Frame):
    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, bg=C["card"],
                         highlightbackground=C["border"], highlightthickness=1, **kw)
        tk.Frame(self, bg=C["card_hdr"]).pack(fill="x")  # top accent line
        hdr = tk.Frame(self, bg=C["card_hdr"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=F_B, bg=C["card_hdr"],
                 fg=C["text"], padx=14, pady=9).pack(side="left")
        sep = tk.Frame(self, bg=C["border"], height=1)
        sep.pack(fill="x")
        self._body = tk.Frame(self, bg=C["card"])
        self._body.pack(fill="x", padx=14, pady=(10, 14))

    @property
    def body(self) -> tk.Frame:
        return self._body


# ── ThumbnailGrid ────────────────────────────────────────────
class ThumbnailGrid(tk.Frame):
    """Scrollable page-thumbnail grid with click-to-select, move, delete, append."""
    COLS = 4
    TW, TH = 108, 140

    def __init__(self, parent, on_change=None, **kw):
        super().__init__(parent, bg=C["card"], **kw)
        self._photos:  list[ImageTk.PhotoImage] = []
        self._order:   list[int]                = []
        self._sel:     set[int]                 = set()
        self._cells:   dict[int, tuple]         = {}
        self._sources: list[tuple[str, int]]    = []  # (file_path, orig_page_idx)
        self._on_change = on_change
        self._build()

    def _build(self):
        cv = tk.Canvas(self, bg=C["card"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=cv.yview)
        cv.config(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._inner = tk.Frame(cv, bg=C["card"])
        wid = cv.create_window((0, 0), window=self._inner, anchor="nw")
        cv.bind("<Configure>",  lambda e: cv.itemconfig(wid, width=e.width))
        self._inner.bind("<Configure>",
                        lambda e: cv.config(scrollregion=cv.bbox("all")))
        cv.bind("<MouseWheel>",
                lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))
        self._cv = cv

    # ── public API ────────────────────────────────────────────
    def load(self, path: str, on_ready=None):
        self._clear(); self._photos.clear(); self._sources.clear()
        self._order.clear(); self._sel.clear(); self._cells.clear()
        threading.Thread(target=self._render, args=(path, False, on_ready),
                        daemon=True).start()

    def append(self, path: str, on_ready=None):
        """Append all pages from another PDF after the current pages."""
        threading.Thread(target=self._render, args=(path, True, on_ready),
                        daemon=True).start()

    def select_all(self):
        self._sel = set(range(len(self._order)))
        for p in self._sel: self._restyle(p)
        self._notify()

    def deselect_all(self):
        prev = set(self._sel); self._sel.clear()
        for p in prev: self._restyle(p)
        self._notify()

    def delete_selected(self) -> int:
        n = len(self._sel)
        if not n: return 0
        self._order = [i for p, i in enumerate(self._order) if p not in self._sel]
        self._sel.clear(); self._rebuild(); return n

    def move_up(self):
        sel = sorted(self._sel)
        if not sel or sel[0] == 0: return
        for i in sel:
            self._order[i-1], self._order[i] = self._order[i], self._order[i-1]
        self._sel = {s - 1 for s in self._sel}; self._rebuild()

    def move_down(self):
        sel = sorted(self._sel, reverse=True)
        if not sel or sel[0] == len(self._order) - 1: return
        for i in sel:
            self._order[i], self._order[i+1] = self._order[i+1], self._order[i]
        self._sel = {s + 1 for s in self._sel}; self._rebuild()

    def get_order(self)       -> list[int]: return list(self._order)
    def page_count(self)      -> int:       return len(self._order)
    def selected_count(self)  -> int:       return len(self._sel)

    def get_page_sources(self) -> list[tuple[str, int]]:
        """(file_path, orig_page_idx) for every page in current display order."""
        return [self._sources[i] for i in self._order]

    def get_selected_sources(self) -> list[tuple[str, int]]:
        """(file_path, orig_page_idx) for selected pages in position order."""
        return [self._sources[self._order[p]] for p in sorted(self._sel)]

    # ── internals ─────────────────────────────────────────────
    def _render(self, path: str, is_append: bool, on_ready):
        imgs = []
        try:
            doc = fitz.open(path)
            for pg in doc:
                z = min(self.TW / pg.rect.width, self.TH / pg.rect.height) * 1.6
                pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((self.TW, self.TH), Image.LANCZOS)
                imgs.append(img)
            doc.close()
        except Exception as e:
            self.after(0, messagebox.showerror, "오류", f"렌더링 실패:\n{e}"); return
        srcs = [(path, i) for i in range(len(imgs))]
        if is_append:
            self.after(0, self._append_grid, imgs, srcs, on_ready)
        else:
            self.after(0, self._init_grid,  imgs, srcs, on_ready)

    def _init_grid(self, imgs, srcs, on_ready):
        self._photos  = [ImageTk.PhotoImage(i) for i in imgs]
        self._order   = list(range(len(self._photos)))
        self._sources = list(srcs)
        self._rebuild()
        if on_ready: on_ready(len(self._photos))

    def _append_grid(self, imgs, srcs, on_ready):
        offset = len(self._photos)
        self._photos.extend(ImageTk.PhotoImage(i) for i in imgs)
        self._order.extend(range(offset, offset + len(imgs)))
        self._sources.extend(srcs)
        self._rebuild()
        if on_ready: on_ready(len(self._photos))

    def _clear(self):
        for w in self._inner.winfo_children(): w.destroy()

    def _rebuild(self):
        self._clear(); self._cells.clear()
        for pos, orig in enumerate(self._order):
            r, c = divmod(pos, self.COLS)
            sel = pos in self._sel
            bg  = C["sel"]     if sel else C["card"]
            bc  = C["primary"] if sel else C["border"]
            cell = tk.Frame(self._inner, bg=bg, padx=5, pady=5, cursor="hand2")
            cell.grid(row=r, column=c, padx=4, pady=4, sticky="n")
            bdr  = tk.Frame(cell, bg=bc, padx=2, pady=2)
            bdr.pack()
            tk.Label(bdr, image=self._photos[orig], bg=C["card"]).pack()
            nlbl = tk.Label(cell, text=f"p.{orig+1}", font=F_SM, bg=bg, fg=C["sub"])
            nlbl.pack(pady=(3, 0))
            self._cells[pos] = (cell, bdr, nlbl)
            cmd = lambda e, p=pos: self._click(p)
            for w in (cell, bdr, nlbl, *bdr.winfo_children()):
                w.bind("<Button-1>", cmd)
        self._notify()

    def _click(self, pos: int):
        self._sel.discard(pos) if pos in self._sel else self._sel.add(pos)
        self._restyle(pos); self._notify()

    def _restyle(self, pos: int):
        if pos not in self._cells: return
        sel = pos in self._sel
        bg  = C["sel"]     if sel else C["card"]
        bc  = C["primary"] if sel else C["border"]
        cell, bdr, nlbl = self._cells[pos]
        cell.config(bg=bg); bdr.config(bg=bc); nlbl.config(bg=bg)

    def _notify(self):
        if self._on_change: self._on_change(self.page_count(), self.selected_count())


# ── FlatNotebook ─────────────────────────────────────────────
class FlatNotebook(tk.Frame):
    """Borderless notebook: underline-indicator tabs, no ttk ridge."""

    _IND_H = 3   # active-tab indicator height in px

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._tabs:   list[tuple] = []   # (lbl, ind, frame)
        self._active: int         = -1

        self._strip = tk.Frame(self, bg=C["bg"])
        self._strip.pack(fill="x")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")
        self._deck = tk.Frame(self, bg=C["bg"])
        self._deck.pack(fill="both", expand=True)

    def add(self, text: str) -> tk.Frame:
        idx   = len(self._tabs)
        frame = tk.Frame(self._deck, bg=C["bg"])

        wrap = tk.Frame(self._strip, bg=C["bg"])
        wrap.pack(side="left")
        # indicator sits at bottom, always present; color change makes it visible
        ind = tk.Frame(wrap, bg=C["bg"], height=self._IND_H)
        ind.pack(fill="x", side="bottom")
        lbl = tk.Label(wrap, text=text, font=F,
                       bg=C["bg"], fg=C["sub"],
                       padx=18, pady=10, cursor="hand2")
        lbl.pack(side="top")

        self._tabs.append((lbl, ind, frame))
        lbl.bind("<Button-1>", lambda _, i=idx: self.select(i))
        lbl.bind("<Enter>",
                 lambda _, l=lbl, i=idx:
                 l.config(fg=C["text"]) if i != self._active else None)
        lbl.bind("<Leave>",
                 lambda _, l=lbl, i=idx:
                 l.config(fg=C["sub"]) if i != self._active else None)

        if idx == 0:
            self.select(0)
        return frame

    def select(self, idx: int):
        for i, (lbl, ind, frame) in enumerate(self._tabs):
            if i == idx:
                lbl.config(fg=C["primary"], font=F_B)
                ind.config(bg=C["primary"])
                frame.pack(fill="both", expand=True)
            else:
                lbl.config(fg=C["sub"], font=F)
                ind.config(bg=C["bg"])
                frame.pack_forget()
        self._active = idx


# ── Main App ─────────────────────────────────────────────────
class PDFIkkcu(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_display_scaling(self)
        self.title("PDF ikkcu")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(580, 560)
        self._merge_files: list[str] = []
        self._show_pw = self._show_pw2 = False
        self._closing = False
        self._set_icon()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 600)
        h = max(self.winfo_reqheight(), 620)
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        timer = threading.Timer(0.25, self._force_exit_current_process)
        timer.daemon = True
        timer.start()
        try:
            for pb in ("enc_pb", "pg_pb", "mg_pb", "sp_pb", "cp_pb"):
                widget = getattr(self, pb, None)
                if widget:
                    widget.stop()
            self.quit()
            self.destroy()
        except tk.TclError:
            self._force_exit_current_process()

    @staticmethod
    def _force_exit_current_process():
        os._exit(0)

    # ── icon ──────────────────────────────────────────────────
    def _set_icon(self):
        try:
            from PIL import ImageDraw
            sz = 256
            img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([8, 8, sz-8, sz-8], radius=44, fill="#111827")
            d.rounded_rectangle([48, 32, 184, 224], radius=12, fill="#FFFFFF")
            d.polygon([(144, 32), (184, 72), (184, 32)], fill="#D8DEE7")
            d.line([(144, 32), (144, 72), (184, 72)], fill="#8A94A3", width=4)
            d.rectangle([48, 124, 184, 168], fill=C["primary"])
            try:
                from PIL import ImageFont
                fnt = ImageFont.truetype("arialbd.ttf", 36)
            except Exception:
                fnt = ImageFont.load_default()
            d.text((62, 130), "PDF", fill="white", font=fnt)
            self._icon_img = ImageTk.PhotoImage(img)
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    # ── shell ─────────────────────────────────────────────────
    def _build_ui(self):
        HDR = C["chrome"]; HDR_SUB = C["chrome_sub"]

        hdr = tk.Frame(self, bg=HDR)
        hdr.pack(fill="x")
        lf = tk.Frame(hdr, bg=HDR)
        lf.pack(side="left", padx=22, pady=14)
        tk.Label(lf, text="PDF ikkcu", font=F_TTL,
                 bg=HDR, fg=C["text"]).pack(side="left")
        tk.Label(lf, text="Document Workbench", font=F_SM,
                 bg=HDR, fg=HDR_SUB
                 ).pack(side="left", padx=(10, 0))
        tk.Label(lf, text="v1.0", font=F_SM,
                 bg=HDR, fg=HDR_SUB).pack(side="left", padx=(8, 0))
        lnk = tk.Label(hdr, text="© ikkcu.com", font=F_SM,
                       bg=HDR, fg=HDR_SUB, cursor="hand2")
        lnk.pack(side="right", padx=22)
        lnk.bind("<Enter>", lambda _: lnk.config(fg=C["text"]))
        lnk.bind("<Leave>", lambda _: lnk.config(fg=HDR_SUB))
        lnk.bind("<Button-1>", lambda _: webbrowser.open("https://ikkcu.com"))
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        foot = tk.Frame(self, bg=C["bg"])
        foot.pack(fill="x", side="bottom")
        tk.Label(foot, text="© 2025 ikkcu.com — All rights reserved",
                 font=F_SM, bg=C["bg"], fg=HDR_SUB, pady=5).pack()

        nb = FlatNotebook(self)
        nb.pack(fill="both", expand=True, pady=(0, 6))

        for name, builder in [("암호화",    self._build_enc_tab),
                               ("페이지 편집", self._build_pg_tab),
                               ("병합",      self._build_mg_tab),
                               ("나누기",    self._build_sp_tab),
                               ("압축",      self._build_cp_tab)]:
            builder(nb.add(f"  {name}  "))

    def _tab_frame(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"], padx=16, pady=14)
        f.pack(fill="both", expand=True)
        return f

    def _status_row(self, parent, sv: tk.StringVar, pb_attr: str):
        pb = mkpb(parent)
        pb.pack(fill="x", pady=(0, 3))
        setattr(self, pb_attr, pb)
        tk.Label(parent, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x", pady=(0, 8))

    def _save_btn(self, parent, text: str, cmd) -> tk.Button:
        b = hbtn(parent, text, cmd, C["success"], C["suc_h"])
        b.config(font=(*MG, FS_BTN, "bold"), pady=11)
        b.pack(fill="x")
        return b

    def _file_row(self, parent, var: tk.StringVar, browse_cmd):
        parent.columnconfigure(0, weight=1)
        centry(parent, var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(parent, "찾아보기", browse_cmd,
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)

    # ── TAB: 암호화 ───────────────────────────────────────────
    def _build_enc_tab(self, parent):
        f = self._tab_frame(parent)

        c = SectionCard(f, "PDF 파일"); c.pack(fill="x", pady=(0, 10))
        self.enc_file_var = tk.StringVar()
        self._file_row(c.body, self.enc_file_var, self._enc_browse)

        c2 = SectionCard(f, "비밀번호 설정"); c2.pack(fill="x", pady=(0, 10))
        self._pw_section(c2.body)

        c3 = SectionCard(f, "암호화 강도"); c3.pack(fill="x", pady=(0, 10))
        self.algo_var = tk.StringVar(value="AES-256")
        for i, (lbl, val) in enumerate([("AES-256  (최고 보안 / 권장)", "AES-256"),
                                         ("AES-128  (표준 보안)",        "AES-128"),
                                         ("RC4-128  (구형 호환)",        "RC4-128")]):
            tk.Radiobutton(c3.body, text=lbl, variable=self.algo_var, value=val,
                           font=F, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).grid(row=i, column=0, sticky="w", pady=2)

        c4 = SectionCard(f, "저장 위치"); c4.pack(fill="x", pady=(0, 12))
        self.enc_out_var = tk.StringVar()
        self._file_row(c4.body, self.enc_out_var,
                       lambda: self._save_dialog(self.enc_out_var, self.enc_file_var))

        self.enc_sv = tk.StringVar(value="파일을 선택하고 비밀번호를 입력하세요.")
        self._status_row(f, self.enc_sv, "enc_pb")
        self._save_btn(f, "  암호화하여 저장", self._enc_start)

    def _pw_section(self, parent):
        parent.columnconfigure(0, weight=1)
        tk.Label(parent, text="비밀번호", font=F_SM, bg=C["card"],
                 fg=C["sub"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,3))
        self.pw_var = tk.StringVar()
        self._pw_e = centry(parent, self.pw_var); self._pw_e.config(show="*")
        self._pw_e.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._eye1 = hbtn(parent, "Show", self._tgl_pw1,
                          C["border"], "#CBD5E1", C["text"], padx=10, pady=6)
        self._eye1.grid(row=1, column=1)

        sf = tk.Frame(parent, bg=C["card"]); sf.grid(row=2, column=0, columnspan=2,
                                                      sticky="w", pady=(6,0))
        self._sbars = []
        row_f = tk.Frame(sf, bg=C["card"]); row_f.pack(side="left")
        for _ in range(4):
            seg = tk.Frame(row_f, width=52, height=5, bg=C["border"])
            seg.pack_propagate(False); seg.pack(side="left", padx=2)
            self._sbars.append(seg)
        self._slbl = tk.Label(sf, text="", font=F_SM, bg=C["card"], fg=C["sub"])
        self._slbl.pack(side="left", padx=(10, 0))
        self.pw_var.trace_add("write", lambda *_: self._pw_strength())

        tk.Label(parent, text="비밀번호 확인", font=F_SM, bg=C["card"],
                 fg=C["sub"]).grid(row=3, column=0, columnspan=2,
                                   sticky="w", pady=(10,3))
        self.pw2_var = tk.StringVar()
        self._pw2_e = centry(parent, self.pw2_var); self._pw2_e.config(show="*")
        self._pw2_e.grid(row=4, column=0, sticky="ew", padx=(0, 8))
        self._eye2 = hbtn(parent, "Show", self._tgl_pw2,
                          C["border"], "#CBD5E1", C["text"], padx=10, pady=6)
        self._eye2.grid(row=4, column=1)
        self.pw2_var.trace_add("write", lambda *_: self._pw_match())
        self._mlbl = tk.Label(parent, text="", font=F_SM, bg=C["card"], fg=C["sub"])
        self._mlbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4,0))

    # ── TAB: 페이지 편집 ──────────────────────────────────────
    def _build_pg_tab(self, parent):
        f = self._tab_frame(parent)

        # File selection card (top)
        c1 = SectionCard(f, "PDF 파일")
        c1.pack(fill="x", pady=(0, 8))
        b = c1.body; b.columnconfigure(0, weight=1)
        self.pg_file_var = tk.StringVar()
        centry(b, self.pg_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(b, "찾아보기", self._pg_browse, C["primary"], C["pri_h"],
             padx=10, pady=6).grid(row=0, column=1)
        self.pg_info_lbl = tk.Label(b, text="", font=F_SM, bg=C["card"], fg=C["sub"])
        self.pg_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Save + status + button (bottom — packed before mid to anchor at bottom)
        bot = tk.Frame(f, bg=C["bg"])
        bot.pack(fill="x", side="bottom")
        c3 = SectionCard(bot, "저장 위치")
        c3.pack(fill="x", pady=(8, 8))
        b3 = c3.body; b3.columnconfigure(0, weight=1)
        self.pg_out_var = tk.StringVar()
        centry(b3, self.pg_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(b3, "찾아보기",
             lambda: self._save_dialog(self.pg_out_var, self.pg_file_var, "_edited"),
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)
        self.pg_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        self._status_row(bot, self.pg_sv, "pg_pb")
        self._save_btn(bot, "  편집 결과 저장", self._pg_save)

        # Thumbnail preview + sidebar (middle, expands to fill remaining space)
        mid = tk.Frame(f, bg=C["bg"])
        mid.pack(fill="both", expand=True)

        # Sidebar frame (right — pack first to reserve space)
        sb = tk.Frame(mid, bg=C["bg"])
        sb.pack(side="right", fill="y", padx=(8, 0))

        # Thumbnail card (left, expandable)
        thumb_outer = tk.Frame(mid, bg=C["card"],
                               highlightbackground=C["border"], highlightthickness=1)
        thumb_outer.pack(side="left", fill="both", expand=True)
        th_hdr = tk.Frame(thumb_outer, bg=C["card_hdr"])
        th_hdr.pack(fill="x")
        tk.Label(th_hdr, text="페이지 미리보기  —  클릭하여 선택, 버튼으로 편집",
                 font=F_B, bg=C["card_hdr"], fg=C["text"], padx=14, pady=9).pack(side="left")
        tk.Frame(thumb_outer, bg=C["border"], height=1).pack(fill="x")
        thumb_body = tk.Frame(thumb_outer, bg=C["card"])
        thumb_body.pack(fill="both", expand=True)

        self.thumb = ThumbnailGrid(thumb_body, on_change=self._pg_grid_changed)
        self.thumb.pack(fill="both", expand=True)

        self._pg_loading = tk.Label(thumb_body,
                                    text="PDF를 로드하면 미리보기가 표시됩니다.",
                                    font=F_SM, bg=C["card"], fg=C["muted"])
        self._pg_loading.place(relx=0.5, rely=0.5, anchor="center")

        # Sidebar content (self.thumb now exists, lambdas are safe)
        self.pg_status_lbl = tk.Label(sb, text="", font=F_SM,
                                      bg=C["bg"], fg=C["sub"], wraplength=90)
        self.pg_status_lbl.pack(fill="x", pady=(0, 8))
        for txt, cmd in [("▲ 위로",   self.thumb.move_up),
                         ("▼ 아래로", self.thumb.move_down)]:
            hbtn(sb, txt, cmd, C["primary"], C["pri_h"],
                 padx=8, pady=6).pack(fill="x", pady=(0, 4))
        tk.Frame(sb, bg=C["border"], height=1).pack(fill="x", pady=6)
        hbtn(sb, "선택 삭제", self._pg_delete, C["danger"], C["dan_h"],
             padx=8, pady=6).pack(fill="x", pady=(0, 4))
        hbtn(sb, "전체 선택", self.thumb.select_all,
             C["sub"], "#475569", padx=8, pady=6).pack(fill="x", pady=(0, 4))
        hbtn(sb, "선택 해제", self.thumb.deselect_all,
             C["sub"], "#475569", padx=8, pady=6).pack(fill="x", pady=(0, 4))
        tk.Frame(sb, bg=C["border"], height=1).pack(fill="x", pady=6)
        hbtn(sb, "+ 추가", self._pg_add, C["primary"], C["pri_h"],
             padx=8, pady=6).pack(fill="x", pady=(0, 4))
        hbtn(sb, "↓ 추출", self._pg_extract, C["success"], C["suc_h"],
             padx=8, pady=6).pack(fill="x")

    # ── TAB: 병합 ─────────────────────────────────────────────
    def _build_mg_tab(self, parent):
        f = self._tab_frame(parent)

        # Save + status + button (bottom — packed first to anchor at bottom)
        bot = tk.Frame(f, bg=C["bg"])
        bot.pack(fill="x", side="bottom")
        c2 = SectionCard(bot, "저장 위치")
        c2.pack(fill="x", pady=(8, 8))
        b2 = c2.body; b2.columnconfigure(0, weight=1)
        self.mg_out_var = tk.StringVar()
        centry(b2, self.mg_out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(b2, "찾아보기", lambda: self._save_dialog(self.mg_out_var),
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)
        self.mg_sv = tk.StringVar(value="병합할 PDF 파일을 추가하세요.")
        self._status_row(bot, self.mg_sv, "mg_pb")
        self._save_btn(bot, "  PDF 병합하여 저장", self._mg_start)

        # Expandable file list card (middle)
        list_outer = tk.Frame(f, bg=C["card"],
                              highlightbackground=C["border"], highlightthickness=1)
        list_outer.pack(fill="both", expand=True)
        lh = tk.Frame(list_outer, bg=C["card_hdr"])
        lh.pack(fill="x")
        tk.Label(lh, text="병합할 PDF 파일 목록", font=F_B,
                 bg=C["card_hdr"], fg=C["text"], padx=14, pady=9).pack(side="left")
        tk.Frame(list_outer, bg=C["border"], height=1).pack(fill="x")
        lb_body = tk.Frame(list_outer, bg=C["card"])
        lb_body.pack(fill="both", expand=True, padx=14, pady=(10, 14))

        # Action buttons (right)
        bf = tk.Frame(lb_body, bg=C["card"])
        bf.pack(side="right", fill="y", padx=(10, 0))
        for txt, cmd in [("+ 추가", self._mg_add), ("▲ 위로", self._mg_up),
                         ("▼ 아래로", self._mg_dn)]:
            hbtn(bf, txt, cmd, C["primary"], C["pri_h"],
                 padx=8, pady=6).pack(fill="x", pady=(0, 4))
        tk.Frame(bf, bg=C["border"], height=1).pack(fill="x", pady=6)
        for txt, cmd in [("제거", self._mg_rm), ("전체 제거", self._mg_clear)]:
            hbtn(bf, txt, cmd, C["danger"], C["dan_h"],
                 padx=8, pady=6).pack(fill="x", pady=(0, 4))

        # Listbox + scrollbar (left, expandable)
        lf = tk.Frame(lb_body, bg=C["card"])
        lf.pack(side="left", fill="both", expand=True)
        self.mg_lb = tk.Listbox(lf, font=F, bg=C["card"], fg=C["text"],
                                 relief="solid", bd=1, highlightthickness=1,
                                 highlightcolor=C["primary"],
                                 highlightbackground=C["border"],
                                 selectbackground=C["sel"],
                                 selectforeground=C["text"], height=8)
        mg_sb = ttk.Scrollbar(lf, orient="vertical", command=self.mg_lb.yview)
        self.mg_lb.config(yscrollcommand=mg_sb.set)
        self.mg_lb.pack(side="left", fill="both", expand=True)
        mg_sb.pack(side="right", fill="y")

    # ── TAB: 나누기 ───────────────────────────────────────────
    def _build_sp_tab(self, parent):
        f = self._tab_frame(parent)

        c1 = SectionCard(f, "PDF 파일"); c1.pack(fill="x", pady=(0, 10))
        b1 = c1.body; b1.columnconfigure(0, weight=1)
        self.sp_file_var = tk.StringVar()
        centry(b1, self.sp_file_var).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(b1, "찾아보기", self._sp_browse, C["primary"], C["pri_h"],
             padx=10, pady=6).grid(row=0, column=1)
        self.sp_info_lbl = tk.Label(b1, text="", font=F_SM, bg=C["card"], fg=C["sub"])
        self.sp_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4,0))

        c2 = SectionCard(f, "나누기 방식"); c2.pack(fill="x", pady=(0, 10))
        mb = c2.body
        self.sp_mode = tk.StringVar(value="each")
        modes = [("each",  "모든 페이지를 개별 파일로 분리"),
                 ("range", "페이지 범위 지정  (예: 1-3, 5, 7-9)"),
                 ("every", "N 페이지마다 분리")]
        for i, (v, lbl) in enumerate(modes):
            tk.Radiobutton(mb, text=lbl, variable=self.sp_mode, value=v,
                           font=F, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"],
                           command=self._sp_mode_change
                           ).grid(row=i, column=0, sticky="w", pady=2)
        self._sp_range_f = tk.Frame(mb, bg=C["card"])
        self._sp_range_f.grid(row=1, column=1, padx=(12,0), sticky="w")
        self.sp_range_var = tk.StringVar()
        centry(self._sp_range_f, self.sp_range_var, width=22).pack()
        self._sp_range_f.grid_remove()
        self._sp_every_f = tk.Frame(mb, bg=C["card"])
        self._sp_every_f.grid(row=2, column=1, padx=(12,0), sticky="w")
        tk.Label(self._sp_every_f, text="N =", font=F,
                 bg=C["card"], fg=C["text"]).pack(side="left")
        self.sp_every_var = tk.StringVar(value="2")
        tk.Spinbox(self._sp_every_f, textvariable=self.sp_every_var,
                   from_=1, to=999, width=5, font=F,
                   relief="solid", bd=1).pack(side="left", padx=(4,0))
        self._sp_every_f.grid_remove()

        c3 = SectionCard(f, "저장 폴더"); c3.pack(fill="x", pady=(0, 10))
        b3 = c3.body; b3.columnconfigure(0, weight=1)
        self.sp_dir_var = tk.StringVar()
        centry(b3, self.sp_dir_var).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(b3, "폴더 선택",
             lambda: self.sp_dir_var.set(filedialog.askdirectory(title="저장 폴더") or self.sp_dir_var.get()),
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)

        self.sp_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        self._status_row(f, self.sp_sv, "sp_pb")
        self._save_btn(f, "  PDF 나누기", self._sp_start)

    # ── TAB: 압축 ─────────────────────────────────────────────
    def _build_cp_tab(self, parent):
        f = self._tab_frame(parent)

        c1 = SectionCard(f, "PDF 파일"); c1.pack(fill="x", pady=(0, 10))
        b1 = c1.body; b1.columnconfigure(0, weight=1)
        self.cp_file_var = tk.StringVar()
        centry(b1, self.cp_file_var).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(b1, "찾아보기", self._cp_browse, C["primary"], C["pri_h"],
             padx=10, pady=6).grid(row=0, column=1)
        self.cp_info_lbl = tk.Label(b1, text="", font=F_SM, bg=C["card"], fg=C["sub"])
        self.cp_info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4,0))

        c2 = SectionCard(f, "압축 옵션"); c2.pack(fill="x", pady=(0, 10))
        ob = c2.body
        self.cp_streams = tk.BooleanVar(value=True)
        self.cp_dedup   = tk.BooleanVar(value=True)
        self.cp_meta    = tk.BooleanVar(value=False)
        for row, (var, txt) in enumerate([
                (self.cp_streams, "콘텐츠 스트림 압축  (Deflate / zlib)"),
                (self.cp_dedup,   "중복 객체 제거  (identical objects)"),
                (self.cp_meta,    "메타데이터 제거")]):
            tk.Checkbutton(ob, text=txt, variable=var, font=F,
                           bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).grid(row=row, column=0, sticky="w", pady=2)
        lf = tk.Frame(ob, bg=C["card"]); lf.grid(row=3, column=0, sticky="w", pady=(8,0))
        tk.Label(lf, text="압축 레벨:", font=F, bg=C["card"], fg=C["text"]).pack(side="left")
        self.cp_level = tk.IntVar(value=9)
        for lvl, lbl in [(1, "빠름 (1)"), (6, "균형 (6)"), (9, "최대 (9)")]:
            tk.Radiobutton(lf, text=lbl, variable=self.cp_level, value=lvl,
                           font=F_SM, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).pack(side="left", padx=(8,0))

        c3 = SectionCard(f, "저장 위치"); c3.pack(fill="x", pady=(0, 10))
        b3 = c3.body; b3.columnconfigure(0, weight=1)
        self.cp_out_var = tk.StringVar()
        centry(b3, self.cp_out_var).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(b3, "찾아보기",
             lambda: self._save_dialog(self.cp_out_var, self.cp_file_var, "_compressed"),
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)

        self.cp_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        self._status_row(f, self.cp_sv, "cp_pb")
        self._save_btn(f, "  압축하여 저장", self._cp_start)

    # ── shared utils ──────────────────────────────────────────
    def _save_dialog(self, out_var: tk.StringVar,
                     src_var: tk.StringVar | None = None,
                     suffix: str = "") -> None:
        src = src_var.get() if src_var else ""
        init = os.path.dirname(src) if src and os.path.isfile(src) else os.path.expanduser("~")
        if suffix and src:
            base, ext = os.path.splitext(src)
            init_file = os.path.basename(base) + suffix + ext
        else:
            init_file = ""
        p = filedialog.asksaveasfilename(
            title="저장 위치 선택", initialdir=init,
            initialfile=init_file,
            defaultextension=".pdf", filetypes=[("PDF 파일", "*.pdf")])
        if p: out_var.set(p)

    def _thread(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _ok(self, pb, sv, msg_title, msg_body):
        pb.stop(); sv.set(msg_body.split("\n")[0])
        messagebox.showinfo(msg_title, msg_body)

    def _err(self, pb, sv, e):
        pb.stop(); sv.set("오류가 발생했습니다.")
        messagebox.showerror("오류", str(e))

    def _open_pdf(self) -> str:
        return filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])

    @staticmethod
    def _reader(path: str) -> PdfReader:
        r = PdfReader(path)
        if r.is_encrypted: r.decrypt("")
        return r

    # ── 암호화 handlers ───────────────────────────────────────
    def _tgl_pw1(self):
        self._show_pw = not self._show_pw
        self._pw_e.config(show="" if self._show_pw else "*")
        self._eye1.config(text="Hide" if self._show_pw else "Show")

    def _tgl_pw2(self):
        self._show_pw2 = not self._show_pw2
        self._pw2_e.config(show="" if self._show_pw2 else "*")
        self._eye2.config(text="Hide" if self._show_pw2 else "Show")

    def _pw_strength(self):
        pw = self.pw_var.get()
        score = sum([len(pw)>=8, len(pw)>=12,
                     any(c.isdigit() for c in pw),
                     any(c in "!@#$%^&*()" for c in pw)])
        cols  = ["#EF4444","#F97316","#EAB308","#22C55E"]
        labls = ["취약","보통","강함","매우 강함"]
        for i, b in enumerate(self._sbars):
            b.config(bg=cols[score-1] if pw and i < score else C["border"])
        self._slbl.config(text=labls[score-1] if pw else "",
                          fg=cols[score-1] if pw else C["sub"])

    def _pw_match(self):
        p1, p2 = self.pw_var.get(), self.pw2_var.get()
        if not p2:   self._mlbl.config(text="")
        elif p1==p2: self._mlbl.config(text="✓ 비밀번호 일치",    fg=C["success"])
        else:        self._mlbl.config(text="✗ 비밀번호 불일치",  fg=C["danger"])

    def _enc_browse(self):
        p = self._open_pdf()
        if p:
            self.enc_file_var.set(p)
            base, ext = os.path.splitext(p)
            self.enc_out_var.set(base + "_encrypted" + ext)

    def _enc_start(self):
        src = self.enc_file_var.get().strip()
        pw1, pw2 = self.pw_var.get(), self.pw2_var.get()
        out = self.enc_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not pw1: messagebox.showerror("오류", "비밀번호를 입력하세요."); return
        if pw1 != pw2: messagebox.showerror("오류", "비밀번호가 일치하지 않습니다."); return
        if not out: messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        self._thread(self._enc_run, src, pw1, out, self.algo_var.get())

    def _enc_run(self, src, pw, out, algo):
        self.after(0, self.enc_pb.start, 10)
        self.after(0, self.enc_sv.set, "암호화 진행 중...")
        try:
            r = self._reader(src); w = PdfWriter()
            for pg in r.pages: w.add_page(pg)
            if r.metadata: w.add_metadata(dict(r.metadata))
            w.encrypt(user_password=pw, owner_password=pw, algorithm=algo)
            with open(out, "wb") as fh: w.write(fh)
            self.after(0, self._ok, self.enc_pb, self.enc_sv,
                       "완료", f"암호화 완료!\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self._err, self.enc_pb, self.enc_sv, e)

    # ── 페이지 편집 handlers ──────────────────────────────────
    def _pg_browse(self):
        p = self._open_pdf()
        if not p: return
        self.pg_file_var.set(p)
        self.pg_sv.set("썸네일 렌더링 중...")
        self._pg_loading.config(text="렌더링 중...")
        self._pg_loading.lift()
        base, ext = os.path.splitext(p)
        self.pg_out_var.set(base + "_edited" + ext)
        self.thumb.load(p, on_ready=self._pg_ready)

    def _pg_ready(self, n: int):
        self._pg_loading.lower()
        self.pg_info_lbl.config(text=f"총 {n}페이지")
        self.pg_sv.set(f"총 {n}페이지 로드됨. 클릭하여 선택하세요.")

    def _pg_grid_changed(self, total: int, sel: int):
        if sel:
            self.pg_status_lbl.config(text=f"{sel}페이지 선택\n(전체 {total})")
        else:
            self.pg_status_lbl.config(text=f"전체 {total}페이지")

    def _pg_delete(self):
        n = self.thumb.delete_selected()
        if not n: messagebox.showwarning("알림", "삭제할 페이지를 선택하세요."); return
        self.pg_sv.set(f"{n}페이지 삭제됨. 현재 {self.thumb.page_count()}페이지.")

    def _pg_add(self):
        p = self._open_pdf()
        if not p: return
        self.pg_sv.set("페이지 추가 중...")
        self._pg_loading.config(text="렌더링 중..."); self._pg_loading.lift()
        self.thumb.append(p, on_ready=self._pg_append_ready)

    def _pg_append_ready(self, n: int):
        self._pg_loading.lower()
        self.pg_info_lbl.config(text=f"총 {n}페이지")
        self.pg_sv.set(f"총 {n}페이지. 클릭하여 선택하세요.")

    def _pg_extract(self):
        if self.thumb.selected_count() == 0:
            messagebox.showwarning("알림", "추출할 페이지를 선택하세요."); return
        out = filedialog.asksaveasfilename(
            title="추출 저장 위치", defaultextension=".pdf",
            filetypes=[("PDF 파일", "*.pdf")])
        if not out: return
        sources = self.thumb.get_selected_sources()
        self._thread(self._pg_write, sources, out, self.pg_pb, self.pg_sv, "추출")

    def _pg_save(self):
        if self.thumb.page_count() == 0:
            messagebox.showerror("오류", "PDF 파일을 먼저 로드하세요."); return
        out = self.pg_out_var.get().strip()
        if not out: messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        sources = self.thumb.get_page_sources()
        self._thread(self._pg_write, sources, out, self.pg_pb, self.pg_sv, "저장")

    def _pg_write(self, sources: list, out: str, pb, sv, label: str):
        self.after(0, pb.start, 10)
        self.after(0, sv.set, f"{label} 중...")
        try:
            readers: dict[str, PdfReader] = {}
            w = PdfWriter()
            for path, idx in sources:
                if path not in readers:
                    readers[path] = self._reader(path)
                w.add_page(readers[path].pages[idx])
            with open(out, "wb") as fh: w.write(fh)
            self.after(0, self._ok, pb, sv,
                       "완료", f"{len(sources)}페이지 {label} 완료!\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self._err, pb, sv, e)

    # ── 병합 handlers ─────────────────────────────────────────
    def _mg_add(self):
        paths = filedialog.askopenfilenames(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")])
        for p in paths:
            if p not in self._merge_files:
                self._merge_files.append(p)
                self.mg_lb.insert("end", f"  {os.path.basename(p)}")
        self.mg_sv.set(f"{len(self._merge_files)}개 파일 준비됨.")

    def _mg_rm(self):
        for i in reversed(self.mg_lb.curselection()):
            self.mg_lb.delete(i); del self._merge_files[i]
        self.mg_sv.set(f"{len(self._merge_files)}개 파일 준비됨.")

    def _mg_clear(self):
        self.mg_lb.delete(0, "end"); self._merge_files.clear()
        self.mg_sv.set("병합할 PDF 파일을 추가하세요.")

    def _mg_up(self):
        sel = list(self.mg_lb.curselection())
        if not sel or sel[0] == 0: return
        for i in sel:
            t = self.mg_lb.get(i); self.mg_lb.delete(i)
            self.mg_lb.insert(i-1, t)
            self._merge_files[i], self._merge_files[i-1] = \
                self._merge_files[i-1], self._merge_files[i]
        self.mg_lb.selection_clear(0, "end")
        for i in sel: self.mg_lb.selection_set(i-1)

    def _mg_dn(self):
        sel = list(self.mg_lb.curselection())
        if not sel or sel[-1] == self.mg_lb.size()-1: return
        for i in reversed(sel):
            t = self.mg_lb.get(i); self.mg_lb.delete(i)
            self.mg_lb.insert(i+1, t)
            self._merge_files[i], self._merge_files[i+1] = \
                self._merge_files[i+1], self._merge_files[i]
        self.mg_lb.selection_clear(0, "end")
        for i in sel: self.mg_lb.selection_set(i+1)

    def _mg_start(self):
        if len(self._merge_files) < 2:
            messagebox.showerror("오류", "PDF 파일을 2개 이상 추가하세요."); return
        out = self.mg_out_var.get().strip()
        if not out: messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        self._thread(self._mg_run, list(self._merge_files), out)

    def _mg_run(self, files, out):
        self.after(0, self.mg_pb.start, 10)
        self.after(0, self.mg_sv.set, "병합 중...")
        try:
            w = PdfWriter()
            for p in files:
                r = self._reader(p)
                for pg in r.pages: w.add_page(pg)
            with open(out, "wb") as fh: w.write(fh)
            self.after(0, self._ok, self.mg_pb, self.mg_sv,
                       "완료", f"병합 완료! ({len(files)}개 파일)\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self._err, self.mg_pb, self.mg_sv, e)

    # ── 나누기 handlers ───────────────────────────────────────
    def _sp_browse(self):
        p = self._open_pdf()
        if not p: return
        self.sp_file_var.set(p)
        try:
            n = len(self._reader(p).pages)
            self.sp_info_lbl.config(text=f"총 {n}페이지")
            self.sp_dir_var.set(os.path.dirname(p))
            self.sp_sv.set(f"총 {n}페이지. 나누기 방식을 선택하세요.")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _sp_mode_change(self):
        self._sp_range_f.grid_remove(); self._sp_every_f.grid_remove()
        m = self.sp_mode.get()
        if m == "range": self._sp_range_f.grid()
        elif m == "every": self._sp_every_f.grid()

    @staticmethod
    def _parse_ranges(s: str, total: int) -> list[list[int]]:
        groups: list[list[int]] = []
        for part in s.split(","):
            part = part.strip()
            if not part: continue
            m = re.match(r"^(\d+)-(\d+)$", part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if a < 1 or b > total or a > b:
                    raise ValueError(f"잘못된 범위: {part}  (1~{total})")
                groups.append(list(range(a-1, b)))
            elif re.match(r"^\d+$", part):
                p = int(part)
                if not 1 <= p <= total:
                    raise ValueError(f"잘못된 페이지: {p}  (1~{total})")
                groups.append([p-1])
            else:
                raise ValueError(f"파싱 오류: '{part}'")
        return groups

    def _sp_start(self):
        src = self.sp_file_var.get().strip()
        d   = self.sp_dir_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not d or not os.path.isdir(d):
            messagebox.showerror("오류", "유효한 저장 폴더를 선택하세요."); return
        try:
            r = self._reader(src); total = len(r.pages)
            m = self.sp_mode.get()
            if m == "each":
                groups = [[i] for i in range(total)]
            elif m == "range":
                rng = self.sp_range_var.get().strip()
                if not rng: messagebox.showerror("오류", "페이지 범위를 입력하세요."); return
                groups = self._parse_ranges(rng, total)
            else:
                try: n = int(self.sp_every_var.get()); assert n >= 1
                except: messagebox.showerror("오류", "N은 1 이상의 정수여야 합니다."); return
                groups = [list(range(i, min(i+n, total))) for i in range(0, total, n)]
        except Exception as e:
            messagebox.showerror("오류", str(e)); return
        self._thread(self._sp_run, src, groups, d)

    def _sp_run(self, src, groups, d):
        self.after(0, self.sp_pb.start, 10)
        self.after(0, self.sp_sv.set, "나누기 진행 중...")
        try:
            r = self._reader(src)
            base = os.path.splitext(os.path.basename(src))[0]
            pad  = len(str(len(groups)))
            for idx, grp in enumerate(groups):
                w = PdfWriter()
                for pg in grp: w.add_page(r.pages[pg])
                fname = f"{base}_part{str(idx+1).zfill(pad)}.pdf"
                with open(os.path.join(d, fname), "wb") as fh: w.write(fh)
            self.after(0, self._ok, self.sp_pb, self.sp_sv,
                       "완료", f"{len(groups)}개 파일로 분리 완료!\n\n폴더:\n{d}")
        except Exception as e:
            self.after(0, self._err, self.sp_pb, self.sp_sv, e)

    # ── 압축 handlers ─────────────────────────────────────────
    def _cp_browse(self):
        p = self._open_pdf()
        if not p: return
        self.cp_file_var.set(p)
        kb = os.path.getsize(p) / 1024
        try:
            n = len(PdfReader(p).pages)
            self.cp_info_lbl.config(text=f"총 {n}페이지  /  {kb:.1f} KB")
        except Exception:
            self.cp_info_lbl.config(text=f"{kb:.1f} KB")
        base, ext = os.path.splitext(p)
        self.cp_out_var.set(base + "_compressed" + ext)
        self.cp_sv.set("압축 옵션을 선택하고 저장하세요.")

    def _cp_start(self):
        src = self.cp_file_var.get().strip()
        out = self.cp_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not out: messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        self._thread(self._cp_run, src, out,
                     self.cp_streams.get(), self.cp_dedup.get(),
                     self.cp_meta.get(), self.cp_level.get())

    def _cp_run(self, src, out, streams, dedup, rm_meta, level):
        self.after(0, self.cp_pb.start, 10)
        self.after(0, self.cp_sv.set, "압축 중...")
        try:
            r = self._reader(src); w = PdfWriter()
            for pg in r.pages:
                if streams: pg.compress_content_streams(level=level)
                w.add_page(pg)
            if not rm_meta and r.metadata:
                w.add_metadata(dict(r.metadata))
            if dedup:
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            with open(out, "wb") as fh: w.write(fh)
            orig_kb = os.path.getsize(src) / 1024
            out_kb  = os.path.getsize(out) / 1024
            ratio   = (1 - out_kb/orig_kb) * 100 if orig_kb else 0
            msg = (f"압축 완료!\n\n원본:  {orig_kb:.1f} KB\n"
                   f"결과:  {out_kb:.1f} KB\n절감:  {ratio:.1f}%\n\n저장 위치:\n{out}")
            self.after(0, self.cp_pb.stop)
            self.after(0, self.cp_sv.set,
                       f"완료: {orig_kb:.1f} KB → {out_kb:.1f} KB ({ratio:.1f}% 절감)")
            self.after(0, messagebox.showinfo, "완료", msg)
        except Exception as e:
            self.after(0, self._err, self.cp_pb, self.cp_sv, e)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # required for PyInstaller on Windows
    app = PDFIkkcu()
    app.mainloop()
