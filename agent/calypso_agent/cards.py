"""Paper-cut call cards. Image bytes must come from approved sources.

The agent's FaceTime video is a 720×1280 portrait frame (`render(..., size=CALL_SIZE)`); the
1280×720 landscape path is kept for the offline demo. Layouts follow the Figma page `06 In-Call`.
The fonts have no U+207B, so "Calypso⁻¹" only ever comes from the header art, never drawn text.
"""

import argparse
from functools import lru_cache
import os
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .contract import Card

ASSETS = Path(__file__).resolve().parent / "assets"
CALL_SIZE = (720, 1280)

PAPER = (0xFB, 0xF6, 0xEE)
CARD = (0xFF, 0xFF, 0xFF)
INK = (0x1E, 0x2A, 0x44)
INK_SOFT = (0x4A, 0x47, 0x59)
PERIWINKLE = (0x9A, 0xA6, 0xE8)
PERIWINKLE_DEEP = (0x3E, 0x4A, 0x9E)
PERIWINKLE_MIST = (0xC9, 0xD0, 0xF5)
APRICOT = (0xF4, 0xA9, 0x7A)
APRICOT_CREAM = (0xFA, 0xD3, 0xB5)
BACKGROUND = PAPER

# System-state titles (all `memory` cards).
CONNECTING = "Connecting…"
LISTENING = "Listening…"
CAPTIONS = "Let’s talk"
QUIET_DAY = "Nothing new yet today. Rest days matter too."

# Type scale: file, size, line height.
STYLES = {
    "display": ("Fraunces-SemiBold.ttf", 96, 108),
    "title": ("Fraunces-SemiBold.ttf", 72, 84),
    "headline": ("Nunito-Bold.ttf", 56, 68),
    "body": ("Nunito-Regular.ttf", 48, 64),
    "strong": ("Nunito-Bold.ttf", 48, 64),
    "caption": ("Nunito-SemiBold.ttf", 40, 52),
}

# Shell geometry (portrait).
MARGIN, TEXT_W = 48, 624
WAVE_Y = 1216
TOP, BOTTOM = 152, 1184  # content area 120–1216 minus 32 padding
GAP = 32
CAPTION_LINES = 7
_PAGE = re.compile(r" · (\d+) of (\d+)$")
_TIME = re.compile(r"^(\d{1,2}:\d{2}\s?[AaPp][Mm])\b\s*[·•\-–—:|]?\s*(.*)$")


@lru_cache(maxsize=64)
def _truetype(path, size):
    return ImageFont.truetype(path, size)


def _face(style):
    name, size, _ = STYLES[style]
    return _truetype(str(ASSETS / "fonts" / name), size)


def _leading(style):
    return STYLES[style][2]


def font(size):
    """Nunito Regular at `size`; CALYPSO_FONT may point at another TTF."""
    custom = os.getenv("CALYPSO_FONT")
    if custom:
        try:
            return _truetype(custom, size)
        except OSError:
            pass
    return _truetype(str(ASSETS / "fonts" / "Nunito-Regular.ttf"), size)


@lru_cache(maxsize=None)
def _art(name):
    return Image.open(ASSETS / "art" / name).convert("RGBA")


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
        for piece in re.split(r"(?<=-)(?=.)", word):  # prefer breaking after a hyphen
            if face.getlength(line + piece) <= width:
                line += piece
                continue
            if line:
                lines.append(line)
                line = ""
            for char in piece:
                if line and face.getlength(line + char) > width:
                    lines.append(line)
                    line = ""
                line += char
    if line:
        lines.append(line)
    return lines


def fit_lines(texts, face, width, max_lines):
    """Wrap `texts` (one paragraph each); past `max_lines`, cut at the last whole word + "…"."""
    lines = [line for text in texts for line in wrapped(text, face, width)]
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    words = lines[-1].split(" ")
    while len(words) > 1 and face.getlength(" ".join(words) + "…") > width:
        words.pop()
    last = " ".join(words)
    while last and face.getlength(last + "…") > width:  # one word wider than the line
        last = last[:-1]
    lines[-1] = last.rstrip(" ,;:·-–—") + "…"
    return lines


