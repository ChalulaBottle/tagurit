"""
MD Convert — scan for markdown files, convert to PDF/HTML from a notched-square window.

Stack (researched, not guessed): Tkinter + -transparentcolor for the custom
shape (stdlib, no install), mistune for HTML (pure-Python, faster than
markdown2), xhtml2pdf for PDF (pure-Python, verified working — WeasyPrint is
a documented Windows breakage, not used here). DOCX deferred (python-docx,
when needed).

Theming: NETUS house style (docs/THEME.md in the NETUS repo) — calm light
palette, no glow/no glitch, neutral frame with colored internal accents
("a colored container shouts"). Shape is NETUS's own house shape: a
notched-corner panel via polygon (never border-radius), not the hexagon
this started as — widened so full file paths are legible, not clipped.
Fonts fall back to NETUS's own documented chain: none of IBM Plex Mono /
Inter / Syne are installed on this machine, so Consolas (mono) and Segoe UI
(sans) are used, matching THEME.md's stated fallback stacks.

IMPORTANT — launch with pythonw/pyw, not py/python: the console-subsystem
launcher creates a real console window that sits directly behind this one,
so -transparentcolor's "transparent" regions show that console's black
background instead of the desktop. pyw.exe (windowless subsystem) avoids
this entirely. Verified both failure modes live before landing on this.

Run: pyw md_convert.py
"""

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import mistune
from xhtml2pdf import pisa

import metadata_engine
import rewrite_engine

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "scan_config.json"

DEFAULT_ROOTS = [
    str(Path.home() / "Downloads"),
    str(Path.home() / "Documents"),
    str(Path.home() / "Desktop"),
]
EXCLUDE_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "site-packages", "AppData",
}

KEY_COLOR = "#ff00ff"   # magenta — chroma-keyed transparent by -transparentcolor;
                        # nothing in the warm clay/pink palette below is near it
# Warm palette, pulled from NETUS's own calculator (site/calculator/index.html),
# not the cooler global THEME.md doc — the calculator is a page-scoped :root
# per THEME.md's own rule ("own <style>, own :root tokens"), and it's the
# actual "warm and fun" corner of the house system.
CARD = "#E3A98A"        # --p-bg — clay panel fill
CARD_2 = "#F5E0D5"      # --p-socket — recessed surface (listbox/search body)
RIM = "#7A5B4A"         # --p-rim — square/panel boundary
INK = "#352820"         # --p-ink — text on the clay panel (6.99:1, per their own comment)
# NETUS has no separate secondary-ink token here — their own pattern is
# color:var(--p-ink) with opacity .75 / .6 (see .trainbar-fine etc). Tkinter
# text has no alpha, so these are --p-ink pre-blended against --p-bg at
# those exact ratios, not new colors picked from nothing.
INK_2 = "#61483B"       # p-ink at .75 opacity on clay, blended
INK_3 = "#7B5C4A"       # p-ink at .6 opacity on clay, blended
BLUE = "#2E6FA8"        # NETUS --blue — kept as-is, no warm equivalent needed
AID = "#1B6B4A"         # NETUS --aid — done / success, kept as-is

# The "pulse square" (calculator's .sq tile), for the format picker:
PROG = "#D54D76"        # --prog — blossom pink, the "on/selected" tile fill
PROG_DEEP = "#841F3D"   # --prog-deep — selected tile's border
P_EDGE = "#A95F76"      # --p-edge — hard offset shadow color
HINT_EDGE = "#66AD8E"   # --hint-edge — pulse phase 1 (their real dotBreathe colors —
SLIP_BORDER = "#3F7F5C" # --slip-border — pulse phase 2   deliberately cool-green
                        # against the warm panel, per their own contrast reasoning)
FONT_MONO = "Consolas"  # NETUS --mono fallback (IBM Plex Mono not installed here)
FONT_SANS = "Segoe UI"  # NETUS --sans fallback (Inter not installed here)

NOTCH = 13  # matches THEME.md's own documented clip-path notch size exactly


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"roots": DEFAULT_ROOTS}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def scan_for_markdown(roots: list) -> list:
    """Walk each root, skipping known-noise directories. Returns sorted file paths."""
    found = []
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
            for name in filenames:
                if name.lower().endswith(".md"):
                    found.append(str(Path(dirpath) / name))
    return sorted(found)


def convert_to_html(md_path: str, out_path: str) -> None:
    raw = Path(md_path).read_text(encoding="utf-8")
    md = rewrite_engine.rewrite(raw)  # re-typed, not sliced from `raw` — see rewrite_engine.py
    html_body = mistune.html(md)
    html = f"<!doctype html><meta charset='utf-8'><body>{html_body}</body>"
    Path(out_path).write_text(html, encoding="utf-8")


