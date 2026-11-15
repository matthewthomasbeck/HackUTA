"""Readable 1280×720 card frames. Image bytes must come from approved sources."""

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .contract import Card

BACKGROUND = (12, 24, 40)
FOREGROUND = (245, 248, 250)
ACCENT = (112, 224, 199)


def font(size):
    candidates = [os.getenv("CALYPSO_FONT"), "DejaVuSans.ttf",
                  "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                  "/System/Library/Fonts/Supplemental/Arial.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
    for path in filter(None, candidates):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def wrapped(text, face, width):
    """Wrap even unbroken strings; every output line fits the pixel budget."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if face.getlength(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        for char in word:
            if line and face.getlength(line + char) > width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines


def text_block(draw, texts, *, x, y, width, size, line_height, max_lines, fill):
    face = font(size)
    lines = [line for text in texts for line in wrapped(text, face, width)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and face.getlength(last + "…") > width:
            last = last[:-1]
        lines[-1] = last + "…"
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=face, fill=fill, anchor="lt")


def render(card: Card, images: dict[str, Image.Image]) -> Image.Image:
    image = Image.new("RGB", (1280, 720), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((64, 48), "Calypso⁻¹", font=font(40), fill=ACCENT, anchor="lt")
    identity = card.kind == "identity"
    width = 800 if identity else 1152
    text_block(draw, [card.title], x=64, y=136, width=width, size=76,
               line_height=88, max_lines=2, fill=FOREGROUND)
    text_block(draw, card.lines, x=64, y=350, width=width, size=44,
               line_height=58, max_lines=4, fill=FOREGROUND)
    if identity:
        bounds = (928, 160, 1216, 560)
        photo = next((images[url] for url in card.image_urls if url in images), None)
        if photo is not None:
            image.paste(ImageOps.fit(photo.convert("RGB"), (288, 400)), (928, 160))
        else:
            draw.rounded_rectangle(bounds, radius=24, fill=(33, 52, 72))
            draw.ellipse((1018, 228, 1126, 336), fill=(129, 154, 173))
            draw.rounded_rectangle((978, 360, 1166, 500), radius=60, fill=(129, 154, 173))
    return image


def idle_frame():
    return render(Card(kind="memory", title="Listening…", lines=[]), {})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.demo:
        parser.error("Use --demo to generate sample cards")
    Path("out").mkdir(exist_ok=True)
    for card in [Card(kind="identity", title="Sarah", lines=["daughter", "You bake together on Sundays."]),
                 Card(kind="learning", title="Getting to know someone new…", lines=[]),
                 Card(kind="today", title="Today", lines=["A quiet day at home"]),
                 Card(kind="memory", title="A shared memory", lines=["Baking together on Sundays."])]:
        render(card, {}).save(f"out/{card.kind}.png")
    idle_frame().save("out/idle.png")


if __name__ == "__main__":
    main()