def _draw_lines(draw, lines, face, line_height, *, x, y, width, fill, align="left"):
    ascent, descent = face.getmetrics()
    offset = (line_height - ascent - descent) // 2 + ascent
    for index, line in enumerate(lines):
        baseline = y + index * line_height + offset
        if align == "center":
            draw.text((x + width / 2, baseline), line, font=face, fill=fill, anchor="ms")
        else:
            draw.text((x, baseline), line, font=face, fill=fill, anchor="ls")
    return len(lines) * line_height


def text_block(draw, texts, *, x, y, width, line_height, max_lines, fill, size=None, face=None,
               align="left"):
    """Draw wrapped, truncated text; returns the height used."""
    face = face or font(size)
    lines = fit_lines(texts, face, width, max_lines)
    return _draw_lines(draw, lines, face, line_height, x=x, y=y, width=width, fill=fill, align=align)


# --- Blocks: (height, draw(image, draw, top)) stacked down the content area ---

def _text(texts, style, color, *, max_lines, align="center", x=MARGIN, width=TEXT_W):
    texts = [t for t in texts if t and t.strip()]
    face, leading = _face(style), _leading(style)
    lines = fit_lines(texts, face, width, max_lines)
    if not lines:
        return None
    return (len(lines) * leading,
            lambda image, draw, top: _draw_lines(draw, lines, face, leading, x=x, y=top,
                                                 width=width, fill=color, align=align))


def _picture(name, x=None):
    art = _art(name)
    left = (CALL_SIZE[0] - art.width) // 2 if x is None else x
    return art.height, lambda image, draw, top: image.paste(art, (left, top), art)


def _rounded_mask(size, radius):
    scale = 4
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1),
                                          radius=radius * scale, fill=255)
    return big.resize(size, Image.LANCZOS)


def _mat(width, height, photo):
    """Apricot Cream mat (radius 24, padding 16) around a rounded photo with a 4px white border."""
    left = (CALL_SIZE[0] - width) // 2
    inner = (width - 32, height - 32)

    def paint(image, draw, top):
        draw.rounded_rectangle((left, top, left + width - 1, top + height - 1), radius=24,
                               fill=APRICOT_CREAM)
        fitted = ImageOps.fit(photo.convert("RGB"), inner)
        image.paste(fitted, (left + 16, top + 16), _rounded_mask(inner, 16))
        draw.rounded_rectangle((left + 16, top + 16, left + 15 + inner[0], top + 15 + inner[1]),
                               radius=16, outline=CARD, width=4)
    return height, paint


def _height(blocks, gap=GAP):
    blocks = [b for b in blocks if b]
    return sum(h for h, _ in blocks) + gap * max(len(blocks) - 1, 0)


def _first_fit(*candidates):
    for blocks in candidates:
        if _height(blocks) <= BOTTOM - TOP:
            return blocks
    return candidates[-1]


