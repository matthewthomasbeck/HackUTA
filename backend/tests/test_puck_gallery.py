"""GET /puck/gallery: full voice-print snapshot for the puck (replace-all sync)."""
import numpy as np

from calypso.identity.vectors import normalize, to_blob
from calypso.timeutil import now_iso

from conftest import AUTH


def _insert_person(conn, person_id, name, relationship="friend", is_patient=0):
    conn.execute(
        "INSERT INTO people (id, name, relationship, is_patient, facts, created_at) "
        "VALUES (?, ?, ?, ?, '[]', ?)",
        (person_id, name, relationship, is_patient, now_iso()),
    )


def _insert_print(conn, person_id, vec, print_id=None):
    conn.execute(
        "INSERT INTO voice_prints (id, person_id, vec, source, speech_s, created_at) "
        "VALUES (?, ?, ?, 'call', 3.0, ?)",
        (print_id or person_id + "-v", person_id, to_blob(vec), now_iso()),
    )


def test_gallery_empty_without_prints(client):
    r = client.get("/puck/gallery", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"people": []}


def test_gallery_requires_auth(client):
    assert client.get("/puck/gallery").status_code == 401


def test_gallery_mean_embedding_and_metadata(client, conn):
    _insert_person(conn, "p_sarah", "Sarah", "daughter")
    a = normalize(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    b = normalize(np.array([0.0, 1.0, 0.0], dtype=np.float32))
    _insert_print(conn, "p_sarah", a, "v1")
    _insert_print(conn, "p_sarah", b, "v2")
    # Person with no prints must be omitted (puck drop = delete).
    _insert_person(conn, "p_ghost", "Ghost")
    conn.commit()

    r = client.get("/puck/gallery", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert len(body["people"]) == 1
    speaker = body["people"][0]
    assert speaker["person_id"] == "p_sarah"
    assert speaker["display_name"] == "Sarah"
    assert speaker["relationship"] == "daughter"
    assert speaker["is_patient"] is False
    emb = np.asarray(speaker["embedding"], dtype=np.float32)
    expected = normalize((a + b) / 2.0)
    assert emb.shape == expected.shape
    assert np.allclose(emb, expected, atol=1e-5)
    assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-5


def test_gallery_includes_patient(client, conn):
    _insert_person(conn, "p_mary", "Mary", None, is_patient=1)
    _insert_print(conn, "p_mary", normalize(np.ones(4, dtype=np.float32)))
    conn.commit()

    people = client.get("/puck/gallery", headers=AUTH).json()["people"]
    assert len(people) == 1
    assert people[0]["person_id"] == "p_mary"
    assert people[0]["is_patient"] is True


def test_gallery_skips_mismatched_dim_prints(client, conn):
    _insert_person(conn, "p_x", "X")
    good = normalize(np.array([1.0, 0.0], dtype=np.float32))
    bad = normalize(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    _insert_print(conn, "p_x", good, "g")
    _insert_print(conn, "p_x", bad, "b")
    conn.commit()

    emb = client.get("/puck/gallery", headers=AUTH).json()["people"][0]["embedding"]
    assert len(emb) == 2
    assert np.allclose(emb, good, atol=1e-5)
