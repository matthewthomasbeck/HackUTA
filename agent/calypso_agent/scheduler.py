"""FIFO cards with a minimum reading time and bounded duplicate history."""

from collections import deque
import time

from .contract import Card


class CardScheduler:
    def __init__(self, min_show_s=6, max_show_s=10, *, clock=time.monotonic):
        if not 0 < min_show_s <= max_show_s:
            raise ValueError("Require 0 < min_show_s <= max_show_s")
        self.min_show_s, self.max_show_s = min_show_s, max_show_s
        self.clock = clock
        self._queue = deque()
        self._queued = set()
        self._shown = {}
        self._card = None
        self._since = 0

    @staticmethod
    def _key(card):
        return card.model_dump_json()

    def push(self, card: Card) -> bool:
        now = self.clock()
        self._shown = {k: t for k, t in self._shown.items() if now - t < 60}
        key = self._key(card)
        if key in self._queued or key in self._shown:
            return False
        if card.kind == "identity":
            # Placeholders carry no memory to read: an actual identity should not
            # wait behind them. Real cards keep their minimum reading time.
            self._queue = deque(c for c in self._queue if c.kind != "learning")
            self._queued = {self._key(c) for c in self._queue}
            if self._card is not None and self._card.kind == "learning":
                self._card = None
        elif card.kind == "learning":
            # Only the most recent pending neutral state is relevant.
            self._queue = deque(c for c in self._queue if c.kind != "learning")
            self._queued = {self._key(c) for c in self._queue}
        self._queue.append(card.model_copy(deep=True))
        self._queued.add(key)
        return True

    def current(self, now=None) -> Card | None:
        now = self.clock() if now is None else now
        if self._card is not None:
            age = now - self._since
            if age < self.min_show_s or (not self._queue and age < self.max_show_s):
                return self._card
            self._card = None
        if self._queue:
            self._card = self._queue.popleft()
            key = self._key(self._card)
            self._queued.remove(key)
            self._shown[key] = now
            self._since = now
        return self._card
