"""One-line episode summaries. They state only facts present in the inputs."""
import logging
import os
import re
from typing import Iterable, Protocol

_log = logging.getLogger("calypso.summarizer")
NEUTRAL = "Talked with someone"

SYSTEM = (
    "You write one-line memory-timeline entries for a person with dementia. Write ONE line of at most "
    "12 words, plain and warm. Name only the people listed under People and only the place given under "
    "Place (never name a place if it is \"somewhere\"). Names of people, shops, restaurants or towns that are "
    "only mentioned in the conversation must not appear: describe topics generically (\"talked about dinner "
    "plans\"). Never invent names, places, activities or details. If unsure, reply exactly: "
    f"{NEUTRAL}"
)

_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)([^\W\d_]+)")


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def grounded(summary: str, lines: list[str], allowed: Iterable[str]) -> str:
    """`summary`, or NEUTRAL if it names anyone or anything outside `allowed`.

    Deterministic gate for the "never name a person or place without evidence" rule:
    a capitalized word mid-sentence must be one of the allowed names (people, their
    relationships, the place). A capitalized sentence-first word is rejected too when
    the transcript only ever writes it capitalized (a proper noun such as "Bob").
    """
    ok = {w.casefold() for a in allowed if a for w in _words(a)} | {"i"}
    starts = {m.start(1) for m in _SENTENCE_START.finditer(summary)}
    line_words = [w for l in lines for w in _words(l)]
    lower_seen = {w.casefold() for w in line_words if not w[0].isupper()}
    proper_in_lines = {w.casefold() for w in line_words if w[0].isupper()} - lower_seen
    for m in _WORD.finditer(summary):
        w = m.group(0)
        if not w[0].isupper() or w.casefold() in ok:
            continue
        if m.start() not in starts or w.casefold() in proper_in_lines:
            _log.info("summary %r names %r without evidence; using neutral", summary, w)
            return NEUTRAL
    return summary


class Summarizer(Protocol):
    def summarize(self, lines: list[str], people: list[str], place: str) -> str: ...


class FakeSummarizer:
    def summarize(self, lines: list[str], people: list[str], place: str) -> str:
        if people:
            return "Talked with " + ", ".join(people)
        if lines:
            return lines[0][:60]
        return NEUTRAL


class ClaudeSummarizer:
    def __init__(self, settings=None) -> None:
        import anthropic

        self.client = anthropic.Anthropic(timeout=10.0)
        self.model = os.environ.get("CALYPSO_SUMMARY_MODEL", "claude-sonnet-4-6")

    def summarize(self, lines: list[str], people: list[str], place: str) -> str:
        prompt = (f"Place: {place}\nPeople: {', '.join(people) or 'unknown'}\nConversation:\n"
                  + "\n".join(f"- {l}" for l in lines[:40]))
        try:
            msg = self.client.messages.create(
                model=self.model, max_tokens=60, system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            text = text.splitlines()[0].strip() if text else ""
            return text or NEUTRAL
        except Exception as exc:  # a failed summary must not block the timeline
            _log.warning("summary failed: %s", exc)
            return NEUTRAL


def get_summarizer(settings) -> Summarizer:
    if settings.summarizer == "claude":
        return ClaudeSummarizer(settings)
    return FakeSummarizer()
