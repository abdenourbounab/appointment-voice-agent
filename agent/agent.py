import asyncio
import logging
import os
from datetime import datetime
from typing import Annotated

import dateparser
import httpx
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext, JobProcess, RunContext, inference
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import silero

load_dotenv()

logger = logging.getLogger("appointment-agent")

API_URL = os.environ.get("API_URL", "http://localhost:5000")

SYSTEM_PROMPT = (
    "Tu es un assistant vocal de prise de rendez-vous pour une concession automobile. "
    "Demande poliment au client pour quelle date il souhaite prendre rendez-vous. "
    "Dès qu'il indique une date, appelle immédiatement la fonction save_appointment_date. "
    "Remercie ensuite le client et termine la conversation. "
    "Parle uniquement en français. Sois bref et professionnel."
)

# Maximum time to wait for the customer to provide a date before hanging up and Delay between date capture and hang-up
DATE_TIMEOUT_SECONDS = 60
HANGUP_DELAY_SECONDS = 10


class AppointmentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        # Instance-level state - each call gets its own isolated context
        self.appointment_date: datetime | None = None
        # Event set as soon as the LLM captures the date, used to unblock the session handler
        self.date_captured = asyncio.Event()

    @function_tool()
    async def save_appointment_date(
        self,
        context: RunContext,
        date: Annotated[str, "La date de rendez-vous souhaitée par le client, ex: '15 mars 2026 à 14h00'."],
    ) -> str:
        """Save the desired appointment date provided by the customer."""
        # Parse the natural language French date string into a proper datetime
        parsed = dateparser.parse(date, languages=["fr"])
        if parsed is None:
            logger.warning("Could not parse date string: %s", date)
            return "Je n'ai pas pu comprendre cette date. Pouvez-vous la reformuler ?"

        self.appointment_date = parsed
        self.date_captured.set()
        logger.info("Appointment date captured: %s", parsed.isoformat())
        return f"Parfait, j'ai bien noté votre rendez-vous pour le {date}."


# AgentServer registers this file as a LiveKit agent worker
server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def session_handler(ctx: JobContext) -> None:
    agent = AppointmentAgent()

    # All models go through LiveKit Inference - no external API keys needed
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=inference.STT(model="deepgram/nova-3", language="fr"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="cartesia/sonic-3:4325f426-c4e0-418e-a0e5-97fcdfcdf8e6"),
    )

    await session.start(room=ctx.room, agent=agent)

    # linked_participant is available after session.start()
    participant = session.room_io.linked_participant
    caller_identity = participant.identity if participant else "unknown"

    await session.generate_reply(
        instructions="Salue le client et demande-lui pour quelle date il souhaite prendre rendez-vous."
    )

    # asyncio.Event avoids polling - resumes instantly when the date is set
    try:
        await asyncio.wait_for(agent.date_captured.wait(), timeout=DATE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Timeout reached without capturing an appointment date (room=%s)", ctx.room.name)

    await asyncio.sleep(HANGUP_DELAY_SECONDS)
    await _notify_api(ctx.room.name, caller_identity, agent.appointment_date)
    await session.aclose()
    await ctx.room.disconnect()


async def _notify_api(room_id: str, caller_identity: str, appointment_date: datetime | None) -> None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_URL}/end-of-call",
                json={
                    "room_id": room_id,
                    "caller_identity": caller_identity,
                    "appointment_date": appointment_date.isoformat() if appointment_date else None,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("API notified successfully: %s", resp.json())
    except Exception as exc:
        logger.error("Failed to notify API: %s", exc)


if __name__ == "__main__":
    agents.cli.run_app(server)

