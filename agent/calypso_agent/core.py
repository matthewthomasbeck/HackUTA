"""Transport-independent group call controller for the first milestone."""

from .backend_client import Backend
from .scheduler import CardScheduler
from .state import CallState


class GroupCall:
    def __init__(self, backend: Backend, call, scheduler):
        self.backend, self.call, self.scheduler = backend, call, scheduler
        self.state = CallState({})

    @classmethod
    async def start(cls, backend, participants, *, scheduler=None):
        call = await backend.start_call("group", participants)
        return cls(backend, call, scheduler or CardScheduler())

    async def on_frame(self, key: str, jpeg: bytes):
        response = await self.backend.recognize(jpeg, key, self.call.id)
        # This milestone requires a caller-specific track. Composite face tracking
        # needs the live spike and stable face association before it can be enabled.
        if len(response.faces) != 1:
            self.state.on_result(key, None)
            return
        result = response.faces[0].result
        if result.status == "identified" and result.person_id:
            self.state.people[result.person_id] = await self.backend.person(result.person_id)
        for card in self.state.on_result(key, result):
            if self.scheduler.push(card):
                await self.backend.event("card.queued", {"call_id": self.call.id, "card": card.model_dump(mode="json")})

    async def end(self):
        await self.backend.end_call(self.call.id)
