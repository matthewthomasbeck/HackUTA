"""Per-call recognition decisions; uncertainty never becomes a guessed identity."""

from collections import defaultdict

from .contract import Card, PersonDetail, RecognitionResult


class CallState:
    def __init__(self, people: dict[str, PersonDetail]):
        self.people = people
        self.participants: dict[str, RecognitionResult] = {}
        self._learning_frames = defaultdict(int)
        self._identities: set[tuple[str, str]] = set()
        self._learned: set[str] = set()

    def on_result(self, key: str, result: RecognitionResult | None) -> list[Card]:
        if result is None:
            self.participants.pop(key, None)
            self._learning_frames[key] = 0
            return []
        self.participants[key] = result
        if result.status != "learning":
            self._learning_frames[key] = 0
        if result.status == "identified":
            person = self.people.get(result.person_id)
            if person is None or person.is_patient or not person.name:
                return []
            identity = (key, person.id)
            if identity in self._identities:
                return []
            self._identities.add(identity)
            lines = ([person.relationship] if person.relationship else [])
            lines += (person.memories or person.facts)[:3]
            return [Card(kind="identity", title=person.name, lines=lines,
                         image_urls=[person.face_photo_url] if person.face_photo_url else [])]
        if result.status == "learning":
            self._learning_frames[key] += 1
            if self._learning_frames[key] >= 3 and key not in self._learned:
                self._learned.add(key)
                return [Card(kind="learning", title="Getting to know someone new…", lines=[])]
        return []
