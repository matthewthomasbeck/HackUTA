"""Media transport's sole decision interface: the Claude gateway on Vultr."""

import json
import os
from pathlib import Path

import httpx


class GatewayClient:
    def __init__(self, url, token, state_file, *, client=None):
        self.http = client or httpx.AsyncClient(base_url=url.rstrip("/"), timeout=40,
            headers={"Authorization": f"Bearer {token}"})
        self.owns_client = client is None
        self.state_file = Path(state_file)
        self.session_id = None

    async def start(self, mode, participant, outcome):
        enrolled = None
        if mode == "group" and self.state_file.exists():
            enrolled = json.loads(self.state_file.read_text()).get("person_id")
        response = await self.http.post("/agent/sessions", json={"mode": mode,
            "participant": participant, "controlled": True, "outcome": outcome,
            "enrolled_person_id": enrolled})
        response.raise_for_status()
        self.session_id = response.json()["session_id"]

    async def event(self, kind, **fields):
        response = await self.http.post(f"/agent/sessions/{self.session_id}/events",
                                       json={"kind": kind, **fields})
        response.raise_for_status()
        effects = response.json()
        if effects.get("enrolled_person_id"):
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_file.with_suffix(".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump({"person_id": effects["enrolled_person_id"]}, stream)
            os.replace(temporary, self.state_file)
        return effects

    async def shown(self, card):
        response = await self.http.post("/agent/events", json={"stage": "card.shown",
            "payload": {"session_id": self.session_id, "controlled": True, "card": card}})
        response.raise_for_status()

    async def close(self):
        try:
            if self.session_id:
                response = await self.http.post(f"/agent/sessions/{self.session_id}/end")
                response.raise_for_status()
        finally:
            if self.owns_client:
                await self.http.aclose()
