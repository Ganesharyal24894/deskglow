"""AudioSource on PipeWire: `pw-record` mono s16 to stdout, `pw-dump` for the sink."""
import asyncio
import json
import subprocess


def default_sink_name():
    """Best-effort: find an Audio/Sink node name to record its monitor from."""
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True,
                             timeout=5).stdout
        data = json.loads(out)
        for obj in data:
            props = (obj.get("info") or {}).get("props") or {}
            if props.get("media.class") == "Audio/Sink":
                return props.get("node.name")
    except Exception:
        return None
    return None


def record_command(target, rate):
    cmd = ["pw-record", "--rate", str(rate), "--channels", "1", "--format", "s16"]
    if target:
        cmd += ["--target", target]
    return cmd + ["-"]


class PipeWireAudioSource:
    def __init__(self, sink_lookup=None):
        self._sink_lookup = sink_lookup or default_sink_name
        self._proc = None
        self._block = 0

    async def start(self, source, target, rate, block):
        if not target and source != "mic":
            target = self._sink_lookup()   # capture the speaker output's monitor
        # "mic": pw-record with no target captures the default input
        cmd = record_command(target, rate)
        self._block = block
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        return " ".join(cmd)

    async def read(self):
        import numpy as np
        try:
            raw = await self._proc.stdout.readexactly(self._block * 2)
        except asyncio.IncompleteReadError:
            return None
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    async def stop(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            pass
