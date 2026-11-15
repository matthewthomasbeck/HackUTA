"""Face prints, voiceprints, fusion, enrollment de-duplication and /recognize (fake models)."""
import base64
import io
import wave

import numpy as np
import pytest

from calypso.config import Settings
from calypso.identity.audio import concat_wavs, decode_wav, trim_silence, wav_seconds
from calypso.identity.fuse import fuse

from conftest import AUTH, face, tone_wav


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def settings(env):
    return Settings.from_env()


# --- audio --------------------------------------------------------------------

def test_decode_resamples_and_downmixes():
    x = decode_wav(tone_wav(220, seconds=2.0, rate=48000, channels=2))
    assert x.dtype == np.float32 and abs(len(x) - 32000) <= 1
    assert abs(len(decode_wav(tone_wav(220, seconds=2.0, rate=8000))) - 32000) <= 1


def test_silence_has_no_speech():
    silent = io.BytesIO()
    with wave.open(silent, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 48000)
    assert trim_silence(decode_wav(silent.getvalue()))[1] == 0.0
    assert trim_silence(decode_wav(tone_wav(300, 3.0)))[1] == pytest.approx(3.0, abs=0.1)


def test_concat_wavs_joins_and_skips_garbage():
    joined = concat_wavs([tone_wav(200, 1.0), b"not a wav", tone_wav(200, 1.5, rate=48000)])
    assert wav_seconds(joined) == pytest.approx(2.5, abs=0.01)
    assert concat_wavs([b"junk"]) is None


# --- fusion rule --------------------------------------------------------------

def test_enrolled_face_identified(settings):
    r = fuse({"a": 0.80, "b": 0.20}, None, settings)
    assert (r.status, r.person_id) == ("identified", "a")


def test_recognize_ambiguous_top2_is_uncertain(settings):
    assert fuse({"a": 0.50, "b": 0.47}, None, settings).status == "uncertain"


def test_stranger_is_learning(settings):
    assert fuse({"a": 0.12, "b": 0.05}, None, settings).status == "learning"
    assert fuse({}, None, settings).status == "learning"  # nobody has face prints yet


def test_voice_disagreement_uncertain(settings):
    r = fuse({"a": 0.80, "b": 0.20}, {"b": 0.75, "a": 0.20}, settings)
    assert r.status == "uncertain" and r.person_id is None


def test_voice_agreement_keeps_identity(settings):
    r = fuse({"a": 0.80}, {"a": 0.70}, settings)
    assert (r.status, r.person_id, r.voice_score) == ("identified", "a", 0.70)


def test_voice_only_needs_stricter_threshold(settings):
    assert fuse(None, {"a": settings.voice_match + 0.05, "b": 0.0}, settings).status == "uncertain"
    r = fuse(None, {"a": settings.voice_match + 0.15, "b": 0.0}, settings)
    assert (r.status, r.person_id) == ("identified", "a")
    assert fuse(None, {"a": 0.10}, settings).status == "learning"
    assert fuse(None, None, settings).status == "learning"


def test_mid_face_score_is_uncertain_not_learning(settings):
    assert fuse({"a": 0.35}, None, settings).status == "uncertain"


# --- enrollment ---------------------------------------------------------------

def intro(client, faces=(), voice=None, **fields):
    body = {"transcript": "hi", "face_jpegs_b64": [b64(f) for f in faces],
            "voice_wav_b64": b64(voice) if voice else None, **fields}
    r = client.post("/people/from_intro", headers=AUTH, json=body)
    assert r.status_code in (200, 201), r.text
    return r


def counts(conn):
    q = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return q("people"), q("face_embeddings"), q("voice_prints")


def test_from_intro_enrolls_face_and_voice(client, conn):
    r = intro(client, [face("sarah")] * 3, tone_wav(220), name="Sarah", relationship="daughter",
              facts=["Baking on Sundays"], phone="+15555550101")
    p = r.json()
    assert r.status_code == 201 and not p["matched_existing"]
    assert (p["name"], p["relationship"], p["facts"], p["phone"]) == ("Sarah", "daughter", ["Baking on Sundays"], "+15555550101")
    assert (p["face_prints_added"], p["voice_prints_added"]) == (3, 1)
    assert counts(conn) == (1, 3, 1)
    assert p["face_photo_url"].endswith(f"/media/faces/{p['id']}.jpg")


def test_same_phone_updates_instead_of_duplicating(client, conn):
    first = intro(client, [face("sarah")] * 3, phone="+15555550101", name="Sarah", facts=["Baking"]).json()
    again = intro(client, [face("sarah-new-haircut")] * 3, phone="+15555550101", name="Sarah", facts=["Gardening", "baking"])
    p = again.json()
    assert again.status_code == 200 and p["matched_existing"] and p["matched_by"] == "phone"
    assert p["id"] == first["id"] and p["facts"] == ["Baking", "Gardening"]
    assert counts(conn) == (1, 6, 0)


