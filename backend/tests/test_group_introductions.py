"""Manual group introductions: face results only, never enrollment writes."""
import pytest
from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession


def session():
    return Session("sid", "cid", StartSession(mode="group_intro", participant="bridge"),
                   {"id": "mary", "name": "Mary", "is_patient": True})


class Backend:
    def __init__(self):
        self.faces = []
        self.requests = []
    async def __call__(self, method, path, body=None):
        self.requests.append((method, path, body))
        if path == "/recognize":
            assert body["exclude_patient"] is False
            assert not body.get("voice_wav_b64")
            return {"faces": self.faces}
        assert method == "GET" and path.startswith("/people/")
        person = path.rsplit("/", 1)[1]
        return {"id": person, "name": {"k": "Keanu", "s": "Sarah", "mary": "Mary"}[person],
                "relationship": {"k": "brother", "s": "Mary's daughter", "mary": None}[person],
                "is_patient": person == "mary", "facts": ["School together"]}


def face(person, status="identified"):
    return {"result": {"status": status, "person_id": person}}


@pytest.mark.asyncio
async def test_composite_grid_announces_each_relative_once_and_excludes_mary():
    state, api, controller = session(), Backend(), ClaudeController()
    greeting = await controller.respond(state, MediaEvent(kind="start"), api)
    assert len(greeting.speech) == 1 and not greeting.done
    assert not (await controller.respond(state, MediaEvent(kind="start"), api)).speech
    api.faces = [face("mary"), face("k"), face("s"), face(None, "uncertain")]
    event = MediaEvent(kind="frame", jpeg_b64="eA==", source_key="grid")
    assert not (await controller.respond(state, event, api)).speech
    effects = await controller.respond(state, event, api)
    assert effects.speech == ["Hi Mary, you're speaking with Keanu, your brother.",
                              "Hi Mary, you're speaking with Sarah, your daughter."]
    assert [c.title for c in effects.cards] == ["Keanu", "Sarah"]
    assert effects.cards[0].lines == ["Mary's brother", "School together"]
    assert not effects.done and not state.done
    assert not (await controller.respond(state, event, api)).speech
    api.faces = []
    await controller.respond(state, event, api)
    api.faces = [face("k")]
    await controller.respond(state, event, api)
    assert not (await controller.respond(state, event, api)).speech  # rejoin within same call
    assert not any(path == "/people/mary" for _, path, _ in api.requests)


@pytest.mark.asyncio
async def test_unknown_or_patient_only_never_announces_or_enrolls():
    state, api, controller = session(), RecallBackend(card=None), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    for faces in [[face("mary")], [face(None, "learning")], [face(None, "uncertain")], []]:
        api.faces = faces
        for _ in range(3):
            effects = await controller.respond(state, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
            assert not effects.speech and not effects.cards and not effects.done
    assert not (await controller.respond(state, MediaEvent(kind="utterance", text="I am Keanu", voice_wav_b64="d2F2"), api)).speech
    # Speech may only reach the call log and grounded recall: never identity lookups or enrollment.
    assert all(path in {"/recognize", "/calls/cid/lines", "/recall"} for _, path, _ in api.requests)
    assert not state.group_announced


@pytest.mark.asyncio
async def test_evidence_is_per_video_source_and_duplicates_do_not_count_twice():
    state, api, controller = session(), Backend(), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    api.faces = [face("k"), face("k")]
    async def frame(source):
        return await controller.respond(state, MediaEvent(kind="frame", jpeg_b64="eA==", source_key=source), api)
    assert not (await frame("a")).speech
    assert not (await frame("b")).speech
    api.faces = [face(None, "uncertain")]
    assert not (await frame("a")).speech
    api.faces = [face("k")]
    assert not (await frame("a")).speech
    assert len((await frame("a")).speech) == 1
    assert not (await frame("b")).speech  # already announced in this call


@pytest.mark.asyncio
async def test_long_gap_does_not_count_as_consecutive_evidence(monkeypatch):
    import calypso.claude_controller as module
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    state, api, controller = session(), Backend(), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    api.faces = [face("k")]
    event = MediaEvent(kind="frame", jpeg_b64="eA==")
    assert not (await controller.respond(state, event, api)).speech
    now[0] = 110
    assert not (await controller.respond(state, event, api)).speech
    now[0] = 111
    assert len((await controller.respond(state, event, api)).speech) == 1


class RecallBackend(Backend):
    def __init__(self, card=None, delay=0):
        super().__init__()
        self.card, self.delay = card, delay
    async def __call__(self, method, path, body=None):
        if path == "/recall" or path.startswith("/calls/"):
            self.requests.append((method, path, body))
            if path == "/recall":
                if self.delay:
                    import asyncio
                    await asyncio.sleep(self.delay)
                return {"intent": "today" if self.card else "none", "card": self.card}
            return {"ok": True}
        return await super().__call__(method, path, body)


TODAY = {"kind": "today", "title": "Today", "lines": ["4:07 AM · somewhere · Had coffee with someone"]}


@pytest.mark.asyncio
async def test_group_intro_utterance_shows_recall_card_silently():
    state, api, controller = session(), RecallBackend(card=TODAY), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    effects = await controller.respond(state, MediaEvent(kind="utterance", text="Mom, what did you do today?"), api)
    assert [c.kind for c in effects.cards] == ["today"] and not effects.speech
    recall = [b for _, p, b in api.requests if p == "/recall"]
    assert recall == [{"lines": [{"speaker": "bridge", "text": "Mom, what did you do today?"}]}]
    assert not [p for _, p, _ in api.requests if p == "/recognize" or p.startswith("/people")]


@pytest.mark.asyncio
async def test_group_intro_unrelated_speech_no_card_and_no_identity_change():
    state, api, controller = session(), RecallBackend(card=None), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    effects = await controller.respond(state, MediaEvent(kind="utterance", text="I'm Sarah"), api)
    assert not effects.cards and not effects.speech and not state.group_announced


@pytest.mark.asyncio
async def test_group_intro_recall_failure_never_raises():
    state, api, controller = session(), RecallBackend(card=TODAY, delay=5), ClaudeController()
    await controller.respond(state, MediaEvent(kind="start"), api)
    effects = await controller.respond(state, MediaEvent(kind="utterance", text="what did you do today"), api)
    assert not effects.cards and not effects.done


@pytest.mark.asyncio
async def test_group_intro_ignores_utterance_before_start_and_empty_text():
    state, api, controller = session(), RecallBackend(card=TODAY), ClaudeController()
    assert not (await controller.respond(state, MediaEvent(kind="utterance", text="what did you do today"), api)).cards
    await controller.respond(state, MediaEvent(kind="start"), api)
    assert not (await controller.respond(state, MediaEvent(kind="utterance", text="  "), api)).cards
    assert not [p for _, p, _ in api.requests if p == "/recall"]
