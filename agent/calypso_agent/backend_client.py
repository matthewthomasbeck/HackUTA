"""Backend HTTP boundary. Fakes return fixtures, never simulated model claims."""

import base64
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote
from uuid import uuid4

import httpx

from .contract import (BusEvent, Call, CallCreate, CallLineIn, FaceResult,
                       IntroRequest, Person, PersonDetail, RecognitionResult,
                       RecognizeRequest, RecognizeResponse)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class Backend(Protocol):
    async def patient(self) -> Person: ...
    async def person(self, person_id: str) -> PersonDetail: ...
    async def enroll(self, intro: IntroRequest) -> Person: ...
    async def recognize(self, jpeg: bytes, key: str, call_id: str) -> RecognizeResponse: ...
    async def start_call(self, kind: str, participants: list[str]) -> Call: ...
    async def log_line(self, call_id: str, line: CallLineIn) -> None: ...
    async def end_call(self, call_id: str) -> None: ...
    async def event(self, stage: str, payload: dict) -> None: ...


class BackendClient:
    def __init__(self, base_url: str, token: str, *, client: httpx.AsyncClient | None = None):
        if not token:
            raise ValueError("CALYPSO_API_TOKEN is required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = client or httpx.AsyncClient(timeout=3)
        self._owns_client = client is None

    async def close(self):
        if self._owns_client:
            await self.http.aclose()

    async def _request(self, method, path, **kwargs):
        response = await self.http.request(method, self.base_url + path,
            headers={"Authorization": f"Bearer {self.token}"}, **kwargs)
        response.raise_for_status()
        return response.json()

    async def patient(self):
        records = await self._request("GET", "/people", params={"is_patient": "true"})
        people = [Person.model_validate(p) for p in records]
        if len(people) != 1 or not people[0].is_patient:
            raise ValueError("Exactly one enrolled patient is required")
        return people[0]

    async def person(self, person_id):
        return PersonDetail.model_validate(await self._request("GET", f"/people/{quote(person_id, safe='')}"))

    async def enroll(self, intro):
        return Person.model_validate(await self._request("POST", "/people/from_intro", json=intro.model_dump(mode="json")))

    async def recognize(self, jpeg, key, call_id):
        body = RecognizeRequest(face_jpeg_b64=b64(jpeg), exclude_patient=True,
                                participant_key=key, call_id=call_id)
        return RecognizeResponse.model_validate(await self._request("POST", "/recognize", json=body.model_dump(mode="json")))

    async def start_call(self, kind, participants):
        body = CallCreate(kind=kind, participants=participants)
        return Call.model_validate(await self._request("POST", "/calls", json=body.model_dump(mode="json")))

    async def log_line(self, call_id, line):
        await self._request("POST", f"/calls/{quote(call_id, safe='')}/lines", json=line.model_dump(mode="json"))

    async def end_call(self, call_id):
        await self._request("POST", f"/calls/{quote(call_id, safe='')}/end")

    async def event(self, stage, payload):
        body = BusEvent(stage=stage, payload=payload)
        await self._request("POST", "/agent/events", json=body.model_dump(mode="json"))


class FakeBackendClient:
    """In-memory enrollment by exact fixture bytes, not face recognition.

    The enrollment result is supplied by the test/demo. No transcript parsing,
    face matching, phone inference, or external services happen here.
    """
    def __init__(self, *, patient: Person, enrollment: PersonDetail):
        if not patient.is_patient or enrollment.is_patient:
            raise ValueError("Expected a patient and a separate relative fixture")
        self._patient = patient
        self.enrollment = enrollment
        self.people = {patient.id: PersonDetail(**patient.model_dump())}
        self.faces: dict[str, str] = {}
        self.intros: list[IntroRequest] = []
        self.calls: list[Call] = []
        self.lines: list[tuple[str, CallLineIn]] = []
        self.events: list[BusEvent] = []

    async def patient(self):
        return self._patient.model_copy(deep=True)

    async def person(self, person_id):
        return self.people[person_id].model_copy(deep=True)

    async def enroll(self, intro):
        self.intros.append(intro.model_copy(deep=True))
        person = self.enrollment.model_copy(deep=True)
        if intro.phone:
            person.phone = intro.phone
        self.people[person.id] = person
        for face in intro.face_jpegs_b64:
            self.faces[face] = person.id
        return Person.model_validate(person.model_dump())

    async def recognize(self, jpeg, key, call_id):
        person_id = self.faces.get(b64(jpeg))
        status = "identified" if person_id else "learning"
        return RecognizeResponse(faces=[FaceResult(result=RecognitionResult(status=status, person_id=person_id))])

    async def start_call(self, kind, participants):
        call = Call(id=uuid4().hex, kind=kind, participants=participants,
                    started=datetime.now(timezone.utc))
        self.calls.append(call)
        return call.model_copy(deep=True)

    async def log_line(self, call_id, line):
        self.lines.append((call_id, line.model_copy(deep=True)))

    async def end_call(self, call_id):
        call = next(c for c in self.calls if c.id == call_id)
        call.ended = call.ended or datetime.now(timezone.utc)

    async def event(self, stage, payload):
        self.events.append(BusEvent(stage=stage, payload=payload))
