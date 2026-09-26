"""Render every Deskglow desktop-app screen offscreen and save PNGs.

    QT_QPA_PLATFORM=offscreen python tools/gui_screenshots.py OUTPUT_DIR

Uses a scripted fake daemon client (no daemon, no Bluetooth) whose replies
match the approved design's sample content. Addresses are the design's
made-up samples.
"""
import asyncio
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from deskglow.model.settings import DEFAULTS  # noqa: E402
from deskglow.view.gui.app import build_ui  # noqa: E402

MONITORS = {"DP-1": {"left": 0, "top": 0, "width": 2560, "height": 1440},
            "HDMI-1": {"left": 2560, "top": 0, "width": 1920, "height": 1080}}
CANDIDATES = [
    {"address": "A4:C1:38:5E:22:9B", "name": "MELK-OA10", "rssi": -55, "certain": True},
    {"address": "BE:32:57:A0:13:6C", "name": "ELK-BLEDOM", "rssi": -76, "certain": False},
    {"address": "C4:18:E9:02:7F:21", "name": "LEDBLE-7F21", "rssi": -88, "certain": False},
]
BASE = dict(copy.deepcopy(DEFAULTS), ok=True, connected=True, configured=True,
            address="A4:C1:38:5E:22:9B", device_name="MELK-OA10", name="Desk strip",
            rssi=-58, sunset_available=True, last_solid="#FFB46E", brightness=80,
            max_brightness=85, screen=None, audio_level=None, focus=None)
STATES = {
    "home": dict(mode="solid", args={"rgb": [255, 180, 110]}, color="#FFB46E"),
    "effects": dict(mode="pattern", args={"name": "fade-colors", "speed": 50}, color=None),
    "sync": dict(mode="screen", args={}, color="#4A7BFF",
                 screen={"color": "#4A7BFF", "fps": 15.0}),
    "focus": dict(mode="pomodoro", args={"work": 25, "break": 5, "rounds": 4}, color="#28A0C8",
                  focus={"phase": "focus", "remaining": 1122.0, "total": 1500.0, "round": 2,
                         "rounds": 4, "paused": False}),
    "settings": dict(mode="solid", args={"rgb": [255, 180, 110]}, color="#FFB46E",
                     tray_on=True, hotkey_on=True),
    "setup": dict(mode="off", configured=False, address=None, color=None),
    "tray": dict(mode="solid", args={"rgb": [255, 180, 110]}, color="#FFB46E"),
}


class FakeClient:
    """DaemonClient stand-in: answers from STATES[self.state]."""

    def __init__(self):
        self.state = "home"

    async def ensure_daemon(self):
        return True

    async def request(self, req, timeout=25.0):
        cmd = req.get("cmd")
        if cmd == "status":
            return dict(BASE, **STATES[self.state])
        if cmd == "monitors":
            return {"ok": True, "monitors": MONITORS}
        if cmd == "scan":
            return {"ok": True, "candidates": CANDIDATES}
        return {"ok": True}


class FakeAutostart:
    def is_enabled(self):
        return True

    def set_enabled(self, enabled):
        pass


class FakeServices:
    autostart = FakeAutostart()

    class storage:  # noqa: N801
        @staticmethod
        def log_path():
            return "/tmp/deskglow.log"

    @staticmethod
    def hotkey():
        return FakeHotkey()


class FakeHotkey:
    def register(self, sequence, callback):
        return True

    def unregister(self):
        pass


def settle(app, ui, client, state):
    client.state = state
    ui.poller.refresh()
    for _ in range(40):
        app.processEvents()
        asyncio.run(asyncio.sleep(0.005))
    ui.poller.refresh()
    for _ in range(40):
        app.processEvents()
        asyncio.run(asyncio.sleep(0.005))


def main(out):
    os.makedirs(out, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    client = FakeClient()
    ui = build_ui(app, client, FakeServices(), tray=False)
    ui.ctx.set_tray_available(True)      # as on a desktop with a tray
    ui.window.show()
    if hasattr(ui.pages.get("sync"), "meter"):
        ui.pages["sync"].meter_demo([30, 52, 70, 88, 64, 45, 78, 92, 60, 40, 55, 72, 84, 58,
                                     36, 48, 66, 42])
    for page in ("home", "effects", "sync", "focus", "settings", "setup"):
        settle(app, ui, client, page)
        ui.window.go(page)
        settle(app, ui, client, page)
        ui.window.grab().save(os.path.join(out, f"{page}.png"))
    settle(app, ui, client, "tray")
    ui.panel.resize(340, 520)
    ui.panel.show()
    settle(app, ui, client, "tray")
    ui.panel.grab().save(os.path.join(out, "tray.png"))
    ui.shutdown()
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
