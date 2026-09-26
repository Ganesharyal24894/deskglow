"""Interfaces (ports) the controllers depend on, plus small plain-data types.

Implementations live in deskglow.drivers; deskglow.app picks them.
"""
from .audio import AudioSource
from .container import Services
from .encoder import FrameEncoder
from .ipc import IpcClient, IpcHandler, IpcServer
from .link import AdapterError, LightLink, LinkSession
from .process import Autostart, ProcessControl
from .scanner import Advert, Scanner
from .screen import FocusTracker, Rect, ScreenSource
from .storage import Storage

__all__ = [
    "AdapterError", "Advert", "AudioSource", "Autostart", "FocusTracker",
    "FrameEncoder", "IpcClient", "IpcHandler", "IpcServer", "LightLink",
    "LinkSession", "ProcessControl", "Rect", "Scanner", "ScreenSource",
    "Services", "Storage",
]
