"""Minimal tabbed Tkinter GUI for sc295.

Talks to the daemon over the same unix socket the CLI uses (no BLE logic here).
Zero extra dependencies. Requests run on a worker thread so the UI never freezes;
results marshal back via root.after.

Tabs:
  Main      - power, color, brightness, and the "ambient" modes
  Patterns  - the controller's built-in effects (Lotus-style) + speed
  Utility   - pomodoro (and room for more utilities later)
"""
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, colorchooser

from . import ipc
from .config import socket_path
from .cli import _ensure_daemon
from .modes.patterns import pattern_names

PAD = 8
PRESETS = [
    ("Warm", (255, 180, 110)), ("White", (255, 255, 255)),
    ("Red", (255, 0, 0)), ("Orange", (255, 90, 0)),
    ("Green", (0, 200, 60)), ("Teal", (0, 150, 150)),
    ("Blue", (0, 80, 255)), ("Cyan", (0, 200, 255)),
    ("Purple", (140, 40, 200)), ("Pink", (255, 40, 120)),
]


async def _do(req):
    if not await _ensure_daemon():
        return {"ok": False, "error": "daemon unreachable"}
    return await ipc.request(socket_path(), req)


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Light")
        root.resizable(False, False)
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TButton", padding=6)
        style.configure("Mode.TButton", padding=(6, 8))

        self._build()
        self.poll()

    # ---- widget construction --------------------------------------------

    def _build(self):
        outer = ttk.Frame(self.root, padding=PAD)
        outer.grid(sticky="nsew")

        # status bar (shared across tabs)
        bar = ttk.Frame(outer)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, PAD))
        self.dot = tk.Canvas(bar, width=14, height=14, highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(0, 6))
        self._dot_id = self.dot.create_oval(2, 2, 12, 12, fill="#888", outline="")
        self.status_lbl = ttk.Label(bar, text="connecting…")
        self.status_lbl.grid(row=0, column=1, sticky="w")

        nb = ttk.Notebook(outer)
        nb.grid(row=1, column=0, sticky="nsew")
        self._build_main(nb)
        self._build_patterns(nb)
        self._build_utility(nb)

    def _build_main(self, nb):
        tab = ttk.Frame(nb, padding=PAD)
        nb.add(tab, text="Main")

        power = ttk.Frame(tab)
        power.grid(row=0, column=0, sticky="ew", pady=(0, PAD))
        ttk.Button(power, text="On", command=self.on_power_on).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(power, text="Off", command=self.on_power_off).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(power, text="Reset", command=self.on_reset).grid(row=0, column=2, sticky="ew", padx=2)
        for i in range(3):
            power.columnconfigure(i, weight=1)

        cf = ttk.LabelFrame(tab, text="Color", padding=PAD)
        cf.grid(row=1, column=0, sticky="ew", pady=(0, PAD))
        for i, (_name, rgb) in enumerate(PRESETS):
            tk.Button(cf, bg=_hex(rgb), activebackground=_hex(rgb), width=3,
                      height=1, relief="flat", bd=1,
                      command=lambda c=rgb: self.set_color(c)).grid(
                row=i // 5, column=i % 5, padx=3, pady=3, sticky="ew")
        ttk.Button(cf, text="Custom color…", command=self.pick_color).grid(
            row=2, column=0, columnspan=5, sticky="ew", pady=(6, 0))

        bf = ttk.LabelFrame(tab, text="Brightness", padding=PAD)
        bf.grid(row=2, column=0, sticky="ew", pady=(0, PAD))
        self.bri_lbl = ttk.Label(bf, text="100%", width=5)
        self.bri_lbl.grid(row=0, column=1, padx=(6, 0))
        self.bri = ttk.Scale(bf, from_=0, to=100, orient="horizontal",
                             command=self._bri_move)
        self.bri.set(100)
        self.bri.grid(row=0, column=0, sticky="ew")
        self.bri.bind("<ButtonRelease-1>", self._bri_commit)
        bf.columnconfigure(0, weight=1)

        mf = ttk.LabelFrame(tab, text="Modes", padding=PAD)
        mf.grid(row=3, column=0, sticky="ew")
        ttk.Button(mf, text="Screen", style="Mode.TButton",
                   command=self.on_screen).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.style_var = tk.StringVar(value="vivid")
        ttk.Combobox(mf, textvariable=self.style_var, width=9, state="readonly",
                     values=["average", "vivid", "dominant", "edge"]).grid(row=0, column=1, padx=2)
        self.mon_var = tk.StringVar(value="focus")
        mon = ttk.Combobox(mf, textvariable=self.mon_var, width=9, state="readonly",
                           values=["focus", "HDMI-0", "eDP-1-1", "both"])
        mon.grid(row=0, column=2, padx=2)
        mon.bind("<<ComboboxSelected>>", lambda e: self.set_monitor())

        ttk.Button(mf, text="Calm", style="Mode.TButton",
                   command=lambda: self.set_mode("calm")).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(mf, text="Circadian", style="Mode.TButton",
                   command=lambda: self.set_mode("circadian")).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(mf, text="Audio", style="Mode.TButton",
                   command=self.on_audio).grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        self.audio_src = tk.StringVar(value="system")
        ttk.Combobox(mf, textvariable=self.audio_src, width=9, state="readonly",
                     values=["system", "mic"]).grid(row=2, column=1, padx=2)
        for i in range(3):
            mf.columnconfigure(i, weight=1)

    def _build_patterns(self, nb):
        tab = ttk.Frame(nb, padding=PAD)
        nb.add(tab, text="Patterns")

        ttk.Label(tab, text="Built-in effects").grid(row=0, column=0, sticky="w")
        listwrap = ttk.Frame(tab)
        listwrap.grid(row=1, column=0, sticky="nsew", pady=(2, PAD))
        sb = ttk.Scrollbar(listwrap, orient="vertical")
        self.pat_list = tk.Listbox(listwrap, height=9, width=26,
                                   activestyle="none", exportselection=False,
                                   yscrollcommand=sb.set)
        sb.config(command=self.pat_list.yview)
        self.pat_list.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        for name in pattern_names():
            self.pat_list.insert("end", name)
        self.pat_list.selection_set(0)
        self.pat_list.bind("<Double-Button-1>", lambda e: self.on_pattern())

        sf = ttk.Frame(tab)
        sf.grid(row=2, column=0, sticky="ew")
        ttk.Label(sf, text="Speed").grid(row=0, column=0)
        self.pat_speed = ttk.Scale(sf, from_=1, to=100, orient="horizontal")
        self.pat_speed.set(50)
        self.pat_speed.grid(row=0, column=1, sticky="ew", padx=6)
        sf.columnconfigure(1, weight=1)
        ttk.Button(tab, text="Apply pattern", command=self.on_pattern).grid(
            row=3, column=0, sticky="ew", pady=(PAD, 0))

    def _build_utility(self, nb):
        tab = ttk.Frame(nb, padding=PAD)
        nb.add(tab, text="Utility")

        pf = ttk.LabelFrame(tab, text="Pomodoro", padding=PAD)
        pf.grid(row=0, column=0, sticky="ew")
        ttk.Label(pf, text="Work (min)").grid(row=0, column=0, sticky="w")
        self.work = tk.IntVar(value=25)
        ttk.Spinbox(pf, from_=1, to=90, width=5, textvariable=self.work).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(pf, text="Break (min)").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.brk = tk.IntVar(value=5)
        ttk.Spinbox(pf, from_=1, to=60, width=5, textvariable=self.brk).grid(row=1, column=1, padx=(6, 0), pady=(4, 0))
        ttk.Label(pf, text="Rounds").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.rounds = tk.IntVar(value=4)
        ttk.Spinbox(pf, from_=1, to=12, width=5, textvariable=self.rounds).grid(row=2, column=1, padx=(6, 0), pady=(4, 0))
        ttk.Button(pf, text="Start Pomodoro", command=self.on_pomodoro).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(PAD, 0))

        ttk.Label(tab, text="(more utilities coming)", foreground="#888").grid(
            row=1, column=0, sticky="w", pady=(PAD, 0))

    # ---- request plumbing ------------------------------------------------

    def submit(self, req, cb=None):
        def worker():
            try:
                resp = asyncio.run(_do(req))
            except Exception as e:
                resp = {"ok": False, "error": str(e)}
            if cb:
                self.root.after(0, lambda: cb(resp))
        threading.Thread(target=worker, daemon=True).start()

    def flash_error(self, resp):
        if resp and not resp.get("ok"):
            self.status_lbl.config(text=f"error: {resp.get('error')}")

    # ---- actions ---------------------------------------------------------

    def on_power_on(self):
        self.set_color((255, 180, 110))

    def on_power_off(self):
        self.submit({"cmd": "off"}, self.flash_error)

    def on_reset(self):
        self.submit({"cmd": "reset"}, self.flash_error)

    def set_color(self, rgb):
        self.submit({"cmd": "set_mode", "mode": "solid",
                     "args": {"rgb": [int(c) for c in rgb]}}, self.flash_error)

    def pick_color(self):
        rgb, _ = colorchooser.askcolor(parent=self.root, title="Pick a color")
        if rgb:
            self.set_color(rgb)

    def _bri_move(self, _v):
        self.bri_lbl.config(text=f"{int(float(self.bri.get()))}%")

    def _bri_commit(self, _e):
        self.submit({"cmd": "config", "key": "max_brightness",
                     "value": int(float(self.bri.get()))}, self.flash_error)

    def set_mode(self, name, args=None):
        self.submit({"cmd": "set_mode", "mode": name, "args": args or {}},
                    self.flash_error)

    def on_screen(self):
        self.set_mode("screen", {"style": self.style_var.get()})

    def set_monitor(self):
        self.submit({"cmd": "config", "key": "screen_monitor",
                     "value": self.mon_var.get()}, self.flash_error)

    def on_audio(self):
        self.set_mode("audio", {"source": self.audio_src.get()})

    def on_pattern(self):
        sel = self.pat_list.curselection()
        if not sel:
            return
        name = self.pat_list.get(sel[0])
        self.set_mode("pattern", {"name": name,
                                  "speed": int(float(self.pat_speed.get()))})

    def on_pomodoro(self):
        self.set_mode("pomodoro", {"work": self.work.get(),
                                   "break": self.brk.get(),
                                   "rounds": self.rounds.get()})

    # ---- status polling --------------------------------------------------

    def poll(self):
        self.submit({"cmd": "status"}, self.on_status)
        self.root.after(2500, self.poll)

    def on_status(self, resp):
        if not resp or not resp.get("ok"):
            self.dot.itemconfig(self._dot_id, fill="#c0392b")
            self.status_lbl.config(text="daemon unreachable")
            return
        connected = resp.get("connected")
        self.dot.itemconfig(self._dot_id, fill="#27ae60" if connected else "#e67e22")
        state = "connected" if connected else "connecting…"
        self.status_lbl.config(text=f"{resp.get('desc', resp.get('mode'))}  ·  {state}")
        # initialise controls from the daemon's real state (once), so the
        # dropdowns/slider reflect reality instead of their defaults
        if not getattr(self, "_synced", False):
            self._synced = True
            if resp.get("max_brightness") is not None:
                self.bri.set(resp["max_brightness"])
                self.bri_lbl.config(text=f"{resp['max_brightness']}%")
            if resp.get("screen_monitor"):
                self.mon_var.set(resp["screen_monitor"])
            if resp.get("screen_style"):
                self.style_var.set(resp["screen_style"])


def main():
    # className sets the X11 WM_CLASS so the window matches the .desktop launcher
    # (StartupWMClass=Light) and picks up its icon in the dock / app switcher.
    root = tk.Tk(className="Light")
    try:
        icon = _load_window_icon(root)
        if icon:
            root.iconphoto(True, icon)
    except Exception:
        pass
    App(root)
    root.mainloop()


def _load_window_icon(root):
    """Best-effort titlebar/taskbar icon from an installed PNG, if one exists."""
    import os
    for size in ("256x256", "128x128", "64x64", "48x48"):
        p = os.path.expanduser(
            f"~/.local/share/icons/hicolor/{size}/apps/sc295-light.png")
        if os.path.exists(p):
            return tk.PhotoImage(file=p)
    return None


if __name__ == "__main__":
    main()
