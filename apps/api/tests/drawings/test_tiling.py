"""Tests for drawing tile generation and coordinate transformations (FN-004, TC-011)."""

import pytest
from PIL import Image

from dev_pre_review.drawings.tiling import (
    DrawingTile,
    TileGenerator,
    page_to_tile_coords,
    tile_to_page_coords,
)


def test_tile_generator_creates_overlapping_tiles() -> None:
    # 2480 x 3508 page (approx A4 @ 300 DPI)
    image = Image.new("RGB", (2480, 3508), color="white")
    generator = TileGenerator(tile_size=1024, overlap=0.25)

    tiles = generator.create(image, page_number=1)
    assert len(tiles) > 1

    # Check first tile properties
    first = tiles[0]
    assert isinstance(first, DrawingTile)
    assert first.page_number == 1
    assert first.tile_index == 0
    assert first.x == 0
    assert first.y == 0
    assert first.width <= 1024
    assert first.height <= 1024
    assert first.overlap == 0.25
    assert len(first.image_bytes) > 0


def test_tile_coordinate_round_trip() -> None:
    tile = DrawingTile(
        page_number=1,
        tile_index=3,
        x=768,  # Step with 25% overlap on 1024px is 768px offset
        y=1536,
        width=1024,
        height=1024,
        overlap=0.25,
        image_bytes=b"dummy",
    )

    local_x, local_y = 150.0, 200.0
    page_x, page_y = tile_to_page_coords(local_x, local_y, tile)
    assert page_x == 768.0 + 150.0
    assert page_y == 1536.0 + 200.0

    round_x, round_y = page_to_tile_coords(page_x, page_y, tile)
    assert pytest.approx(round_x) == local_x
    assert pytest.approx(round_y) == local_y
