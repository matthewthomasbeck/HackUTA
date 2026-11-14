# Hour-1 spike results

Fill these in during Task 0. Later tasks read these values. Copy the env ones into `.env`.

| Key | Owner | Value | Notes |
|---|---|---|---|
| `AGENT_TRACK_MODE` (`per_participant` \| `composite`) | Keanu | | participants/tracks seen in a group call |
| `GROUP_CALL_START` (`agent_dials_both` \| `agent_dials_relative_then_add` \| `manual_only`) | Keanu | | |
| 5-minute call cap hit? | Keanu | | |
| Grok STT mode (`streaming` \| `batch_only`) + latency | Vishnu | | |
| Grok TTS (`ok` \| `fallback:<name>`) + latency | Vishnu | | |
| `PUCK_MIC` device name (`arecord -l`) | Matt | | Saramonic lav via USB-A adapter |
| `PUCK_SOUND_BACKEND` / accelerator (`coral` \| `hailo` \| `none`) | Matt | | |
| Sound tag ms/segment (cpu / accelerator) | Matt | | |
| Battery life with accelerator | Matt | | |