def convert_to_pdf(md_path: str, out_path: str) -> None:
    raw = Path(md_path).read_text(encoding="utf-8")
    md = rewrite_engine.rewrite(raw)  # re-typed, not sliced from `raw` — see rewrite_engine.py
    html_body = mistune.html(md)
    html = f"<!doctype html><meta charset='utf-8'><body>{html_body}</body>"
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f)
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} error(s)")
    metadata_engine.clean_pdf_metadata(out_path, title=metadata_engine.title_from_md_path(md_path))


CONVERTERS = {
    "HTML": (".html", convert_to_html),
    "PDF": (".pdf", convert_to_pdf),
}


def notched_rect_points(w, h, notch=NOTCH):
    """NETUS's actual house shape — an octagon-corner-cut rectangle, matching
    THEME.md's CSS clip-path exactly: polygon(0 n,n 0,...). Never border-radius."""
    return [
        0, notch, notch, 0, w - notch, 0, w, notch,
        w, h - notch, w - notch, h, notch, h, 0, h - notch,
    ]


class MDConvertApp:
    def __init__(self):
        self.cfg = load_config()
        self.files = []       # full scan result
        self.displayed = []   # filtered subset currently shown in the listbox

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY_COLOR)
        self.root.wm_attributes("-transparentcolor", KEY_COLOR)
        # overrideredirect windows get no window-manager z-order promotion on
        # creation — without this they can spawn genuinely visible (per the
        # Win32 API) but stacked BEHIND other existing windows. Verified this
        # was happening: two prior launches both reported visible=True at the
        # correct rect while showing nothing on screen, until this was added.
        self.root.wm_attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

        # wide enough that a real file path doesn't get clipped
        self.W, self.H = 760, 480
        self.root.geometry(f"{self.W}x{self.H}+200+200")
        # overrideredirect windows have no window manager forcing a realize —
        # geometry() can silently stick at the 1x1 default until the event
        # loop processes it. Force it now, before anything relies on self.W/H.
        self.root.update_idletasks()

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                 bg=KEY_COLOR, highlightthickness=0)
        self.canvas.pack()

        # neutral rim, not a bright glow — "a colored container shouts" (THEME.md)
        self.canvas.create_polygon(notched_rect_points(self.W, self.H),
                                    fill=CARD, outline=RIM, width=1)

        # draggable via the panel background
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)

        self._build_controls()

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + (event.x - self._dx)
        y = self.root.winfo_y() + (event.y - self._dy)
        self.root.geometry(f"+{x}+{y}")

    def _build_controls(self):
        pad = 24  # inset from the notched corners — far smaller than a hex needs

        title = tk.Label(self.root, text="TAGURIT", fg=INK, bg=CARD,
                          font=(FONT_MONO, 17, "bold"))
        title.place(x=pad, y=18, width=self.W - pad * 2 - 30)

        close_btn = tk.Button(self.root, text="x", command=self.root.destroy,
                               fg=INK_3, bg=CARD, bd=0, font=(FONT_MONO, 10),
                               activebackground=CARD, activeforeground=INK)
        close_btn.place(x=self.W - 40, y=16, width=22, height=22)

        self._last_output_dir = None
        self.status = tk.Label(self.root, text=f"{len(self.cfg['roots'])} folders configured",
                                fg=INK_2, bg=CARD, font=(FONT_MONO, 12), cursor="hand2")
        self.status.place(x=pad, y=46, width=self.W - pad * 2)
        self.status.bind("<Button-1>", self._on_status_click)

        # listbox must exist BEFORE the search entry is constructed below —
        # placeholder text triggers the search trace immediately via
        # entry.insert(), and _on_search_change touches self.listbox. Code
        # order here is about attribute-existence, not visual top-to-bottom
        # order (the search box still appears above the list on screen).
        self.listbox = tk.Listbox(self.root, fg=INK, bg=CARD_2,
                                   selectbackground=BLUE, selectforeground=CARD,
                                   bd=0, font=(FONT_SANS, 13), highlightthickness=0)
        self.listbox.place(x=pad, y=104, width=self.W - pad * 2, height=280)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        search = tk.Entry(self.root, textvariable=self.search_var, fg=INK, bg=CARD_2,
                           insertbackground=INK, bd=0, font=(FONT_SANS, 13))
        search.place(x=pad, y=74, width=self.W - pad * 2, height=30)
        self._add_placeholder(search, "Filter by path...")

        self._make_button("Scan", self.on_scan, pad, 396, 110, 26,
                           fg=CARD, bg=BLUE, font=(FONT_SANS, 10, "bold"))

        self._make_button("+ Folder", self.on_add_folder, pad + 120, 396, 110, 26,
                           fg=INK, bg=CARD_2, font=(FONT_SANS, 10))

        self.format_var = tk.StringVar(value="PDF")
        self._build_format_tiles(x=self.W - pad - 110, y=396, w=110, h=26)

        self._make_button("Convert selected", self.on_convert, pad, 432, self.W - pad * 2, 30,
                           fg=CARD, bg=BLUE, font=(FONT_SANS, 11, "bold"))

    def _make_button(self, text, command, x, y, w, h, fg, bg, font):
        """NETUS's `.etch` convention: "the wrapper carries the shadow." Approximated
        here as a canvas rectangle offset behind the button, deepened on hover for a
        lift feel — Tkinter has no true CSS blur/box-shadow to draw on."""
        shadow = self.canvas.create_rectangle(x + 5, y + 5, x + w + 5, y + h + 5,
                                               fill=RIM, outline="")
        btn = tk.Button(self.root, text=text, command=command, fg=fg, bg=bg,
                         bd=0, font=font, activebackground=bg, activeforeground=fg)
        btn.place(x=x, y=y, width=w, height=h)

        def on_enter(_):
            btn.place(x=x, y=y - 2, width=w, height=h)
            self.canvas.coords(shadow, x + 5, y + 7, x + w + 5, y + h + 7)
            self.canvas.itemconfig(shadow, fill=INK_3)

        def on_leave(_):
            btn.place(x=x, y=y, width=w, height=h)
            self.canvas.coords(shadow, x + 5, y + 5, x + w + 5, y + h + 5)
            self.canvas.itemconfig(shadow, fill=RIM)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _build_format_tiles(self, x, y, w, h):
        """NETUS's `.sq` tile (the calculator's tier picker), repurposed as the
        format switch. The selected tile pulses using their real dotBreathe
        keyframes (--hint-edge/--slip-border, alternating shadow offset) —
        their own comment: "the pulse [is] a pointer that means 'read this
        next'", here repurposed as "this is what's selected."

        Known gap vs. the source: THEME.md requires every remaining animation
        to respect prefers-reduced-motion; Tkinter has no stdlib way to query
        that OS setting without a ctypes call, so this pulse always runs. Not
        implemented — flagging rather than silently dropping their own rule.
        """
        self._fmt_tiles = {}
        gap = 6
        tile_w = (w - gap) / 2
        for i, key in enumerate(CONVERTERS.keys()):
            tx = x + i * (tile_w + gap)
            shadow = self.canvas.create_rectangle(tx + 5, y + 5, tx + tile_w + 5, y + h + 5,
                                                   fill=RIM, outline="")
            lbl = tk.Label(self.root, text=key, font=(FONT_SANS, 9, "bold"), highlightthickness=2)
            lbl.place(x=tx, y=y, width=tile_w, height=h)
            lbl.bind("<Button-1>", lambda _, k=key: self._select_format(k))
            self._fmt_tiles[key] = {"x": tx, "y": y, "w": tile_w, "h": h, "shadow": shadow, "label": lbl}
        self._pulse_phase = 0
        self._render_format_tiles()
        self._pulse_tick()

    def _select_format(self, key):
        self.format_var.set(key)
        self._render_format_tiles()

    def _render_format_tiles(self):
        selected = self.format_var.get()
        for key, t in self._fmt_tiles.items():
            on = key == selected
            t["label"].config(bg=(PROG if on else CARD_2), fg=(CARD if on else INK),
                               highlightbackground=(PROG_DEEP if on else RIM))
            if not on:
                self.canvas.coords(t["shadow"], t["x"] + 5, t["y"] + 5,
                                    t["x"] + t["w"] + 5, t["y"] + t["h"] + 5)
                self.canvas.itemconfig(t["shadow"], fill=RIM)

    def _pulse_tick(self):
        """dotBreathe's real two-phase cycle (3px<->6px, same 3px swing), shifted
        up to a 5px/8px range to match the wider resting shadow elsewhere in this
        pass — --hint-edge <-> --slip-border, ~1.05s per phase (2.1s full cycle),
        only on the currently-selected tile."""
        if not self.root.winfo_exists():
            return
        t = self._fmt_tiles.get(self.format_var.get())
        if t:
            self._pulse_phase = 1 - self._pulse_phase
            offset = 5 if self._pulse_phase == 0 else 8
            color = HINT_EDGE if self._pulse_phase == 0 else SLIP_BORDER
            self.canvas.coords(t["shadow"], t["x"] + offset - 1, t["y"] + offset,
                                t["x"] + t["w"] + offset - 1, t["y"] + t["h"] + offset)
            self.canvas.itemconfig(t["shadow"], fill=color)
        self.root.after(1050, self._pulse_tick)

    def _add_placeholder(self, entry, text):
        """Simple placeholder-on-empty behavior — Tkinter Entry has no native support.

        Order matters: entry.insert() below fires the search StringVar's write
        trace immediately (the Entry is bound to it via textvariable), so
        _placeholder_text must be set BEFORE insert(), not after — setting it
        after caused an AttributeError the trace callback hit mid-construction.
        """
        self._placeholder_text = text
        entry.insert(0, text)
        entry.config(fg=INK_3)

        def on_focus_in(_):
            if entry.get() == text:
                entry.delete(0, tk.END)
                entry.config(fg=INK)

        def on_focus_out(_):
            if not entry.get():
                entry.insert(0, text)
                entry.config(fg=INK_3)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def _on_search_change(self, *_):
        self._refresh_listbox(self._current_query())

    def _current_query(self):
        """The real (typed) query, or '' if the box still shows the placeholder.

        Bug this fixes: on_scan() used to pass self.search_var.get() straight
        through, which is literally "Filter by path..." when the box has
        never been touched — every file's path fails to contain that literal
        string, so the listbox rendered empty while the status line still
        correctly reported the true scan count. That mismatch (count right,
        list empty) was the exact symptom reported.
        """
        query = self.search_var.get()
        return "" if query == self._placeholder_text else query

    def _refresh_listbox(self, query=""):
        query = query.lower().strip()
        self.displayed = [f for f in self.files if query in f.lower()] if query else list(self.files)
        self.listbox.delete(0, tk.END)
        for f in self.displayed:
            self.listbox.insert(tk.END, f)

    def on_scan(self):
        self.files = scan_for_markdown(self.cfg["roots"])
        self._refresh_listbox(self._current_query())
        self.status.config(text=f"{len(self.files)} markdown files found", fg=INK_2)

    def on_add_folder(self):
        folder = filedialog.askdirectory(title="Add a folder to scan")
        if folder and folder not in self.cfg["roots"]:
            self.cfg["roots"].append(folder)
            save_config(self.cfg)
            self.status.config(text=f"{len(self.cfg['roots'])} folders configured", fg=INK_2)

    def on_convert(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Tagurit", "Select a file first.")
            return
        md_path = self.displayed[sel[0]]
        fmt = self.format_var.get()
        ext, converter = CONVERTERS[fmt]
        # A prior run's same-named output was found to be silently overwritten
        # with no warning (confirmed via adversarial testing) — disambiguate
        # instead, same convention as Windows' own "Copy (2)".
        out_path = self._dedupe_path(str(Path(md_path).with_suffix(ext)))

        # xhtml2pdf measured at 50+ seconds on a multi-MB markdown file — running
        # that on the main thread freezes the whole GUI with no feedback at all.
        # Converting on a worker thread keeps the window responsive; UI updates
        # are marshaled back via root.after() since Tkinter isn't thread-safe.
        self.status.config(text="Converting…", fg=INK_2)

        def worker():
            try:
                converter(md_path, out_path)
            except Exception as e:
                self.root.after(0, lambda: self._on_convert_error(e))
            else:
                self.root.after(0, lambda: self._on_convert_done(out_path))

        threading.Thread(target=worker, daemon=True).start()

    def _on_convert_done(self, out_path):
        # Full path, not just the filename — the app scans across many
        # directories at once, so "Saved: file.pdf" alone gives no clue
        # which of them it landed in. Status line doubles as a link to
        # open that folder, since that's the actual question being asked.
        self.status.config(text=f"Saved: {out_path}  (click to open folder)", fg=AID)
        self._last_output_dir = str(Path(out_path).parent)

    def _on_convert_error(self, e):
        self.status.config(text="Conversion failed", fg=INK_2)
        messagebox.showerror("Tagurit", f"Conversion failed: {e}")

    @staticmethod
    def _dedupe_path(out_path: str) -> str:
        p = Path(out_path)
        if not p.exists():
            return out_path
        n = 2
        while True:
            candidate = p.parent / f"{p.stem} ({n}){p.suffix}"
            if not candidate.exists():
                return str(candidate)
            n += 1

    def _on_status_click(self, _event):
        if self._last_output_dir and Path(self._last_output_dir).is_dir():
            os.startfile(self._last_output_dir)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    MDConvertApp().run()
