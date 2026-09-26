"""The ONLY code that touches hardware, the OS or radio libraries.

One module per platform integration; deskglow.app picks which ones to use.
Optional or OS-specific libraries (mss, Xlib, numpy, soundcard, pynput,
dbus_fast, Quartz, winreg, ctypes.windll) are imported lazily, inside the
functions that use them, so a core install without the extras still works and
every driver module imports (and is unit-tested) on any OS.
"""
