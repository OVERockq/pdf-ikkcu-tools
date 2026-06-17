"""
PDF 암호화 툴 v2
의존성: pip install -r requirements.txt
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading

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
    "border":    "#E2E8F0",
    "text":      "#1E293B",
    "sub":       "#64748B",
    "badge_bg":  "#EFF6FF",
    "badge_fg":  "#1D4ED8",
}

FONT       = ("Malgun Gothic", 10)
FONT_B     = ("Malgun Gothic", 10, "bold")
FONT_SM    = ("Malgun Gothic", 9)
FONT_TITLE = ("Malgun Gothic", 14, "bold")


def _hover_btn(parent, text, cmd, bg, hover_bg, fg="white"):
    b = tk.Button(
        parent, text=text, command=cmd,
        font=FONT_B, bg=bg, fg=fg,
        relief="flat", bd=0, padx=12, pady=7,
        cursor="hand2", activebackground=hover_bg, activeforeground=fg,
    )
    b.bind("<Enter>", lambda _: b.config(bg=hover_bg))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b


class SectionCard(tk.Frame):
    def __init__(self, parent, title, icon="", **kw):
        super().__init__(parent, bg=C["card"], relief="flat", bd=0, **kw)
        hdr = tk.Frame(self, bg=C["card"])
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        lbl = (icon + "  " + title) if icon else title
        tk.Label(hdr, text=lbl, font=FONT_B, bg=C["card"], fg=C["text"]).pack(side="left")
        self._body = tk.Frame(self, bg=C["card"])
        self._body.pack(fill="x", padx=16, pady=(0, 16))

    @property
    def body(self):
        return self._body


class PDFEncryptorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 암호화 툴")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self._show_pw = False
        self._show_pw2 = False
        self._build_ui()
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - self.winfo_width())  // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        outer = tk.Frame(self, bg=C["bg"], padx=20, pady=20)
        outer.pack(fill="both", expand=True)

        # 헤더
        hdr = tk.Frame(outer, bg=C["bg"])
        hdr.pack(fill="x", pady=(0, 14))
        tk.Label(hdr, text="PDF 암호화 툴", font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Label(hdr, text=" v2.0 ", font=FONT_SM,
                 bg=C["badge_bg"], fg=C["badge_fg"],
                 padx=4, pady=2).pack(side="left", padx=(8, 0))

        # 카드 1: 파일
        c1 = SectionCard(outer, "PDF 파일", "")
        c1.pack(fill="x", pady=(0, 10))
        self._build_file_row(c1.body)

        # 카드 2: 비밀번호
        c2 = SectionCard(outer, "비밀번호 설정", "")
        c2.pack(fill="x", pady=(0, 10))
        self._build_password_rows(c2.body)

        # 카드 3: 옵션
        c3 = SectionCard(outer, "암호화 강도", "")
        c3.pack(fill="x", pady=(0, 10))
        self._build_options(c3.body)

        # 카드 4: 저장
        c4 = SectionCard(outer, "저장 위치", "")
        c4.pack(fill="x", pady=(0, 14))
        self._build_output_row(c4.body)

        # 진행 바
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor=C["border"], background=C["primary"],
                        thickness=6, borderwidth=0)
        self.progress = ttk.Progressbar(
            outer, mode="indeterminate", length=460,
            style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="파일을 선택하고 비밀번호를 입력하세요.")
        tk.Label(outer, textvariable=self.status_var,
                 font=FONT_SM, bg=C["bg"], fg=C["sub"],
                 anchor="w").pack(fill="x", pady=(0, 12))

        # 실행 버튼
        run_btn = _hover_btn(outer, "  암호화하여 저장",
                             self._start_encrypt, C["success"], C["success_h"])
        run_btn.config(font=("Malgun Gothic", 11, "bold"), pady=12)
        run_btn.pack(fill="x")

    def _build_file_row(self, parent):
        parent.columnconfigure(0, weight=1)
        self.file_var = tk.StringVar()
        tk.Entry(parent, textvariable=self.file_var, width=46,
                 font=FONT, relief="solid", bd=1,
                 highlightthickness=1, highlightcolor=C["primary"],
                 highlightbackground=C["border"]).grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        b = _hover_btn(parent, "찾아보기", self._browse_file, C["primary"], C["primary_h"])
        b.grid(row=0, column=1)

    def _build_password_rows(self, parent):
        parent.columnconfigure(0, weight=1)

        tk.Label(parent, text="비밀번호", font=FONT_SM,
                 bg=C["card"], fg=C["sub"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        self.pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(parent, textvariable=self.pw_var, show="*",
                                  width=44, font=FONT, relief="solid", bd=1,
                                  highlightthickness=1, highlightcolor=C["primary"],
                                  highlightbackground=C["border"])
        self._pw_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        self._eye1 = _hover_btn(parent, "Show", self._toggle_pw1,
                                C["border"], "#CBD5E1", C["text"])
        self._eye1.grid(row=1, column=1)

        # 강도 바
        sf = tk.Frame(parent, bg=C["card"])
        sf.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.strength_bars = []
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
        self._pw2_entry = tk.Entry(parent, textvariable=self.pw2_var, show="*",
                                   width=44, font=FONT, relief="solid", bd=1,
                                   highlightthickness=1, highlightcolor=C["primary"],
                                   highlightbackground=C["border"])
        self._pw2_entry.grid(row=4, column=0, sticky="ew", padx=(0, 8))

        self._eye2 = _hover_btn(parent, "Show", self._toggle_pw2,
                                C["border"], "#CBD5E1", C["text"])
        self._eye2.grid(row=4, column=1)

        self.pw2_var.trace_add("write", lambda *_: self._check_match())
        self.match_lbl = tk.Label(parent, text="", font=FONT_SM,
                                   bg=C["card"], fg=C["sub"])
        self.match_lbl.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_options(self, parent):
        self.algo_var = tk.StringVar(value="AES-256")
        opts = [
            ("AES-256  (최고 보안 / 권장)", "AES-256"),
            ("AES-128  (표준 보안)",        "AES-128"),
            ("RC4-128  (구형 호환)",        "RC4-128"),
        ]
        for i, (label, val) in enumerate(opts):
            tk.Radiobutton(
                parent, text=label,
                variable=self.algo_var, value=val,
                font=FONT, bg=C["card"], fg=C["text"],
                activebackground=C["card"], selectcolor=C["card"],
            ).grid(row=i, column=0, sticky="w", pady=2)

    def _build_output_row(self, parent):
        parent.columnconfigure(0, weight=1)
        self.out_var = tk.StringVar()
        tk.Entry(parent, textvariable=self.out_var, width=46,
                 font=FONT, relief="solid", bd=1,
                 highlightthickness=1, highlightcolor=C["primary"],
                 highlightbackground=C["border"]).grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        b = _hover_btn(parent, "찾아보기", self._browse_output, C["primary"], C["primary_h"])
        b.grid(row=0, column=1)

    # ── 토글 ─────────────────────────────────────────────────
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
        score = 0
        if len(pw) >= 8:  score += 1
        if len(pw) >= 12: score += 1
        if any(c.isdigit() for c in pw): score += 1
        if any(c in "!@#$%^&*()" for c in pw): score += 1

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

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")]
        )
        if path:
            self.file_var.set(path)
            base, ext = os.path.splitext(path)
            self.out_var.set(base + "_encrypted" + ext)

    def _browse_output(self):
        src = self.file_var.get()
        initial = os.path.dirname(src) if src and os.path.isfile(src) else os.path.expanduser("~")
        path = filedialog.asksaveasfilename(
            title="저장 위치 선택", initialdir=initial,
            defaultextension=".pdf", filetypes=[("PDF 파일", "*.pdf")]
        )
        if path:
            self.out_var.set(path)

    def _start_encrypt(self):
        src = self.file_var.get().strip()
        pw1 = self.pw_var.get()
        pw2 = self.pw2_var.get()
        out = self.out_var.get().strip()

        if not src or not os.path.isfile(src):
            messagebox.showerror("오류", "유효한 PDF 파일을 선택하세요.")
            return
        if not pw1:
            messagebox.showerror("오류", "비밀번호를 입력하세요.")
            return
        if pw1 != pw2:
            messagebox.showerror("오류", "비밀번호가 일치하지 않습니다.")
            return
        if not out:
            messagebox.showerror("오류", "저장 위치를 지정하세요.")
            return

        threading.Thread(
            target=self._encrypt,
            args=(src, pw1, out, self.algo_var.get()),
            daemon=True
        ).start()

    def _encrypt(self, src, password, out, algo):
        self.after(0, self.progress.start, 10)
        self.after(0, self.status_var.set, "암호화 진행 중...")

        try:
            reader = PdfReader(src)
            if reader.is_encrypted:
                reader.decrypt("")

            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            if reader.metadata:
                writer.add_metadata(dict(reader.metadata))

            algo_map = {
                "AES-256": {"algorithm": "AES-256"},
                "AES-128": {"algorithm": "AES-128"},
                "RC4-128": {"algorithm": "RC4-128"},
            }
            kwargs = algo_map.get(algo, {"algorithm": "AES-256"})
            writer.encrypt(user_password=password, owner_password=password, **kwargs)

            with open(out, "wb") as f:
                writer.write(f)

            self.after(0, self._on_success, out)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self, out):
        self.progress.stop()
        self.status_var.set("완료 -> " + os.path.basename(out))
        messagebox.showinfo("완료", "암호화가 완료되었습니다!\n\n저장 위치:\n" + out)

    def _on_error(self, msg):
        self.progress.stop()
        self.status_var.set("오류가 발생했습니다.")
        messagebox.showerror("오류", "암호화 중 오류:\n" + msg)


if __name__ == "__main__":
    app = PDFEncryptorApp()
    app.mainloop()
