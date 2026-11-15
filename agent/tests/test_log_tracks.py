"""Check that spike evidence reflects publications, including muted video."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

from livekit import rtc

spec = importlib.util.spec_from_file_location(
    "log_tracks", Path(__file__).parents[1] / "spikes" / "log_tracks.py")
log_tracks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log_tracks)


def publication(sid, kind, **kwargs):
    return NS(sid=sid, kind=kind, muted=False, **kwargs)


def test_separate_participants_and_tracks():
    room = NS(name="spike", remote_participants={
        "b": NS(identity="relative-b", track_publications={}),
        "a": NS(identity="relative-a", track_publications={
            "audio": publication("AU1", rtc.TrackKind.KIND_AUDIO),
            "video": publication("VI1", rtc.TrackKind.KIND_VIDEO, width=1280, height=720),
        }),
    })
    result = log_tracks.snapshot(room)
    assert result["participant_count"] == 2
    assert result["participants"] == [
        {"identity": "relative-a", "audio": [{"sid": "AU1", "muted": False}],
         "video": [{"sid": "VI1", "muted": False, "width": 1280, "height": 720}]},
        {"identity": "relative-b", "audio": [], "video": []},
    ]


def test_muted_composite_publication_is_still_reported():
    video = publication("VI-grid", rtc.TrackKind.KIND_VIDEO, width=1920, height=1080)
    video.muted = True
    room = NS(name="spike", remote_participants={
        "bridge": NS(identity="bridge", track_publications={"v": video})})
    result = log_tracks.snapshot(room)
    assert result["participant_count"] == 1
    assert result["participants"][0]["video"][0]["muted"] is True
    # A participant count alone does not prove the video is a composite grid.
    assert "AGENT_TRACK_MODE" not in result


def test_empty_room():
    assert log_tracks.snapshot(NS(name="spike", remote_participants={})) == {
        "room": "spike", "participant_count": 0, "participants": []}
