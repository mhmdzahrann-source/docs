"""Thin client around the official WhatsApp Business Cloud API (Meta Graph API).

Same approach as instagram.py: official API only, every call is logged, and
rate-limit / network errors are retried with exponential backoff.
"""

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger("whatsapp")

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# 4/17/32/613 = generic Graph throttling, 130429/131048/131056 = WhatsApp
# throughput / spam-rate / pair-rate limits.
RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613, 130429, 131048, 131056}

MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2

# WhatsApp limits: reply-button titles max 20 chars, max 3 buttons.
MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20


class WhatsAppAPIError(Exception):
    """Raised when the Cloud API returns a non-retryable error."""


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    try:
        error = response.json().get("error", {})
    except ValueError:
        return False
    return error.get("code") in RATE_LIMIT_ERROR_CODES


def _post(url: str, payload: dict, access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            last_exception = exc
            logger.warning("WhatsApp API network error (attempt %s/%s): %s", attempt, MAX_RETRIES, exc)
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
            continue

        logger.info("WhatsApp API POST %s -> %s: %s", url, response.status_code, response.text[:500])

        if response.status_code < 400:
            return response.json() if response.content else {}

        if _is_rate_limited(response) and attempt < MAX_RETRIES:
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning("Rate limited by WhatsApp API, retrying in %ss (attempt %s/%s)", wait, attempt, MAX_RETRIES)
            time.sleep(wait)
            continue

        try:
            error_body: Any = response.json()
        except ValueError:
            error_body = {"raw": response.text}
        raise WhatsAppAPIError(f"WhatsApp API error ({response.status_code}): {error_body}")

    raise WhatsAppAPIError(f"WhatsApp API request failed after {MAX_RETRIES} attempts: {last_exception}")


def _messages_url(phone_number_id: str) -> str:
    return f"{GRAPH_API_BASE}/{phone_number_id}/messages"


def send_text(to: str, text: str, phone_number_id: str, access_token: str) -> dict:
    """Send a free-form text message.

    Only allowed inside the 24-hour customer-service window (i.e. the
    customer messaged you in the last 24h) — which is always the case when
    replying to an incoming message.
    """

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4096]},
    }
    return _post(_messages_url(phone_number_id), payload, access_token)


def send_buttons(to: str, text: str, buttons: list[tuple[str, str]], phone_number_id: str, access_token: str) -> dict:
    """Send a message with up to 3 tappable reply buttons.

    `buttons` is a list of (id, title). When tapped, the webhook receives an
    `interactive.button_reply` with that id.
    """

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": button_id, "title": title[:MAX_BUTTON_TITLE]}}
                    for button_id, title in buttons[:MAX_BUTTONS]
                ]
            },
        },
    }
    return _post(_messages_url(phone_number_id), payload, access_token)


def mark_as_read(message_id: str, phone_number_id: str, access_token: str) -> dict:
    """Show blue ticks on the customer's message."""

    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    return _post(_messages_url(phone_number_id), payload, access_token)
