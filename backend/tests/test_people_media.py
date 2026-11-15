"""People CRUD, memories, image links, and the public media routes."""
import base64
import io

from calypso import db

from conftest import AUTH, JPEG


def make_person(client, **body):
    r = client.post("/people", headers=AUTH, json=body)
    assert r.status_code == 201
    return r.json()


def test_create_list_and_filter_patient(client):
    make_person(client, name="Mary", is_patient=True)
    make_person(client, name="Sarah", relationship="daughter")
    everyone = client.get("/people", headers=AUTH).json()
    patients = client.get("/people?is_patient=true", headers=AUTH).json()
    relatives = client.get("/people?is_patient=false", headers=AUTH).json()
    assert [p["name"] for p in everyone] == ["Mary", "Sarah"]
    assert [p["name"] for p in patients] == ["Mary"]
    assert [p["name"] for p in relatives] == ["Sarah"]


def test_person_json_matches_ios_shape(client):
    p = make_person(client, name="Sarah", relationship="daughter", facts=["Has a dog named Biscuit"])
    assert set(p) == {"id", "name", "relationship", "is_patient", "face_photo_url", "facts", "phone"}
    assert p["face_photo_url"] is None  # no photo yet


def test_person_detail_has_memories(client, conn):
    p = make_person(client, name="Sarah")
    conn.execute(
        "INSERT INTO day_events (id, start_ts, end_ts, place, place_confidence, people, summary)"
        " VALUES ('e1', '2026-11-14T15:10:00.000Z', '2026-11-14T15:40:00.000Z', 'Blue Bean Café', 0.95, ?, 'Coffee with Sarah')",
        (db.dumps([p["id"]]),),
    )
    conn.commit()
    d = client.get(f"/people/{p['id']}", headers=AUTH).json()
    assert d["memories"] == ["Nov 14 · Blue Bean Café · Coffee with Sarah"]
    assert d["name"] == "Sarah"  # flat: Person fields + memories


def test_person_detail_memories_empty_by_default(client):
    p = make_person(client, name="Tom")
    assert client.get(f"/people/{p['id']}", headers=AUTH).json()["memories"] == []


def test_patch_person_name_returns_person(client):
    p = make_person(client)
    assert p["name"] is None  # "Unnamed visitor" in the app
    r = client.patch(f"/people/{p['id']}", headers=AUTH, json={"name": "Eric"})
    assert r.status_code == 200 and r.json()["name"] == "Eric" and r.json()["id"] == p["id"]


def test_unknown_person_404(client):
    assert client.get("/people/nope", headers=AUTH).status_code == 404
    assert client.patch("/people/nope", headers=AUTH, json={"name": "x"}).status_code == 404


