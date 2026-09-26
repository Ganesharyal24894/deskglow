"""The strip address for the tools: `--address AA:BB:CC:DD:EE:FF` (or `-a`) on the
command line, else $DESKGLOW_ADDRESS. Consumed args are removed from sys.argv so
a script's own argument parsing never sees them."""
import os
import sys

USAGE = ("pass the strip's MAC address with --address AA:BB:CC:DD:EE:FF "
         "or set DESKGLOW_ADDRESS (find it with tools/discover.py or `deskglow setup`)")


def strip_address(argv=None):
    argv = sys.argv if argv is None else argv
    for i, arg in enumerate(argv[1:], start=1):
        if arg in ("-a", "--address") and i + 1 < len(argv):
            address = argv[i + 1]
            del argv[i:i + 2]
            return address
        if arg.startswith("--address="):
            del argv[i]
            return arg.split("=", 1)[1]
    address = os.environ.get("DESKGLOW_ADDRESS")
    if not address:
        sys.exit(f"{os.path.basename(argv[0])}: {USAGE}")
    return address
