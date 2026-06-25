"""PDF.ikkcu Tools — Freeware PDF Tool v2.0"""
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
# ▼ Ko-fi 링크
BMC_URL = "https://ko-fi.com/ikkcu"
APP_URL  = "https://ikkcu.com"

C = {
    # Content surfaces
    "bg":        "#EBEBEB",   # main content background (light gray, Acrobat-style)
    "doc_bg":    "#525252",   # viewer canvas dark background
    "card":      "#FFFFFF",
    "card_hdr":  "#F5F6F7",
    # Action colors
    "primary":   "#0D66D0",  "pri_h":  "#0950AA",  "pri_t":  "#E8F0FE",
    "success":   "#107154",  "suc_h":  "#085E46",
    "danger":    "#CE2112",  "dan_h":  "#A81B0E",
    # Neutrals
    "border":    "#D1D5DB",
    "text":      "#1D1D1D",
    "sub":       "#6B7280",
    "muted":     "#9CA3AF",
    "sel":       "#D4E3FB",
    "badge_bg":  "#E8F0FE",  "badge_fg": "#0950AA",
    # App chrome (dark header / tab strip — Acrobat-inspired)
    "chrome":    "#1E1E1E",
    "chrome_sub":"#AAAAAA",
    "chrome_bdr":"#3A3A3A",
    "tab_bg":    "#2C2C2C",
    "tab_act_bg":"#3C3C3C",
    "tab_ind":   "#CE2112",   # Adobe red indicator on active tab
}

def _ui_family() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("Apple SD Gothic Neo",)
    if os.name == "nt":
        return ("Malgun Gothic", "Segoe UI")  # Malgun Gothic: 한영 모두 커버 → 탭 폰트 일관성
    return ("Noto Sans CJK KR", "Noto Sans")

MG = _ui_family()

def _font_sizes() -> tuple[int, int, int, int]:
    return (13, 12, 18, 14) if sys.platform == "darwin" else (10, 9, 15, 11)

FS, FS_SM, FS_TTL, FS_BTN = _font_sizes()
F      = (MG[0], FS)
F_B    = (MG[0], FS, "bold")
F_SM   = (MG[0], FS_SM)
F_TTL  = (MG[0], FS_TTL, "bold")

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

def button_text_color(fg: str) -> str:
    if sys.platform == "darwin" and fg == "white":
        return C["text"]
    return fg

# ── helpers ──────────────────────────────────────────────────
def hbtn(parent, text, cmd, bg, bgh, fg="white", **kw) -> tk.Button:
    fg = button_text_color(fg)
    kw.setdefault("padx", 12); kw.setdefault("pady", 6)
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
        # Acrobat-style: thin accent line at top, clean header
        tk.Frame(self, bg=C["primary"], height=2).pack(fill="x")
        hdr = tk.Frame(self, bg=C["card_hdr"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=F_B, bg=C["card_hdr"],
                 fg=C["text"], padx=12, pady=7).pack(side="left")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")
        self._body = tk.Frame(self, bg=C["card"])
        self._body.pack(fill="x", padx=12, pady=(8, 12))

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
        self._photos:   list[ImageTk.PhotoImage] = []
        self._pil_imgs: list                     = []
        self._rots:     list[int]                = []
        self._order:    list[int]                = []
        self._sel:      set[int]                 = set()
        self._cells:    dict[int, tuple]         = {}
        self._sources:  list[tuple[str, int]]    = []
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
        self._pil_imgs = list(imgs)
        self._photos   = [ImageTk.PhotoImage(i) for i in imgs]
        self._order    = list(range(len(self._photos)))
        self._rots     = [0] * len(imgs)
        self._sources  = list(srcs)
        self._rebuild()
        if on_ready: on_ready(len(self._photos))

    def _append_grid(self, imgs, srcs, on_ready):
        offset = len(self._photos)
        self._pil_imgs.extend(imgs)
        self._photos.extend(ImageTk.PhotoImage(i) for i in imgs)
        self._rots.extend([0] * len(imgs))
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
    """Acrobat-style dark tab strip with red active indicator."""

    _IND_H = 3

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["tab_bg"], **kw)
        self._tabs:   list[tuple] = []
        self._active: int         = -1

        self._strip = tk.Frame(self, bg=C["tab_bg"])
        self._strip.pack(fill="x")
        tk.Frame(self, bg=C["chrome_bdr"], height=1).pack(fill="x")
        self._deck = tk.Frame(self, bg=C["bg"])
        self._deck.pack(fill="both", expand=True)

    def add(self, text: str) -> tk.Frame:
        idx   = len(self._tabs)
        frame = tk.Frame(self._deck, bg=C["bg"])

        wrap = tk.Frame(self._strip, bg=C["tab_bg"])
        wrap.pack(side="left")
        # indicator at TOP (Acrobat style) — red bar on active tab
        ind = tk.Frame(wrap, bg=C["tab_bg"], height=self._IND_H)
        ind.pack(fill="x", side="top")
        lbl = tk.Label(wrap, text=text, font=F,
                       bg=C["tab_bg"], fg=C["chrome_sub"],
                       padx=16, pady=9, cursor="hand2")
        lbl.pack(side="top")

        self._tabs.append((lbl, ind, frame))
        lbl.bind("<Button-1>", lambda _, i=idx: self.select(i))
        lbl.bind("<Enter>",
                 lambda _, l=lbl, w=wrap, i=idx: (
                     l.config(fg="white"),
                     w.config(bg=C["tab_act_bg"]),
                     l.config(bg=C["tab_act_bg"]),
                 ) if i != self._active else None)
        lbl.bind("<Leave>",
                 lambda _, l=lbl, w=wrap, i=idx: (
                     l.config(fg=C["chrome_sub"]),
                     w.config(bg=C["tab_bg"]),
                     l.config(bg=C["tab_bg"]),
                 ) if i != self._active else None)

        if idx == 0:
            self.select(0)
        return frame

    def select(self, idx: int):
        for i, (lbl, ind, frame) in enumerate(self._tabs):
            wrap = lbl.master
            if i == idx:
                lbl.config(fg="white", font=F_B, bg=C["tab_act_bg"])
                wrap.config(bg=C["tab_act_bg"])
                ind.config(bg=C["tab_ind"])
                frame.pack(fill="both", expand=True)
            else:
                lbl.config(fg=C["chrome_sub"], font=F, bg=C["tab_bg"])
                wrap.config(bg=C["tab_bg"])
                ind.config(bg=C["tab_bg"])
                frame.pack_forget()
        self._active = idx


