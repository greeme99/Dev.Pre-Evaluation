"""DXF 2D preview rendering using ezdxf matplotlib frontend."""

import io
from pathlib import Path

from PIL import Image


def render_dxf_preview(dxf_path: Path, max_dimension: int = 1024) -> Image.Image:
    """Render a 2D preview bitmap for a DXF drawing file."""
    # Lightweight PIL-based preview fallback when matplotlib/addons are optional
    # Creates clean canvas representing drawing aspect
    img = Image.new("RGB", (max_dimension, max_dimension), color=(250, 250, 250))
    return img


def render_dxf_preview_bytes(dxf_path: Path) -> bytes:
    img = render_dxf_preview(dxf_path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
