from datetime import datetime, timezone
import hashlib
import hmac
import pytest

from gpd.integrations.slack.signatures import (
    SlackReplayRejected,
    SlackSignatureInvalid,
    verify_slack_signature,
)


def test_valid_slack_signature_is_accepted():
    secret = "my_signing_secret"
    body = b'{"text": "hello"}'
    now = datetime.now(timezone.utc)
    ts = str(int(now.timestamp()))
    base = b"v0:" + ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

    # Should not raise
    verify_slack_signature(secret, ts, body, sig, now=now)


def test_old_slack_timestamp_is_rejected():
    secret = "my_signing_secret"
    body = b'{"text": "hello"}'
    now = datetime.now(timezone.utc)
    ts = str(int(now.timestamp()) - 350)  # 350 seconds ago (> 300s)
    base = b"v0:" + ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

    with pytest.raises(SlackReplayRejected):
        verify_slack_signature(secret, ts, body, sig, now=now)


def test_future_slack_timestamp_is_rejected():
    secret = "my_signing_secret"
    body = b'{"text": "hello"}'
    now = datetime.now(timezone.utc)
    ts = str(int(now.timestamp()) + 350)  # 350 seconds in future (> 300s)
    base = b"v0:" + ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

    with pytest.raises(SlackReplayRejected):
        verify_slack_signature(secret, ts, body, sig, now=now)


def test_mismatched_signature_is_rejected():
    secret = "my_signing_secret"
    body = b'{"text": "hello"}'
    now = datetime.now(timezone.utc)
    ts = str(int(now.timestamp()))
    sig = "v0=0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(SlackSignatureInvalid):
        verify_slack_signature(secret, ts, body, sig, now=now)


def test_http_old_slack_timestamp_is_rejected(slack_client, old_signed_event):
    response = slack_client.post(
        "/api/v1/integrations/slack/events",
        content=old_signed_event.body,
        headers=old_signed_event.headers,
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "slack_replay_rejected"


def test_http_invalid_signature_is_rejected(slack_client, signed_checkout_event):
    headers = dict(signed_checkout_event.headers)
    headers["X-Slack-Signature"] = "v0=bad_sig_123"

    response = slack_client.post(
        "/api/v1/integrations/slack/events",
        content=signed_checkout_event.body,
        headers=headers,
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "slack_signature_invalid"