def _stack(image, blocks, *, top=TOP, gap=GAP, center=True):
    blocks = [b for b in blocks if b]
    y = top + max((BOTTOM - top - _height(blocks, gap)) // 2, 0) if center else top
    draw = ImageDraw.Draw(image)
    for height, paint in blocks:
        paint(image, draw, y)
        y += height + gap
    return y - gap


def _shell():
    image = Image.new("RGB", CALL_SIZE, PAPER)
    image.paste(_art("header.png"), (0, 0), _art("header.png"))
    image.paste(_art("wave-strip.png"), (0, WAVE_Y), _art("wave-strip.png"))
    return image


def _photo(card, images):
    return next((images[url] for url in card.image_urls if url in images), None)


def _fit_with_body(build):
    """Try the full layout, then drop the gull, then shorten the body text."""
    return _first_fit(build(True, 3), *(build(False, n) for n in (3, 2, 1, 0)))


# --- Card layouts ---

def _identity(image, card, images):
    photo = _photo(card, images)
    hero = _mat(400, 440, photo) if photo is not None else _picture("avatar-known.png")
    name = _text([card.title], "display", INK, max_lines=2)
    relation = _text(card.lines[:1], "headline", PERIWINKLE_DEEP, max_lines=2)
    def build(gull, body):
        rest = _text(card.lines[1:], "body", INK_SOFT, max_lines=body) if body else None
        return [hero, name, relation, rest, _picture("gull-presenting-120.png") if gull else None]
    _stack(image, _fit_with_body(build))


def _learning(image, card, images):
    def build(gull, body):
        return [_picture("avatar-unknown.png"),
                _text([card.title], "title", INK, max_lines=3),
                _text(card.lines, "body", INK_SOFT, max_lines=body) if body else None,
                _picture("gull-thinking-120.png") if gull else None]
    _stack(image, _fit_with_body(build))


def _moment(line):
    """A white row: optional Apricot time tag, then the rest in Body Strong."""
    match = _TIME.match(line.strip())
    tag, rest = (match.group(1), match.group(2)) if match else (None, line.strip())
    strong, caption = _face("strong"), _face("caption")
    lines = fit_lines([rest], strong, TEXT_W - 48, 2) if rest else []
    height = 32 + (64 if tag else 0) + (4 if tag and lines else 0) + 64 * len(lines)

    def paint(image, draw, top, boat=False):
        draw.rounded_rectangle((MARGIN, top, MARGIN + TEXT_W - 1, top + height - 1), radius=24, fill=CARD)
        y = top + 16
        if tag:
            width = int(caption.getlength(tag)) + 40
            draw.rounded_rectangle((MARGIN + 24, y, MARGIN + 24 + width, y + 63), radius=16, fill=APRICOT)
            _draw_lines(draw, [tag], caption, 52, x=MARGIN + 44, y=y + 6, width=width, fill=INK)
            if boat:
                art = _art("boat.png")
                image.paste(art, (MARGIN + TEXT_W - 24 - art.width, y + 32 - art.height // 2), art)
            y += 68
        _draw_lines(draw, lines, strong, 64, x=MARGIN + 24, y=y, width=TEXT_W - 48, fill=INK)
    return height, paint, bool(tag)


def _today(image, card, images):
    if not card.lines:
        _stack(image, [_picture("gull-resting-200.png"),
                       _text([card.title], "title", INK, max_lines=2),
                       _text([QUIET_DAY], "body", INK_SOFT, max_lines=3)])
        return
    draw = ImageDraw.Draw(image)
    y = _stack(image, [_text([card.title], "title", INK, max_lines=2, align="left")], center=False) + GAP
    rows = []
    for line in card.lines:
        row = _moment(line)
        if y + row[0] > BOTTOM:
            break  # drop the rest; never shrink text
        rows.append((y, row))
        y += row[0] + 16
    for index, (top, (_, paint, tagged)) in enumerate(rows):
        paint(image, draw, top, boat=tagged and index == len(rows) - 1)


def _captions(image, card):
    page = _PAGE.search(card.title)
    heading = card.title[:page.start()] if page else card.title
    _stack(image, [_text([heading], "caption", PERIWINKLE_DEEP, max_lines=1, align="left"),
                   _text(card.lines, "body", INK, max_lines=CAPTION_LINES, align="left")],
           gap=24, center=False)
    if page:
        _, paint = _text([f"{page.group(1)} of {page.group(2)}"], "caption", INK_SOFT, max_lines=1)
        paint(image, ImageDraw.Draw(image), BOTTOM - _leading("caption"))


def _scene(height, layers):
    def paint(image, draw, top):
        for layer in layers:
            layer(image, draw, top)
    return height, paint


def _put(name, x, y):
    art = _art(name)
    return lambda image, draw, top: image.paste(art, (x, top + y), art)


def _connecting(image):
    gull = _art("gull-sailing-400.png")
    waves_y = gull.height - 10
    scene = _scene(waves_y + _art("scene-waves.png").height,
                   [_put("scene-waves.png", 0, waves_y), _put("gull-sailing-400.png", (720 - gull.width) // 2, 0)])
    _stack(image, [scene, _text([CONNECTING], "title", INK, max_lines=1)])


def _listening(image):
    sun = lambda image, draw, top: draw.ellipse((480, top + 40, 599, top + 159), fill=APRICOT_CREAM)
    scene = _scene(525 + _art("scene-waves.png").height,
                   [sun, _put("scene-waves.png", 0, 525), _put("island-home.png", 378, 375),
                    _put("gull-lantern-300.png", 108, 306)])
    _stack(image, [scene, _text([LISTENING], "headline", INK, max_lines=1)])


def _panel(card):
    """White panel, 4px Periwinkle Mist border: Caption title / Headline line 0 / Body rest."""
    def build(body):
        inner = [_text([card.title], "caption", PERIWINKLE_DEEP, max_lines=2, x=88, width=544),
                 _text(card.lines[:1], "headline", INK, max_lines=2, x=88, width=544),
                 _text(card.lines[1:], "body", INK_SOFT, max_lines=body, x=88, width=544) if body else None]
        height = 96 + _height(inner, 24)
        def paint(image, draw, top):
            draw.rounded_rectangle((MARGIN, top, MARGIN + TEXT_W - 1, top + height - 1), radius=32,
                                   fill=CARD, outline=PERIWINKLE_MIST, width=4)
            _stack(image, inner, top=top + 48, gap=24, center=False)
        return height, paint
    return build


def _memory(image, card, images):
    if card.title == CONNECTING:
        return _connecting(image)
    if card.title == LISTENING:
        return _listening(image)
    if card.title.startswith(CAPTIONS):
        return _captions(image, card)
    photo = _photo(card, images)
    if photo is not None:
        def build(gull, body):
            return [_text([card.title], "caption", PERIWINKLE_DEEP, max_lines=2),
                    _mat(TEXT_W, 440, photo),
                    _text(card.lines[:1], "headline", INK, max_lines=2),
                    _text(card.lines[1:], "body", INK_SOFT, max_lines=min(body, 2)) if body else None,
                    _picture("gull-holding-photo-120.png") if gull else None]
    else:
        panel = _panel(card)
        def build(gull, body):
            return [panel(body), _picture("gull-lantern-200.png") if gull else None]
    _stack(image, _fit_with_body(build))


LAYOUTS = {"identity": _identity, "learning": _learning, "today": _today, "memory": _memory}


def render_portrait(card, images):
    image = _shell()
    LAYOUTS[card.kind](image, card, images)
    return image


def stamp_footer(image, *, status=None, test=False):
    """Draw the shell footer band above the wave strip: optional TEST MODE pill, then a status line."""
    if not status and not test:
        return image
    draw = ImageDraw.Draw(image)
    caption = _face("caption")
    top = WAVE_Y - 24
    status_top = pill_top = None
    if status:
        top = status_top = top - 52
    if test:
        top = pill_top = top - (16 if status else 0) - 68
    draw.rectangle((0, top, CALL_SIZE[0] - 1, WAVE_Y - 1), fill=PAPER)
    if status:
        lines = fit_lines([status], caption, TEXT_W, 1)
        _draw_lines(draw, lines, caption, 52, x=MARGIN, y=status_top, width=TEXT_W, fill=INK_SOFT,
                    align="center")
    if test:
        label = "TEST MODE"
        width = int(caption.getlength(label)) + 48
        left = (CALL_SIZE[0] - width) // 2
        draw.rounded_rectangle((left, pill_top, left + width - 1, pill_top + 67), radius=34,
                               fill=APRICOT_CREAM)
        _draw_lines(draw, [label], caption, 52, x=left, y=pill_top + 8, width=width, fill=INK,
                    align="center")
    return image


def render(card: Card, images: dict[str, Image.Image], *, size=(1280, 720)) -> Image.Image:
    if size == CALL_SIZE:
        return render_portrait(card, images)
    image = Image.new("RGB", (1280, 720), PAPER)
    image.paste(_art("header.png"), (0, 0), _art("header.png"))
    draw = ImageDraw.Draw(image)
    identity = card.kind == "identity"
    width = 800 if identity else 1152
    text_block(draw, [card.title], x=64, y=152, width=width, face=_face("title"),
               line_height=84, max_lines=2, fill=INK)
    text_block(draw, card.lines, x=64, y=350, width=width, face=_face("body"),
               line_height=64, max_lines=4, fill=INK_SOFT)
    if identity:
        photo = _photo(card, images)
        if photo is not None:
            image.paste(ImageOps.fit(photo.convert("RGB"), (288, 400)), (928, 160),
                        _rounded_mask((288, 400), 16))
        else:
            draw.rounded_rectangle((928, 160, 1215, 559), radius=24, fill=APRICOT_CREAM)
            avatar = _art("avatar-known.png")
            image.paste(avatar, (1072 - avatar.width // 2, 360 - avatar.height // 2), avatar)
    return image


def caption_cards(text):
    """Page full spoken captions; no words lost to a tiny landscape subtitle."""
    lines = wrapped(text, _face("body"), TEXT_W)
    pages = [lines[i:i + CAPTION_LINES] for i in range(0, len(lines), CAPTION_LINES)]
    if not pages:
        return [Card(kind="memory", title=LISTENING, lines=[])]
    count = len(pages)
    return [Card(kind="memory", title=CAPTIONS if count == 1 else f"{CAPTIONS} · {n} of {count}",
                 lines=page) for n, page in enumerate(pages, 1)]


def idle_frame():
    return render(Card(kind="memory", title=LISTENING, lines=[]), {}, size=CALL_SIZE)


def _demo_photo():
    """A drawn placeholder (sky, sun, hills), clearly not a real person or place."""
    image = Image.new("RGB", (600, 420), PERIWINKLE_MIST)
    draw = ImageDraw.Draw(image)
    draw.ellipse((420, 50, 500, 130), fill=APRICOT)
    draw.polygon([(40, 420), (240, 170), (440, 420)], fill=PERIWINKLE_DEEP)
    draw.polygon([(250, 420), (420, 250), (600, 420)], fill=INK_SOFT)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.demo:
        parser.error("Use --demo to generate sample cards")
    out = Path("out")
    out.mkdir(exist_ok=True)
    photo = {"demo-photo": _demo_photo()}
    talk = ("Good morning, Mary! Sarah is here with you today. She drove in from Austin and brought "
            "Biscuit along. Would you like to hear about your morning? After lunch you sat in the "
            "garden and listened to the birds for a while before your nap.")
    cards = {
        "identity-photo": (Card(kind="identity", title="Sarah", image_urls=["demo-photo"],
                                lines=["Your daughter", "You bake together on Sundays."]), photo),
        "identity-no-photo": (Card(kind="identity", title="Tom",
                                   lines=["Your neighbor", "He waves hello from next door."]), {}),
        "identity-long": (Card(kind="identity", title="Margaret-Anne Whitfield", lines=[
            "Your oldest and dearest friend from the neighborhood",
            "You have walked to the lake together every single morning for many years and talked about everything.",
            "She always brings fresh lemon cake whenever she comes to visit your home on Sundays."]), {}),
        "learning": (Card(kind="learning", title="Getting to know someone new…", lines=[]), {}),
        "learning-ask": (Card(kind="learning", title="Who’s joining us?",
                              lines=["Say their name and I’ll remember them."]), {}),
        "today": (Card(kind="today", title="Your day so far", lines=[
            "9:30 AM · Grocery shopping with Mom", "11:00 AM · Coffee with Sarah",
            "12:30 PM · Lunch at home", "3:00 PM · A walk in the garden",
            "5:00 PM · Dinner with Tom"]), {}),
        "today-quiet": (Card(kind="today", title="A quiet day", lines=[]), {}),
        "memory-photo": (Card(kind="memory", title="A shared memory", image_urls=["demo-photo"],
                              lines=["Baking with Sarah", "Sundays in your kitchen — cinnamon rolls."]), photo),
        "memory-text": (Card(kind="memory", title="A shared memory",
                             lines=["Baking with Sarah", "Sundays in your kitchen — cinnamon rolls."]), {}),
        "connecting": (Card(kind="memory", title=CONNECTING, lines=[]), {}),
        "listening": (Card(kind="memory", title=LISTENING, lines=[]), {}),
    }
    for index, page in enumerate(caption_cards(talk), 1):
        cards[f"captions-{index}"] = (page, {})
    for name, (card, images) in cards.items():
        render(card, images, size=CALL_SIZE).save(out / f"{name}-portrait.png")
        render(card, images).save(out / f"{name}.png")
    stamp_footer(render(cards["learning"][0], {}, size=CALL_SIZE),
                 status="Learning faces · 3 samples", test=True).save(out / "learning-footer-portrait.png")
    idle_frame().save(out / "idle.png")


if __name__ == "__main__":
    main()
