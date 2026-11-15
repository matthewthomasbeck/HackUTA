"""One-line episode summaries. They state only facts present in the inputs."""
import logging
import os
from typing import Protocol

_log = logging.getLogger("calypso.summarizer")
NEUTRAL = "Talked with someone"

SYSTEM = (
    "You write one-line memory-timeline entries for a person with dementia. Write ONE line of at most "
    "12 words, plain and warm. Use only facts present in the conversation lines, the people names and the "
    f"place given. Never invent names, places, activities or details. If unsure, reply exactly: {NEUTRAL}"
)


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