def test_same_face_updates_instead_of_duplicating(client, conn):
    first = intro(client, [face("keanu")] * 3, name="Keanu", relationship="brother").json()
    p = intro(client, [face("keanu")] * 3, name="Keanu", relationship="brother").json()
    assert p["matched_existing"] and p["matched_by"] == "face" and p["id"] == first["id"]
    assert counts(conn)[0] == 1


def test_same_voice_updates_when_no_face(client, conn):
    first = intro(client, voice=tone_wav(330), name="Tom").json()
    p = intro(client, voice=tone_wav(330, seconds=4.0), name="Tom").json()
    assert p["matched_existing"] and p["matched_by"] == "voice" and p["id"] == first["id"]
    assert counts(conn) == (1, 0, 2)


def test_different_person_is_new(client, conn):
    intro(client, [face("sarah")] * 3, tone_wav(220), name="Sarah")
    p = intro(client, [face("tom")] * 3, tone_wav(440), name="Tom").json()
    assert not p["matched_existing"] and counts(conn) == (2, 6, 2)


def test_face_and_voice_disagree_creates_new_person(client, conn):
    intro(client, [face("sarah")] * 3, name="Sarah")
    intro(client, voice=tone_wav(440), name="Tom")
    # Sarah's face but Tom's voice: conflicting evidence must not merge into either.
    p = intro(client, [face("sarah")] * 3, tone_wav(440), name="Someone").json()
    assert not p["matched_existing"] and counts(conn)[0] == 3


def test_patient_is_never_merged_into(client, conn):
    patient = client.post("/people", headers=AUTH, json={"name": "Mary", "is_patient": True, "phone": "+15555550199"}).json()
    client.post(f"/people/{patient['id']}/faces", headers=AUTH, files={"image": ("f.jpg", io.BytesIO(face("mary")), "image/jpeg")})
    p = intro(client, [face("mary")] * 3, phone="+15555550199", name="Visitor").json()
    assert not p["matched_existing"] and p["id"] != patient["id"]


def test_short_or_bad_voice_is_noted_not_fatal(client, conn):
    p = intro(client, [face("sarah")] * 3, tone_wav(220, seconds=0.8), name="Sarah").json()
    assert p["voice_prints_added"] == 0 and any("speech" in n for n in p["notes"])
    q = intro(client, [face("tom")], b"RIFFgarbage", name="Tom").json()
    assert q["voice_prints_added"] == 0 and any("unreadable" in n for n in q["notes"])


def test_add_face_and_voice_endpoints(client):
    pid = client.post("/people", headers=AUTH, json={"name": "Sarah"}).json()["id"]
    up = lambda path, field, data: client.post(f"/people/{pid}/{path}", headers=AUTH, files={field: ("x", io.BytesIO(data))})
    assert up("faces", "image", face("sarah")).json()["face_prints"] == 1
    assert up("faces", "image", b"NOFACE").status_code == 422
    assert up("voice", "audio", tone_wav(220)).json()["voice_prints"] == 1
    assert up("voice", "audio", tone_wav(220, seconds=1.0)).status_code == 422


# --- recognize ----------------------------------------------------------------

