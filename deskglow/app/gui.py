"""GUI script `deskglow-gui`: the desktop app (needs the `gui` extra)."""
import sys

from .wiring import build_services


def main(argv=None):
    try:
        from ..view.gui.app import run
    except ImportError as e:
        print(f"deskglow-gui needs PySide6: pip install 'deskglow[gui]' ({e})", file=sys.stderr)
        return 1
    try:
        services = build_services()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return run(services, argv)


if __name__ == "__main__":
    sys.exit(main())
