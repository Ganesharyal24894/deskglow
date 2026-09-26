"""Turning the strip back on: remember what was lit, restore it on `on`."""
from ..model.color import clamp8
from ..model.settings import WARM_WHITE


def _rgb_or_none(value):
    """A clean [r, g, b] from a request's rgb, or None if it isn't one."""
    try:
        if len(value) == 3 and not any(isinstance(c, bool) for c in value):
            return [clamp8(float(c)) for c in value]
    except (TypeError, ValueError):
        pass
    return None


class PowerMixin:
    """Mixed into Daemon. Expects state, settings, mode_name, mode_args, set_mode."""

    def _remember(self, name, args):
        """Called before every mode switch (under the mode lock)."""
        if name == "off" and self.mode_name != "off":
            self.state["resume"] = {"mode": self.mode_name, "args": self.mode_args}
        if name == "solid":
            rgb = _rgb_or_none((args or {}).get("rgb"))
            if rgb is not None:
                self.state["last_solid"] = rgb

    def last_solid(self):
        rgb = _rgb_or_none(self.state.get("last_solid"))
        return rgb if rgb is not None else list(WARM_WHITE)

    async def turn_on_solid(self):
        """Light the last solid colour (warm white if there never was one)."""
        await self.set_mode("solid", {"rgb": self.last_solid()})

    async def turn_on(self):
        """Resume the mode that was running before `off`, else a solid colour."""
        resume = self.state.get("resume")
        if (isinstance(resume, dict) and isinstance(resume.get("mode"), str)
                and resume["mode"] != "off"):
            await self.set_mode(resume["mode"], resume.get("args") or {})
            if self.mode_name != "off":
                return
        await self.turn_on_solid()