def recognize(client, **body):
    r = client.post("/recognize", headers=AUTH, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_recognize_identifies_enrolled_face(client):
    sarah = intro(client, [face("sarah")] * 3, tone_wav(220), name="Sarah").json()
    res = recognize(client, face_jpeg_b64=b64(face("sarah")), voice_wav_b64=b64(tone_wav(220)))
    r = res["faces"][0]["result"]
    assert (r["status"], r["person_id"]) == ("identified", sarah["id"]) and r["face_score"] > 0.99
    assert r["voice_score"] > 0.99 and res["faces"][0]["bbox"] is not None


def test_recognize_stranger_learning_and_composite(client):
    intro(client, [face("sarah")] * 3, name="Sarah")
    assert recognize(client, face_jpeg_b64=b64(face("bob")))["faces"][0]["result"]["status"] == "learning"
    both = recognize(client, face_jpeg_b64=b64(face("sarah,bob")))["faces"]
    assert [f["result"]["status"] for f in both] == ["identified", "learning"]


def test_recognize_voice_only(client):
    tom = intro(client, voice=tone_wav(330), name="Tom").json()
    res = recognize(client, voice_wav_b64=b64(tone_wav(330)))
    assert res["faces"] == [] and (res["voice_only"]["status"], res["voice_only"]["person_id"]) == ("identified", tom["id"])


def test_recognize_patient_never_returned(client):
    patient = client.post("/people", headers=AUTH, json={"name": "Mary", "is_patient": True}).json()
    client.post(f"/people/{patient['id']}/faces", headers=AUTH, files={"image": ("f.jpg", io.BytesIO(face("mary")), "image/jpeg")})
    r = recognize(client, face_jpeg_b64=b64(face("mary")))["faces"][0]["result"]
    assert r["person_id"] is None and r["status"] == "learning"


def test_recognize_emits_scores_for_dashboard(client):
    intro(client, [face("sarah")] * 3, name="Sarah")
    recognize(client, face_jpeg_b64=b64(face("sarah")), participant_key="phone-1")
    ev = [e for e in client.get("/events/recent").json() if e["stage"] == "recognize"][-1]["payload"]
    assert ev["participant_key"] == "phone-1" and ev["faces"][0]["face_top3"][0]["score"] > 0.99
    assert ev["thresholds"]["face_match"] == pytest.approx(0.40)


@pytest.mark.asyncio
async def test_setup_call_audio_becomes_voiceprint_and_second_call_dedupes(env):
    """Claude setup flow end to end: utterance audio -> from_intro -> voiceprint; repeat caller -> same person."""
    import httpx

    from calypso.app import create_app
    from calypso.claude_controller import ClaudeController
    from calypso import db
    from test_claude_gateway import FakeClaude

    app = create_app()
    script = lambda name: [
        ("speak", {"text": "Who are you to Mary?"}), None,
        ("confirm_intro", {"name": name, "relationship": "brother", "memory": "Same school"}), None,
        ("save_intro", {}), ("finish", {}), None,
    ]
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", headers=AUTH) as c:
            await c.post("/people", json={"name": "Mary", "is_patient": True})

            async def call(name, phone):
                app.state.claude_controller = ClaudeController(FakeClaude(script(name)))
                sid = (await c.post("/agent/sessions", json={"mode": "setup", "participant": "chert-bridge-x",
                                                             "caller_phone": phone})).json()["session_id"]
                ev = lambda **f: c.post(f"/agent/sessions/{sid}/events", json=f)
                await ev(kind="start")
                await ev(kind="utterance", text=f"I'm {name}, Mary's brother", voice_wav_b64=b64(tone_wav(330, 2.0)))
                done = (await ev(kind="utterance", text="Yes", voice_wav_b64=b64(tone_wav(330, 1.0)),
                                 face_jpegs_b64=[b64(face("keanu"))] * 3)).json()
                await c.post(f"/agent/sessions/{sid}/end")
                return done

            first = await call("Keanu", "+15555550142")
            assert first["done"] and first["enrolled_person_id"]
            conn = db.connect(Settings.from_env().db_path)
            pid = first["enrolled_person_id"]
            row = db.get_person(conn, pid)
            assert (row["name"], row["relationship"], db.loads(row["facts"])) == ("Keanu", "brother", ["Same school"])
            # 2 s + 1 s of caller speech were joined into one 3 s clip -> one voiceprint.
            assert conn.execute("SELECT COUNT(*), MAX(speech_s) FROM voice_prints WHERE person_id=?", (pid,)).fetchone()[:] == (1, 3.0)
            assert conn.execute("SELECT COUNT(*) FROM face_embeddings WHERE person_id=?", (pid,)).fetchone()[0] == 3

            second = await call("Keanu", "+15555550142")  # same relative calls again
            assert second["enrolled_person_id"] == pid
            assert conn.execute("SELECT COUNT(*) FROM people WHERE is_patient=0").fetchone()[0] == 1
            assert db.loads(db.get_person(conn, pid)["facts"]) == ["Same school"]  # merged, not duplicated or wiped
            conn.close()


def test_missing_models_degrade_to_learning(monkeypatch, env):
    monkeypatch.setenv("CALYPSO_FACE", "opencv")
    monkeypatch.setenv("CALYPSO_VOICE", "sherpa")
    monkeypatch.setenv("CALYPSO_MODELS_DIR", str(env / "no-models-here"))
    from fastapi.testclient import TestClient

    from calypso.app import create_app

    with TestClient(create_app()) as c:
        res = c.post("/recognize", headers=AUTH, json={"face_jpeg_b64": b64(b"x"), "voice_wav_b64": b64(tone_wav(220))}).json()
        assert res["faces"] == [] and res["voice_only"]["status"] == "learning"
        p = c.post("/people/from_intro", headers=AUTH, json={"face_jpegs_b64": [b64(b"x")], "name": "Sarah"}).json()
        assert p["name"] == "Sarah" and p["face_prints_added"] == 0 and any("unavailable" in n for n in p["notes"])
