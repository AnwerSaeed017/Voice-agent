"""Webhook that Vapi calls during and after each phone call."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, Header
from fastapi.responses import JSONResponse

from app.containers.container import Container
from app.core.exceptions import UnauthorizedError
from app.interfaces.service import IVoiceAgentService
from app.interfaces.utilities import ISecretVerifier

vapi_router = APIRouter(prefix="/vapi", tags=["Voice Agent"])


@vapi_router.post(
    "/webhook",
    summary="Vapi server messages",
    description="Receives tool calls during a call and the end-of-call report after it.",
)
@inject
def handle_webhook(
    payload: dict = Body(...),
    x_vapi_secret: str | None = Header(None),
    voice_agent: IVoiceAgentService = Depends(Provide[Container.services.voice_agent_service]),
    secret_verifier: ISecretVerifier = Depends(Provide[Container.utilities.secret_verifier]),
) -> JSONResponse:
    if not secret_verifier.is_valid(x_vapi_secret):
        raise UnauthorizedError("Invalid or missing webhook secret.")
    message = payload.get("message")
    # This endpoint answers in Vapi's own format, not the REST envelope.
    return JSONResponse(voice_agent.handle_message(message if isinstance(message, dict) else {}))
