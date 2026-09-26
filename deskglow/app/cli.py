"""Console script `deskglow` (also `python -m deskglow`)."""
import sys

from ..view import cli as view_cli
from .wiring import build_services


def main(argv=None):
    return view_cli.main(argv, services_factory=build_services)


if __name__ == "__main__":
    sys.exit(main())
