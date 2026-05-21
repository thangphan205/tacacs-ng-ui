import html
import json
import logging

import emails  # type: ignore
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
        elif channel.channel_type == "gchat":
            return _send_gchat(config=config, subject=subject, body=body)
        elif channel.channel_type == "email":
            return _send_email(config=config, subject=subject, body=body)
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

    divider = "─" * 28
    text = f"🔔 <b>{html.escape(subject)}</b>\n<code>{divider}</code>\n{html.escape(body)}\n<code>{divider}</code>"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    topic_id = config.get("topic_id")
    if topic_id:
        payload["message_thread_id"] = int(topic_id)
    resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Telegram API error {resp.status_code}: {resp.text[:200]}"


def _send_slack(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "slack config missing webhook_url"

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔔 {subject}", "emoji": True},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body},
            },
            {"type": "divider"},
        ]
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


def _send_discord(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "discord config missing webhook_url"

    # extract severity from subject like "[HIGH] TACACS Alert: ..."
    severity_key = "high"
    for sev in ("critical", "high", "medium", "low"):
        if f"[{sev.upper()}]" in subject:
            severity_key = sev
            break
    color = _DISCORD_SEVERITY_COLOR.get(severity_key, 0xE74C3C)

    payload = {
        "embeds": [
            {
                "title": f"🔔 {subject}",
                "description": body,
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
                        {"type": "TextBlock", "text": body, "wrap": True, "spacing": "Medium"},
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


def _send_gchat(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, "gchat config missing webhook_url"

    text = f"🔔 *{subject}*\n\n{body}"
    resp = httpx.post(webhook_url, json={"text": text}, timeout=_TIMEOUT)
    if resp.is_success:
        return True, None
    return False, f"Google Chat webhook error {resp.status_code}: {resp.text[:200]}"


def _send_email(*, config: dict, subject: str, body: str) -> tuple[bool, str | None]:
    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_password = config.get("smtp_password", "")
    from_email = config.get("from_email", smtp_user)
    to_email = config.get("to_email", "")
    use_tls = config.get("tls", True)

    if not smtp_host or not to_email:
        return False, "email config missing smtp_host or to_email"

    html_body = f"<pre style='font-family:monospace'>{body}</pre>"
    message = emails.Message(
        subject=f"🔔 {subject}",
        html=html_body,
        mail_from=from_email,
    )
    smtp_options: dict = {"host": smtp_host, "port": smtp_port}
    if use_tls:
        smtp_options["tls"] = True
    if smtp_user:
        smtp_options["user"] = smtp_user
    if smtp_password:
        smtp_options["password"] = smtp_password

    response = message.send(to=to_email, smtp=smtp_options)
    if response.status_code in (250, 200):
        return True, None
    return False, f"SMTP error {response.status_code}: {response.error}"
