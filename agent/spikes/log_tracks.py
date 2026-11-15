"""Observe a Chert LiveKit room without publishing audio or video.

Run from agent/: uv run --env-file ../.env python spikes/log_tracks.py
Requires LIVEKIT_URL and a short-lived LIVEKIT_TOKEN for the call's room.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
import time

from livekit import rtc


def snapshot(room):
    """Return publication metadata only; never store frames or audio."""
    participants = []
    for participant in sorted(room.remote_participants.values(), key=lambda p: p.identity):
        audio, video = [], []
        for publication in sorted(participant.track_publications.values(), key=lambda p: p.sid):
            track = {"sid": publication.sid, "muted": publication.muted}
            if publication.kind == rtc.TrackKind.KIND_AUDIO:
                audio.append(track)
            elif publication.kind == rtc.TrackKind.KIND_VIDEO:
                video.append({**track, "width": publication.width, "height": publication.height})
        participants.append({"identity": participant.identity, "audio": audio, "video": video})
    return {"room": room.name, "participant_count": len(participants), "participants": participants}


def emit(event, started, **fields):
    print(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                      "elapsed_s": round(time.monotonic() - started, 3),
                      "event": event, **fields}), flush=True)


async def log_room(room, duration=360):
    """Log an already-connected room, including one dispatched by Chert."""
    stopped = asyncio.Event()
    started = time.monotonic()

    @room.on("disconnected")
    def disconnected(reason):
        emit("disconnected", started, reason=str(reason))
        stopped.set()

    @room.on("reconnecting")
    def reconnecting():
        emit("reconnecting", started)

    @room.on("reconnected")
    def reconnected():
        emit("reconnected", started)

    try:
        emit("connected", started, room=room.name)
        deadline = started + duration if duration else float("inf")
        while not stopped.is_set():
            emit("tracks", started, **snapshot(room))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                emit("observation_complete", started)
                break
            try:
                await asyncio.wait_for(stopped.wait(), timeout=min(2, remaining))
            except TimeoutError:
                pass
    finally:
        room.off("disconnected", disconnected)
        room.off("reconnecting", reconnecting)
        room.off("reconnected", reconnected)


async def observe(url, token, duration=360):
    room = rtc.Room()
    try:
        # Publication dimensions suffice for this spike. Avoid subscribing to media.
        await room.connect(url, token, options=rtc.RoomOptions(auto_subscribe=False))
        await log_room(room, duration)
    finally:
        await room.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=360,
                        help="Seconds to observe (default: 360; 0: until Ctrl-C).")
    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration must be nonnegative")
    url, token = os.getenv("LIVEKIT_URL"), os.getenv("LIVEKIT_TOKEN")
    if not url or not token:
        parser.error("Set LIVEKIT_URL and LIVEKIT_TOKEN in the environment; do not pass tokens on the command line.")
    try:
        asyncio.run(observe(url, token, args.duration))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
