from calypso_agent.latency import fresh_cards, latency_ms


def test_fresh_card_kept():
    cards = [{"kind": "today"}]
    assert fresh_cards(cards, 0.0, 3.9) == cards


def test_stale_recall_card_dropped():
    assert fresh_cards([{"kind": "memory"}, {"kind": "today"}], 0.0, 4.1) == []


def test_identity_card_never_dropped():
    cards = [{"kind": "identity"}]
    assert fresh_cards(cards, 0.0, 10.0) == cards


def test_latency_ms_rounds():
    assert latency_ms(1.0, 1.2346) == 235
