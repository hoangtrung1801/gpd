from datetime import datetime, timezone
import json
from typing import Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gpd.api.errors import ApiEnvelope, ApiException
from gpd.db.engine import Database
from gpd.integrations.slack.client import SlackClient
from gpd.integrations.slack.config import get_slack_bot_token, get_slack_signing_secret
from gpd.integrations.slack.service import SlackService
from gpd.integrations.slack.signatures import (
    SlackReplayRejected,
    SlackSignatureInvalid,
    verify_slack_signature,
)

router = APIRouter(tags=["slack"])


class SlackStatus(BaseModel):
    installed: bool = False
    signing_secret_configured: bool = False
    bot_token_configured: bool = False


@router.get("/api/v1/integrations/slack/status", response_model=ApiEnvelope[SlackStatus])
@router.get("/integrations/slack/status", response_model=ApiEnvelope[SlackStatus])
def get_slack_status(request: Request) -> ApiEnvelope[SlackStatus]:
    secret = get_slack_signing_secret(request)
    token = get_slack_bot_token(request)

    sec_configured = bool(secret and secret.get_secret_value())
    tok_configured = bool(token and token.get_secret_value())

    status = SlackStatus(
        installed=sec_configured and tok_configured,
        signing_secret_configured=sec_configured,
        bot_token_configured=tok_configured,
    )
    return ApiEnvelope[SlackStatus](ok=True, data=status)


@router.post("/api/v1/integrations/slack/events")
@router.post("/integrations/slack/events")
async def handle_slack_events(request: Request) -> Any:
    # Verify signature BEFORE JSON parse!
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    secret = get_slack_signing_secret(request)

    if secret and secret.get_secret_value():
        if not timestamp or not signature:
            raise SlackSignatureInvalid("Missing Slack signature or timestamp headers")
        verify_slack_signature(secret, timestamp, raw_body, signature)
    elif timestamp or signature:
        # If headers provided even without secret configured in app, check timestamp replay
        if timestamp:
            try:
                if abs(datetime.now(timezone.utc).timestamp() - int(timestamp)) > 300:
                    raise SlackReplayRejected("Slack timestamp outside 300s replay window")
            except (ValueError, TypeError):
                raise SlackReplayRejected("Invalid timestamp")
        if signature and not secret:
            # Cannot verify signature without secret
            pass

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ApiException(400, "invalid_json", "Failed to parse JSON body") from exc

    # URL verification must be synchronous
    if payload.get("type") == "url_verification":
        return JSONResponse(status_code=200, content={"challenge": payload.get("challenge")})

    # Event callback
    db: Database = request.app.state.database
    bot_tok = get_slack_bot_token(request)
    tok_str = bot_tok.get_secret_value() if bot_tok else None
    client = SlackClient(bot_token=tok_str)
    slack_service: SlackService = getattr(
        request.app.state, "slack_service", None
    ) or SlackService(db, slack_client=client)
    task_detail = await slack_service.handle_event(payload)

    resp_data = {
        "ok": True,
        "data": task_detail.model_dump(mode="json") if task_detail else None,
        "task": task_detail.model_dump(mode="json") if task_detail else None,
        "public_id": task_detail.public_id if task_detail else None,
        "acceptance_criteria": task_detail.acceptance_criteria if task_detail else None,
        "summary": task_detail.summary if task_detail else None,
        "participants": task_detail.participants if task_detail else [],
    }
    return JSONResponse(status_code=200, content=resp_data)
