"""Offline enrollment → recognition demo with explicitly fictional fixtures."""

import asyncio
from io import BytesIO
from pathlib import Path

from PIL import Image

from .backend_client import FakeBackendClient
from .cards import render
from .contract import Person, PersonDetail
from .conversation import SetupScript
from .core import GroupCall
from .speech import FakeSTT, FakeTTS


async def main():
    backend = FakeBackendClient(
        patient=Person(id="demo-patient", name="Mary", is_patient=True),
        enrollment=PersonDetail(id="demo-relative", name="Sarah", relationship="daughter",
                                facts=["You bake together on Sundays."]),
    )
    # Colored images stand in for camera crops. They are not real face samples.
    crops = []
    for color in ("blue", "green", "red"):
        stream = BytesIO()
        Image.new("RGB", (64, 64), color).save(stream, "JPEG")
        crops.append(stream.getvalue())
    speech = FakeTTS()
    setup = SetupScript(backend, FakeSTT(["I'm Sarah, Mary's daughter.",
                                        "We bake together on Sundays.", "Yes"]), speech)
    person = await setup.run(crops)
    assert person is not None
    print("OFFLINE DEMO — fictional profiles; exact fixture bytes stand in for recognition.")
    for line in speech.spoken:
        print(f"Agent: {line}")
    print(f"Setup ended; saved relative: {person.name}")
    group = await GroupCall.start(backend, ["demo-patient", person.id])
    try:
        await group.on_frame("relative-phone", crops[0])
        card = group.scheduler.current()
        assert card is not None and card.kind == "identity"
        Path("out").mkdir(exist_ok=True)
        path = Path("out/enrolled-relative.png")
        render(card, {}).save(path)
        print(f"Separate group call: {card.title} → identity card at {path}")
    finally:
        await group.end()
    print("Both calls ended; no network, real recognition, speech, or FaceTime was used.")


if __name__ == "__main__":
    asyncio.run(main())
