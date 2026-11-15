from pathlib import Path

import pytest
from PIL import Image, ImageFont

ASSETS = Path(__file__).resolve().parents[1] / "calypso_agent" / "assets"

ART_WIDTHS = {
    "header.png": 720,
    "wave-strip.png": 720,
    "scene-waves.png": 720,
    "boat.png": 84,
    "island-home.png": 264,
    "avatar-unknown.png": 280,
    "avatar-known.png": 280,
    "gull-presenting-120.png": 120,
    "gull-thinking-120.png": 120,
    "gull-thinking-200.png": 200,
    "gull-holding-photo-120.png": 120,
    "gull-lantern-200.png": 200,
    "gull-lantern-300.png": 300,
    "gull-resting-200.png": 200,
    "gull-sailing-400.png": 400,
}
FONTS = [
    "Fraunces-SemiBold.ttf",
    "Nunito-Regular.ttf",
    "Nunito-SemiBold.ttf",
    "Nunito-Bold.ttf",
]


@pytest.mark.parametrize("name,width", ART_WIDTHS.items())
def test_art_is_rgba_with_expected_width(name, width):
    with Image.open(ASSETS / "art" / name) as im:
        assert im.mode == "RGBA"
        assert im.width == width


@pytest.mark.parametrize("name", FONTS)
def test_font_loads(name):
    assert ImageFont.truetype(str(ASSETS / "fonts" / name), 48) is not None


@pytest.mark.parametrize("name", ["Fraunces-OFL.txt", "Nunito-OFL.txt"])
def test_licenses_present(name):
    assert (ASSETS / "fonts" / name).stat().st_size > 0
