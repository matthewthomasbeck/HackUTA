"""Real backend persistence with explicitly controlled recognition, for stage 1."""

import json
import os
from pathlib import Path

from .contract import FaceResult, PersonDetail, RecognitionResult, RecognizeResponse


class ControlledBackend:
    def __init__(self, backend, path, *, outcome="learning", name="Sample relative", relationship="relative"):
        if outcome not in {"identified", "learning", "uncertain"}:
            raise ValueError("Invalid STAGE1_RECOGNITION")
        self.backend, self.path = backend, Path(path)
        self.outcome, self.name, self.relationship = outcome, name, relationship

    def __getattr__(self, name):
        return getattr(self.backend, name)

    async def enroll(self, intro):
        person = await self.backend.enroll(intro)
        # Save only the backend id; transcripts/images remain in the backend.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"person_id": person.id}, stream)
        os.replace(temporary, self.path)
        return person

    def enrolled_id(self):
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text())["person_id"]

    async def person(self, person_id):
        stored = await self.backend.person(person_id)
        if stored.is_patient:
            return stored
        # Visibly label synthetic identity; never present it as a real match.
        return PersonDetail(**{**stored.model_dump(), "name": f"Test profile: {self.name}",
            "relationship": self.relationship, "facts": [], "memories": [], "face_photo_url": None})

    async def recognize(self, jpeg, key, call_id):
        # Exercise the actual backend route/dashboard as well; ignore its model
        # output only in this explicit test adapter.
        await self.backend.recognize(jpeg, key, call_id)
        person_id = self.enrolled_id()
        outcome = self.outcome if person_id else "learning"
        result = RecognitionResult(status=outcome, person_id=person_id if outcome == "identified" else None)
        await self.backend.event("stage1.recognition", {"call_id": call_id, "participant_key": key,
            "controlled": True, "status": outcome})
        return RecognizeResponse(faces=[FaceResult(result=result)])
