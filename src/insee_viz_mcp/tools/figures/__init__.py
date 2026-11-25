"""The three render tools, one module per figure form.

`map.py`, `bars.py` and `line.py` each own one drawing: the spec to build, the warnings only that
form can produce, and the table behind it. `common.py` holds what all three share.
"""

from .bars import render_bars
from .line import render_line
from .map import render_map

__all__ = ["render_bars", "render_line", "render_map"]
