from PIL import Image, ImageChops
import pytest

from calypso_agent.cards import (BACKGROUND, CALL_SIZE, CAPTIONS, CONNECTING, LISTENING, PAPER,
                                 caption_cards, fit_lines, font, idle_frame, render,
                                 stamp_footer)
from calypso_agent.contract import Card

RED = (255, 0, 0)


def portrait(card, images=None):
    return render(card, images or {}, size=CALL_SIZE)


def non_paper_bbox(image, box):
    region = image.crop(box)
    return ImageChops.difference(region, Image.new("RGB", region.size, PAPER)).getbbox()


def test_palette_and_constants():
    assert BACKGROUND == PAPER == (0xFB, 0xF6, 0xEE)
    assert CONNECTING == "Connecting…" and LISTENING == "Listening…"
    assert CAPTIONS == "Let’s talk"


CARDS = [
    Card(kind="identity", title="Sarah", lines=["Your daughter", "You bake together on Sundays."]),
    Card(kind="identity", title="Margaret-Anne Whitfield " * 3, lines=["word " * 60] * 4),
    Card(kind="learning", title="Getting to know someone new…", lines=[]),
    Card(kind="learning", title="Who’s joining us?", lines=["Say their name and I’ll remember them."]),
    Card(kind="today", title="Today", lines=[]),
    Card(kind="today", title="Today", lines=["9:30 AM · Grocery shopping with Mom"] * 9),
    Card(kind="memory", title="A shared memory", lines=["Baking with Sarah", "Sundays."]),
    Card(kind="memory", title=CONNECTING, lines=[]),
    Card(kind="memory", title=LISTENING, lines=[]),
    Card(kind="memory", title=CAPTIONS, lines=["Hello there"]),
]


@pytest.mark.parametrize("card", CARDS, ids=lambda c: f"{c.kind}-{c.title[:12]}")
def test_portrait_shell(card):
    image = portrait(card)
    assert image.size == CALL_SIZE and image.mode == "RGB"
    assert image.getpixel((8, 600)) == PAPER and image.getpixel((712, 600)) == PAPER
    assert non_paper_bbox(image, (0, 0, 720, 120)) is not None  # header art
    assert non_paper_bbox(image, (0, 1216, 720, 1280)) is not None  # wave strip
    if card.title in (CONNECTING, LISTENING):
        return  # their scene waves are full-bleed by design
    # Nothing leaks into the side margins of the content area.
    assert non_paper_bbox(image, (0, 120, 40, 1216)) is None
    assert non_paper_bbox(image, (680, 120, 720, 1216)) is None


def test_truncation_cuts_at_whole_words():
    face = font(48)
    words = [f"word{i}" for i in range(60)]
    lines = fit_lines([" ".join(words)], face, 624, 2)
    assert len(lines) == 2 and lines[-1].endswith("…")
    kept = " ".join(lines)[:-1].split()
    assert kept == words[:len(kept)]
    assert all(face.getlength(line) <= 624 for line in lines)


def test_truncation_still_breaks_a_single_giant_word():
    face = font(48)
    lines = fit_lines(["x" * 200], face, 624, 1)
    assert len(lines) == 1 and lines[0].endswith("…") and face.getlength(lines[0]) <= 624


def test_short_text_is_not_truncated():
    assert fit_lines(["Hello there"], font(48), 624, 2) == ["Hello there"]


def test_today_rows_never_cross_content_bottom():
    card = Card(kind="today", title="Today",
                lines=[f"{h}:30 PM · Blue Bean Café · Coffee with Sarah and a long walk home" for h in range(1, 12)])
    image = portrait(card)
    assert non_paper_bbox(image, (0, 1184, 720, 1216)) is None
    assert non_paper_bbox(image, (48, 900, 672, 1184)) is not None  # rows did fill the page


def test_identity_without_photo_never_pastes_a_photo():
    card = Card(kind="identity", title="Sarah", lines=["Your daughter"], image_urls=["missing"])
    red = Image.new("RGB", (300, 300), RED)
    without = portrait(card, {"someone-else": red})
    assert RED not in {color for _, color in without.getcolors(1 << 20)}
    supplied = portrait(card, {"missing": red})
    assert supplied.getpixel((360, 372)) == RED


def test_memory_photo_only_when_supplied():
    card = Card(kind="memory", title="Photos from today", lines=["A walk"], image_urls=["p"])
    red = Image.new("RGB", (300, 300), RED)
    assert RED not in {color for _, color in portrait(card).getcolors(1 << 20)}
    assert RED in {color for _, color in portrait(card, {"p": red}).getcolors(1 << 20)}


def test_caption_titles_and_page_indicator():
    pages = caption_cards(" ".join(f"word{i}" for i in range(100)))
    assert len(pages) > 1
    assert [p.title for p in pages] == [f"Let’s talk · {i} of {len(pages)}" for i in range(1, len(pages) + 1)]
    assert caption_cards("Hello")[0].title == "Let’s talk"
    paged = portrait(pages[0])
    single = portrait(caption_cards("Hello")[0])
    band = (48, 1120, 672, 1184)
    left, _, right, _ = non_paper_bbox(paged, band)
    assert abs((48 + left + 48 + right) / 2 - 360) < 12  # centered
    assert non_paper_bbox(single, band) is None


def test_idle_frame_is_listening_portrait():
    assert idle_frame().tobytes() == portrait(Card(kind="memory", title=LISTENING, lines=[])).tobytes()


def test_stamp_footer_changes_only_footer_band():
    base = portrait(Card(kind="learning", title="Getting to know someone new…", lines=[]))
    assert stamp_footer(base.copy()).tobytes() == base.tobytes()
    status = stamp_footer(base.copy(), status="Learning faces · 3 samples")
    both = stamp_footer(base.copy(), status="Learning faces · 3 samples", test=True)
    for stamped in (status, both):
        box = ImageChops.difference(stamped, base).getbbox()
        assert box is not None and box[1] >= 1040 and box[3] <= 1216
    assert ImageChops.difference(both, status).getbbox()[1] < ImageChops.difference(status, base).getbbox()[1]


def test_landscape_uses_paper_and_does_not_crash():
    for card in CARDS:
        image = render(card, {})
        assert image.size == (1280, 720) and image.getpixel((1270, 710)) == PAPER


def test_long_hyphenated_name_breaks_after_the_hyphen():
    from calypso_agent.cards import _face, wrapped
    lines = wrapped("Margaret-Anne Whitfield", _face("display"), 624)
    assert lines[0] in ("Margaret-", "Margaret-Anne") and "".join(lines).replace(" ", "") == "Margaret-AnneWhitfield"
