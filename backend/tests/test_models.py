from calypso.models import Card, Intent, Person


def test_person_defaults():
    p = Person(id="p1")
    assert p.is_patient is False and p.facts == []


def test_intent_rejects_unknown_kind():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Intent(intent="weather")


def test_card_roundtrip_json():
    c = Card(kind="today", title="Today", lines=["A quiet day at home"])
    assert Card.model_validate_json(c.model_dump_json()) == c
