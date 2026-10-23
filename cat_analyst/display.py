"""Map the primary-display selection from Qt logical units to physical pixels."""
from __future__ import annotations


def primary_monitor(monitors: list[dict]) -> dict:
    # mss.monitors[0] is the virtual desktop. Enumeration order of real displays
    # is not guaranteed: index 1 can be a secondary display, even on Windows.
    physical = monitors[1:]
    marked = [monitor for monitor in physical if monitor.get('is_primary')]
    if len(marked) == 1:
        return marked[0]
    # Windows positions the primary display at desktop origin. Older mss
    # versions do not expose is_primary; do not fall back to list order.
    at_origin = [monitor for monitor in physical
                 if monitor['left'] == 0 and monitor['top'] == 0]
    if len(at_origin) == 1:
        return at_origin[0]
    raise ValueError('Cannot identify the primary display. Check Windows display settings.')


def selection_region(monitors: list[dict], logical_width: int, logical_height: int,
                     left: int, top: int, width: int, height: int) -> dict:
    monitor = primary_monitor(monitors)
    if logical_width <= 0 or logical_height <= 0 or width <= 0 or height <= 0:
        raise ValueError('The selected capture area is empty.')
    # Use actual display dimensions rather than assuming the monitor index or
    # multiplying desktop origins by a DPI ratio (origins are already physical).
    scale_x = monitor['width'] / logical_width
    scale_y = monitor['height'] / logical_height
    x1 = max(0, min(monitor['width'], round(left * scale_x)))
    y1 = max(0, min(monitor['height'], round(top * scale_y)))
    x2 = max(0, min(monitor['width'], round((left + width) * scale_x)))
    y2 = max(0, min(monitor['height'], round((top + height) * scale_y)))
    if x2 - x1 < 2 or y2 - y1 < 2:
        raise ValueError('The selected area lies outside the primary display.')
    return dict(left=monitor['left'] + x1, top=monitor['top'] + y1,
                width=x2 - x1, height=y2 - y1)
