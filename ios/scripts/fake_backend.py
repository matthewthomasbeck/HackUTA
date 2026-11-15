# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Fake Calypso⁻¹ backend for running the iOS app before the real one is deployed.

Serves the endpoints APIClient calls, with seeded people and a day of events
anchored on whatever date the app asks for. Uploads are kept in memory, so
uploaded photos and visits show up in Today on the next refresh.

    uv run ios/scripts/fake_backend.py                 # 0.0.0.0:8000, token "dev-token"
    uv run ios/scripts/fake_backend.py --port 9000 --token abc
    python3 ios/scripts/fake_backend.py                # also works; plain-color images without Pillow

Point the app at it in ios/Secrets.xcconfig (use the Mac's LAN IP on a device;
ATS allows plain http to local-network IPs, but not Tailscale's 100.x ones, so
over Tailscale run `tailscale serve --bg 8000` and use the https ts.net URL):

    API_BASE_URL = http:/$()/192.168.1.23:8000
    API_TOKEN = dev-token
"""
import argparse
import colorsys
import io
import json
import re
import socket
import struct
import zlib
from datetime import date, datetime, time, timedelta
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

LOCAL_TZ = datetime.now().astimezone().tzinfo

PEOPLE = {
    "p_patient": {"id": "p_patient", "name": "Mary", "relationship": None, "is_patient": True,
                  "facts": ["Retired schoolteacher", "Loves crosswords"]},
    "p_mom": {"id": "p_mom", "name": "Mom", "relationship": "mother", "is_patient": False,
              "facts": ["Loves gardening", "Calls every Sunday"]},
    "p_sarah": {"id": "p_sarah", "name": "Sarah", "relationship": "daughter", "is_patient": False,
                "facts": ["Lives in Austin", "Has a dog named Biscuit"]},
    "p_tom": {"id": "p_tom", "name": "Tom", "relationship": "neighbor", "is_patient": False,
              "facts": ["Fixes the fence every spring"]},
    # Not named yet: the app shows "Getting to know someone new…".
    "p_unknown": {"id": "p_unknown", "name": None, "relationship": None, "is_patient": False,
                  "facts": []},
}

MEMORIES = {
    "p_mom": ["Grocery shopping at Kroger this morning", "Talked about the tomato garden on Sunday"],
    "p_sarah": ["Coffee at Blue Bean Café", "Showed photos of Biscuit at the park",
                "Visited for Thanksgiving planning"],
    "p_tom": ["Waved hello over the fence"],
}

# Uploaded state, kept in memory until the server restarts.
uploaded_photos: dict[str, dict] = {}  # id -> {"taken_at": datetime, "jpeg": bytes}
uploaded_visits: dict[str, dict] = {}  # id -> visit JSON with parsed datetimes


def at(day: date, hh: int, mm: int) -> datetime:
    return datetime.combine(day, time(hh, mm), LOCAL_TZ)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)


def seeded_events(day: date) -> list[dict]:
    today = date.today()
    if day > today:
        return []
    if day < today - timedelta(days=2):
        return []
    return [
        {"id": f"ev_{day}_kroger", "start": at(day, 9, 10), "end": at(day, 9, 55),
         "place": "Kroger", "place_confidence": 0.87, "people": ["p_mom"],
         "summary": "Went grocery shopping with Mom.", "evidence": ["visit:v1"],
         "photo_ids": ["ph_kroger"]},
        {"id": f"ev_{day}_cafe", "start": at(day, 10, 30), "end": at(day, 11, 40),
         "place": "Blue Bean Café", "place_confidence": 0.91, "people": ["p_sarah", "p_unknown"],
         "summary": "Coffee with Sarah and a friend of hers. Talked about Biscuit's new trick.",
         "evidence": ["visit:v2", "photo:ph_cafe1"],
         # ph_sensitive always 404s, like a sensitive photo on the real backend.
         "photo_ids": ["ph_cafe1", "ph_cafe2", "ph_sensitive"]},
        {"id": f"ev_{day}_lunch", "start": at(day, 12, 15), "end": at(day, 13, 0),
         "place": "Home", "place_confidence": 0.95, "people": [],
         "summary": "Lunch at home.", "evidence": [], "photo_ids": []},
        {"id": f"ev_{day}_walk", "start": at(day, 15, 0), "end": at(day, 15, 45),
         # Low place confidence: neutral wording, never a made-up name.
         "place": "Somewhere with park sounds", "place_confidence": 0.42, "people": ["p_tom"],
         "summary": "An afternoon walk. Tom said hello.", "evidence": [], "photo_ids": []},
    ]


def events_for(day: date) -> list[dict]:
    events = seeded_events(day)
    for v in uploaded_visits.values():
        if v["arrived"].astimezone(LOCAL_TZ).date() != day:
            continue
        end = v["departed"] or datetime.now(LOCAL_TZ)
        named = bool(v.get("place_name"))
        events.append({
            "id": f"ev_visit_{v['id']}", "start": v["arrived"], "end": end,
            "place": v["place_name"] if named else "Somewhere nearby",
            "place_confidence": 0.8 if named else 0.4, "people": [],
            "summary": "Visit uploaded from this phone." if v["departed"] else "Still here.",
            "evidence": [f"visit:{v['id']}"], "photo_ids": [],
        })
    if len(events) > 1:  # An uploaded visit means it wasn't a quiet day.
        events = [e for e in events if not e["id"].endswith("_quiet")]

    # Attach each uploaded photo to the event it falls inside, or a catch-all one.
    loose = []
    for pid, p in sorted(uploaded_photos.items(), key=lambda kv: kv[1]["taken_at"]):
        taken = p["taken_at"]
        if taken.astimezone(LOCAL_TZ).date() != day:
            continue
        home = next((e for e in events if e["start"] <= taken <= e["end"]), None)
        if home:
            home["photo_ids"].append(pid)
        else:
            loose.append((pid, taken))
    if loose:
        events.append({
            "id": f"ev_{day}_photos", "start": loose[0][1], "end": loose[-1][1],
            "place": "Photos from this phone", "place_confidence": 0.5, "people": [],
            "summary": f"{len(loose)} photo(s) uploaded.", "evidence": [],
            "photo_ids": [pid for pid, _ in loose],
        })

    for e in events:
        e["start"], e["end"] = iso(e["start"]), iso(e["end"])
    return events


# --- Placeholder images -------------------------------------------------------

def color_for(key: str) -> tuple[int, int, int]:
    hue = (sum(map(ord, key)) * 37 % 360) / 360
    r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.45)
    return int(r * 255), int(g * 255), int(b * 255)


def font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def solid_png(rgb: tuple[int, int, int], size: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = (b"\x00" + bytes(rgb) * size) * size
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def jpeg(label: str, key: str, size: int) -> bytes:
    """A labeled placeholder; a solid PNG when Pillow is missing (UIImage doesn't mind)."""
    if Image is None:
        return solid_png(color_for(key), size)
    img = Image.new("RGB", (size, size), color_for(key))
    draw = ImageDraw.Draw(img)
    draw.text((size / 2, size / 2), label, fill="white", font=font(size // 3), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def face_jpeg(person_id: str) -> bytes | None:
    p = PEOPLE.get(person_id)
    if not p:
        return None
    return jpeg((p["name"] or "?")[0].upper(), person_id, 256)


def photo_jpeg(photo_id: str) -> bytes | None:
    if photo_id in uploaded_photos:
        return uploaded_photos[photo_id]["jpeg"]
    if photo_id.startswith("ph_") and photo_id != "ph_sensitive":
        return jpeg(photo_id.removeprefix("ph_")[:6], photo_id, 400)
    return None


# --- HTTP ---------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    token = "dev-token"

    def base_url(self) -> str:
        # Behind `tailscale serve` the app talks https, so face URLs must too (ATS).
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "localhost")
        proto = self.headers.get("X-Forwarded-Proto") or ("https" if host.endswith(".ts.net") else "http")
        return f"{proto}://{host}"

    def person_json(self, p: dict) -> dict:
        return {"phone": None, **p, "face_photo_url": f"{self.base_url()}/media/faces/{p['id']}.jpg"}

    def send_json(self, body, status: int = 200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_jpeg(self, data: bytes | None):
        if data is None:
            return self.send_json({"detail": "not found"}, 404)
        self.send_response(200)
        is_png = data.startswith(b"\x89PNG")
        self.send_header("Content-Type", "image/png" if is_png else "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {self.token}":
            return True
        self.send_json({"detail": "bad or missing bearer token"}, 401)
        return False

    def body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self.send_json({"ok": True})
        # Media is public, like the real backend's unguessable URLs.
        if m := re.fullmatch(r"/media/faces/([\w-]+)\.jpg", path):
            return self.send_jpeg(face_jpeg(m[1]))
        if m := re.fullmatch(r"/media/photos/([\w-]+)\.jpg", path):
            return self.send_jpeg(photo_jpeg(m[1]))
        if not self.authorized():
            return
        if path == "/people":
            return self.send_json([self.person_json(p) for p in PEOPLE.values()])
        if m := re.fullmatch(r"/people/([\w-]+)", path):
            p = PEOPLE.get(m[1])
            if not p:
                return self.send_json({"detail": "not found"}, 404)
            return self.send_json({**self.person_json(p), "memories": MEMORIES.get(p["id"], [])[:5]})
        if m := re.fullmatch(r"/days/(\d{4}-\d{2}-\d{2})/events", path):
            return self.send_json(events_for(date.fromisoformat(m[1])))
        self.send_json({"detail": "not found"}, 404)

    def do_PATCH(self):
        if not self.authorized():
            return
        m = re.fullmatch(r"/people/([\w-]+)", self.path)
        if not m or m[1] not in PEOPLE:
            return self.send_json({"detail": "not found"}, 404)
        PEOPLE[m[1]].update(json.loads(self.body()))
        self.send_json(self.person_json(PEOPLE[m[1]]))

    def do_POST(self):
        if not self.authorized():
            return
        if self.path == "/app/visits":
            for v in json.loads(self.body()):
                uploaded_visits[v["id"]] = {**v, "arrived": parse_iso(v["arrived"]),
                                            "departed": v.get("departed") and parse_iso(v["departed"])}
                print(f"  visit {v['id']}: {v.get('place_name') or (v['lat'], v['lon'])}", flush=True)
            return self.send_json({"ok": True})
        if self.path == "/app/photos":
            header = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode()
            msg = BytesParser(policy=email_policy).parsebytes(header + self.body())
            parts = {p.get_param("name", header="content-disposition"): p.get_content()
                     for p in msg.iter_parts()}
            meta = parts["meta"]
            meta = json.loads(meta if isinstance(meta, str) else meta.decode())
            uploaded_photos[meta["id"]] = {"taken_at": parse_iso(meta["taken_at"]), "jpeg": parts["image"]}
            print(f"  photo {meta['id']}: taken {meta['taken_at']}, {len(parts['image'])} bytes", flush=True)
            return self.send_json({"ok": True})
        self.send_json({"detail": "not found"}, 404)


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()
    Handler.token = args.token
    print(f"Fake Calypso⁻¹ backend on :{args.port}, token {args.token!r}")
    print(f"  Simulator: API_BASE_URL = http:/$()/127.0.0.1:{args.port}")
    print(f"  Device:    API_BASE_URL = http:/$()/{lan_ip()}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