def test_face_photo_url_is_absolute_from_public_url(client):
    p = make_person(client, name="Sarah")
    r = client.post(f"/people/{p['id']}/faces", headers=AUTH, files={"image": ("f.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert r.status_code == 200
    got = client.get(f"/people/{p['id']}", headers=AUTH).json()
    assert got["face_photo_url"] == f"https://calypso.example.com/media/faces/{p['id']}.jpg"


def test_face_url_uses_forwarded_proto_when_public_url_unset(monkeypatch, env):
    monkeypatch.setenv("CALYPSO_PUBLIC_URL", "")
    from fastapi.testclient import TestClient

    from calypso.app import create_app

    with TestClient(create_app()) as c:
        p = c.post("/people", headers=AUTH, json={"name": "Sarah"}).json()
        c.post(f"/people/{p['id']}/faces", headers=AUTH, files={"image": ("f.jpg", io.BytesIO(JPEG), "image/jpeg")})
        got = c.get(f"/people/{p['id']}", headers={**AUTH, "X-Forwarded-Proto": "https",
                                                   "X-Forwarded-Host": "mac.tail1234.ts.net"}).json()
    assert got["face_photo_url"] == f"https://mac.tail1234.ts.net/media/faces/{p['id']}.jpg"


def test_media_face_served_publicly(client):
    p = make_person(client, name="Sarah")
    client.post(f"/people/{p['id']}/faces", headers=AUTH, files={"image": ("f.jpg", io.BytesIO(JPEG), "image/jpeg")})
    r = client.get(f"/media/faces/{p['id']}.jpg")  # no token
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"


def test_media_unknown_and_bad_names_404(client):
    assert client.get("/media/faces/nobody.jpg").status_code == 404
    assert client.get("/media/faces/..%2F..%2Fsecret.jpg").status_code == 404
    assert client.get("/media/photos/nothing.png").status_code == 404


def test_media_sensitive_photo_404(client, conn):
    for pid, sensitive in (("ph_ok", 0), ("ph_card", 1)):
        meta = f'{{"id": "{pid}", "taken_at": "2026-11-14T15:30:00.123Z", "lat": 32.7, "lon": -97.1}}'
        client.post("/app/photos", headers=AUTH, data={"meta": meta},
                    files={"image": ("p.jpg", io.BytesIO(JPEG), "image/jpeg")})
        conn.execute("UPDATE photos SET sensitive = ? WHERE id = ?", (sensitive, pid))
        conn.commit()
    assert client.get("/media/photos/ph_ok.jpg").status_code == 200
    assert client.get("/media/photos/ph_card.jpg").status_code == 404


def test_from_intro_stub_creates_unnamed_person_with_photo(client):
    body = {"transcript": "Hi, I'm Sarah, Mary's daughter.",
            "face_jpegs_b64": [base64.b64encode(JPEG).decode()],
            "voice_wav_b64": base64.b64encode(b"RIFF....WAVE").decode(), "phone": "+15555550123"}
    r = client.post("/people/from_intro", headers=AUTH, json=body)
    assert r.status_code == 201
    p = r.json()
    assert p["name"] is None and p["phone"] == "+15555550123"
    assert p["face_photo_url"].endswith(f"/media/faces/{p['id']}.jpg")
    assert client.get(f"/media/faces/{p['id']}.jpg").content == JPEG


def test_from_intro_bad_base64_422(client):
    r = client.post("/people/from_intro", headers=AUTH, json={"transcript": "x", "face_jpegs_b64": ["@@not-b64@@"]})
    assert r.status_code == 422


def test_add_voice_stores_print_not_audio(client, env):
    from conftest import tone_wav

    p = make_person(client, name="Sarah")
    r = client.post(f"/people/{p['id']}/voice", headers=AUTH,
                    files={"audio": ("v.wav", io.BytesIO(tone_wav(220)), "audio/wav")})
    assert r.status_code == 200 and r.json()["voice_prints"] == 1
    assert not list((env / "data").rglob("*.wav"))
    bad = client.post(f"/people/{p['id']}/voice", headers=AUTH, files={"audio": ("v.wav", io.BytesIO(b"RIFF"), "audio/wav")})
    assert bad.status_code == 422


def test_memories_skip_unsynced_puck_utterances(conn):
    from calypso.routes.people import _memories

    pid = db.insert_person(conn, name="Sarah")["id"]
    for uuid_, synced, text in [("s-ok", 1, "trusted"), ("s-bad", 0, "untrusted")]:
        conn.execute("INSERT INTO segments (segment_uuid, ts_start, ts_end, status, received_at, time_synced)"
                     " VALUES (?, '2026-11-14T16:00:00.000Z', '2026-11-14T16:00:03.000Z', 'done',"
                     " '2026-11-14T16:00:05.000Z', ?)", (uuid_, synced))
        conn.execute("INSERT INTO utterances (id, segment_uuid, ts_start, ts_end, text, source, person_id)"
                     " VALUES (?, ?, '2026-11-14T16:00:00.000Z', '2026-11-14T16:00:03.000Z', ?, 'puck', ?)",
                     (db.new_id(), uuid_, text, pid))
    conn.commit()
    lines = _memories(conn, pid, "America/Chicago")
    assert any("trusted" in l for l in lines) and not any("untrusted" in l for l in lines)
