"""Bounded 1:1 relative enrollment. Patient calling is a separate workflow."""

import asyncio

from .backend_client import Backend, b64
from .contract import CallLineIn, IntroRequest, Person
from .speech import SpeechInput, SpeechOutput


class SetupScript:
    def __init__(self, backend: Backend, stt: SpeechInput, tts: SpeechOutput):
        self.backend, self.stt, self.tts = backend, stt, tts
        self.state = "greet"

    async def _answer(self):
        for attempt in range(2):
            try:
                answer = await asyncio.wait_for(self.stt.listen(timeout_s=20), timeout=36)
            except TimeoutError:
                answer = None
            if answer and answer.strip():
                return answer.strip()
            if attempt == 0:
                await self.tts.speak("I didn't catch that. Could you say it once more?")
        return None

    async def run(self, face_crops: list[bytes], *, phone: str | None = None) -> Person | None:
        if not callable(face_crops) and (len(face_crops) != 3 or not all(face_crops)):
            raise ValueError("Setup requires three nonempty face crops from this caller")
        patient = await self.backend.patient()
        patient_name = patient.name or "your relative"
        call = await self.backend.start_call("setup", [phone] if phone else [])
        transcript = []
        try:
            await self.tts.speak(f"Hi, I'm Calypso⁻¹. I help {patient_name} remember the people they love. Who are you to them?")
            self.state = "ask_relationship"
            intro = await self._answer()
            if intro is None:
                return await self._end_silence()
            transcript.append(intro)
            await self.backend.log_line(call.id, CallLineIn(speaker="caller", text=intro))
            self.state = "ask_memory"
            await self.tts.speak("What's something you two share?")
            memory = await self._answer()
            if memory is None:
                return await self._end_silence()
            transcript.append(memory)
            await self.backend.log_line(call.id, CallLineIn(speaker="caller", text=memory))
            self.state = "confirm"
            await self.tts.speak(f"You said: {intro} And: {memory} Is that right? Please say yes or no.")
            # A refusal ends setup; never save an unconfirmed introduction.
            for _ in range(2):
                answer = await self._answer()
                if answer is None:
                    return await self._end_silence()
                await self.backend.log_line(call.id, CallLineIn(speaker="caller", text=answer))
                normalized = answer.lower().strip(" .!?")
                if normalized in {"yes", "yeah", "yep", "correct", "that's right", "that is right"}:
                    crops = await face_crops() if callable(face_crops) else face_crops
                    if len(crops) != 3 or not all(crops):
                        raise ValueError("Setup requires three face crops from this caller")
                    person = await self.backend.enroll(IntroRequest(
                        transcript="\n".join(transcript), face_jpegs_b64=[b64(c) for c in crops],
                        phone=phone, call_id=call.id))
                    self.state = "done"
                    await self.tts.speak("Thank you. Your introduction is saved.")
                    return person
                if normalized in {"no", "nope", "incorrect"}:
                    self.state = "ended"
                    await self.tts.speak("I won't save that introduction. Please call again to start over.")
                    return None
                await self.tts.speak("Should I save that introduction? Please say yes or no.")
            self.state = "ended"
            await self.tts.speak("I couldn't confirm that, so I haven't saved an introduction.")
            return None
        finally:
            await self.backend.end_call(call.id)

    async def _end_silence(self):
        self.state = "ended"
        await self.tts.speak("Let's try another time. You can call me again when you're ready.")
        return None
