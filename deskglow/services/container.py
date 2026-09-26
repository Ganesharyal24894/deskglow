"""The bundle of chosen implementations the app hands to controllers and views."""
from dataclasses import dataclass
from collections.abc import Callable

from ..model.presets import Preset
from .audio import AudioSource
from .encoder import FrameEncoder
from .hotkey import GlobalHotkey
from .ipc import IpcClient, IpcServer
from .link import LightLink
from .location import LocationHint, no_location
from .process import Autostart, ProcessControl
from .scanner import Scanner
from .screen import FocusTracker, ScreenSource
from .storage import Storage


def _unavailable(what):
    def factory():
        raise RuntimeError(f"{what} is not available on this platform")
    return factory


@dataclass
class Services:
    """Constructor-injected into controllers. Screen, focus and audio are
    factories because a mode opens a fresh one each time it starts."""

    preset: Preset
    encoder: FrameEncoder
    storage: Storage
    link: LightLink
    scanner: Scanner
    ipc_server: IpcServer
    ipc_client: IpcClient
    autostart: Autostart
    process: ProcessControl
    screen: Callable[[], ScreenSource] = _unavailable("screen capture")
    focus: Callable[[], FocusTracker] = _unavailable("focus tracking")
    audio: Callable[[], AudioSource] = _unavailable("audio capture")
    hotkey: Callable[[], GlobalHotkey] = _unavailable("global shortcuts")
    location: LocationHint = no_location
