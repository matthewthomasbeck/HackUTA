"""Register the track observer for Chert's LiveKit dispatch.

From agent/:
    uv run --env-file .env.local python spikes/chert_agent.py dev

In another terminal in agent/:
    npx --yes @trychert/facetime@0.1.0-beta.21 dev --agent calypso-track-spike

This is a silent metadata observer, not the finished media agent. Chert's audio
readiness timeout may end live calls; record that result rather than treating it
as evidence about group topology or the five-minute cap.
"""

import os

from livekit.agents import AgentServer, AutoSubscribe, JobContext, cli

from log_tracks import log_room

server = AgentServer()


@server.rtc_session(agent_name=os.getenv("AGENT_NAME", "calypso-track-spike"))
async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_NONE)
    await log_room(ctx.room, duration=0)


if __name__ == "__main__":
    cli.run_app(server)
