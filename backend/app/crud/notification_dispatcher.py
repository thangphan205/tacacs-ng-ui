import json
import logging

import httpx

from app.models import NotificationChannel

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def dispatch_notification(
    *, channel: NotificationChannel, subject: str, body: str
) -> tuple[bool, str | None]:
    """Send a notification via the configured channel. Returns (success, error_message)."""
    try:
        config = json.loads(channel.config_json or "{}")
    except json.JSONDecodeError as e:
        return False, f"Invalid config_json: {e}"

    try:
        if channel.channel_type == "telegram":
            return _send_telegram(config=config, subject=subject, body=body)
        elif channel.channel_type == "slack":
            return _send_slack(config=config, subject=subject, body=body)
        elif channel.channel_type == "discord":
            return _send_discord(config=config, subject=subject, body=body)
        elif channel.channel_type == "teams":
            return _send_teams(config=config, subject=subject, body=body)
        elif channel.channel_type == "webhook":
            return _send_webhook(config=config, subject=subject, body=body)
        else:
            return False, f"Unknown channel_type: {channel.channel_type}"
    except Exception as e:
        logger.exception("Notification dispatch error for channel %s", channel.id)
        return False, str(e)


def _send_telegram(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not bot_token or not chat_id:
        return False, "telegram config missing bot_token or chat_id"

    text = f"*{subject}*\n\n{body}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = httpx.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return True, None
    return False, f"Telegram API error {resp.status_code}: {resp.text[:200]}"


def _send_slack(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "slack config missing webhook_url"

    resp = httpx.post(
        webhook_url,
        json={"text": f"*{subject}*\n{body}"},
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return True, None
    return False, f"Slack webhook error {resp.status_code}: {resp.text[:200]}"


def _send_discord(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "discord config missing webhook_url"

    resp = httpx.post(
        webhook_url,
        json={"content": f"**{subject}**\n{body}"},
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return True, None
    return False, f"Discord webhook error {resp.status_code}: {resp.text[:200]}"


def _send_teams(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "teams config missing webhook_url"

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": subject, "weight": "Bolder", "size": "Medium"},
                        {"type": "TextBlock", "text": body, "wrap": True},
                    ],
                },
            }
        ],
    }
    resp = httpx.post(webhook_url, json=payload, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Teams webhook error {resp.status_code}: {resp.text[:200]}"


def _send_webhook(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "webhook config missing webhook_url"

    headers = {}
    token = config.get("token", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = httpx.post(
        webhook_url,
        json={"subject": subject, "body": body},
        headers=headers,
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return True, None
    return False, f"Webhook error {resp.status_code}: {resp.text[:200]}"
