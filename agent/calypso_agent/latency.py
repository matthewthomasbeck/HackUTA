"""Recall freshness and latency helpers (no LiveKit dependency)."""

RECALL_STALE_S = 4.0


def fresh_cards(cards, sentence_end, now, *, kinds=("today", "memory")):
    """Drop recall cards that arrive more than RECALL_STALE_S after the sentence ended."""
    if now - sentence_end <= RECALL_STALE_S:
        return list(cards)
    return [card for card in cards if card.get("kind") not in kinds]


def latency_ms(sentence_end, now):
    return round((now - sentence_end) * 1000)