# ── Main App ─────────────────────────────────────────────────
class PDFIkkcu(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_display_scaling(self)
        self.title("PDF.ikkcu Tools")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(860, 600)
        self._merge_files: list[str] = []
        self._show_pw = self._show_pw2 = False
        self._closing = False
        self._settings = self._load_settings()
        self._set_icon()
        self._build_icons()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 1080)
        h = max(self.winfo_reqheight(), 700)
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        try:
            for pb in ("enc_pb", "pg_pb", "mg_pb", "sp_pb", "cp_pb"):
                widget = getattr(self, pb, None)
                if widget:
                    widget.stop()
            self.quit()
            self.destroy()
        except tk.TclError:
            pass

    # ── icon ──────────────────────────────────────────────────
    def _set_icon(self):
        try:
            from PIL import ImageDraw
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base, "icon_pdf-ikkcu.png")
            img = Image.open(path).convert("RGBA").resize((256, 256), Image.LANCZOS)
            mask = Image.new("L", img.size, 0)
            d = ImageDraw.Draw(mask)
            r = round(img.width * 0.20)
            d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=r, fill=255)
            img.putalpha(mask)
            self._icon_img = ImageTk.PhotoImage(img)
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def _icon_label(self, parent, size, bg):
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            img = Image.open(os.path.join(base, "icon_pdf-ikkcu.png")).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(parent, image=photo, bg=bg, bd=0)
            lbl._icon_ref = photo
            return lbl
        except Exception:
            f = tk.Frame(parent, bg=C["danger"], width=size, height=size)
            f.pack_propagate(False)
            tk.Label(f, text="PDF", font=(MG[0], max(6, size // 4), "bold"),
                     bg=C["danger"], fg="white").place(relx=0.5, rely=0.5, anchor="center")
            return f

    # ── Toolbar icons (PIL-generated) ─────────────────────────
    def _build_icons(self):
        try:
            from PIL import ImageDraw
            import math as _m
        except ImportError:
            self._icons = {}; return

        R, SZ = 40, 20
        BLK = "#2D2D2D"
        PRI = "#0D66D0"
        W   = 4

        def _icon(fn):
            img = Image.new("RGBA", (R, R), (0, 0, 0, 0))
            fn(ImageDraw.Draw(img))
            return ImageTk.PhotoImage(img.resize((SZ, SZ), Image.LANCZOS))

        def _open(d):
            d.polygon([(3,15),(3,36),(37,36),(37,15)], fill="#E8A020")
            d.polygon([(3,11),(3,15),(17,15),(20,11)], fill="#CC8010")
            d.rounded_rectangle([3,17,37,36], radius=3, fill="#FFD07A")

        def _toc(d):
            for y in [9, 19, 29]:
                d.ellipse([4,y-3,10,y+3], fill=BLK)
                d.rounded_rectangle([14,y-2,36,y+2], radius=2, fill=BLK)

        def _thumb(d):
            for rx, ry in [(3,3),(22,3),(3,22),(22,22)]:
                d.rounded_rectangle([rx,ry,rx+15,ry+15], radius=2, fill="#9CA3AF")

        def _play(d):
            d.polygon([(8,4),(8,36),(36,20)], fill=PRI)

        def _prev(d):
            d.line([28,5,11,20], fill=BLK, width=5)
            d.line([11,20,28,35], fill=BLK, width=5)

        def _next(d):
            d.line([12,5,29,20], fill=BLK, width=5)
            d.line([29,20,12,35], fill=BLK, width=5)

        def _mag(d, plus=False):
            d.ellipse([3,3,27,27], outline=BLK, width=W)
            d.line([9,15,21,15], fill=BLK, width=3)
            if plus: d.line([15,9,15,21], fill=BLK, width=3)
            d.line([24,24,37,37], fill=BLK, width=W)

        def _rotl(d):
            d.arc([6,4,34,30], start=180, end=0, fill=BLK, width=4)
            d.line([6,17,6,36], fill=BLK, width=4)
            d.polygon([(6,36),(1,26),(13,26)], fill=BLK)

        def _rotr(d):
            d.arc([6,4,34,30], start=180, end=0, fill=BLK, width=4)
            d.line([34,17,34,36], fill=BLK, width=4)
            d.polygon([(34,36),(27,26),(39,26)], fill=BLK)

        def _copy(d):
            d.rounded_rectangle([10,8,36,36], radius=3, fill="white",  outline=BLK, width=2)
            d.rounded_rectangle([ 4,4,30,30], radius=3, fill="#EEF2FF", outline=BLK, width=2)
            d.rectangle([9,12,25,14], fill=BLK)
            d.rectangle([9,18,25,20], fill=BLK)
            d.rectangle([9,24,19,26], fill=BLK)

        def _tools(d):
            d.rounded_rectangle([15,17,38,23], radius=3, fill=BLK)
            d.ellipse([2,8,22,28], fill=BLK)
            d.ellipse([6,12,18,24], fill="white")

        def _search(d):
            d.ellipse([3,3,26,26], outline=BLK, width=W)
            d.line([23,23,37,37], fill=BLK, width=W)

        def _settings(d):
            cx, cy = 20, 20
            teeth = 8
            pts = []
            for i in range(teeth * 2):
                ang = _m.pi * 2 / (teeth * 2) * i
                r = 17 if i % 2 == 0 else 13
                pts.append((cx + r*_m.cos(ang), cy + r*_m.sin(ang)))
            d.polygon(pts, fill=BLK)
            d.ellipse([12,12,28,28], fill="white")
            d.ellipse([16,16,24,24], fill=BLK)

        self._icons = {
            "open":     _icon(_open),
            "toc":      _icon(_toc),
            "thumb":    _icon(_thumb),
            "play":     _icon(_play),
            "prev":     _icon(_prev),
            "next":     _icon(_next),
            "zoom_out": _icon(lambda d: _mag(d, plus=False)),
            "zoom_in":  _icon(lambda d: _mag(d, plus=True)),
            "rot_l":    _icon(_rotl),
            "rot_r":    _icon(_rotr),
            "copy_t":   _icon(_copy),
            "tools":    _icon(_tools),
            "search":   _icon(_search),
            "settings": _icon(_settings),
        }

    # ── Settings ──────────────────────────────────────────────
    _SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".pdf_ikkcu_settings.json")

    def _load_settings(self) -> dict:
        try:
            import json
            with open(self._SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        try:
            import json
            with open(self._SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 실패:\n{e}")

    def _show_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("환경설정"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 480, 360)

        f = tk.Frame(dlg, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        # ── 기본 설정 ──────────────────────────────────────────
        vc = SectionCard(f, "기본 설정"); vc.pack(fill="x", pady=(0, 8))
        vc.body.columnconfigure(1, weight=1)
        tk.Label(vc.body, text="기본 보기 모드", font=F_SM,
                 bg=C["card"], fg=C["sub"]).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        vm_var = tk.StringVar(value=self._settings.get("default_view_mode", "한 페이지"))
        vm_cb = ttk.Combobox(vc.body, textvariable=vm_var, width=12, state="readonly",
                              values=["한 페이지", "양면 보기", "전체 폭"])
        vm_cb.grid(row=0, column=1, sticky="w", pady=4)

        # ── 시스템 연동 ────────────────────────────────────────
        sc2 = SectionCard(f, "시스템 연동"); sc2.pack(fill="x", pady=(0, 8))

        def _make_shortcut():
            try:
                app_path = os.path.abspath(__file__)
                app_dir  = os.path.dirname(app_path)
                desk     = os.path.join(os.path.expanduser("~"), "Desktop")
                if sys.platform == "win32":
                    bat = os.path.join(desk, "PDF.ikkcu Tools.bat")
                    with open(bat, "w", encoding="utf-8") as fh:
                        fh.write(f'@echo off\ncd /d "{app_dir}"\npython "{app_path}"\n')
                    messagebox.showinfo("완료",
                        f"바탕화면에 바로가기가 생성되었습니다.\n\n{bat}", parent=dlg)
                else:
                    cmd = os.path.join(desk, "PDF.ikkcu Tools.command")
                    with open(cmd, "w", encoding="utf-8") as fh:
                        fh.write(f'#!/bin/bash\ncd "{app_dir}"\npython3 "{app_path}"\n')
                    os.chmod(cmd, 0o755)
                    messagebox.showinfo("완료",
                        f"바탕화면에 바로가기가 생성되었습니다.\n\n{cmd}", parent=dlg)
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=dlg)

        def _set_default():
            if sys.platform == "darwin":
                msg = (
                    "macOS에서 기본 PDF 뷰어로 설정하는 방법:\n\n"
                    "1. Finder에서 PDF 파일을 찾습니다.\n"
                    "2. 파일을 우클릭 → '다른 앱으로 열기' → '기타…'\n"
                    "3. PDF.ikkcu 실행 파일 선택 후 '항상 열기' 체크.\n\n"
                    "또는 앱을 .app 번들로 패키징 후 '기본 앱으로 설정' 기능을 사용하세요."
                )
            elif sys.platform == "win32":
                msg = (
                    "Windows에서 기본 PDF 뷰어로 설정하는 방법:\n\n"
                    "1. PDF 파일을 우클릭 → '연결 프로그램' → '다른 앱 선택'\n"
                    "2. python.exe를 선택하고 '항상 이 앱 사용' 체크.\n\n"
                    "또는 설정 앱 → 앱 → 기본 앱 → '.pdf' 항목을 변경하세요."
                )
            else:
                msg = "xdg-mime default pdf_ikkcu.desktop application/pdf\n명령으로 설정할 수 있습니다."
            messagebox.showinfo("기본 뷰어 설정 방법", msg, parent=dlg)

        hbtn(sc2.body, "  바탕화면에 바로가기 만들기  ", _make_shortcut,
             C["primary"], C["pri_h"], pady=8).pack(fill="x", pady=(0, 6))
        hbtn(sc2.body, "  PDF 기본 뷰어로 설정  ", _set_default,
             C["sub"], "#475569", pady=8).pack(fill="x")

        # ── 정보 ───────────────────────────────────────────────
        ic3 = SectionCard(f, "설정 파일 위치"); ic3.pack(fill="x", pady=(0, 8))
        tk.Label(ic3.body, text=self._SETTINGS_PATH, font=F_SM,
                 bg=C["card"], fg=C["muted"]).pack(anchor="w")

        # ── 버튼 행 ────────────────────────────────────────────
        br = tk.Frame(f, bg=C["bg"]); br.pack(fill="x", pady=(4, 0))
        br.columnconfigure(0, weight=1)

        def _save():
            self._settings["default_view_mode"] = vm_var.get()
            self._save_settings()
            messagebox.showinfo("완료", "설정이 저장되었습니다.\n다음 파일 열기 시 적용됩니다.", parent=dlg)
            dlg.destroy()

        hbtn(br, "  저장  ", _save,    C["primary"], C["pri_h"], pady=9).grid(row=0, column=1, padx=(8,0))
        hbtn(br, "  취소  ", dlg.destroy, C["sub"], "#475569", pady=9).grid(row=0, column=2, padx=(8,0))

    # ── shell ─────────────────────────────────────────────────
    def _build_ui(self):
        CH = C["chrome"]; CH_S = C["chrome_sub"]

        # ── Dark app header (Acrobat-style) ───────────────────
        hdr = tk.Frame(self, bg=CH, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        lf = tk.Frame(hdr, bg=CH)
        lf.pack(side="left", padx=14, fill="y")

        # PDF icon badge
        self._icon_label(lf, 30, CH).pack(side="left", padx=(0, 10))

        tk.Label(lf, text="PDF.ikkcu Tools", font=F_B,
                 bg=CH, fg="white").pack(side="left")
        tk.Label(lf, text="v2.0", font=F_SM,
                 bg=CH, fg=CH_S).pack(side="left", padx=(6, 0))

        # Right controls
        rf = tk.Frame(hdr, bg=CH)
        rf.pack(side="right", padx=14, fill="y")

        lnk = tk.Label(rf, text="ikkcu.com", font=F_SM,
                       bg=CH, fg=CH_S, cursor="hand2")
        lnk.pack(side="right", padx=(8, 0))
        lnk.bind("<Enter>", lambda _: lnk.config(fg="white"))
        lnk.bind("<Leave>", lambda _: lnk.config(fg=CH_S))
        lnk.bind("<Button-1>", lambda _: webbrowser.open(APP_URL))

        self._is_fs = False
        def _toggle_fs(e=None):
            self._is_fs = not self._is_fs
            self.attributes("-fullscreen", self._is_fs)
        self.bind("<F11>", _toggle_fs)
        self.bind("<Escape>", lambda e: (
            setattr(self, "_is_fs", False),
            self.attributes("-fullscreen", False),
        ))

        # ── Minimal dark footer ────────────────────────────────
        foot = tk.Frame(self, bg=CH, height=22)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        tk.Label(foot, text="© 2025 ikkcu.com — All rights reserved",
                 font=(MG[0], FS_SM - 1 if sys.platform != "darwin" else FS_SM - 2),
                 bg=CH, fg=CH_S).pack(side="right", padx=14)

        # ── Native menu bar ────────────────────────────────────
        self._build_menubar()

        # ── Main content: viewer (full window) ────────────────
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)
        self._build_vw_tab(main)

    # ── Menu bar ──────────────────────────────────────────────
    def _build_menubar(self):
        IS_MAC = sys.platform == "darwin"
        bar = tk.Menu(self, tearoff=False)
        self.config(menu=bar)

        # ── 파일 ──────────────────────────────────────────────
        mf = tk.Menu(bar, tearoff=False)
        bar.add_cascade(label="파일", menu=mf)
        mf.add_command(label="📂  열기...",
                       command=self._vw_open,
                       accelerator="⌘O" if IS_MAC else "Ctrl+O")
        mf.add_separator()
        mf.add_command(label="✕  파일 닫기",
                       command=self._vw_close_file)
        mf.add_separator()
        mf.add_command(label="⚙  환경설정...",
                       command=self._show_settings,
                       accelerator="⌘," if IS_MAC else "Ctrl+,")
        mf.add_separator()
        mf.add_command(label="종료",
                       command=self._on_close,
                       accelerator="⌘Q" if IS_MAC else "Alt+F4")
        self.bind_all("<Command-o>" if IS_MAC else "<Control-o>",
                      lambda _: self._vw_open())

        # ── 도구 ──────────────────────────────────────────────
        mt = tk.Menu(bar, tearoff=False)
        bar.add_cascade(label="도구", menu=mt)
        mt.add_command(label="🔒  암호화...",      command=self._vw_dlg_encrypt)
        mt.add_command(label="📋  페이지 편집...", command=self._vw_dlg_page_edit)
        mt.add_separator()
        mt.add_command(label="⊕  병합...",        command=self._vw_dlg_merge)
        mt.add_command(label="✂  나누기...",       command=self._vw_dlg_split)
        mt.add_separator()
        mt.add_command(label="🗜  압축...",        command=self._vw_dlg_compress)
        mt.add_separator()
        mt.add_command(label="🖊  도장/서명...",   command=self._vw_dlg_stamp)
        mt.add_separator()
        mt.add_command(label="📝  속성 편집...",  command=self._vw_dlg_props)

        # ── 보기 ──────────────────────────────────────────────
        mv = tk.Menu(bar, tearoff=False)
        bar.add_cascade(label="보기", menu=mv)
        mv.add_command(label="▶  슬라이드쇼",
                       command=self._vw_slideshow_open,
                       accelerator="F5")
        mv.add_separator()
        mv.add_command(label="🔎  확대",
                       command=self._vw_zoom_in,
                       accelerator="⌘+" if IS_MAC else "Ctrl++")
        mv.add_command(label="🔍  축소",
                       command=self._vw_zoom_out,
                       accelerator="⌘−" if IS_MAC else "Ctrl+-")
        mv.add_separator()
        mv.add_command(label="□  한 페이지",      command=self._vw_fit_page)
        mv.add_command(label="↔  전체 폭",        command=self._vw_fit_width)
        mv.add_separator()
        mv.add_command(label="목차 패널 토글",       command=self._vw_toc_toggle)
        mv.add_command(label="페이지 미리보기 토글", command=self._vw_thumb_toggle)
        mv.add_command(label="도구 패널 토글",       command=self._vw_toggle_tools)
        self.bind("<F5>", lambda _: self._vw_slideshow_open())

        # ── 도움말 ────────────────────────────────────────────
        mh = tk.Menu(bar, tearoff=False)
        bar.add_cascade(label="도움말", menu=mh)
        mh.add_command(label="ℹ  앱 정보...",    command=self._show_about)
        mh.add_command(label="☕  Ko-fi 후원...", command=lambda: webbrowser.open(BMC_URL))

    # ── Viewer: Thumbnail panel ───────────────────────────────
    _TH_TW  = 112   # thumbnail render width (px)
    _TH_PAD = 11    # left/right padding inside panel
    _TH_LBL = 19    # height reserved for page-number label
    _TH_GAP = 6     # vertical gap between items

    def _vw_thumb_toggle(self):
        if self._vw_thumb_shown:
            self._vw_thumb_panel.pack_forget()
            self._vw_thumb_shown = False
        else:
            # Hide TOC panel if open (mutual exclusion)
            if self._vw_toc_shown:
                self._vw_toc_panel.pack_forget()
                self._vw_toc_shown = False
            self._vw_thumb_panel.pack(side="left", fill="y",
                                       before=self._vw_cv_outer)
            self._vw_thumb_shown = True
            if self._vw_doc and not self._vw_th_items:
                self._vw_thumb_build()

    def _vw_thumb_build(self):
        if not self._vw_doc: return
        self._vw_th_gen[0] += 1
        gen   = self._vw_th_gen[0]
        path  = self._vw_path
        total = self._vw_total
        TW    = self._TH_TW
        PAD   = self._TH_PAD
        LBL   = self._TH_LBL
        GAP   = self._TH_GAP
        cv    = self._vw_th_cv

        # --- Phase 1 (main thread): draw gray placeholders ----
        cv.delete("all")
        self._vw_th_items = []
        self._vw_th_imgs  = [None] * total

        y = GAP
        for i in range(total):
            page = self._vw_doc[i]
            pw, ph = page.rect.width, page.rect.height
            th = min(int(TW * ph / pw) if pw > 0 else int(TW * 1.414), 200)
            y0, y1 = y, y + th
            self._vw_th_items.append((y0, y1))
            # Placeholder
            cv.create_rectangle(PAD, y0, PAD + TW, y1,
                                 fill="#D8D8D8", outline="#BBBBBB", width=1,
                                 tags=(f"plh_{i}",))
            # Page number centered in placeholder
            cv.create_text(PAD + TW // 2, y0 + th // 2,
                           text=str(i + 1), font=F_SM, fill="#999999",
                           tags=(f"num_{i}",))
            # Page number label below
            cv.create_text(PAD + TW // 2, y1 + LBL // 2,
                           text=str(i + 1), font=F_SM, fill=C["sub"],
                           tags=(f"lbl_{i}",))
            # Highlight border (starts invisible)
            cv.create_rectangle(PAD - 2, y0 - 2, PAD + TW + 2, y1 + 2,
                                 outline="", width=2,
                                 tags=(f"hlt_{i}",))
            y += th + LBL + GAP

        cv.config(scrollregion=(0, 0, PAD * 2 + TW, y))
        self._vw_thumb_mark(self._vw_pg)

        # --- Phase 2 (background thread): render actual thumbnails ---
        def _worker():
            try:
                doc2 = fitz.open(path)
                for i in range(total):
                    if self._vw_th_gen[0] != gen:
                        break
                    page2 = doc2[i]
                    pw2   = page2.rect.width
                    sc2   = TW / pw2 if pw2 > 0 else 1.0
                    pix2  = page2.get_pixmap(matrix=fitz.Matrix(sc2, sc2),
                                             alpha=False)
                    photo = ImageTk.PhotoImage(
                        Image.frombytes("RGB",
                                        [pix2.width, pix2.height],
                                        pix2.samples))

                    def _apply(idx=i, p=photo):
                        if self._vw_th_gen[0] != gen:
                            return
                        self._vw_th_imgs[idx] = p       # keep reference
                        y0i, _ = self._vw_th_items[idx]
                        cv.delete(f"plh_{idx}")
                        cv.delete(f"num_{idx}")
                        cv.create_image(PAD, y0i, anchor="nw", image=p,
                                        tags=(f"img_{idx}",))
                        # Re-raise highlight border above new image
                        cv.tag_raise(f"hlt_{idx}")

                    self.after(0, _apply)
                doc2.close()
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _vw_thumb_click(self, event):
        self._vw_th_cv.focus_set()
        if not self._vw_th_items: return
        cy = self._vw_th_cv.canvasy(event.y)
        for i, (y0, y1) in enumerate(self._vw_th_items):
            if y0 <= cy <= y1 + self._TH_LBL:
                self._vw_goto(i)
                break

    def _vw_thumb_mark(self, idx: int):
        if not self._vw_th_items: return
        cv = self._vw_th_cv
        # Clear all highlights
        for i in range(len(self._vw_th_items)):
            cv.itemconfig(f"hlt_{i}", outline="")
        if 0 <= idx < len(self._vw_th_items):
            cv.itemconfig(f"hlt_{idx}", outline=C["primary"])
            # Auto-scroll so the selected thumbnail is visible
            y0, y1 = self._vw_th_items[idx]
            total_h = self._vw_th_items[-1][1] + self._TH_LBL + self._TH_GAP
            if total_h > 0:
                cv.yview_moveto(max(0.0, (y0 - 20) / total_h))

    # ── Viewer: TOC toggle (promoted from inner closure) ──────
    def _vw_toc_toggle(self):
        if self._vw_toc_shown:
            self._vw_toc_panel.pack_forget()
            self._vw_toc_shown = False
        else:
            # Hide thumbnail panel if open (mutual exclusion)
            if self._vw_thumb_shown:
                self._vw_thumb_panel.pack_forget()
                self._vw_thumb_shown = False
            self._vw_toc_panel.pack(side="left", fill="y",
                                    before=self._vw_cv_outer)
            self._vw_toc_shown = True

    # ── Close current viewer file ─────────────────────────────
    def _vw_close_file(self):
        if self._vw_doc:
            self._vw_doc.close()
            self._vw_doc = None
        self._vw_path = ""
        self._vw_total = 0
        self._vw_pg = 0
        self._vw_cv.delete("all")
        self._vw_pg_var.set("0")
        self._vw_total_lbl.config(text="/ 0")
        self._vw_toc.delete(*self._vw_toc.get_children())
        self._vw_search_nav.pack_forget()
        self._vw_th_gen[0] += 1  # cancel any running render
        self._vw_th_imgs = []
        self._vw_th_items = []
        self._vw_th_cv.delete("all")

    # ── About dialog ─────────────────────────────────────────
    def _show_about(self):
        dlg = tk.Toplevel(self)
        dlg.title("앱 정보"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 480, 360)

        inner = tk.Frame(dlg, bg=C["card"],
                         highlightbackground=C["border"], highlightthickness=1)
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        icon_f = tk.Frame(inner, bg=C["chrome"], height=72)
        icon_f.pack(fill="x")
        icon_row = tk.Frame(icon_f, bg=C["chrome"])
        icon_row.place(relx=0.5, rely=0.5, anchor="center")
        self._icon_label(icon_row, 36, C["chrome"]).pack(side="left", padx=(0, 10))
        tk.Label(icon_row, text="PDF.ikkcu Tools", font=(MG[0], 18, "bold"),
                 bg=C["chrome"], fg="white").pack(side="left")

        body = tk.Frame(inner, bg=C["card"])
        body.pack(fill="x", padx=28, pady=18)

        tk.Label(body, text="PDF.ikkcu Tools",
                 font=(MG[0], FS, "bold"), bg=C["card"], fg=C["text"]).pack(anchor="w")
        tk.Label(body,
                 text="PDF 암호화 · 페이지 편집 · 병합 · 나누기 · 압축 · 도장 삽입을\n"
                      "하나의 앱으로 처리하는 무료 PDF 도구입니다.",
                 font=F_SM, bg=C["card"], fg=C["sub"],
                 justify="left", wraplength=400).pack(anchor="w", pady=(6, 0))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=14)

        for label, value, url in [
            ("개발",     "ikkcu.com", APP_URL),
            ("버전",     "2.0.0",     None),
            ("라이선스", "Freeware",  None),
        ]:
            row = tk.Frame(body, bg=C["card"]); row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=F_SM, width=9,
                     bg=C["card"], fg=C["sub"], anchor="w").pack(side="left")
            if url:
                lnk = tk.Label(row, text=value,
                                font=(MG[0], FS_SM, "underline"),
                                bg=C["card"], fg=C["primary"], cursor="hand2")
                lnk.pack(side="left")
                lnk.bind("<Button-1>", lambda _, u=url: webbrowser.open(u))
            else:
                tk.Label(row, text=value, font=F_SM,
                         bg=C["card"], fg=C["text"]).pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=14)

        bmc_btn = tk.Button(
            body, text="  ☕  Ko-fi로 후원하기",
            font=(MG[0], FS, "bold"),
            bg="#FF5E5B", fg="white",
            relief="flat", bd=0, padx=18, pady=10,
            cursor="hand2",
            activebackground="#E04E4B", activeforeground="white",
            command=lambda: webbrowser.open(BMC_URL),
        )
        bmc_btn.pack(fill="x")
        bmc_btn.bind("<Enter>", lambda _: bmc_btn.config(bg="#E04E4B"))
        bmc_btn.bind("<Leave>", lambda _: bmc_btn.config(bg="#FF5E5B"))

        hbtn(inner, "닫기", dlg.destroy, C["sub"], "#475569",
             pady=8).pack(fill="x", padx=28, pady=(0, 16))

    def _tab_frame(self, parent) -> tk.Frame:
        """스크롤 가능한 탭 컨테이너를 반환합니다."""
        outer = tk.Frame(parent, bg=C["bg"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C["bg"], padx=14, pady=12)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(win_id, width=event.width)

        def _on_enter(event):
            canvas.bind_all("<MouseWheel>",  lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            canvas.bind_all("<Button-4>",    lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>",    lambda e: canvas.yview_scroll( 1, "units"))

        def _on_leave(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        return inner

    def _status_row(self, parent, sv: tk.StringVar, pb_attr: str):
        pb = mkpb(parent)
        pb.pack(fill="x", pady=(4, 3))
        setattr(self, pb_attr, pb)
        tk.Label(parent, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x", pady=(0, 6))

    def _save_btn(self, parent, text: str, cmd) -> tk.Button:
        b = hbtn(parent, text, cmd, C["primary"], C["pri_h"])
        b.config(font=(MG[0], FS_BTN, "bold"), pady=10)
        b.pack(fill="x")
        return b

    def _file_row(self, parent, var: tk.StringVar, browse_cmd):
        parent.columnconfigure(0, weight=1)
        centry(parent, var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(parent, "찾아보기", browse_cmd,
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)

    # ── TAB: PDF 뷰어 ────────────────────────────────────────
    def _build_vw_tab(self, parent):
        parent.configure(bg=C["bg"])

        # viewer state
        self._vw_doc        = None
        self._vw_path       = ""
        self._vw_pg         = 0
        self._vw_total      = 0
        self._vw_zoom       = 1.0
        self._vw_zoom_mode  = self._settings.get("default_view_mode", "한 페이지")
        self._vw_rot        = 0
        self._vw_photo      = None
        self._vw_hits: "list[tuple[int, object]]" = []
        self._vw_hit_pos    = -1
        self._vw_render_ver = 0
        self._vw_mat        = fitz.Matrix(1, 1)
        self._vw_mat_ox     = 0.0
        self._vw_mat_oy     = 0.0
        self._vw_resize_id  = None
        self._vw_toc_shown  = False
        self._vw_toc_pages: "dict[str, int]" = {}
        self._vw_thumb_shown = False
        self._vw_th_items: "list[tuple[int,int]]" = []  # (y0, y1) per page
        self._vw_th_imgs:   list = []                    # ImageTk refs
        self._vw_th_gen     = [0]                        # cancellation token

        # ── Acrobat-style toolbar ─────────────────────────────
        TB_BG  = "#F0F0F0"
        TB_BTN = "#E0E0E0"
        TB_BH  = "#C8C8C8"
        tb = tk.Frame(parent, bg=TB_BG, pady=4)
        tb.pack(fill="x")
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x")

        def _sep():
            tk.Frame(tb, bg="#C0C0C0", width=1).pack(
                side="left", fill="y", padx=5, pady=4)

        ic = getattr(self, "_icons", {})

        def _icon_btn(text, cmd, icon=None, **kw):
            kw.setdefault("padx", 5 if icon else 8)
            kw.setdefault("pady", 4)
            b = hbtn(tb, text, cmd, TB_BTN, TB_BH, C["text"], **kw)
            if icon and icon in ic:
                b.config(image=ic[icon], compound="left")
            return b

        _toc_toggle = self._vw_toc_toggle

        # Open + TOC + Thumbnail + Slideshow
        ob = hbtn(tb, " 열기", self._vw_open, C["primary"], C["pri_h"], padx=8, pady=4)
        if "open" in ic: ob.config(image=ic["open"], compound="left")
        ob.pack(side="left", padx=(8, 2))
        _icon_btn(" 목차",     _toc_toggle,               icon="toc").pack(side="left", padx=2)
        _icon_btn(" 미리보기",  self._vw_thumb_toggle,     icon="thumb").pack(side="left", padx=2)
        _icon_btn(" 슬라이드쇼", self._vw_slideshow_open,  icon="play", padx=6).pack(side="left", padx=2)
        _sep()

        # Navigation group
        _icon_btn("", self._vw_prev, icon="prev", padx=7).pack(side="left", padx=(2, 0))
        self._vw_pg_var = tk.StringVar()
        _pg_e = tk.Entry(tb, textvariable=self._vw_pg_var, width=4, font=F,
                         justify="center", relief="solid", bd=1,
                         highlightthickness=1, highlightcolor=C["primary"],
                         highlightbackground="#C0C0C0", bg="white")
        _pg_e.pack(side="left", padx=3, ipady=2)
        _pg_e.bind("<Return>", lambda _: self._vw_goto_entry())
        self._vw_total_lbl = tk.Label(tb, text="/ —", font=F_SM,
                                       bg=TB_BG, fg=C["sub"])
        self._vw_total_lbl.pack(side="left", padx=(0, 2))
        _icon_btn("", self._vw_next, icon="next", padx=7).pack(side="left", padx=(0, 2))
        _sep()

        # Zoom group
        _icon_btn("", self._vw_zoom_out, icon="zoom_out", padx=7).pack(side="left", padx=(2, 0))
        self._vw_zoom_var = tk.StringVar(value=self._vw_zoom_mode)
        _zc = ttk.Combobox(tb, textvariable=self._vw_zoom_var, width=9,
                            values=["50%", "75%", "100%", "125%", "150%",
                                    "175%", "200%", "250%", "300%",
                                    "전체 폭", "한 페이지", "양면 보기"],
                            state="readonly")
        _zc.pack(side="left", padx=3)
        _zc.bind("<<ComboboxSelected>>", lambda _: self._vw_zoom_apply())
        _icon_btn("", self._vw_zoom_in, icon="zoom_in", padx=7).pack(side="left", padx=(0, 2))
        _sep()

        # Rotation group
        _icon_btn("", self._vw_rot_left,  icon="rot_l", padx=7).pack(side="left", padx=(2, 1))
        _icon_btn("", self._vw_rot_right, icon="rot_r", padx=7).pack(side="left", padx=(1, 2))
        _sep()

        # Copy text
        _icon_btn(" 복사", self._vw_copy_text, icon="copy_t", padx=6).pack(side="left", padx=(2, 0))
        _sep()

        # Integrated tools toggle
        self._vw_tools_shown = True
        self._vw_tool_btn = _icon_btn(" 도구 ◁", self._vw_toggle_tools, icon="tools", padx=6)
        self._vw_tool_btn.pack(side="left", padx=(2, 0))

        # ── Search group — right-anchored ─────────────────────
        # Result nav: ↑↓, hidden until search returns results
        self._vw_search_nav = tk.Frame(tb, bg=TB_BG)
        self._vw_search_nav.pack(side="right", padx=(2, 8))
        self._vw_search_nav.pack_forget()          # hidden initially

        self._vw_hit_lbl = tk.Label(self._vw_search_nav, text="",
                                     font=F_SM, bg=TB_BG, fg=C["sub"])
        self._vw_hit_lbl.pack(side="right", padx=(4, 0))

        def _snav_btn(text, cmd):
            b = tk.Button(self._vw_search_nav, text=text, command=cmd,
                          font=F_B, bg=TB_BTN, fg=C["text"],
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=TB_BH, activeforeground=C["text"],
                          padx=7, pady=4)
            b.bind("<Enter>", lambda _: b.config(bg=TB_BH))
            b.bind("<Leave>", lambda _: b.config(bg=TB_BTN))
            return b

        self._vw_btn_search_next = _snav_btn("↓", lambda: self._vw_search_move(+1))
        self._vw_btn_search_next.pack(side="right", padx=1)
        self._vw_btn_search_prev = _snav_btn("↑", lambda: self._vw_search_move(-1))
        self._vw_btn_search_prev.pack(side="right", padx=1)

        sb2 = hbtn(tb, " 검색", self._vw_search, C["primary"], C["pri_h"], padx=7, pady=4)
        if "search" in ic: sb2.config(image=ic["search"], compound="left")
        sb2.pack(side="right", padx=2)
        self._vw_sq_var = tk.StringVar()
        self._vw_sq_e = tk.Entry(tb, textvariable=self._vw_sq_var, width=14, font=F,
                                  relief="solid", bd=1, bg="white",
                                  highlightthickness=1, highlightcolor=C["primary"],
                                  highlightbackground="#C0C0C0")
        self._vw_sq_e.pack(side="right", padx=3, ipady=2)
        self._vw_sq_e.bind("<Return>", lambda _: self._vw_search())

        # ── content area ──────────────────────────────────────
        content = tk.Frame(parent, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # TOC panel (left, collapsible) — Acrobat navigation panel style
        self._vw_toc_panel = tk.Frame(content, bg="#F5F5F5", width=220,
                                       highlightbackground=C["border"],
                                       highlightthickness=1)
        # Not packed — hidden by default (mutual exclusion with thumb panel)
        self._vw_toc_panel.pack_propagate(False)
        toc_hdr = tk.Frame(self._vw_toc_panel, bg="#E0E0E0")
        toc_hdr.pack(fill="x")
        tk.Label(toc_hdr, text="목차", font=F_B,
                 bg="#E0E0E0", fg=C["text"],
                 padx=10, pady=7).pack(side="left")
        tk.Frame(self._vw_toc_panel, bg=C["border"], height=1).pack(fill="x")
        _toc_body = tk.Frame(self._vw_toc_panel, bg="#F5F5F5")
        _toc_body.pack(fill="both", expand=True)
        self._vw_toc = ttk.Treeview(_toc_body, show="tree",
                                     selectmode="browse")
        _toc_vsb = ttk.Scrollbar(_toc_body, orient="vertical",
                                  command=self._vw_toc.yview)
        self._vw_toc.config(yscrollcommand=_toc_vsb.set)
        self._vw_toc.pack(side="left", fill="both", expand=True)
        _toc_vsb.pack(side="right", fill="y")
        self._vw_toc.bind("<<TreeviewSelect>>", self._vw_toc_click)

        # ── Thumbnail preview panel (left, initially hidden) ──────────
        TP_W = 150
        self._vw_thumb_panel = tk.Frame(content, bg="#F5F5F5", width=TP_W,
                                         highlightbackground=C["border"],
                                         highlightthickness=1)
        # Not packed — hidden by default
        self._vw_thumb_panel.pack_propagate(False)

        th_hdr2 = tk.Frame(self._vw_thumb_panel, bg="#E0E0E0")
        th_hdr2.pack(fill="x")
        tk.Label(th_hdr2, text="페이지", font=F_B, bg="#E0E0E0",
                 fg=C["text"], padx=10, pady=7).pack(side="left")
        tk.Frame(self._vw_thumb_panel, bg=C["border"], height=1).pack(fill="x")

        th_body2 = tk.Frame(self._vw_thumb_panel, bg="#F5F5F5")
        th_body2.pack(fill="both", expand=True)
        self._vw_th_cv = tk.Canvas(th_body2, bg="#F5F5F5",
                                    highlightthickness=1,
                                    highlightbackground="#D0D0D0",
                                    highlightcolor=C["primary"],
                                    takefocus=True, width=TP_W - 16)
        th_vsb2 = ttk.Scrollbar(th_body2, orient="vertical",
                                 command=self._vw_th_cv.yview)
        self._vw_th_cv.config(yscrollcommand=th_vsb2.set)
        th_vsb2.pack(side="right", fill="y")
        self._vw_th_cv.pack(side="left", fill="both", expand=True)
        self._vw_th_cv.bind("<MouseWheel>",
            lambda e: self._vw_th_cv.yview_scroll(int(-e.delta / 120), "units"))
        self._vw_th_cv.bind("<Button-4>",
            lambda e: self._vw_th_cv.yview_scroll(-1, "units"))
        self._vw_th_cv.bind("<Button-5>",
            lambda e: self._vw_th_cv.yview_scroll( 1, "units"))
        self._vw_th_cv.bind("<Button-1>", self._vw_thumb_click)
        self._vw_th_cv.bind("<Up>",   lambda e: self._vw_prev())
        self._vw_th_cv.bind("<Down>", lambda e: self._vw_next())

        # ── Right tools panel (Acrobat-style) — packed BEFORE canvas ──
        TPBG = "#F0F0F0"
        self._vw_tools_panel = tk.Frame(content, bg=TPBG, width=160,
                                         highlightbackground=C["border"],
                                         highlightthickness=1)
        self._vw_tools_panel.pack(side="right", fill="y")
        self._vw_tools_panel.pack_propagate(False)

        tp_hdr = tk.Frame(self._vw_tools_panel, bg="#E0E0E0")
        tp_hdr.pack(fill="x")
        tk.Label(tp_hdr, text="도구", font=F_B, bg="#E0E0E0",
                 fg=C["text"], padx=10, pady=6).pack(side="left")
        tk.Frame(self._vw_tools_panel, bg=C["border"], height=1).pack(fill="x")

        tp_body = tk.Frame(self._vw_tools_panel, bg=TPBG)
        tp_body.pack(fill="both", expand=True, padx=8, pady=8)

        def _tp_btn(text, cmd):
            b = tk.Button(tp_body, text=text, command=cmd,
                          font=F_SM, bg="#FFFFFF", fg=C["text"],
                          relief="flat", bd=0, cursor="hand2",
                          activebackground="#D8E8FB", activeforeground=C["primary"],
                          anchor="w", padx=10, pady=7,
                          highlightthickness=1, highlightbackground=C["border"])
            b.bind("<Enter>", lambda _: b.config(bg="#D8E8FB", fg=C["primary"]))
            b.bind("<Leave>", lambda _: b.config(bg="#FFFFFF", fg=C["text"]))
            b.pack(fill="x", pady=2)

        tk.Label(tp_body, text="현재 파일로 작업", font=(MG[0], FS_SM - 1 if sys.platform != "darwin" else FS_SM),
                 bg=TPBG, fg=C["muted"]).pack(anchor="w", pady=(0, 6))

        _tp_btn("🔒  암호화",       self._vw_dlg_encrypt)
        _tp_btn("📋  페이지 편집",   self._vw_dlg_page_edit)
        _tp_btn("⊕  병합",         self._vw_dlg_merge)
        _tp_btn("✂  나누기",       self._vw_dlg_split)
        _tp_btn("↙  압축",         self._vw_dlg_compress)
        _tp_btn("🖊  도장/서명",    self._vw_dlg_stamp)
        tk.Frame(tp_body, bg=C["border"], height=1).pack(fill="x", pady=(6, 2))
        _tp_btn("📝  속성 편집",     self._vw_dlg_props)

        # Canvas area (right of tools panel, fill remaining space)
        self._vw_cv_outer = tk.Frame(content, bg=C["bg"])
        self._vw_cv_outer.pack(side="left", fill="both", expand=True)

        self._vw_cv = tk.Canvas(self._vw_cv_outer, bg=C["doc_bg"],
                                 highlightthickness=0, cursor="crosshair",
                                 takefocus=True)
        _cv_hsb = ttk.Scrollbar(self._vw_cv_outer, orient="horizontal",
                                 command=self._vw_cv.xview)
        _cv_vsb = ttk.Scrollbar(self._vw_cv_outer, orient="vertical",
                                 command=self._vw_cv.yview)
        self._vw_cv.config(xscrollcommand=_cv_hsb.set,
                            yscrollcommand=_cv_vsb.set)
        _cv_vsb.pack(side="right", fill="y")
        _cv_hsb.pack(side="bottom", fill="x")
        self._vw_cv.pack(fill="both", expand=True)

        self._vw_cv.bind("<MouseWheel>",
            lambda e: self._vw_cv.yview_scroll(int(-e.delta / 120), "units"))
        self._vw_cv.bind("<Button-4>",
            lambda e: self._vw_cv.yview_scroll(-1, "units"))
        self._vw_cv.bind("<Button-5>",
            lambda e: self._vw_cv.yview_scroll(1, "units"))
        self._vw_cv.bind("<Control-MouseWheel>", self._vw_ctrl_wheel)
        self._vw_cv.bind("<Button-1>", lambda e: self._vw_cv.focus_set())
        self._vw_cv.bind("<Left>",  lambda e: self._vw_prev())
        self._vw_cv.bind("<Right>", lambda e: self._vw_next())
        self._vw_cv.bind("<Configure>", self._vw_on_resize)

        self._vw_welcome_id = self._vw_cv.create_text(
            400, 300,
            text="열기 버튼으로 PDF를 여세요.",
            font=F_B, fill="#AAAAAA", justify="center")

        # Acrobat-style status bar at bottom
        sb_frame = tk.Frame(parent, bg="#3A3A3A", height=24)
        sb_frame.pack(fill="x", side="bottom")
        sb_frame.pack_propagate(False)
        self._vw_status = tk.StringVar(value="")
        tk.Label(sb_frame, textvariable=self._vw_status,
                 font=(MG[0], FS_SM - 1 if sys.platform != "darwin" else FS_SM - 2),
                 bg="#3A3A3A", fg="#CCCCCC",
                 anchor="w", padx=10
                 ).pack(fill="both", expand=True)

    def _vw_open(self):
        p = self._open_pdf()
        if p: self._vw_load(p)

    def _vw_load(self, path: str):
        try:
            doc = fitz.open(path)
        except Exception as e:
            ext = os.path.splitext(path)[1].lower()
            hint = ("\n\n(.ai 파일은 PDF 기반 버전만 지원됩니다.\nAdobe Illustrator CS이상에서 저장된 파일이어야 합니다.)"
                    if ext == ".ai" else "")
            messagebox.showerror("오류", f"파일을 열 수 없습니다:\n{e}{hint}"); return
        if self._vw_doc:
            try: self._vw_doc.close()
            except Exception: pass
        self._vw_doc       = doc
        self._vw_path      = path
        self._vw_total     = doc.page_count
        self._vw_pg        = 0
        self._vw_rot       = 0
        self._vw_hits      = []
        self._vw_hit_pos   = -1
        _dm = self._settings.get("default_view_mode", "한 페이지")
        self._vw_zoom_mode = _dm
        self._vw_zoom_var.set(_dm)
        self._vw_hit_lbl.config(text="")
        self._vw_sq_var.set("")
        self._vw_search_nav.pack_forget()   # hide search nav on new file
        self._vw_toc_build()
        self._vw_thumb_build()
        # fit page on load — after() ensures canvas is laid out
        self.after(80, self._vw_fit_page)

    def _vw_toc_build(self):
        self._vw_toc.delete(*self._vw_toc.get_children())
        self._vw_toc_pages.clear()
        toc = self._vw_doc.get_toc(simple=True)
        if not toc:
            self._vw_toc.insert("", "end", text="(목차 없음)"); return
        stack: "list[tuple[str, int]]" = [("", 0)]
        for level, title, page in toc:
            while len(stack) > 1 and stack[-1][1] >= level:
                stack.pop()
            iid = self._vw_toc.insert(
                stack[-1][0], "end",
                text=f"{title}  (p.{page})",
                open=(level <= 2))
            self._vw_toc_pages[iid] = page - 1
            stack.append((iid, level))

    def _vw_toc_click(self, _event):
        sel = self._vw_toc.selection()
        if sel:
            pg = self._vw_toc_pages.get(sel[0])
            if pg is not None: self._vw_goto(pg)

    def _vw_render(self):
        if not self._vw_doc: return
        self._vw_render_ver += 1
        ver = self._vw_render_ver
        threading.Thread(target=self._vw_render_worker,
                         args=(ver,), daemon=True).start()

    def _vw_render_worker(self, ver: int):
        try:
            if ver != self._vw_render_ver: return
            zoom = self._vw_zoom
            rot  = self._vw_rot
            mat  = fitz.Matrix(zoom, zoom).prerotate(rot)

            if self._vw_zoom_mode == "양면 보기" and self._vw_total > 1:
                GAP  = 8
                pg2  = min(self._vw_pg + 1, self._vw_total - 1)
                pix1 = self._vw_doc[self._vw_pg].get_pixmap(matrix=mat, alpha=False)
                pix2 = self._vw_doc[pg2].get_pixmap(matrix=mat, alpha=False)
                img1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
                img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)
                comb_w = pix1.width + GAP + pix2.width
                comb_h = max(pix1.height, pix2.height)
                img = Image.new("RGB", (comb_w, comb_h), (82, 82, 82))
                img.paste(img1, (0, 0))
                img.paste(img2, (pix1.width + GAP, 0))
                irect = self._vw_doc[self._vw_pg].rect * mat
                if ver == self._vw_render_ver:
                    self.after(0, self._vw_show, ver, img,
                               comb_w, comb_h, mat, irect.x0, irect.y0)
            else:
                page  = self._vw_doc[self._vw_pg]
                pix   = page.get_pixmap(matrix=mat, alpha=False)
                img   = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                irect = page.rect * mat
                if ver == self._vw_render_ver:
                    self.after(0, self._vw_show, ver, img,
                               pix.width, pix.height, mat, irect.x0, irect.y0)
        except Exception as e:
            self.after(0, messagebox.showerror, "렌더 오류", str(e))

    def _vw_show(self, ver: int, img, w: int, h: int,
                 mat, ox: float, oy: float):
        if ver != self._vw_render_ver: return
        self._vw_photo  = ImageTk.PhotoImage(img)
        self._vw_mat    = mat
        self._vw_mat_ox = ox
        self._vw_mat_oy = oy
        cv  = self._vw_cv
        cw  = max(cv.winfo_width(), 1)
        ix  = max(0, (cw - w) // 2)
        iy  = 8
        cv.delete("all")
        cv.create_image(ix, iy, image=self._vw_photo, anchor="nw", tags="page")
        cv.config(scrollregion=(0, 0, max(cw, w + 16), h + 16))
        self._vw_draw_hits(ix, iy)
        pg1 = self._vw_pg + 1
        self._vw_pg_var.set(str(pg1))
        self._vw_total_lbl.config(text=f"/ {self._vw_total}")
        pct = int(self._vw_zoom * 100)
        self._vw_zoom_var.set(f"{pct}%")
        fname = os.path.basename(self._vw_path)
        self._vw_status.set(
            f"{fname}  —  {pg1} / {self._vw_total}  |  {pct}%  |  회전 {self._vw_rot}°")

    def _vw_draw_hits(self, ix: int, iy: int):
        cv  = self._vw_cv
        mat = self._vw_mat
        ox  = self._vw_mat_ox
        oy  = self._vw_mat_oy
        for i, (pg_idx, rect) in enumerate(self._vw_hits):
            if pg_idx != self._vw_pg: continue
            r   = rect * mat
            cur = (i == self._vw_hit_pos)
            cv.create_rectangle(
                r.x0 - ox + ix, r.y0 - oy + iy,
                r.x1 - ox + ix, r.y1 - oy + iy,
                fill="#FF8C00" if cur else "yellow",
                stipple="gray50",
                outline="#E65100" if cur else "#B8860B",
                tags="hl")

    def _vw_goto(self, idx: int):
        if not self._vw_doc: return
        self._vw_pg = max(0, min(idx, self._vw_total - 1))
        self._vw_render()
        self._vw_thumb_mark(self._vw_pg)

    def _vw_goto_entry(self):
        try:
            self._vw_goto(int(self._vw_pg_var.get()) - 1)
        except ValueError:
            pass

    def _vw_prev(self):
        if self._vw_pg > 0: self._vw_goto(self._vw_pg - 1)

    def _vw_next(self):
        if self._vw_doc and self._vw_pg < self._vw_total - 1:
            self._vw_goto(self._vw_pg + 1)

    def _vw_zoom_in(self):
        self._vw_zoom_mode = ""
        self._vw_zoom = min(self._vw_zoom * 1.25, 5.0)
        self._vw_render()

    def _vw_zoom_out(self):
        self._vw_zoom_mode = ""
        self._vw_zoom = max(self._vw_zoom / 1.25, 0.2)
        self._vw_render()

    def _vw_zoom_apply(self):
        val = self._vw_zoom_var.get()
        self._vw_zoom_mode = val
        if val == "전체 폭":                    self._vw_fit_width(); return
        if val in ("한 페이지", "양면 보기"):   self._vw_fit_page();  return
        try:
            self._vw_zoom = float(val.rstrip("%")) / 100
        except ValueError:
            return
        self._vw_render()

    def _vw_fit_width(self):
        if not self._vw_doc: return
        cw = self._vw_cv.winfo_width() - 20
        if cw < 1: return
        page = self._vw_doc[self._vw_pg]
        pw = page.rect.height if self._vw_rot in (90, 270) else page.rect.width
        self._vw_zoom = cw / pw
        self._vw_render()

    def _vw_fit_page(self):
        if not self._vw_doc: return
        cw = self._vw_cv.winfo_width()  - 20
        ch = self._vw_cv.winfo_height() - 20
        if cw < 1 or ch < 1: return

        def _dims(pg_idx):
            p = self._vw_doc[pg_idx]
            if self._vw_rot in (90, 270):
                return p.rect.height, p.rect.width
            return p.rect.width, p.rect.height

        if self._vw_zoom_mode == "양면 보기" and self._vw_total > 1:
            pw1, ph1 = _dims(self._vw_pg)
            pg2 = min(self._vw_pg + 1, self._vw_total - 1)
            pw2, ph2 = _dims(pg2)
            GAP = 8
            self._vw_zoom = min(cw / (pw1 + pw2 + GAP), ch / max(ph1, ph2))
        else:
            pw, ph = _dims(self._vw_pg)
            self._vw_zoom = min(cw / pw, ch / ph)

        self._vw_render()

    def _vw_rot_left(self):
        self._vw_rot = (self._vw_rot - 90) % 360; self._vw_render()

    def _vw_rot_right(self):
        self._vw_rot = (self._vw_rot + 90) % 360; self._vw_render()

    def _vw_search(self):
        q = self._vw_sq_var.get().strip()
        if not q or not self._vw_doc: return
        self._vw_hits.clear(); self._vw_hit_pos = -1
        for pg_idx in range(self._vw_total):
            for r in self._vw_doc[pg_idx].search_for(q):
                self._vw_hits.append((pg_idx, r))
        n = len(self._vw_hits)
        # Always show the nav panel after a search
        self._vw_search_nav.pack(side="right", padx=(2, 8))
        if n == 0:
            self._vw_hit_lbl.config(text="없음")
            self._vw_btn_search_prev.config(state="disabled")
            self._vw_btn_search_next.config(state="disabled")
            self._vw_render(); return
        self._vw_btn_search_prev.config(state="normal")
        self._vw_btn_search_next.config(state="normal")
        self._vw_jump_hit(0)

    def _vw_search_move(self, delta: int):
        if not self._vw_hits: return
        self._vw_jump_hit((self._vw_hit_pos + delta) % len(self._vw_hits))

    def _vw_jump_hit(self, pos: int):
        self._vw_hit_pos = pos
        pg_idx, _ = self._vw_hits[pos]
        self._vw_hit_lbl.config(text=f"{pos+1}/{len(self._vw_hits)}")
        self._vw_pg = pg_idx
        self._vw_render()

    def _vw_copy_text(self):
        if not self._vw_doc: return
        text = self._vw_doc[self._vw_pg].get_text()
        if not text.strip():
            messagebox.showinfo("알림",
                "이 페이지에서 텍스트를 추출할 수 없습니다.\n"
                "(스캔 이미지 PDF는 텍스트 레이어가 없습니다.)"); return
        self.clipboard_clear(); self.clipboard_append(text)
        old = self._vw_status.get()
        self._vw_status.set(old + "  ✓ 복사됨")
        self.after(2000, lambda: self._vw_status.set(old))

    def _vw_ctrl_wheel(self, event):
        if event.delta > 0: self._vw_zoom_in()
        else:               self._vw_zoom_out()

    # ── 슬라이드쇼 (전체화면 발표 모드) ──────────────────────────
    def _vw_slideshow_open(self):
        if not self._vw_doc:
            messagebox.showwarning("슬라이드쇼", "PDF를 먼저 열어주세요.")
            return

        ss = tk.Toplevel(self)
        ss.title("슬라이드쇼")
        ss.configure(bg="black")
        ss.attributes("-fullscreen", True)
        ss.focus_set()

        pg        = [self._vw_pg]
        photo_ref = [None]
        render_id = [0]

        cv = tk.Canvas(ss, bg="black", highlightthickness=0, cursor="none")
        cv.pack(fill="both", expand=True)

        def _render(p: int, *, show_hint: bool = False):
            p = max(0, min(p, self._vw_total - 1))
            pg[0] = p
            render_id[0] += 1
            ver = render_id[0]

            def _worker():
                try:
                    cw = cv.winfo_width()
                    ch = cv.winfo_height()
                    if cw < 4 or ch < 4:
                        ss.after(120, lambda: _render(p, show_hint=show_hint))
                        return
                    page  = self._vw_doc[p]
                    pw, ph = page.rect.width, page.rect.height
                    scale = min(cw / pw, ch / ph)
                    mat   = fitz.Matrix(scale, scale)
                    pix   = page.get_pixmap(matrix=mat, alpha=False)
                    img   = Image.frombytes("RGB",
                                            [pix.width, pix.height], pix.samples)
                    iw, ih = pix.width, pix.height
                    x0 = (cw - iw) // 2
                    y0 = (ch - ih) // 2

                    def _show():
                        if ver != render_id[0]: return
                        photo_ref[0] = ImageTk.PhotoImage(img)
                        cv.delete("all")
                        cv.create_image(x0, y0, image=photo_ref[0], anchor="nw")
                        # Page counter — shadow then white text
                        lbl = f"{p + 1}  /  {self._vw_total}"
                        cv.create_text(cw - 18, ch - 13, text=lbl,
                                       font=(MG[0], FS + 2), fill="black",
                                       anchor="se", tags="overlay")
                        cv.create_text(cw - 19, ch - 14, text=lbl,
                                       font=(MG[0], FS + 2), fill="white",
                                       anchor="se", tags="overlay")
                        if show_hint:
                            hint = (
                                "  <  또는 클릭 왼쪽: 이전 페이지   "
                                "  >  또는 클릭 오른쪽: 다음 페이지   "
                                "  Esc: 종료  "
                            )
                            cv.create_text(cw // 2, ch - 20, text=hint,
                                           font=(MG[0], FS_SM),
                                           fill="#DDDDDD", anchor="s",
                                           tags="hint")
                            ss.after(4000, lambda: cv.delete("hint"))

                    ss.after(0, _show)
                except Exception:
                    pass

            threading.Thread(target=_worker, daemon=True).start()

        def _on_key(e):
            k = e.keysym
            if k in ("Escape", "q", "Q"):
                ss.destroy()
            elif k in ("Right", "Next", "space", "Return", "greater"):
                _render(pg[0] + 1)
            elif k in ("Left", "Prior", "BackSpace", "less"):
                _render(pg[0] - 1)
            elif k == "Home":
                _render(0)
            elif k == "End":
                _render(self._vw_total - 1)

        def _on_click(e):
            if e.x >= cv.winfo_width() // 2:
                _render(pg[0] + 1)
            else:
                _render(pg[0] - 1)

        ss.bind("<Key>",        _on_key)
        cv.bind("<Button-1>",   _on_click)
        cv.bind("<Configure>",  lambda e: _render(pg[0]))

        _render(self._vw_pg, show_hint=True)

    def _vw_on_resize(self, event):
        if not self._vw_doc:
            try:
                self._vw_cv.coords(self._vw_welcome_id,
                                    event.width // 2, event.height // 2)
            except Exception:
                pass
            return
        if self._vw_resize_id:
            self.after_cancel(self._vw_resize_id)
        # Re-fit directly using zoom_mode (avoids reading stale combobox value)
        if self._vw_zoom_mode == "전체 폭":
            self._vw_resize_id = self.after(150, self._vw_fit_width)
        elif self._vw_zoom_mode in ("한 페이지", "양면 보기"):
            self._vw_resize_id = self.after(150, self._vw_fit_page)
        else:
            self._vw_resize_id = self.after(150, self._vw_render)

    # ══════════════════════════════════════════════════════════
    # ── 뷰어 통합 도구 패널 ────────────────────────────────────
    # ══════════════════════════════════════════════════════════

    def _vw_require_file(self) -> bool:
        if not self._vw_path or not self._vw_doc:
            messagebox.showwarning("알림", "뷰어에 PDF 파일을 먼저 열어주세요.")
            return False
        return True

    def _vw_toggle_tools(self):
        if self._vw_tools_shown:
            self._vw_tools_panel.pack_forget()
            self._vw_tools_shown = False
            self._vw_tool_btn.config(text="도구 ▷")
        else:
            self._vw_tools_panel.pack(side="right", fill="y",
                                       before=self._vw_cv_outer)
            self._vw_tools_shown = True
            self._vw_tool_btn.config(text="도구 ◁")

    def _dlg_center(self, dlg: tk.Toplevel, w: int, h: int):
        self.update_idletasks()
        x = self.winfo_x() + max(0, (self.winfo_width()  - w) // 2)
        y = self.winfo_y() + max(0, (self.winfo_height() - h) // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    # ── 암호화 다이얼로그 ──────────────────────────────────────
    def _vw_dlg_encrypt(self):
        if not self._vw_require_file(): return
        src = self._vw_path
        base, ext = os.path.splitext(src)

        dlg = tk.Toplevel(self)
        dlg.title("암호화"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 480, 400)

        f = tk.Frame(dlg, bg=C["bg"])
        f.pack(fill="both", expand=True, padx=16, pady=12)

        ic = SectionCard(f, "파일"); ic.pack(fill="x", pady=(0, 8))
        tk.Label(ic.body, text=os.path.basename(src), font=F_SM,
                 bg=C["card"], fg=C["text"], anchor="w").pack(fill="x")

        pc = SectionCard(f, "비밀번호"); pc.pack(fill="x", pady=(0, 8))
        pc.body.columnconfigure(0, weight=1)
        tk.Label(pc.body, text="비밀번호", font=F_SM, bg=C["card"],
                 fg=C["sub"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,3))
        pv = tk.StringVar(); pe = centry(pc.body, pv); pe.config(show="*")
        pe.grid(row=1, column=0, sticky="ew", padx=(0,8))
        self._make_eye_btn(pc.body, pe).grid(row=1, column=1)
        tk.Label(pc.body, text="비밀번호 확인", font=F_SM, bg=C["card"],
                 fg=C["sub"]).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8,3))
        pv2 = tk.StringVar(); pe2 = centry(pc.body, pv2); pe2.config(show="*")
        pe2.grid(row=3, column=0, sticky="ew", padx=(0,8))
        self._make_eye_btn(pc.body, pe2).grid(row=3, column=1)

        ac = SectionCard(f, "암호화 강도"); ac.pack(fill="x", pady=(0, 8))
        av = tk.StringVar(value="AES-256")
        for i, (lbl, val) in enumerate([("AES-256 (권장)", "AES-256"),
                                         ("AES-128", "AES-128"),
                                         ("RC4-128", "RC4-128")]):
            tk.Radiobutton(ac.body, text=lbl, variable=av, value=val,
                           font=F, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).grid(row=0, column=i, sticky="w", padx=(0, 12))

        oc = SectionCard(f, "저장 위치"); oc.pack(fill="x", pady=(0, 8))
        oc.body.columnconfigure(0, weight=1)
        ov = tk.StringVar(value=base + "_encrypted" + ext)
        centry(oc.body, ov).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(oc.body, "찾기", lambda: self._save_dialog(ov),
             C["primary"], C["pri_h"], padx=8, pady=5).grid(row=0, column=1)

        sv = tk.StringVar(value="")
        pb = mkpb(f); pb.pack(fill="x", pady=(0,3))
        tk.Label(f, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        def _run():
            p1, p2, out = pv.get(), pv2.get(), ov.get().strip()
            if not p1: messagebox.showerror("오류", "비밀번호를 입력하세요.", parent=dlg); return
            if p1 != p2: messagebox.showerror("오류", "비밀번호가 일치하지 않습니다.", parent=dlg); return
            if not out: messagebox.showerror("오류", "저장 위치를 지정하세요.", parent=dlg); return
            def _wk():
                self.after(0, pb.start, 10); self.after(0, sv.set, "암호화 중...")
                try:
                    r = self._reader(src); w = PdfWriter()
                    for pg in r.pages: w.add_page(pg)
                    if r.metadata: w.add_metadata(dict(r.metadata))
                    w.encrypt(user_password=p1, owner_password=p1, algorithm=av.get())
                    with open(out, "wb") as fh: w.write(fh)
                    self.after(0, pb.stop); self.after(0, sv.set, "완료!")
                    self.after(0, messagebox.showinfo, "완료", f"암호화 완료!\n\n{out}")
                except Exception as e:
                    self.after(0, pb.stop); self.after(0, sv.set, "오류")
                    self.after(0, messagebox.showerror, "오류", str(e))
            threading.Thread(target=_wk, daemon=True).start()

        hbtn(f, "  암호화하여 저장  ", _run, C["primary"], C["pri_h"],
             pady=10).pack(fill="x", pady=(4,0))

    # ── 페이지 편집 다이얼로그 ─────────────────────────────────
    def _vw_dlg_page_edit(self):
        if not self._vw_require_file(): return
        src = self._vw_path
        base, ext = os.path.splitext(src)

        dlg = tk.Toplevel(self)
        dlg.title("페이지 편집"); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 940, 680)
        dlg.resizable(True, True); dlg.minsize(700, 480)

        sv = tk.StringVar(value="썸네일 로드 중...")
        top = tk.Frame(dlg, bg=C["bg"]); top.pack(fill="x", padx=12, pady=(10,4))
        pb = mkpb(top); pb.pack(fill="x", pady=(0,3))
        tk.Label(top, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        mid = tk.Frame(dlg, bg=C["bg"]); mid.pack(fill="both", expand=True, padx=12)

        # Sidebar
        sb = tk.Frame(mid, bg=C["bg"]); sb.pack(side="right", fill="y", padx=(8,0))
        st_lbl = tk.Label(sb, text="", font=F_SM, bg=C["bg"],
                          fg=C["sub"], wraplength=90)
        st_lbl.pack(fill="x", pady=(0,8))
        thumb_ref = [None]

        def _sb(txt, cmd, bg, bgh):
            hbtn(sb, txt, cmd, bg, bgh, padx=8, pady=6).pack(fill="x", pady=(0,4))

        _sb("▲ 위로",  lambda: thumb_ref[0] and thumb_ref[0].move_up(),   C["primary"], C["pri_h"])
        _sb("▼ 아래로", lambda: thumb_ref[0] and thumb_ref[0].move_down(), C["primary"], C["pri_h"])
        tk.Frame(sb, bg=C["border"], height=1).pack(fill="x", pady=4)
        def _del():
            if thumb_ref[0]:
                n = thumb_ref[0].delete_selected()
                if not n: messagebox.showwarning("알림", "삭제할 페이지를 선택하세요.", parent=dlg)
        _sb("선택 삭제", _del, C["danger"], C["dan_h"])
        _sb("전체 선택", lambda: thumb_ref[0] and thumb_ref[0].select_all(), C["sub"], "#475569")
        _sb("선택 해제", lambda: thumb_ref[0] and thumb_ref[0].deselect_all(), C["sub"], "#475569")
        tk.Frame(sb, bg=C["border"], height=1).pack(fill="x", pady=4)
        def _add():
            p = filedialog.askopenfilename(parent=dlg, title="PDF 추가",
                filetypes=[("PDF", "*.pdf"), ("모두", "*.*")])
            if p and thumb_ref[0]:
                sv.set("추가 중..."); thumb_ref[0].append(p,
                    on_ready=lambda n: sv.set(f"총 {n}페이지"))
        def _extract():
            if thumb_ref[0] and thumb_ref[0].selected_count() > 0:
                self._pg_extract_via_dialog(thumb_ref[0], dlg, pb, sv)
            else:
                messagebox.showwarning("알림", "추출할 페이지를 선택하세요.", parent=dlg)
        _sb("+ PDF 추가", _add, C["primary"], C["pri_h"])
        _sb("↓ 추출",    _extract, C["success"], C["suc_h"])

        # Thumbnail grid
        tc = tk.Frame(mid, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        tc.pack(side="left", fill="both", expand=True)
        th_hdr = tk.Frame(tc, bg=C["card_hdr"]); th_hdr.pack(fill="x")
        tk.Label(th_hdr, text="페이지 미리보기 — 클릭하여 선택",
                 font=F_B, bg=C["card_hdr"], fg=C["text"], padx=12, pady=7).pack(side="left")
        tk.Frame(tc, bg=C["border"], height=1).pack(fill="x")
        tb2 = tk.Frame(tc, bg=C["card"]); tb2.pack(fill="both", expand=True)
        thumb = ThumbnailGrid(tb2,
            on_change=lambda tot, sel: (
                st_lbl.config(text=f"{sel}선택 / 전체{tot}" if sel else f"전체 {tot}페이지"),
                sv.set(f"{sel}페이지 선택" if sel else f"전체 {tot}페이지"),
            ))
        thumb.pack(fill="both", expand=True)
        thumb_ref[0] = thumb
        ll = tk.Label(tb2, text="PDF를 로드하면 미리보기가 표시됩니다.",
                      font=F_SM, bg=C["card"], fg=C["muted"])
        ll.place(relx=0.5, rely=0.5, anchor="center")

        # Save bar
        bot = tk.Frame(dlg, bg=C["bg"]); bot.pack(fill="x", padx=12, pady=(4,10))
        bot.columnconfigure(0, weight=1)
        ov = tk.StringVar(value=base + "_edited" + ext)
        centry(bot, ov).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(bot, "찾기", lambda: self._save_dialog(ov),
             C["primary"], C["pri_h"], padx=8, pady=6).grid(row=0, column=1)

        def _save():
            if not thumb_ref[0] or thumb_ref[0].page_count() == 0:
                messagebox.showerror("오류", "페이지가 없습니다.", parent=dlg); return
            out = ov.get().strip()
            if not out: messagebox.showerror("오류", "저장 위치를 지정하세요.", parent=dlg); return
            self._thread(self._pg_write, thumb_ref[0].get_page_sources(), out, pb, sv, "저장")

        hbtn(bot, "  편집 결과 저장  ", _save, C["primary"], C["pri_h"],
             pady=10).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6,0))

        pb.start(10)
        thumb.load(src, on_ready=lambda n: (
            ll.lower(), pb.stop(), sv.set(f"총 {n}페이지 로드됨."),
        ))

    # ── 병합 다이얼로그 ───────────────────────────────────────
    def _vw_dlg_merge(self):
        if not self._vw_require_file(): return
        src = self._vw_path

        dlg = tk.Toplevel(self)
        dlg.title("PDF 병합"); dlg.resizable(True, False); dlg.grab_set()
        dlg.configure(bg=C["bg"]); self._dlg_center(dlg, 580, 460)

        f = tk.Frame(dlg, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)
        merge_files = [src]

        lc = tk.Frame(f, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        lc.pack(fill="both", expand=True, pady=(0,8))
        lh = tk.Frame(lc, bg=C["card_hdr"]); lh.pack(fill="x")
        tk.Label(lh, text="병합할 PDF 목록", font=F_B, bg=C["card_hdr"],
                 fg=C["text"], padx=12, pady=7).pack(side="left")
        tk.Frame(lc, bg=C["border"], height=1).pack(fill="x")
        lb_body = tk.Frame(lc, bg=C["card"])
        lb_body.pack(fill="both", expand=True, padx=12, pady=10)

        bf = tk.Frame(lb_body, bg=C["card"]); bf.pack(side="right", fill="y", padx=(8,0))
        lb_ref = [None]

        def _add():
            paths = filedialog.askopenfilenames(parent=dlg, title="PDF 추가",
                filetypes=[("PDF", "*.pdf"), ("모두", "*.*")])
            for p in paths:
                if p not in merge_files:
                    merge_files.append(p)
                    lb_ref[0].insert("end", f"  {os.path.basename(p)}")
            sv.set(f"{len(merge_files)}개 파일")

        def _rm():
            for i in reversed(lb_ref[0].curselection()):
                lb_ref[0].delete(i); del merge_files[i]
            sv.set(f"{len(merge_files)}개 파일")

        def _up():
            lb = lb_ref[0]; sel = list(lb.curselection())
            if not sel or sel[0] == 0: return
            for i in sel:
                t = lb.get(i); lb.delete(i); lb.insert(i-1, t)
                merge_files[i], merge_files[i-1] = merge_files[i-1], merge_files[i]
            lb.selection_clear(0, "end")
            for i in sel: lb.selection_set(i-1)

        def _dn():
            lb = lb_ref[0]; sel = list(lb.curselection())
            if not sel or sel[-1] == lb.size()-1: return
            for i in reversed(sel):
                t = lb.get(i); lb.delete(i); lb.insert(i+1, t)
                merge_files[i], merge_files[i+1] = merge_files[i+1], merge_files[i]
            lb.selection_clear(0, "end")
            for i in sel: lb.selection_set(i+1)

        for txt, cmd in [("+ 추가", _add), ("▲ 위로", _up), ("▼ 아래로", _dn)]:
            hbtn(bf, txt, cmd, C["primary"], C["pri_h"], padx=8, pady=6).pack(fill="x", pady=(0,4))
        tk.Frame(bf, bg=C["border"], height=1).pack(fill="x", pady=4)
        hbtn(bf, "제거", _rm, C["danger"], C["dan_h"], padx=8, pady=6).pack(fill="x")

        lf2 = tk.Frame(lb_body, bg=C["card"]); lf2.pack(side="left", fill="both", expand=True)
        lb = tk.Listbox(lf2, font=F, bg=C["card"], fg=C["text"],
                        relief="solid", bd=1, highlightthickness=1,
                        highlightcolor=C["primary"], highlightbackground=C["border"],
                        selectbackground=C["sel"], selectforeground=C["text"], height=10)
        lb_ref[0] = lb
        mg_sb = ttk.Scrollbar(lf2, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=mg_sb.set)
        lb.pack(side="left", fill="both", expand=True)
        mg_sb.pack(side="right", fill="y")
        lb.insert("end", f"  {os.path.basename(src)}  ← 현재 파일")

        oc = SectionCard(f, "저장 위치"); oc.pack(fill="x", pady=(0,8))
        oc.body.columnconfigure(0, weight=1)
        ov = tk.StringVar(value=os.path.join(os.path.dirname(src), "merged.pdf"))
        centry(oc.body, ov).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(oc.body, "찾기", lambda: self._save_dialog(ov),
             C["primary"], C["pri_h"], padx=8, pady=5).grid(row=0, column=1)

        sv = tk.StringVar(value=f"{len(merge_files)}개 파일")
        pb = mkpb(f); pb.pack(fill="x", pady=(0,3))
        tk.Label(f, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        def _run():
            if len(merge_files) < 2:
                messagebox.showerror("오류", "PDF를 2개 이상 추가하세요.", parent=dlg); return
            out = ov.get().strip()
            if not out: messagebox.showerror("오류", "저장 위치를 지정하세요.", parent=dlg); return
            files = list(merge_files)
            def _wk():
                self.after(0, pb.start, 10); self.after(0, sv.set, "병합 중...")
                try:
                    w = PdfWriter(); readers = []
                    for p in files:
                        r = self._reader(p); readers.append(r); w.append(r)
                    with open(out, "wb") as fh: w.write(fh)
                    self.after(0, pb.stop); self.after(0, sv.set, "완료!")
                    self.after(0, messagebox.showinfo, "완료",
                               f"병합 완료! ({len(files)}개 파일)\n\n{out}")
                except Exception as e:
                    self.after(0, pb.stop); self.after(0, sv.set, "오류")
                    self.after(0, messagebox.showerror, "오류", str(e))
            threading.Thread(target=_wk, daemon=True).start()

        hbtn(f, "  PDF 병합하여 저장  ", _run, C["primary"], C["pri_h"],
             pady=10).pack(fill="x", pady=(4,0))

    # ── 나누기 다이얼로그 ─────────────────────────────────────
    def _vw_dlg_split(self):
        if not self._vw_require_file(): return
        src = self._vw_path

        dlg = tk.Toplevel(self)
        dlg.title("PDF 나누기"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"]); self._dlg_center(dlg, 460, 350)

        f = tk.Frame(dlg, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        ic = SectionCard(f, "파일"); ic.pack(fill="x", pady=(0,8))
        tk.Label(ic.body, text=f"{os.path.basename(src)}  ({self._vw_total}페이지)",
                 font=F_SM, bg=C["card"], fg=C["text"]).pack(anchor="w")

        mc = SectionCard(f, "나누기 방식"); mc.pack(fill="x", pady=(0,8))
        mb = mc.body
        sp_mode = tk.StringVar(value="each")
        range_v = tk.StringVar(); every_v = tk.StringVar(value="2")
        range_f = tk.Frame(mb, bg=C["card"])
        every_f = tk.Frame(mb, bg=C["card"])
        range_f.grid(row=1, column=1, padx=(12,0)); range_f.grid_remove()
        every_f.grid(row=2, column=1, padx=(12,0)); every_f.grid_remove()
        centry(range_f, range_v, width=16).pack()
        tk.Label(every_f, text="N =", font=F, bg=C["card"], fg=C["text"]).pack(side="left")
        tk.Spinbox(every_f, textvariable=every_v, from_=1, to=999,
                   width=5, font=F, relief="solid", bd=1).pack(side="left", padx=(4,0))

        def _toggle():
            range_f.grid_remove(); every_f.grid_remove()
            m = sp_mode.get()
            if m == "range": range_f.grid()
            elif m == "every": every_f.grid()

        for row, (v, lbl) in enumerate([("each", "모든 페이지를 개별 파일로"),
                                         ("range","범위 지정  (예: 1-3, 5)"),
                                         ("every","N 페이지마다 분리")]):
            tk.Radiobutton(mb, text=lbl, variable=sp_mode, value=v,
                           font=F, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"],
                           command=_toggle).grid(row=row, column=0, sticky="w", pady=2)

        dc = SectionCard(f, "저장 폴더"); dc.pack(fill="x", pady=(0,8))
        dc.body.columnconfigure(0, weight=1)
        dv = tk.StringVar(value=os.path.dirname(src))
        centry(dc.body, dv).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(dc.body, "폴더",
             lambda: dv.set(filedialog.askdirectory(parent=dlg, title="저장 폴더") or dv.get()),
             C["primary"], C["pri_h"], padx=8, pady=5).grid(row=0, column=1)

        sv = tk.StringVar(value="")
        pb = mkpb(f); pb.pack(fill="x", pady=(0,3))
        tk.Label(f, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        def _run():
            d = dv.get().strip()
            if not d or not os.path.isdir(d):
                messagebox.showerror("오류", "저장 폴더를 선택하세요.", parent=dlg); return
            try:
                r = self._reader(src); total = len(r.pages)
                m = sp_mode.get()
                if m == "each":
                    groups = [[i] for i in range(total)]
                elif m == "range":
                    rng = range_v.get().strip()
                    if not rng: messagebox.showerror("오류", "범위를 입력하세요.", parent=dlg); return
                    groups = self._parse_ranges(rng, total)
                else:
                    try: n2 = int(every_v.get()); assert n2 >= 1
                    except: messagebox.showerror("오류", "N은 1 이상이어야 합니다.", parent=dlg); return
                    groups = [list(range(i, min(i+n2, total))) for i in range(0, total, n2)]
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=dlg); return
            def _wk():
                self.after(0, pb.start, 10); self.after(0, sv.set, "나누기 중...")
                try:
                    r2 = self._reader(src)
                    bname = os.path.splitext(os.path.basename(src))[0]
                    pad = len(str(len(groups)))
                    for idx, grp in enumerate(groups):
                        w = PdfWriter()
                        for pg2 in grp: w.add_page(r2.pages[pg2])
                        fname = f"{bname}_part{str(idx+1).zfill(pad)}.pdf"
                        with open(os.path.join(d, fname), "wb") as fh: w.write(fh)
                    self.after(0, pb.stop); self.after(0, sv.set, "완료!")
                    self.after(0, messagebox.showinfo, "완료",
                               f"{len(groups)}개 파일로 분리 완료!\n\n폴더: {d}")
                except Exception as e2:
                    self.after(0, pb.stop); self.after(0, sv.set, "오류")
                    self.after(0, messagebox.showerror, "오류", str(e2))
            threading.Thread(target=_wk, daemon=True).start()

        hbtn(f, "  PDF 나누기  ", _run, C["primary"], C["pri_h"],
             pady=10).pack(fill="x", pady=(4,0))

    # ── 압축 다이얼로그 ───────────────────────────────────────
    def _vw_dlg_compress(self):
        if not self._vw_require_file(): return
        src = self._vw_path
        base, ext = os.path.splitext(src)
        kb = os.path.getsize(src) / 1024
        try: n_pg = len(PdfReader(src).pages); info = f"{os.path.basename(src)}  ({n_pg}페이지 / {kb:.1f} KB)"
        except Exception: info = f"{os.path.basename(src)}  ({kb:.1f} KB)"

        dlg = tk.Toplevel(self)
        dlg.title("PDF 압축"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"]); self._dlg_center(dlg, 480, 400)

        f = tk.Frame(dlg, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        ic = SectionCard(f, "파일"); ic.pack(fill="x", pady=(0,8))
        tk.Label(ic.body, text=info, font=F_SM, bg=C["card"], fg=C["text"]).pack(anchor="w")

        oc2 = SectionCard(f, "압축 옵션"); oc2.pack(fill="x", pady=(0,8))
        cp_str = tk.BooleanVar(value=True); cp_ded = tk.BooleanVar(value=True)
        cp_met = tk.BooleanVar(value=False)
        for row2, (var2, txt2) in enumerate([
                (cp_str, "콘텐츠 스트림 압축"),
                (cp_ded, "중복 객체 제거"),
                (cp_met, "메타데이터 제거")]):
            tk.Checkbutton(oc2.body, text=txt2, variable=var2, font=F,
                           bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).grid(row=row2, column=0, sticky="w", pady=2)

        ic2 = SectionCard(f, "이미지 해상도"); ic2.pack(fill="x", pady=(0,8))
        cp_img2 = tk.BooleanVar(value=False); cp_dpi2 = tk.IntVar(value=150)
        dpi_f2 = tk.Frame(ic2.body, bg=C["card"])

        def _tog():
            st = "normal" if cp_img2.get() else "disabled"
            for ww in dpi_f2.winfo_children():
                try: ww.config(state=st)
                except tk.TclError: pass

        tk.Checkbutton(ic2.body, text="이미지 DPI 다운샘플링",
                       variable=cp_img2, font=F, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], selectcolor=C["card"],
                       command=_tog).pack(anchor="w", pady=(0,4))
        dpi_f2.pack(anchor="w")
        tk.Label(dpi_f2, text="최대 DPI:", font=F, bg=C["card"], fg=C["text"]).pack(side="left")
        for dv2, dl in [(300,"300"),(150,"150"),(96,"96")]:
            tk.Radiobutton(dpi_f2, text=dl, variable=cp_dpi2, value=dv2,
                           font=F_SM, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).pack(side="left", padx=(8,0))
        _tog()

        sc2 = SectionCard(f, "저장 위치"); sc2.pack(fill="x", pady=(0,8))
        sc2.body.columnconfigure(0, weight=1)
        ov2 = tk.StringVar(value=base + "_compressed" + ext)
        centry(sc2.body, ov2).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(sc2.body, "찾기", lambda: self._save_dialog(ov2),
             C["primary"], C["pri_h"], padx=8, pady=5).grid(row=0, column=1)

        sv2 = tk.StringVar(value="")
        pb2 = mkpb(f); pb2.pack(fill="x", pady=(0,3))
        tk.Label(f, textvariable=sv2, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        def _run():
            out = ov2.get().strip()
            if not out: messagebox.showerror("오류", "저장 위치를 지정하세요.", parent=dlg); return
            def _wk():
                import io as _io
                self.after(0, pb2.start, 10); self.after(0, sv2.set, "압축 중...")
                try:
                    fitz.TOOLS.mupdf_display_errors(False)
                    doc = fitz.open(src)
                    if cp_img2.get():
                        seen: set[int] = set()
                        for page in doc:
                            for img_info in page.get_images(full=True):
                                xref = img_info[0]
                                if xref in seen: continue
                                seen.add(xref)
                                try:
                                    ps = fitz.Pixmap(doc, xref)
                                    if ps.colorspace and ps.colorspace != fitz.csRGB:
                                        ps = fitz.Pixmap(fitz.csRGB, ps)
                                    w_px, h_px = ps.width, ps.height
                                    rect3 = page.rect
                                    est = max(w_px/max(rect3.width/72,0.01),
                                              h_px/max(rect3.height/72,0.01))
                                    if est <= cp_dpi2.get(): continue
                                    sc3 = cp_dpi2.get() / est
                                    nw3 = max(1, int(w_px*sc3)); nh3 = max(1, int(h_px*sc3))
                                    img = Image.open(_io.BytesIO(ps.tobytes("png")))
                                    if img.mode in ("RGBA","LA"):
                                        bg3 = Image.new("RGB", img.size, (255,255,255))
                                        bg3.paste(img, mask=img.split()[-1]); img = bg3
                                    elif img.mode != "RGB": img = img.convert("RGB")
                                    img = img.resize((nw3,nh3), Image.LANCZOS)
                                    buf = _io.BytesIO()
                                    img.save(buf, format="JPEG", quality=85, optimize=True)
                                    page.replace_image(xref,
                                        pixmap=fitz.Pixmap(_io.BytesIO(buf.getvalue())))
                                except Exception: continue
                    if cp_met.get(): doc.set_metadata({})
                    doc.save(out, garbage=4 if cp_ded.get() else 1,
                             deflate=cp_str.get(), deflate_images=False,
                             deflate_fonts=cp_str.get(), clean=True, no_new_id=True)
                    doc.close()
                    ok = os.path.getsize(src)/1024; rk = os.path.getsize(out)/1024
                    ratio = (1-rk/ok)*100 if ok else 0
                    self.after(0, pb2.stop)
                    self.after(0, sv2.set, f"완료: {ok:.1f}→{rk:.1f} KB ({ratio:.1f}%↓)")
                    self.after(0, messagebox.showinfo, "완료",
                               f"압축 완료!\n\n원본: {ok:.1f} KB\n결과: {rk:.1f} KB  ({ratio:.1f}% 절감)\n\n{out}")
                except Exception as e:
                    self.after(0, pb2.stop); self.after(0, sv2.set, "오류")
                    self.after(0, messagebox.showerror, "오류", str(e))
            threading.Thread(target=_wk, daemon=True).start()

        hbtn(f, "  압축하여 저장  ", _run, C["primary"], C["pri_h"],
             pady=10).pack(fill="x", pady=(4,0))

    # ── 도장/서명 다이얼로그 ──────────────────────────────────
    def _vw_dlg_stamp(self):
        if not self._vw_require_file(): return
        src = self._vw_path
        base, ext = os.path.splitext(src)

        dlg = tk.Toplevel(self)
        dlg.title("도장 / 서명 삽입"); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 960, 660)
        dlg.resizable(True, True); dlg.minsize(720, 500)

        # ── State (lists for closure mutability) ──────────────
        cv_ref   = [None]
        img_var  = tk.StringVar()
        x_var    = tk.StringVar(value="1.0"); y_var = tk.StringVar(value="1.0")
        w_var    = tk.StringVar(value="3.0"); h_var = tk.StringVar(value="3.0")
        lock_var = tk.BooleanVar(value=True)
        aspect   = [1.0]; upd    = [False]
        pg_tk    = [None]; stkref = [None]; spil = [None]
        cv_sc    = [1.0];  cv_ox  = [0.0]; cv_oy = [0.0]
        drag_m   = [None]; drag_s = [(0,0)]; drag_b = [(1.,1.,3.,3.)]

        # ── do_render (defined first so all closures can reference it) ──
        def do_render(*_):
            if upd[0]: return
            cv = cv_ref[0]
            if cv is None: return
            cv.delete("all")
            cw = cv.winfo_width(); ch = cv.winfo_height()
            if cw < 10 or ch < 10: return
            try:
                pg_i = max(0, int(prev_pg_v.get() or "1") - 1)
                doc3 = fitz.open(src)
                pg_i = min(pg_i, len(doc3)-1)
                page3 = doc3[pg_i]
                pw3, ph3 = page3.rect.width, page3.rect.height
                pad = 12; sc = min((cw-pad*2)/pw3, (ch-pad*2)/ph3)
                cv_sc[0] = sc; rpw = int(pw3*sc); rph = int(ph3*sc)
                cv_ox[0] = (cw-rpw)/2; cv_oy[0] = (ch-rph)/2
                mat3 = fitz.Matrix(sc, sc)
                pix3 = page3.get_pixmap(matrix=mat3, alpha=False)
                pg_tk[0] = ImageTk.PhotoImage(
                    Image.frombytes("RGB",[pix3.width,pix3.height],pix3.samples))
                doc3.close()
                cv.create_image(cv_ox[0], cv_oy[0], anchor="nw", image=pg_tk[0])
            except Exception: return
            ip = img_var.get().strip()
            if not ip or not os.path.isfile(ip): return
            try:
                xc = float(x_var.get()); yc = float(y_var.get())
                wc = float(w_var.get()); hc = float(h_var.get())
            except ValueError: return
            PT = self._CM_TO_PT; sc = cv_sc[0]
            x0 = xc*PT*sc+cv_ox[0]; y0 = yc*PT*sc+cv_oy[0]
            x1 = (xc+wc)*PT*sc+cv_ox[0]; y1 = (yc+hc)*PT*sc+cv_oy[0]
            sw = max(1,int(x1-x0)); sh = max(1,int(y1-y0))
            try:
                if spil[0] is None: spil[0] = Image.open(ip).convert("RGBA")
                rs = spil[0].resize((sw,sh), Image.LANCZOS)
                bg2 = Image.new("RGB",(sw,sh),(210,210,210)); bg2.paste(rs,mask=rs.split()[3])
                stkref[0] = ImageTk.PhotoImage(bg2)
                cv.create_image(x0,y0,anchor="nw",image=stkref[0],tags="stamp")
            except Exception:
                cv.create_rectangle(x0,y0,x1,y1,fill="#FF000033",outline="#FF4444",tags="stamp")
            cv.create_rectangle(x0,y0,x1,y1,outline="#3B82F6",width=2,dash=(6,3),tags="sel")
            HR = self._CV_HDL_R
            for tg,hx,hy in [("nw",x0,y0),("ne",x1,y0),("sw",x0,y1),("se",x1,y1)]:
                cv.create_rectangle(hx-HR,hy-HR,hx+HR,hy+HR,
                                    fill="#3B82F6",outline="white",width=1,
                                    tags=("handle",f"hdl_{tg}"))

        # ── Canvas drag handlers ───────────────────────────────
        def cv_press(e):
            cv = cv_ref[0]; HR3 = self._CV_HDL_R+3
            for item in reversed(cv.find_overlapping(e.x-HR3,e.y-HR3,e.x+HR3,e.y+HR3)):
                for tg in cv.gettags(item):
                    if tg.startswith("hdl_"):
                        drag_m[0] = f"resize_{tg[4:]}"; drag_s[0] = (e.x,e.y)
                        try: drag_b[0]=(float(x_var.get()),float(y_var.get()),float(w_var.get()),float(h_var.get()))
                        except: drag_m[0]=None; return
                        return
            for item in reversed(cv.find_overlapping(e.x-3,e.y-3,e.x+3,e.y+3)):
                if any(t in cv.gettags(item) for t in ("stamp","sel")):
                    drag_m[0]="move"; drag_s[0]=(e.x,e.y)
                    try: drag_b[0]=(float(x_var.get()),float(y_var.get()),float(w_var.get()),float(h_var.get()))
                    except: drag_m[0]=None; return
                    return
            drag_m[0]=None

        def cv_drag(e):
            m = drag_m[0]
            if not m: return
            PT=self._CM_TO_PT; sc=cv_sc[0]
            if sc==0: return
            dx=(e.x-drag_s[0][0])/(sc*PT); dy=(e.y-drag_s[0][1])/(sc*PT)
            ox,oy,ow,oh=drag_b[0]; lk=lock_var.get(); ar=max(aspect[0],0.001); MN=0.2
            if m=="move": nx,ny,nw,nh=max(0.,ox+dx),max(0.,oy+dy),ow,oh
            elif m=="resize_se": nw=max(MN,ow+dx);nh=(nw/ar)if lk else max(MN,oh+dy);nx,ny=ox,oy
            elif m=="resize_sw": nw=max(MN,ow-dx);nh=(nw/ar)if lk else max(MN,oh+dy);nx=ox+ow-nw;ny=oy
            elif m=="resize_ne": nw=max(MN,ow+dx);nh=(nw/ar)if lk else max(MN,oh-dy);nx=ox;ny=oy+oh-nh
            elif m=="resize_nw": nw=max(MN,ow-dx);nh=(nw/ar)if lk else max(MN,oh-dy);nx=ox+ow-nw;ny=oy+oh-nh
            else: return
            upd[0]=True
            try:
                x_var.set(f"{max(0.,nx):.2f}"); y_var.set(f"{max(0.,ny):.2f}")
                w_var.set(f"{nw:.2f}"); h_var.set(f"{nh:.2f}")
            finally: upd[0]=False
            do_render()

        # ── Aspect-ratio lock handlers ─────────────────────────
        def w_chg(*_):
            if upd[0] or not lock_var.get(): return
            try:
                wc=float(w_var.get())
                if wc>0: upd[0]=True; h_var.set(f"{wc/aspect[0]:.2f}")
            except Exception: pass
            finally: upd[0]=False

        def h_chg(*_):
            if upd[0] or not lock_var.get(): return
            try:
                hc=float(h_var.get())
                if hc>0: upd[0]=True; w_var.set(f"{hc*aspect[0]:.2f}")
            except Exception: pass
            finally: upd[0]=False

        w_var.trace_add("write", w_chg)
        h_var.trace_add("write", h_chg)
        for v in (x_var,y_var,w_var,h_var): v.trace_add("write", lambda *_: do_render())

        # Page preview var (needed by do_render above)
        prev_pg_v = tk.StringVar(value=str(self._vw_pg + 1))

        # ── Layout ────────────────────────────────────────────
        main = tk.Frame(dlg, bg=C["bg"]); main.pack(fill="both", expand=True, padx=12, pady=10)
        left = tk.Frame(main, bg=C["bg"], width=280)
        left.pack(side="left", fill="y", padx=(0,10)); left.pack_propagate(False)
        right = tk.Frame(main, bg=C["bg"]); right.pack(side="left", fill="both", expand=True)

        # ─ Left panel ─────────────────────────────────────────
        img_thumb_lbl = [None]
        img_stkref = [None]

        def pick_img():
            p = filedialog.askopenfilename(parent=dlg, title="이미지 선택",
                filetypes=[("PNG","*.png"),("이미지","*.png *.jpg *.jpeg *.bmp"),("모두","*.*")])
            if not p: return
            img_var.set(p); spil[0]=None
            try:
                im = Image.open(p).convert("RGBA"); iw,ih=im.size
                aspect[0]=iw/ih if ih>0 else 1.0
                try:
                    wc=float(w_var.get()); upd[0]=True; h_var.set(f"{wc/aspect[0]:.2f}")
                except Exception: pass
                finally: upd[0]=False
                th=im.copy(); th.thumbnail((100,100)); tw2,th2=th.size
                bg4=Image.new("RGB",(tw2,th2))
                cell=8
                for cy2 in range(0,th2,cell):
                    for cx2 in range(0,tw2,cell):
                        col2=(255,255,255) if (cx2//cell+cy2//cell)%2==0 else (204,204,204)
                        for py2 in range(cy2,min(cy2+cell,th2)):
                            for px2 in range(cx2,min(cx2+cell,tw2)): bg4.putpixel((px2,py2),col2)
                bg4.paste(th,mask=th.split()[3])
                img_stkref[0]=ImageTk.PhotoImage(bg4)
                img_thumb_lbl[0].config(image=img_stkref[0], text="", compound="left")
            except Exception as e: img_thumb_lbl[0].config(image="", text=f"오류:\n{e}")
            do_render()

        ic_s = SectionCard(left,"도장/서명 이미지"); ic_s.pack(fill="x",pady=(0,8))
        ic_s.body.columnconfigure(0,weight=1)
        centry(ic_s.body,img_var).grid(row=0,column=0,sticky="ew",padx=(0,8))
        hbtn(ic_s.body,"찾기",pick_img,C["primary"],C["pri_h"],padx=8,pady=5).grid(row=0,column=1)
        tl=tk.Label(ic_s.body,text="이미지를 선택하면 미리보기",
                    font=F_SM,fg=C["muted"],bg=C["card"],justify="left")
        tl.grid(row=1,column=0,columnspan=2,sticky="w",pady=(6,0))
        img_thumb_lbl[0]=tl

        pc_s = SectionCard(left,"적용 페이지"); pc_s.pack(fill="x",pady=(0,8))
        pages_mode=tk.StringVar(value="all"); pages_var=tk.StringVar(value="1")
        _rb=dict(font=F,bg=C["card"],activebackground=C["card"],selectcolor=C["card"])
        r1=tk.Frame(pc_s.body,bg=C["card"]); r1.pack(anchor="w")
        tk.Radiobutton(r1,text="모든 페이지",variable=pages_mode,value="all",**_rb).pack(side="left")
        r2=tk.Frame(pc_s.body,bg=C["card"]); r2.pack(anchor="w",pady=2)
        tk.Radiobutton(r2,text="특정 페이지",variable=pages_mode,value="custom",**_rb).pack(side="left")
        centry(r2,pages_var,width=10).pack(side="left",padx=(6,0))
        tk.Label(r2,text="예:1,3,5-7",font=F_SM,bg=C["card"],fg=C["muted"]).pack(side="left",padx=(4,0))
        r3=tk.Frame(pc_s.body,bg=C["card"]); r3.pack(anchor="w")
        tk.Radiobutton(r3,text="마지막 페이지",variable=pages_mode,value="last",**_rb).pack(side="left")

        oc_s = SectionCard(left,"저장 위치"); oc_s.pack(fill="x",pady=(0,8))
        oc_s.body.columnconfigure(0,weight=1)
        ov_s = tk.StringVar(value=base+"_stamped"+ext)
        centry(oc_s.body,ov_s).grid(row=0,column=0,sticky="ew",padx=(0,8))
        hbtn(oc_s.body,"찾기",lambda:self._save_dialog(ov_s),
             C["primary"],C["pri_h"],padx=8,pady=5).grid(row=0,column=1)

        sv_s=tk.StringVar(value=""); pb_s=mkpb(left); pb_s.pack(fill="x",pady=(0,3))
        tk.Label(left,textvariable=sv_s,font=F_SM,bg=C["bg"],
                 fg=C["sub"],anchor="w",wraplength=260).pack(fill="x")

        def _run_stamp():
            ip=img_var.get().strip(); out=ov_s.get().strip()
            if not ip or not os.path.isfile(ip):
                messagebox.showerror("오류","이미지 파일을 선택하세요.",parent=dlg); return
            if not out:
                messagebox.showerror("오류","저장 위치를 지정하세요.",parent=dlg); return
            try: xc=float(x_var.get());yc=float(y_var.get());wc=float(w_var.get());hc=float(h_var.get())
            except ValueError:
                messagebox.showerror("오류","위치/크기 값을 확인하세요.",parent=dlg); return
            if wc<=0 or hc<=0:
                messagebox.showerror("오류","너비와 높이는 0보다 커야 합니다.",parent=dlg); return
            mode=pages_mode.get()
            if mode=="last": pages=["last"]
            elif mode=="custom":
                try: pages=self._parse_pages(pages_var.get()); assert pages
                except Exception:
                    messagebox.showerror("오류","페이지를 올바르게 입력하세요.",parent=dlg); return
            else: pages=None
            def _wk():
                import io as _io2
                self.after(0,pb_s.start,10); self.after(0,sv_s.set,"삽입 중...")
                try:
                    doc2=fitz.open(src); tot=len(doc2)
                    if pages is None: idxs=list(range(tot))
                    elif pages==["last"]: idxs=[tot-1]
                    else: idxs=[p2-1 for p2 in pages if 1<=p2<=tot]
                    PT=self._CM_TO_PT
                    rect2=fitz.Rect(xc*PT,yc*PT,(xc+wc)*PT,(yc+hc)*PT)
                    pil_i=Image.open(ip).convert("RGBA")
                    buf2=_io2.BytesIO(); pil_i.save(buf2,format="PNG")
                    ib2=buf2.getvalue()
                    for idx2 in idxs: doc2[idx2].insert_image(rect2,stream=ib2,overlay=True)
                    doc2.save(out,garbage=1,deflate=True); doc2.close()
                    self.after(0,pb_s.stop); self.after(0,sv_s.set,"완료!")
                    self.after(0,messagebox.showinfo,"완료",
                               f"삽입 완료! {len(idxs)}페이지\n\n{out}")
                except Exception as e:
                    self.after(0,pb_s.stop); self.after(0,sv_s.set,"오류")
                    self.after(0,messagebox.showerror,"오류",str(e))
            threading.Thread(target=_wk,daemon=True).start()

        hbtn(left,"  도장/서명 삽입  ",_run_stamp,C["primary"],C["pri_h"],
             pady=10).pack(fill="x",pady=(4,0))

        # ─ Right panel: canvas preview ────────────────────────
        rv=tk.Frame(right,bg=C["card"],highlightbackground=C["border"],highlightthickness=1)
        rv.pack(fill="both",expand=True)
        rv_hdr=tk.Frame(rv,bg=C["card_hdr"]); rv_hdr.pack(fill="x")
        tk.Label(rv_hdr,text="미리보기  ·  드래그하여 이동  /  모서리 핸들로 크기 조절",
                 font=F_B,bg=C["card_hdr"],fg=C["text"],padx=12,pady=7).pack(side="left")
        pg_row=tk.Frame(rv_hdr,bg=C["card_hdr"]); pg_row.pack(side="right",padx=10)
        tk.Label(pg_row,text="페이지:",font=F_SM,bg=C["card_hdr"],fg=C["sub"]).pack(side="left")
        centry(pg_row,prev_pg_v,width=4).pack(side="left",padx=(4,0))
        hbtn(pg_row,"렌더",do_render,C["primary"],C["pri_h"],padx=7,pady=4).pack(side="left",padx=(6,0))
        tk.Frame(rv,bg=C["border"],height=1).pack(fill="x")

        rv_body=tk.Frame(rv,bg=C["card"]); rv_body.pack(fill="both",expand=True,padx=10,pady=(6,10))
        cv2=tk.Canvas(rv_body,bg=C["doc_bg"],highlightthickness=1,
                      highlightbackground=C["border"],cursor="crosshair")
        cv2.pack(fill="both",expand=True)
        cv_ref[0]=cv2

        lbl_cfg3=dict(font=F_SM,bg=C["card"],fg=C["sub"])
        nr3=tk.Frame(rv_body,bg=C["card"]); nr3.pack(anchor="w",pady=(8,0))
        for col3,(lbl3,var3) in enumerate([(("X",x_var),("Y",y_var),
                                            ("너비",w_var),("높이",h_var))[col3]
                                           for col3 in range(4)]):
            tk.Label(nr3,text=lbl3,**lbl_cfg3).grid(row=0,column=col3*3,sticky="e",padx=(16 if col3 else 0,2))
            centry(nr3,var3,width=5).grid(row=0,column=col3*3+1)
            tk.Label(nr3,text="cm",**lbl_cfg3).grid(row=0,column=col3*3+2,sticky="w",padx=(1,0))
        tk.Checkbutton(nr3,text="비율 고정",variable=lock_var,
                       font=F_SM,bg=C["card"],fg=C["sub"],
                       activebackground=C["card"],selectcolor=C["card"]
                       ).grid(row=0,column=12,padx=(14,0))

        cv2.bind("<ButtonPress-1>",  cv_press)
        cv2.bind("<B1-Motion>",      cv_drag)
        cv2.bind("<ButtonRelease-1>",lambda e: drag_m.__setitem__(0,None))
        cv2.bind("<Configure>",      lambda e: dlg.after(60,do_render))

        dlg.after(120, do_render)

    # ── 속성 편집 다이얼로그 ──────────────────────────────────
    def _vw_dlg_props(self):
        if not self._vw_require_file(): return
        src = self._vw_path
        base, ext = os.path.splitext(src)

        # Read existing metadata
        try:
            r0 = self._reader(src)
            meta0 = r0.metadata or {}
        except Exception as e:
            messagebox.showerror("오류", str(e)); return

        def _get(key):
            v = meta0.get(key, "") or ""
            return str(v).strip()

        dlg = tk.Toplevel(self)
        dlg.title("문서 속성 편집"); dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(bg=C["bg"])
        self._dlg_center(dlg, 500, 480)

        f = tk.Frame(dlg, bg=C["bg"]); f.pack(fill="both", expand=True, padx=16, pady=12)

        # File info
        ic = SectionCard(f, "파일"); ic.pack(fill="x", pady=(0, 8))
        try: n_pg = len(r0.pages); kb = os.path.getsize(src) / 1024
        except Exception: n_pg = 0; kb = 0
        tk.Label(ic.body, text=f"{os.path.basename(src)}  ·  {n_pg}페이지  ·  {kb:.1f} KB",
                 font=F_SM, bg=C["card"], fg=C["text"]).pack(anchor="w")

        # Read-only fields (shown but not editable)
        ro_meta = [
            ("제작 앱",  _get("/Producer")),
            ("생성일",   _get("/CreationDate")),
            ("수정일",   _get("/ModDate")),
        ]
        filtered = [(l, v) for l, v in ro_meta if v]
        if filtered:
            rc = SectionCard(f, "원본 정보 (읽기 전용)"); rc.pack(fill="x", pady=(0, 8))
            rc.body.columnconfigure(1, weight=1)
            for i, (lbl, val) in enumerate(filtered):
                tk.Label(rc.body, text=lbl, font=F_SM, bg=C["card"],
                         fg=C["sub"], width=10, anchor="e"
                         ).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=2)
                tk.Label(rc.body, text=val, font=F_SM, bg=C["card"],
                         fg=C["text"], anchor="w"
                         ).grid(row=i, column=1, sticky="w", pady=2)

        # Editable fields
        mc = SectionCard(f, "편집 가능 속성"); mc.pack(fill="x", pady=(0, 8))
        mc.body.columnconfigure(1, weight=1)
        fields = [
            ("제목",   "/Title"),
            ("작성자", "/Author"),
            ("주제",   "/Subject"),
            ("키워드", "/Keywords"),
            ("앱",    "/Creator"),
        ]
        vars_map: "dict[str, tk.StringVar]" = {}
        for i, (lbl, key) in enumerate(fields):
            tk.Label(mc.body, text=lbl, font=F_SM, bg=C["card"],
                     fg=C["sub"], width=7, anchor="e"
                     ).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            v = tk.StringVar(value=_get(key))
            centry(mc.body, v).grid(row=i, column=1, sticky="ew", pady=4)
            vars_map[key] = v

        # Save location
        oc = SectionCard(f, "저장 위치"); oc.pack(fill="x", pady=(0, 8))
        oc.body.columnconfigure(0, weight=1)
        ov = tk.StringVar(value=base + "_meta" + ext)
        centry(oc.body, ov).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        hbtn(oc.body, "찾기", lambda: self._save_dialog(ov),
             C["primary"], C["pri_h"], padx=8, pady=5).grid(row=0, column=1)

        sv = tk.StringVar(value="")
        pb = mkpb(f); pb.pack(fill="x", pady=(0, 3))
        tk.Label(f, textvariable=sv, font=F_SM, bg=C["bg"],
                 fg=C["sub"], anchor="w").pack(fill="x")

        def _run():
            out = ov.get().strip()
            if not out:
                messagebox.showerror("오류", "저장 위치를 지정하세요.", parent=dlg); return
            def _wk():
                self.after(0, pb.start, 10); self.after(0, sv.set, "저장 중...")
                try:
                    r = self._reader(src); w = PdfWriter()
                    for pg in r.pages: w.add_page(pg)
                    # Start from existing metadata, then apply edits
                    new_meta: dict = dict(meta0) if meta0 else {}
                    for key, var in vars_map.items():
                        val = var.get().strip()
                        if val:
                            new_meta[key] = val
                        elif key in new_meta:
                            del new_meta[key]
                    w.add_metadata(new_meta)
                    with open(out, "wb") as fh: w.write(fh)
                    self.after(0, pb.stop); self.after(0, sv.set, "완료!")
                    self.after(0, messagebox.showinfo, "완료",
                               f"속성 저장 완료!\n\n{out}")
                except Exception as e:
                    self.after(0, pb.stop); self.after(0, sv.set, "오류")
                    self.after(0, messagebox.showerror, "오류", str(e))
            threading.Thread(target=_wk, daemon=True).start()

        hbtn(f, "  속성 저장  ", _run, C["primary"], C["pri_h"],
             pady=10).pack(fill="x", pady=(4, 0))

    # ── Page-edit extract helper (dialog-context) ─────────────
    def _pg_extract_via_dialog(self, thumb: "ThumbnailGrid",
                                parent, pb, sv: tk.StringVar):
        fmt = self._ask_extract_format()
        if not fmt: return
        sources = thumb.get_selected_sources()
        if fmt == "PDF":
            out = filedialog.asksaveasfilename(
                parent=parent, title="추출 저장",
                defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
            if not out: return
            self._thread(self._pg_write, sources, out, pb, sv, "추출")
        else:
            folder = filedialog.askdirectory(parent=parent, title="이미지 저장 폴더")
            if not folder: return
            stem = os.path.splitext(os.path.basename(sources[0][0]))[0]
            self._thread(self._pg_extract_images, sources, folder, stem, fmt.lower())

    # ── TAB: 암호화 & 권한 제한 ──────────────────────────────
    def _build_enc_tab(self, parent):
        f = self._tab_frame(parent)

        c = SectionCard(f, "PDF 파일"); c.pack(fill="x", pady=(0, 10))
        self.enc_file_var = tk.StringVar()
        self._file_row(c.body, self.enc_file_var, self._enc_browse)

        self._c2_pw = SectionCard(f, "열람 비밀번호"); self._c2_pw.pack(fill="x", pady=(0, 10))
        # hint는 pack, _pw_section은 grid → 같은 부모에 혼용 불가
        # → hint를 body에 pack하고, pw 입력 영역은 별도 inner frame에 grid
        self._pw_hint = tk.Label(self._c2_pw.body, text="", font=F_SM,
                                 bg=C["card"], fg=C["sub"])
        self._pw_hint.pack(anchor="w")
        _pw_inner = tk.Frame(self._c2_pw.body, bg=C["card"])
        _pw_inner.pack(fill="x")
        self._pw_section(_pw_inner)

        # ── 권한 제한 (선택 옵션)
        c_perm = SectionCard(f, "권한 제한"); c_perm.pack(fill="x", pady=(0, 10))
        self.enc_use_perms = tk.BooleanVar(value=False)
        tk.Checkbutton(c_perm.body,
                       text="권한 제한 적용  (소유자 비밀번호로 제어)",
                       variable=self.enc_use_perms,
                       font=F, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], selectcolor=C["card"],
                       command=self._enc_perm_toggle
                       ).pack(anchor="w", pady=(0, 4))

        self._enc_perm_frame = tk.Frame(c_perm.body, bg=C["card"])
        self._enc_perm_frame.columnconfigure(0, weight=1)

        tk.Label(self._enc_perm_frame, text="소유자 비밀번호",
                 font=F_SM, bg=C["card"], fg=C["sub"]
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
        self.enc_ow_var = tk.StringVar()
        self._enc_ow_e = centry(self._enc_perm_frame, self.enc_ow_var)
        self._enc_ow_e.config(show="*")
        self._enc_ow_e.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._make_eye_btn(self._enc_perm_frame, self._enc_ow_e).grid(row=1, column=1)

        tk.Label(self._enc_perm_frame,
                 text="비워두면 권한 보호용 비밀번호가 자동 생성됩니다. (사용자 PW와 같으면 오류)",
                 font=F_SM, bg=C["card"], fg=C["muted"]
                 ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 10))

        self.enc_perm_print    = tk.BooleanVar(value=True)
        self.enc_perm_print_hq = tk.BooleanVar(value=True)
        self.enc_perm_copy     = tk.BooleanVar(value=True)
        self.enc_perm_modify   = tk.BooleanVar(value=False)
        self.enc_perm_annot    = tk.BooleanVar(value=True)
        self.enc_perm_form     = tk.BooleanVar(value=True)
        self.enc_perm_assemble = tk.BooleanVar(value=False)
        _pitems = [
            ("인쇄 허용",       self.enc_perm_print),
            ("고품질 인쇄 허용", self.enc_perm_print_hq),
            ("텍스트 복사 허용", self.enc_perm_copy),
            ("내용 수정 허용",   self.enc_perm_modify),
            ("주석 추가 허용",   self.enc_perm_annot),
            ("양식 입력 허용",   self.enc_perm_form),
            ("페이지 조립 허용", self.enc_perm_assemble),
        ]
        cb_f = tk.Frame(self._enc_perm_frame, bg=C["card"])
        cb_f.grid(row=3, column=0, columnspan=2, sticky="w")
        for i, (lbl, var) in enumerate(_pitems):
            tk.Checkbutton(cb_f, text=lbl, variable=var,
                           font=F, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).grid(row=i // 2, column=i % 2, sticky="w",
                                  padx=(0, 18), pady=2)
        # hidden until toggle is on
        # (self._enc_perm_frame not packed here)

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

        c2b = SectionCard(f, "이미지 해상도 조정"); c2b.pack(fill="x", pady=(0, 10))
        ib = c2b.body
        self.cp_img_resize = tk.BooleanVar(value=False)
        img_chk = tk.Checkbutton(ib, text="이미지 DPI 다운샘플링 적용",
                                  variable=self.cp_img_resize, font=F,
                                  bg=C["card"], fg=C["text"],
                                  activebackground=C["card"], selectcolor=C["card"],
                                  command=self._cp_toggle_dpi)
        img_chk.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self._cp_dpi_frame = tk.Frame(ib, bg=C["card"])
        self._cp_dpi_frame.grid(row=1, column=0, columnspan=4, sticky="w")
        tk.Label(self._cp_dpi_frame, text="최대 DPI:", font=F,
                 bg=C["card"], fg=C["text"]).pack(side="left")
        self.cp_dpi = tk.IntVar(value=150)
        for dpi, lbl in [(300, "300  (고품질)"), (150, "150  (균형)"), (96, "96  (소형화)")]:
            tk.Radiobutton(self._cp_dpi_frame, text=lbl, variable=self.cp_dpi, value=dpi,
                           font=F_SM, bg=C["card"], fg=C["text"],
                           activebackground=C["card"], selectcolor=C["card"]
                           ).pack(side="left", padx=(8, 0))
        tk.Label(self._cp_dpi_frame,
                 text="  ※ 텍스트·벡터는 유지됩니다",
                 font=F_SM, bg=C["card"], fg=C["muted"]).pack(side="left", padx=(12, 0))
        self._cp_toggle_dpi()  # 초기 상태 반영

        c3 = SectionCard(f, "저장 위치"); c3.pack(fill="x", pady=(0, 10))
        b3 = c3.body; b3.columnconfigure(0, weight=1)
        self.cp_out_var = tk.StringVar()
        centry(b3, self.cp_out_var).grid(row=0, column=0, sticky="ew", padx=(0,8))
        hbtn(b3, "찾아보기",
             lambda: self._save_dialog(self.cp_out_var, self.cp_file_var, "_compressed"),
             C["primary"], C["pri_h"], padx=10, pady=6).grid(row=0, column=1)

        self.cp_sv = tk.StringVar(value="PDF 파일을 선택하세요.")
        self._status_row(f, self.cp_sv, "cp_pb")

        # 압축 후 열기 옵션
        self.cp_open_after = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="압축 완료 후 파일 열기",
                       variable=self.cp_open_after, font=F_SM,
                       bg=C["bg"], fg=C["sub"],
                       activebackground=C["bg"], selectcolor=C["bg"]
                       ).pack(anchor="w", pady=(0, 6))

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
            title="파일 선택",
            filetypes=[
                ("PDF / AI 파일", "*.pdf *.ai"),
                ("PDF 파일",       "*.pdf"),
                ("Adobe Illustrator", "*.ai"),
                ("모든 파일",      "*.*"),
            ])

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

    def _enc_perm_toggle(self):
        if self.enc_use_perms.get():
            self._enc_perm_frame.pack(fill="x", pady=(0, 4))
            self._pw_hint.config(
                text="💡 권한 제한 모드: 비워두면 암호 없이 열람 가능 (편집·출력만 제한)",
                fg=C["primary"]
            )
        else:
            self._enc_perm_frame.pack_forget()
            self._pw_hint.config(text="")

    def _enc_start(self):
        from pypdf.constants import UserAccessPermissions
        src = self.enc_file_var.get().strip()
        pw1, pw2 = self.pw_var.get(), self.pw2_var.get()
        out = self.enc_out_var.get().strip()
        use_perms = self.enc_use_perms.get()

        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return

        # ── 비밀번호 검증 ────────────────────────────────────────
        if not use_perms:
            # 일반 암호화: 사용자 비밀번호 필수
            if not pw1:
                messagebox.showerror("오류", "비밀번호를 입력하세요."); return
            if pw1 != pw2:
                messagebox.showerror("오류", "비밀번호가 일치하지 않습니다."); return
            owner_pw = pw1
        else:
            # 권한 제한 모드:
            #   - 소유자 PW: 비워두면 랜덤 생성 (사용자 PW와 반드시 달라야 함)
            #   - 사용자 PW: 선택 (비워두면 암호 없이 열림)
            import secrets
            owner_pw = self.enc_ow_var.get().strip()
            if not owner_pw:
                # 비어 있으면 랜덤 생성 — 사용자 PW와 같으면 권한이 무시되므로
                # 절대 같아질 수 없도록 UUID 기반으로 생성
                owner_pw = secrets.token_hex(16)
            elif owner_pw == pw1:
                # 소유자 PW = 사용자 PW이면 PDF 뷰어가 소유자 모드로 열어 권한 무시
                messagebox.showerror("오류",
                    "소유자 비밀번호가 사용자 비밀번호와 동일합니다.\n"
                    "권한 제한을 적용하려면 서로 다른 비밀번호를 사용하세요."); return
            if pw1 and pw1 != pw2:
                messagebox.showerror("오류", "비밀번호가 일치하지 않습니다."); return

        perm_flags = None
        if use_perms:
            # 양수 방식으로 권한 플래그 계산 (~ 연산자의 정밀도 이슈 방지)
            _P = UserAccessPermissions
            _all_user_bits = int(
                _P.PRINT | _P.MODIFY | _P.EXTRACT | _P.ADD_OR_MODIFY |
                _P.FILL_FORM_FIELDS | _P.EXTRACT_TEXT_AND_GRAPHICS |
                _P.ASSEMBLE_DOC | _P.PRINT_TO_REPRESENTATION
            )
            # 예약 비트(항상 1)만 있는 기반값에서 시작
            _base = int(_P(4294967292)) & (~_all_user_bits & 0xFFFFFFFF)
            perm = _base
            if self.enc_perm_print.get():    perm |= int(_P.PRINT)
            if self.enc_perm_print_hq.get(): perm |= int(_P.PRINT_TO_REPRESENTATION)
            if self.enc_perm_copy.get():     perm |= int(_P.EXTRACT)
            if self.enc_perm_modify.get():   perm |= int(_P.MODIFY)
            if self.enc_perm_annot.get():    perm |= int(_P.ADD_OR_MODIFY)
            if self.enc_perm_form.get():     perm |= int(_P.FILL_FORM_FIELDS)
            if self.enc_perm_assemble.get(): perm |= int(_P.ASSEMBLE_DOC)
            perm_flags = _P(perm)

        self._thread(self._enc_run, src, pw1, out, self.algo_var.get(), owner_pw, perm_flags)

    def _enc_run(self, src, pw, out, algo, owner_pw, perm_flags):
        self.after(0, self.enc_pb.start, 10)
        self.after(0, self.enc_sv.set, "암호화 진행 중...")
        try:
            r = self._reader(src); w = PdfWriter()
            for pg in r.pages: w.add_page(pg)
            if r.metadata: w.add_metadata(dict(r.metadata))
            kw: dict = dict(user_password=pw, owner_password=owner_pw, algorithm=algo)
            if perm_flags is not None:
                kw["permissions_flag"] = perm_flags
            w.encrypt(**kw)
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
        fmt = self._ask_extract_format()
        if not fmt: return
        sources = self.thumb.get_selected_sources()
        if fmt == "PDF":
            out = filedialog.asksaveasfilename(
                title="추출 저장 위치", defaultextension=".pdf",
                filetypes=[("PDF 파일", "*.pdf")])
            if not out: return
            self._thread(self._pg_write, sources, out, self.pg_pb, self.pg_sv, "추출")
        else:
            folder = filedialog.askdirectory(title="이미지 저장 폴더 선택")
            if not folder: return
            stem = os.path.splitext(os.path.basename(sources[0][0]))[0]
            self._thread(self._pg_extract_images, sources, folder, stem, fmt.lower())

    def _ask_extract_format(self) -> "str | None":
        result: list = [None]
        dlg = tk.Toplevel(self)
        dlg.title("추출 형식 선택")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=C["bg"])

        tk.Label(dlg, text="추출할 파일 형식을 선택하세요",
                 font=F_B, bg=C["bg"], fg=C["text"],
                 pady=16, padx=24).pack()

        desc_f = tk.Frame(dlg, bg=C["bg"])
        desc_f.pack(padx=24, pady=(0, 6))
        tk.Label(desc_f,
                 text="JPG · PNG 선택 시 각 페이지를 이미지 파일로 저장하며\n파일명에 원본 페이지 번호가 추가됩니다.",
                 font=F_SM, bg=C["bg"], fg=C["sub"], justify="center").pack()

        btn_f = tk.Frame(dlg, bg=C["bg"])
        btn_f.pack(padx=24, pady=(8, 6))
        for fmt, bg, bgh, label in [
            ("PDF", C["primary"], C["pri_h"], "PDF\n단일 파일"),
            ("JPG", C["success"], C["suc_h"], "JPG\n이미지"),
            ("PNG", C["success"], C["suc_h"], "PNG\n이미지"),
        ]:
            def _pick(f=fmt):
                result[0] = f; dlg.destroy()
            hbtn(btn_f, label, _pick, bg, bgh,
                 padx=20, pady=10).pack(side="left", padx=6)

        cancel_f = tk.Frame(dlg, bg=C["bg"])
        cancel_f.pack(pady=(0, 14))
        hbtn(cancel_f, "취소", dlg.destroy,
             C["border"], "#CBD5E1", C["text"], padx=14, pady=6).pack()

        self.update_idletasks(); dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - dlg.winfo_reqwidth())  // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")
        dlg.wait_window()
        return result[0]

    def _pg_extract_images(self, sources: list, folder: str, stem: str, ext: str):
        self.after(0, self.pg_pb.start, 10)
        self.after(0, self.pg_sv.set, f"이미지 추출 중 ({ext.upper()})...")
        try:
            zoom = 200 / 72
            mat  = fitz.Matrix(zoom, zoom)
            for path, orig_idx in sources:
                doc  = fitz.open(path)
                page = doc[orig_idx]
                pix  = page.get_pixmap(matrix=mat, alpha=False)
                img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_num = orig_idx + 1
                fname = f"{stem}_p{page_num:03d}.{ext}"
                out_path = os.path.join(folder, fname)
                if ext == "jpg":
                    img.save(out_path, format="JPEG", quality=92, optimize=True)
                else:
                    img.save(out_path, format="PNG", optimize=True)
                doc.close()
            self.after(0, self._ok, self.pg_pb, self.pg_sv,
                       "완료",
                       f"{len(sources)}페이지 {ext.upper()} 추출 완료!\n\n폴더:\n{folder}")
        except Exception as e:
            self.after(0, self._err, self.pg_pb, self.pg_sv, e)

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
            readers = []  # write 완료 전까지 모든 reader를 살려둠
            for p in files:
                r = self._reader(p)
                readers.append(r)
                w.append(r)  # add_page 대신 append() — 크로스 레퍼런스·리소스 전체 복사
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
    def _cp_toggle_dpi(self):
        state = "normal" if self.cp_img_resize.get() else "disabled"
        for w in self._cp_dpi_frame.winfo_children():
            try: w.config(state=state)
            except tk.TclError: pass

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
                     self.cp_meta.get(), self.cp_level.get(),
                     self.cp_img_resize.get(), self.cp_dpi.get(),
                     self.cp_open_after.get())

    def _cp_run(self, src, out, streams, dedup, rm_meta, level, img_resize, max_dpi, open_after=False):
        self.after(0, self.cp_pb.start, 10)
        self.after(0, self.cp_sv.set, "압축 중...")
        try:
            import io as _io
            fitz.TOOLS.mupdf_display_errors(False)

            # ── fitz 단일 엔진으로 통합 ──────────────────────────────────
            # fitz.save() 파라미터:
            #   deflate=True       : 미압축 스트림만 FlateDecode 적용 (이미 압축된 스트림 건너뜀)
            #   deflate_images=False: JPEG 등 이미 압축된 이미지 스트림 재압축 안 함
            #   deflate_fonts=True : 미압축 폰트 스트림만 압축
            #   garbage=4          : 미참조·중복 객체 제거 (dedup 역할)
            #   clean=True         : xref 테이블 재구성으로 손상된 참조 복구
            doc = fitz.open(src)

            # 이미지 DPI 다운샘플링
            if img_resize:
                seen: set[int] = set()
                for page in doc:
                    for img_info in page.get_images(full=True):
                        xref = img_info[0]
                        if xref in seen:
                            continue
                        seen.add(xref)
                        try:
                            # fitz.Pixmap(doc, xref): /Decode 배열·컬러스페이스 모두 적용
                            # → extract_image() 대신 사용해야 색상 반전 방지
                            pix_src = fitz.Pixmap(doc, xref)

                            # CMYK·Gray·Indexed 등 RGB 외 컬러스페이스 변환
                            if pix_src.colorspace and pix_src.colorspace != fitz.csRGB:
                                pix_src = fitz.Pixmap(fitz.csRGB, pix_src)

                            w_px, h_px = pix_src.width, pix_src.height
                            rect = page.rect
                            est_dpi = max(
                                w_px / max(rect.width  / 72, 0.01),
                                h_px / max(rect.height / 72, 0.01),
                            )
                            if est_dpi <= max_dpi:
                                continue

                            scale = max_dpi / est_dpi
                            new_w = max(1, int(w_px * scale))
                            new_h = max(1, int(h_px * scale))

                            # fitz → PIL (PNG 경유: 알파 채널 보존)
                            img = Image.open(_io.BytesIO(pix_src.tobytes("png")))

                            # 알파 채널 처리: 흰색 배경으로 합성 (JPEG는 투명 미지원)
                            if img.mode in ("RGBA", "LA"):
                                bg = Image.new("RGB", img.size, (255, 255, 255))
                                bg.paste(img, mask=img.split()[-1])
                                img = bg
                            elif img.mode != "RGB":
                                img = img.convert("RGB")

                            img = img.resize((new_w, new_h), Image.LANCZOS)
                            buf = _io.BytesIO()
                            img.save(buf, format="JPEG", quality=85, optimize=True)
                            page.replace_image(xref, pixmap=fitz.Pixmap(_io.BytesIO(buf.getvalue())))
                        except Exception:
                            continue

            # 메타데이터 제거
            if rm_meta:
                doc.set_metadata({})

            doc.save(
                out,
                garbage=4 if dedup else 1,   # 4=중복·미참조 객체 완전 제거
                deflate=streams,              # 미압축 스트림만 FlateDecode (이미 압축된 건 스킵)
                deflate_images=False,         # JPEG/PNG 등 이미 압축된 이미지 재압축 방지
                deflate_fonts=streams,        # 폰트 스트림도 동일 정책
                clean=True,                   # xref 재구성
                no_new_id=True,
            )
            doc.close()

            orig_kb = os.path.getsize(src) / 1024
            out_kb  = os.path.getsize(out) / 1024
            ratio   = (1 - out_kb / orig_kb) * 100 if orig_kb else 0
            msg = (f"압축 완료!\n\n원본:  {orig_kb:.1f} KB\n"
                   f"결과:  {out_kb:.1f} KB\n절감:  {ratio:.1f}%\n\n저장 위치:\n{out}")
            self.after(0, self.cp_pb.stop)
            self.after(0, self.cp_sv.set,
                       f"완료: {orig_kb:.1f} KB → {out_kb:.1f} KB ({ratio:.1f}% 절감)")
            self.after(0, messagebox.showinfo, "완료", msg)
            if open_after:
                import subprocess
                self.after(200, lambda: subprocess.Popen(
                    ["cmd", "/c", "start", "", out] if os.name == "nt"
                    else ["open", out] if sys.platform == "darwin"
                    else ["xdg-open", out]
                ))
        except Exception as e:
            self.after(0, self._err, self.cp_pb, self.cp_sv, e)


    # ── TAB: 정보 ─────────────────────────────────────────────
    @staticmethod
    def _make_eye_btn(parent, entry: tk.Entry) -> tk.Button:
        """Show/Hide 토글 버튼을 생성하고 반환합니다."""
        state = [False]
        def toggle():
            state[0] = not state[0]
            entry.config(show="" if state[0] else "*")
            btn.config(text="Hide" if state[0] else "Show")
        btn = hbtn(parent, "Show", toggle,
                   C["border"], "#CBD5E1", C["text"], padx=10, pady=6)
        return btn


    # ── TAB: 도장/서명 ────────────────────────────────────────
    _CM_TO_PT  = 28.3465
    _CV_HDL_R  = 7

    def _build_stamp_tab(self, parent):
        # parent는 FlatNotebook 프레임 → fill="both", expand=True 로 팩됨
        # _tab_frame 없이 직접 사용해야 캔버스가 윈도우 크기를 따라 확장됨
        parent.configure(bg=C["bg"])
        main = tk.Frame(parent, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=12)

        left  = tk.Frame(main, bg=C["bg"], width=275)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        right = tk.Frame(main, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        # ═══ LEFT ══════════════════════════════════════════
        c1 = SectionCard(left, "PDF 파일"); c1.pack(fill="x", pady=(0, 8))
        self.stamp_pdf_var = tk.StringVar()
        self._file_row(c1.body, self.stamp_pdf_var, self._stamp_pdf_browse)
        self._stamp_pdf_info = tk.Label(c1.body, text="", font=F_SM,
                                         bg=C["card"], fg=C["sub"])
        self._stamp_pdf_info.grid(row=1, column=0, columnspan=2,
                                   sticky="w", pady=(4, 0))

        c2 = SectionCard(left, "도장 / 서명 이미지 (PNG)")
        c2.pack(fill="x", pady=(0, 8))
        self.stamp_img_var = tk.StringVar()
        self._file_row(c2.body, self.stamp_img_var, self._stamp_img_browse)
        self._stamp_thumb_lbl = tk.Label(
            c2.body, bg=C["card"],
            text="이미지를 선택하면\n미리보기가 표시됩니다.",
            font=F_SM, fg=C["muted"], justify="left")
        self._stamp_thumb_lbl.grid(row=1, column=0, columnspan=2,
                                    sticky="w", pady=(8, 0))

        c3 = SectionCard(left, "적용 페이지"); c3.pack(fill="x", pady=(0, 8))
        self.stamp_pages_mode = tk.StringVar(value="all")
        _rb = dict(font=F, bg=C["card"],
                   activebackground=C["card"], selectcolor=C["card"])
        r1 = tk.Frame(c3.body, bg=C["card"]); r1.pack(anchor="w")
        tk.Radiobutton(r1, text="모든 페이지",
                       variable=self.stamp_pages_mode, value="all", **_rb
                       ).pack(side="left")
        r2 = tk.Frame(c3.body, bg=C["card"]); r2.pack(anchor="w", pady=4)
        tk.Radiobutton(r2, text="특정 페이지",
                       variable=self.stamp_pages_mode, value="custom", **_rb
                       ).pack(side="left")
        self.stamp_pages_var = tk.StringVar(value="1")
        centry(r2, self.stamp_pages_var, width=10
               ).pack(side="left", padx=(6, 0))
        tk.Label(r2, text="예: 1,3,5-7", font=F_SM,
                 bg=C["card"], fg=C["muted"]
                 ).pack(side="left", padx=(6, 0))
        r3 = tk.Frame(c3.body, bg=C["card"]); r3.pack(anchor="w")
        tk.Radiobutton(r3, text="마지막 페이지",
                       variable=self.stamp_pages_mode, value="last", **_rb
                       ).pack(side="left")

        c5 = SectionCard(left, "저장 위치"); c5.pack(fill="x", pady=(0, 12))
        self.stamp_out_var = tk.StringVar()
        self._file_row(c5.body, self.stamp_out_var,
                       lambda: self._save_dialog(self.stamp_out_var,
                                                  self.stamp_pdf_var))

        self.stamp_sv = tk.StringVar(value="PDF와 이미지 파일을 선택하세요.")
        self._status_row(left, self.stamp_sv, "stamp_pb")
        self._save_btn(left, "  도장/서명 삽입", self._stamp_start)

        # ═══ RIGHT ═════════════════════════════════════════
        # 확장형 카드 (SectionCard 대신 직접 구성 — fill="both" 가능하게)
        rv = tk.Frame(right, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        rv.pack(fill="both", expand=True)

        # 카드 헤더
        rv_hdr = tk.Frame(rv, bg=C["card_hdr"])
        rv_hdr.pack(fill="x")
        tk.Label(rv_hdr, text="미리보기 · 위치 / 크기 편집",
                 font=F_B, bg=C["card_hdr"], fg=C["text"],
                 padx=14, pady=9).pack(side="left")

        # 페이지 선택 + 렌더링 (헤더 오른쪽)
        pg_row = tk.Frame(rv_hdr, bg=C["card_hdr"]); pg_row.pack(side="right", padx=10)
        tk.Label(pg_row, text="페이지:", font=F_SM,
                 bg=C["card_hdr"], fg=C["sub"]).pack(side="left")
        self._stamp_prev_pg = tk.StringVar(value="1")
        centry(pg_row, self._stamp_prev_pg, width=4
               ).pack(side="left", padx=(5, 0))
        hbtn(pg_row, "렌더링", self._stamp_do_render,
             C["primary"], C["pri_h"], padx=8, pady=4
             ).pack(side="left", padx=(6, 0))

        tk.Frame(rv, bg=C["border"], height=1).pack(fill="x")

        # 카드 본문 — 캔버스 + 수치 입력
        rv_body = tk.Frame(rv, bg=C["card"])
        rv_body.pack(fill="both", expand=True, padx=12, pady=(10, 10))

        # 힌트 레이블
        tk.Label(rv_body,
                 text="도장을 드래그하여 이동  ·  모서리 핸들로 크기 조절",
                 font=F_SM, bg=C["card"], fg=C["muted"]
                 ).pack(anchor="w", pady=(0, 6))

        # 캔버스
        self._stamp_cv = tk.Canvas(rv_body, bg=C["doc_bg"],
                                    highlightthickness=1,
                                    highlightbackground=C["border"],
                                    cursor="crosshair")
        self._stamp_cv.pack(fill="both", expand=True, pady=(0, 10))
        self._stamp_cv.bind("<ButtonPress-1>",  self._cv_press)
        self._stamp_cv.bind("<B1-Motion>",       self._cv_drag)
        self._stamp_cv.bind("<ButtonRelease-1>", self._cv_release)
        self._stamp_cv.bind("<Configure>",
                             lambda e: self.after(60, self._stamp_do_render))

        # 수치 입력 행 (캔버스 아래 고정)
        self.stamp_x_var      = tk.StringVar(value="1.0")
        self.stamp_y_var      = tk.StringVar(value="1.0")
        self.stamp_w_var      = tk.StringVar(value="3.0")
        self.stamp_h_var      = tk.StringVar(value="3.0")
        self.stamp_lock_ratio = tk.BooleanVar(value=True)
        self._stamp_aspect    = [1.0]
        self._stamp_upd_flag  = [False]

        nr = tk.Frame(rv_body, bg=C["card"]); nr.pack(anchor="w")
        lbl_cfg = dict(font=F_SM, bg=C["card"], fg=C["sub"])
        for col, (lbl, var) in enumerate([
            ("X", self.stamp_x_var), ("Y", self.stamp_y_var),
            ("너비", self.stamp_w_var), ("높이", self.stamp_h_var),
        ]):
            tk.Label(nr, text=lbl, **lbl_cfg).grid(
                row=0, column=col * 3, sticky="e",
                padx=(20 if col else 0, 3))
            centry(nr, var, width=6).grid(row=0, column=col * 3 + 1)
            tk.Label(nr, text="cm", **lbl_cfg).grid(
                row=0, column=col * 3 + 2, sticky="w", padx=(2, 0))
        tk.Checkbutton(nr, text="비율 고정",
                       variable=self.stamp_lock_ratio,
                       font=F_SM, bg=C["card"], fg=C["sub"],
                       activebackground=C["card"], selectcolor=C["card"]
                       ).grid(row=0, column=12, padx=(14, 0))

        self.stamp_w_var.trace_add("write", lambda *_: self._stamp_w_changed())
        self.stamp_h_var.trace_add("write", lambda *_: self._stamp_h_changed())
        for v in (self.stamp_x_var, self.stamp_y_var,
                  self.stamp_w_var, self.stamp_h_var):
            v.trace_add("write", lambda *_: self._stamp_cv_refresh())

        # 캔버스 내부 상태
        self._cv_scale      = 1.0
        self._cv_off_x      = 0.0
        self._cv_off_y      = 0.0
        self._cv_page_w     = 595.0
        self._cv_page_h     = 842.0
        self._cv_drag_mode  = None
        self._cv_drag_start = (0, 0)
        self._cv_drag_base  = (1.0, 1.0, 3.0, 3.0)
        self._cv_page_tk    = None
        self._cv_stamp_tk   = None
        self._cv_stamp_pil  = None

    # ── 도장/서명 handlers ────────────────────────────────────
    def _stamp_pdf_browse(self):
        p = self._open_pdf()
        if not p: return
        self.stamp_pdf_var.set(p)
        base, ext = os.path.splitext(p)
        self.stamp_out_var.set(base + "_stamped" + ext)
        try:
            n = len(self._reader(p).pages)
            self._stamp_pdf_info.config(text=f"총 {n}페이지")
        except Exception:
            pass
        self.after(120, self._stamp_do_render)

    def _stamp_img_browse(self):
        path = filedialog.askopenfilename(
            title="도장/서명 이미지 선택",
            filetypes=[("PNG 이미지", "*.png"),
                       ("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.gif"),
                       ("모든 파일",   "*.*")])
        if not path: return
        self.stamp_img_var.set(path)
        self._cv_stamp_pil = None
        try:
            img = Image.open(path).convert("RGBA")
            w, h = img.size
            self._stamp_aspect[0] = w / h if h > 0 else 1.0
            try:
                w_cm = float(self.stamp_w_var.get())
                self._stamp_upd_flag[0] = True
                self.stamp_h_var.set(f"{w_cm / self._stamp_aspect[0]:.2f}")
                self._stamp_upd_flag[0] = False
            except Exception:
                pass
            thumb = img.copy(); thumb.thumbnail((120, 120))
            cell = 8; tw, th = thumb.size
            bg = Image.new("RGB", (tw, th))
            for cy in range(0, th, cell):
                for cx in range(0, tw, cell):
                    col = (255, 255, 255) \
                          if (cx // cell + cy // cell) % 2 == 0 \
                          else (204, 204, 204)
                    for py in range(cy, min(cy + cell, th)):
                        for px2 in range(cx, min(cx + cell, tw)):
                            bg.putpixel((px2, py), col)
            bg.paste(thumb, mask=thumb.split()[3])
            self._stamp_tk = ImageTk.PhotoImage(bg)
            self._stamp_thumb_lbl.config(image=self._stamp_tk, text="",
                                          compound="left")
        except Exception as e:
            self._stamp_thumb_lbl.config(image="",
                                          text=f"미리보기 오류:\n{e}")
        self.after(120, self._stamp_do_render)

    def _stamp_w_changed(self):
        if self._stamp_upd_flag[0] or not self.stamp_lock_ratio.get(): return
        try:
            w = float(self.stamp_w_var.get())
            if w > 0:
                self._stamp_upd_flag[0] = True
                self.stamp_h_var.set(f"{w / self._stamp_aspect[0]:.2f}")
        except Exception:
            pass
        finally:
            self._stamp_upd_flag[0] = False

    def _stamp_h_changed(self):
        if self._stamp_upd_flag[0] or not self.stamp_lock_ratio.get(): return
        try:
            h = float(self.stamp_h_var.get())
            if h > 0:
                self._stamp_upd_flag[0] = True
                self.stamp_w_var.set(f"{h * self._stamp_aspect[0]:.2f}")
        except Exception:
            pass
        finally:
            self._stamp_upd_flag[0] = False

    # ── 좌표 변환 ─────────────────────────────────────────────
    def _cm_to_cv(self, x_cm: float, y_cm: float):
        pt = self._CM_TO_PT
        return (x_cm * pt * self._cv_scale + self._cv_off_x,
                y_cm * pt * self._cv_scale + self._cv_off_y)

    def _cv_to_cm(self, cx: float, cy: float):
        pt = self._CM_TO_PT
        return ((cx - self._cv_off_x) / (self._cv_scale * pt),
                (cy - self._cv_off_y) / (self._cv_scale * pt))

    # ── 캔버스 렌더링 ─────────────────────────────────────────
    def _stamp_do_render(self):
        cv = self._stamp_cv
        cv.delete("all")
        cw = cv.winfo_width(); ch = cv.winfo_height()
        if cw < 10 or ch < 10:
            return

        src = self.stamp_pdf_var.get().strip()
        if not src or not os.path.isfile(src):
            cv.create_text(cw // 2, ch // 2,
                           text="PDF 파일을 선택하면\n미리보기가 표시됩니다.",
                           fill="#BBBBBB", font=F_SM, justify="center")
            return

        try:
            pg_idx = max(0, int(self._stamp_prev_pg.get() or "1") - 1)
            doc    = fitz.open(src)
            pg_idx = min(pg_idx, len(doc) - 1)
            page   = doc[pg_idx]
            pw = page.rect.width; ph = page.rect.height
            pad   = 14
            scale = min((cw - pad * 2) / pw, (ch - pad * 2) / ph)
            self._cv_scale  = scale
            self._cv_page_w = pw; self._cv_page_h = ph
            rpw = int(pw * scale); rph = int(ph * scale)
            self._cv_off_x = (cw - rpw) / 2
            self._cv_off_y = (ch - rph) / 2
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pil_pg = Image.frombytes("RGB",
                                      [pix.width, pix.height], pix.samples)
            self._cv_page_tk = ImageTk.PhotoImage(pil_pg)
            doc.close()
            cv.create_image(self._cv_off_x, self._cv_off_y,
                            anchor="nw", image=self._cv_page_tk)
        except Exception as e:
            cv.create_text(cw // 2, ch // 2,
                           text=f"렌더링 실패:\n{e}",
                           fill="#FF8888", font=F_SM, justify="center")
            return

        img_path = self.stamp_img_var.get().strip()
        if not img_path or not os.path.isfile(img_path):
            cv.create_text(cw // 2, ch - 24,
                           text="이미지를 선택하면 도장 위치가 표시됩니다.",
                           fill="#AAAAAA", font=F_SM)
            return

        try:
            x_cm = float(self.stamp_x_var.get())
            y_cm = float(self.stamp_y_var.get())
            w_cm = float(self.stamp_w_var.get())
            h_cm = float(self.stamp_h_var.get())
        except ValueError:
            return

        x0, y0 = self._cm_to_cv(x_cm, y_cm)
        x1, y1 = self._cm_to_cv(x_cm + w_cm, y_cm + h_cm)
        sw = max(1, int(x1 - x0)); sh = max(1, int(y1 - y0))

        try:
            if self._cv_stamp_pil is None:
                self._cv_stamp_pil = Image.open(img_path).convert("RGBA")
            rs     = self._cv_stamp_pil.resize((sw, sh), Image.LANCZOS)
            bg_img = Image.new("RGB", (sw, sh), (210, 210, 210))
            bg_img.paste(rs, mask=rs.split()[3])
            self._cv_stamp_tk = ImageTk.PhotoImage(bg_img)
            cv.create_image(x0, y0, anchor="nw",
                            image=self._cv_stamp_tk, tags="stamp")
        except Exception:
            cv.create_rectangle(x0, y0, x1, y1,
                                fill="#FF000033", outline="#FF4444",
                                tags="stamp")

        cv.create_rectangle(x0, y0, x1, y1,
                            outline="#3B82F6", width=2,
                            dash=(6, 3), tags="sel_border")
        hr = self._CV_HDL_R
        for tag, hx, hy in [("nw", x0, y0), ("ne", x1, y0),
                              ("sw", x0, y1), ("se", x1, y1)]:
            cv.create_rectangle(hx - hr, hy - hr, hx + hr, hy + hr,
                                fill="#3B82F6", outline="#FFFFFF", width=1,
                                tags=("handle", f"hdl_{tag}"))

    def _stamp_cv_refresh(self):
        if self._stamp_upd_flag[0]: return
        if not hasattr(self, "_stamp_cv"): return
        self._stamp_do_render()

    # ── 드래그/리사이즈 ───────────────────────────────────────
    def _cv_press(self, event):
        x, y = event.x, event.y
        cv   = self._stamp_cv
        hr   = self._CV_HDL_R + 3
        for item in reversed(cv.find_overlapping(x-hr, y-hr, x+hr, y+hr)):
            for tag in cv.gettags(item):
                if tag.startswith("hdl_"):
                    self._cv_start_drag(f"resize_{tag[4:]}", x, y)
                    return
        for item in reversed(cv.find_overlapping(x-3, y-3, x+3, y+3)):
            if any(t in cv.gettags(item) for t in ("stamp", "sel_border")):
                self._cv_start_drag("move", x, y)
                return
        self._cv_drag_mode = None

    def _cv_start_drag(self, mode: str, x: int, y: int):
        self._cv_drag_mode  = mode
        self._cv_drag_start = (x, y)
        try:
            self._cv_drag_base = (
                float(self.stamp_x_var.get()), float(self.stamp_y_var.get()),
                float(self.stamp_w_var.get()), float(self.stamp_h_var.get()),
            )
        except ValueError:
            self._cv_drag_mode = None; return
        self._stamp_cv.config(cursor={
            "move": "fleur",
            "resize_se": "size_nw_se", "resize_nw": "size_nw_se",
            "resize_ne": "size_ne_sw", "resize_sw": "size_ne_sw",
        }.get(mode, "crosshair"))

    def _cv_drag(self, event):
        mode = self._cv_drag_mode
        if not mode: return
        pt = self._CM_TO_PT; sc = self._cv_scale
        if sc == 0: return
        dx = (event.x - self._cv_drag_start[0]) / (sc * pt)
        dy = (event.y - self._cv_drag_start[1]) / (sc * pt)
        ox, oy, ow, oh = self._cv_drag_base
        locked = self.stamp_lock_ratio.get()
        ar     = max(self._stamp_aspect[0], 0.001)
        MIN    = 0.2
        if mode == "move":
            nx, ny, nw, nh = max(0.0, ox+dx), max(0.0, oy+dy), ow, oh
        elif mode == "resize_se":
            nw = max(MIN, ow+dx); nh = (nw/ar) if locked else max(MIN, oh+dy)
            nx, ny = ox, oy
        elif mode == "resize_sw":
            nw = max(MIN, ow-dx); nh = (nw/ar) if locked else max(MIN, oh+dy)
            nx = ox+ow-nw; ny = oy
        elif mode == "resize_ne":
            nw = max(MIN, ow+dx); nh = (nw/ar) if locked else max(MIN, oh-dy)
            nx = ox; ny = oy+oh-nh
        elif mode == "resize_nw":
            nw = max(MIN, ow-dx); nh = (nw/ar) if locked else max(MIN, oh-dy)
            nx = ox+ow-nw; ny = oy+oh-nh
        else:
            return
        self._stamp_upd_flag[0] = True
        try:
            self.stamp_x_var.set(f"{max(0.0, nx):.2f}")
            self.stamp_y_var.set(f"{max(0.0, ny):.2f}")
            self.stamp_w_var.set(f"{nw:.2f}")
            self.stamp_h_var.set(f"{nh:.2f}")
        finally:
            self._stamp_upd_flag[0] = False
        self._stamp_do_render()

    def _cv_release(self, event):
        self._cv_drag_mode = None
        self._stamp_cv.config(cursor="crosshair")

    @staticmethod
    def _parse_pages(s: str) -> list:
        pages = []
        for part in s.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                pages.extend(range(int(a.strip()), int(b.strip()) + 1))
            elif part:
                pages.append(int(part))
        return sorted(set(pages))

    def _stamp_start(self):
        import io as _sio
        src = self.stamp_pdf_var.get().strip()
        img = self.stamp_img_var.get().strip()
        out = self.stamp_out_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요."); return
        if not img or not os.path.isfile(img):
            messagebox.showerror("오류", "이미지 파일을 선택하세요."); return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요."); return
        try:
            x_cm = float(self.stamp_x_var.get())
            y_cm = float(self.stamp_y_var.get())
            w_cm = float(self.stamp_w_var.get())
            h_cm = float(self.stamp_h_var.get())
        except ValueError:
            messagebox.showerror("오류", "위치/크기 값을 올바르게 입력하세요."); return
        if w_cm <= 0 or h_cm <= 0:
            messagebox.showerror("오류", "너비와 높이는 0보다 커야 합니다."); return
        mode = self.stamp_pages_mode.get()
        if mode == "last":
            pages = "last"
        elif mode == "custom":
            try:
                pages = self._parse_pages(self.stamp_pages_var.get())
                if not pages: raise ValueError
            except Exception:
                messagebox.showerror("오류",
                    "페이지를 올바르게 입력하세요.\n예: 1, 3, 5-7"); return
        else:
            pages = None
        self._thread(self._stamp_run, src, img, out, x_cm, y_cm, w_cm, h_cm, pages)

    def _stamp_run(self, src, img_path, out, x_cm, y_cm, w_cm, h_cm, pages):
        import io as _sio
        self.after(0, self.stamp_pb.start, 10)
        self.after(0, self.stamp_sv.set, "삽입 중...")
        try:
            doc   = fitz.open(src); total = len(doc)
            if pages is None:
                idxs = list(range(total))
            elif pages == "last":
                idxs = [total - 1]
            else:
                idxs = [p-1 for p in pages if 1 <= p <= total]
            pt   = self._CM_TO_PT
            rect = fitz.Rect(x_cm*pt, y_cm*pt,
                             (x_cm+w_cm)*pt, (y_cm+h_cm)*pt)
            pil_img = Image.open(img_path).convert("RGBA")
            buf = _sio.BytesIO(); pil_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            for idx in idxs:
                doc[idx].insert_image(rect, stream=img_bytes, overlay=True)
            doc.save(out, garbage=1, deflate=True); doc.close()
            n = len(idxs)
            self.after(0, self._ok, self.stamp_pb, self.stamp_sv,
                       "완료",
                       f"삽입 완료!\n적용 페이지: {n}페이지\n\n저장 위치:\n{out}")
        except Exception as e:
            self.after(0, self._err, self.stamp_pb, self.stamp_sv, e)


    def _build_about_tab(self, parent):
        # _tab_frame 없이 parent 직접 사용 → place(relx/rely) 정상 동작
        parent.configure(bg=C["bg"])

        inner = tk.Frame(parent, bg=C["card"],
                         highlightbackground=C["border"], highlightthickness=1)
        inner.place(relx=0.5, rely=0.5, anchor="center", width=460)

        icon_f = tk.Frame(inner, bg=C["chrome"], height=80)
        icon_f.pack(fill="x")
        icon_row = tk.Frame(icon_f, bg=C["chrome"])
        icon_row.place(relx=0.5, rely=0.5, anchor="center")
        self._icon_label(icon_row, 36, C["chrome"]).pack(side="left", padx=(0, 10))
        tk.Label(icon_row, text="PDF.ikkcu Tools", font=(MG[0], 18, "bold"),
                 bg=C["chrome"], fg="white").pack(side="left")

        body = tk.Frame(inner, bg=C["card"])
        body.pack(fill="x", padx=32, pady=24)

        tk.Label(body, text="PDF.ikkcu Tools",
                 font=(MG[0], FS, "bold"), bg=C["card"], fg=C["text"]
                 ).pack(anchor="w")
        tk.Label(body,
                 text="PDF 암호화 · 페이지 편집 · 병합 · 나누기 · 압축 · 도장 삽입을\n"
                      "하나의 앱으로 처리하는 무료 PDF 도구입니다.",
                 font=F_SM, bg=C["card"], fg=C["sub"],
                 justify="left", wraplength=400
                 ).pack(anchor="w", pady=(6, 0))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=18)

        for label, value, url in [
            ("개발",     "ikkcu.com",  APP_URL),
            ("버전",     "2.0.0",      None),
            ("라이선스", "Freeware",   None),
        ]:
            row = tk.Frame(body, bg=C["card"]); row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=F_SM, width=9,
                     bg=C["card"], fg=C["sub"], anchor="w").pack(side="left")
            if url:
                lnk = tk.Label(row, text=value,
                                font=(MG[0], FS_SM, "underline"),
                                bg=C["card"], fg=C["primary"], cursor="hand2")
                lnk.pack(side="left")
                lnk.bind("<Button-1>", lambda _, u=url: webbrowser.open(u))
            else:
                tk.Label(row, text=value, font=F_SM,
                         bg=C["card"], fg=C["text"]).pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=18)

        bmc_btn = tk.Button(
            body, text="  Ko-fi로 후원하기",
            font=(MG[0], FS, "bold"),
            bg="#FF5E5B", fg="white",
            relief="flat", bd=0, padx=18, pady=10,
            cursor="hand2",
            activebackground="#E04E4B", activeforeground="white",
            command=lambda: webbrowser.open(BMC_URL),
        )
        bmc_btn.pack(fill="x")
        bmc_btn.bind("<Enter>", lambda _: bmc_btn.config(bg="#E04E4B"))
        bmc_btn.bind("<Leave>", lambda _: bmc_btn.config(bg="#FF5E5B"))

        tk.Label(body,
                 text="이 앱이 유용하셨다면 커피 한 잔으로 응원해 주세요 :)",
                 font=F_SM, bg=C["card"], fg=C["muted"]
                 ).pack(anchor="center", pady=(8, 0))

        tk.Label(inner, text="© 2025 ikkcu.com — All rights reserved",
                 font=F_SM, bg=C["card"], fg=C["muted"], pady=12
                 ).pack()



if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app = PDFIkkcu()
    app.mainloop()
