"""Drawing tile generation and coordinate transformation (FN-004, TC-011)."""

import io
from uuid import UUID, uuid4

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field


class DrawingTile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tile_id: UUID = Field(default_factory=uuid4)
    page_number: int
    tile_index: int
    x: int
    y: int
    width: int
    height: int
    overlap: float = 0.25
    image_bytes: bytes


class TileGenerator:
    def __init__(self, tile_size: int = 1024, overlap: float = 0.25) -> None:
        self.tile_size = tile_size
        self.overlap = overlap

    def create(self, image: Image.Image, page_number: int = 1) -> list[DrawingTile]:
        img_width, img_height = image.size
        step = int(self.tile_size * (1.0 - self.overlap))
        if step <= 0:
            step = self.tile_size

        tiles: list[DrawingTile] = []
        tile_index = 0

        y = 0
        while y < img_height:
            tile_h = min(self.tile_size, img_height - y)
            x = 0
            while x < img_width:
                tile_w = min(self.tile_size, img_width - x)

                # Crop sub-image
                box = (x, y, x + tile_w, y + tile_h)
                tile_img = image.crop(box)

                # Encode to bytes (PNG)
                buf = io.BytesIO()
                tile_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()

                tile = DrawingTile(
                    page_number=page_number,
                    tile_index=tile_index,
                    x=x,
                    y=y,
                    width=tile_w,
                    height=tile_h,
                    overlap=self.overlap,
                    image_bytes=img_bytes,
                )
                tiles.append(tile)
                tile_index += 1

                if x + tile_w >= img_width:
                    break
                x += step

            if y + tile_h >= img_height:
                break
            y += step

        return tiles


def tile_to_page_coords(local_x: float, local_y: float, tile: DrawingTile) -> tuple[float, float]:
    """Convert local tile pixel coordinates to full page pixel coordinates."""
    return float(tile.x) + local_x, float(tile.y) + local_y


def page_to_tile_coords(page_x: float, page_y: float, tile: DrawingTile) -> tuple[float, float]:
    """Convert full page pixel coordinates to local tile pixel coordinates."""
    return page_x - float(tile.x), page_y - float(tile.y)
