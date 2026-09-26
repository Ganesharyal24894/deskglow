"""Monitor geometry for screen mode: which rect to sample. Pure functions."""


def pick_monitor(monitors, point):
    """Return the rect of the monitor containing `point`, else the first monitor."""
    if point is not None:
        x, y = point
        for rect in monitors.values():
            if (rect["left"] <= x < rect["left"] + rect["width"]
                    and rect["top"] <= y < rect["top"] + rect["height"]):
                return rect
    return next(iter(monitors.values()))


def bounding_rect(monitors):
    """Rect covering all monitors (for 'both')."""
    left = min(r["left"] for r in monitors.values())
    top = min(r["top"] for r in monitors.values())
    right = max(r["left"] + r["width"] for r in monitors.values())
    bottom = max(r["top"] + r["height"] for r in monitors.values())
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}
