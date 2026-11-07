import html
import json
import logging

import emails  # type: ignore
import httpx

from app.crud.alert_formatter import (
    DISCORD,
    GCHAT,
    HTML,
    SLACK,
    AlertMessage,
    render,
)
from app.models import NotificationChannel

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0


def dispatch_notification(
    *,
    channel: NotificationChannel,
    subject: str,
    body: str,
    payload: dict | None = None,
    message: AlertMessage | None = None,
) -> tuple[bool, str | None]:
    """Send a notification via the configured channel. Returns (success, error_message).

    `payload` carries the structured alert data (e.g. offending IP, fail counts).
    Only the `webhook` channel forwards it as-is (under a `data` key) so downstream
    automation can act on fields like `data.ip` without parsing the free-text body.

    `message` is the structured alert from `alert_formatter`; channels with
    their own markup render it themselves instead of sending the plain `body`.
    Without it (the channel test button) every channel sends subject + body.
    """
    try:
        config = json.loads(channel.config_json or "{}")
    except json.JSONDecodeError as e:
        return False, f"Invalid config_json: {e}"

    try:
        if channel.channel_type == "telegram":
            return _send_telegram(
                config=config, subject=subject, body=body, message=message
            )
        elif channel.channel_type == "slack":
            return _send_slack(
                config=config, subject=subject, body=body, message=message
            )
        elif channel.channel_type == "discord":
            return _send_discord(
                config=config, subject=subject, body=body, message=message
            )
        elif channel.channel_type == "teams":
            return _send_teams(config=config, subject=subject, body=body)
        elif channel.channel_type == "webhook":
            return _send_webhook(
                config=config, subject=subject, body=body, payload=payload
            )
        elif channel.channel_type == "gchat":
            return _send_gchat(
                config=config, subject=subject, body=body, message=message
            )
        elif channel.channel_type == "email":
            return _send_email(
                config=config, subject=subject, body=body, message=message
            )
        else:
            return False, f"Unknown channel_type: {channel.channel_type}"
    except Exception as e:
        logger.exception("Notification dispatch error for channel %s", channel.id)
        return False, str(e)


# Telegram rejects messages over 4096 characters; entries are capped by the
# formatter, so this only guards against pathological values.
_TELEGRAM_MAX = 4096


def _send_telegram(
    *, config: dict, subject: str, body: str, message: AlertMessage | None = None
) -> tuple[bool, str | None]:
    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not bot_token or not chat_id:
        return False, "telegram config missing bot_token or chat_id"

    text = render(message, HTML) if message else None
    if text is None or len(text) > _TELEGRAM_MAX:
        divider = "─" * 28
        plain = body if text is None else body[: _TELEGRAM_MAX - 200]
        text = f"🔔 <b>{html.escape(subject)}</b>\n<code>{divider}</code>\n{html.escape(plain)}\n<code>{divider}</code>"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    topic_id = config.get("topic_id")
    if topic_id:
        payload["message_thread_id"] = int(topic_id)
    resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Telegram API error {resp.status_code}: {resp.text[:200]}"


def _send_slack(
    *, config: dict, subject: str, body: str, message: AlertMessage | None = None
) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "slack config missing webhook_url"

    header = message.heading if message else f"🔔 {subject}"
    text = render(message, SLACK, heading=False) if message else body
    payload = {
        # Plain-text fallback for notifications and clients without blocks.
        "text": message.subject if message else subject,
        "blocks": [
            {
                "type": "header",
                # Slack caps header text at 150 characters.
                "text": {"type": "plain_text", "text": header[:150], "emoji": True},
            },
            {"type": "divider"},
            {
                "type": "section",
                # ... and section text at 3000.
                "text": {"type": "mrkdwn", "text": text[:3000]},
            },
            {"type": "divider"},
        ],
    }
    resp = httpx.post(webhook_url, json=payload, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Slack webhook error {resp.status_code}: {resp.text[:200]}"


_DISCORD_SEVERITY_COLOR = {
    "low": 0xF1C40F,
    "medium": 0xE67E22,
    "high": 0xE74C3C,
    "critical": 0x992D22,
}


def _send_discord(
    *, config: dict, subject: str, body: str, message: AlertMessage | None = None
) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "discord config missing webhook_url"

    if message:
        severity_key = message.severity
    else:
        # The test notification has no message; read "[HIGH] ..." off the subject.
        severity_key = "high"
        for sev in ("critical", "high", "medium", "low"):
            if f"[{sev.upper()}]" in subject:
                severity_key = sev
                break
    color = _DISCORD_SEVERITY_COLOR.get(severity_key, 0xE74C3C)

    title = message.heading if message else f"🔔 {subject}"
    description = render(message, DISCORD, heading=False) if message else body
    payload = {
        "embeds": [
            {
                # Discord caps embed titles at 256 and descriptions at 4096.
                "title": title[:256],
                "description": description[:4096],
                "color": color,
            }
        ]
    }
    resp = httpx.post(webhook_url, json=payload, timeout=_TIMEOUT)
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
                        {
                            "type": "TextBlock",
                            "text": f"🔔 {subject}",
                            "weight": "Bolder",
                            "size": "Large",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": body,
                            "wrap": True,
                            "spacing": "Medium",
                        },
                    ],
                },
            }
        ],
    }
    resp = httpx.post(webhook_url, json=payload, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Teams webhook error {resp.status_code}: {resp.text[:200]}"


def _send_webhook(
    *, config: dict, subject: str, body: str, payload: dict | None = None
) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "webhook config missing webhook_url"

    headers = {}
    token = config.get("token", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    json_body: dict = {"subject": subject, "body": body}
    if payload:
        json_body["data"] = payload

    resp = httpx.post(
        webhook_url,
        json=json_body,
        headers=headers,
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return True, None
    return False, f"Webhook error {resp.status_code}: {resp.text[:200]}"


def _send_gchat(
    *, config: dict, subject: str, body: str, message: AlertMessage | None = None
) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "gchat config missing webhook_url"

    text = render(message, GCHAT) if message else f"🔔 *{subject}*\n\n{body}"
    resp = httpx.post(webhook_url, json={"text": text}, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Google Chat webhook error {resp.status_code}: {resp.text[:200]}"


def _send_email(
    *, config: dict, subject: str, body: str, message: AlertMessage | None = None
) -> tuple[bool, str | None]:
    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_password = config.get("smtp_password", "")
    from_email = config.get("from_email", smtp_user)
    to_email = config.get("to_email", "")
    use_tls = config.get("tls", True)

    if not smtp_host or not to_email:
        return False, "email config missing smtp_host or to_email"

    content = render(message, HTML) if message else html.escape(body, quote=False)
    html_body = (
        f"<pre style='font-family:monospace;white-space:pre-wrap'>{content}</pre>"
    )
    email_message = emails.Message(
        subject=f"🔔 {subject}",
        html=html_body,
        text=body,
        mail_from=from_email,
    )
    smtp_options: dict = {"host": smtp_host, "port": smtp_port}
    if use_tls:
        smtp_options["tls"] = True
    if smtp_user:
        smtp_options["user"] = smtp_user
    if smtp_password:
        smtp_options["password"] = smtp_password

    response = email_message.send(to=to_email, smtp=smtp_options)
    if response.status_code in (250, 200):
        return True, None
    return False, f"SMTP error {response.status_code}: {response.error}"
