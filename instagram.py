"""Thin client around the official Instagram Graph API.

Only the official Graph API is used here (no Selenium, no unofficial /
private Instagram APIs). Every call logs the response and retries with
exponential backoff when Instagram/Facebook signals a rate limit.
"""

import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger("instagram")

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Facebook/Instagram error subcodes that indicate throttling and are worth
# retrying. See: https://developers.facebook.com/docs/graph-api/guides/error-handling
RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613}

MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2


class InstagramAPIError(Exception):
    """Raised when the Graph API returns a non-retryable error."""


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    try:
        error = response.json().get("error", {})
    except ValueError:
        return False
    return error.get("code") in RATE_LIMIT_ERROR_CODES


def _request(method: str, url: str, **kwargs: Any) -> dict:
    """Perform an HTTP request against the Graph API with retry/backoff."""

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=15) as client:
                response = client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            last_exception = exc
            logger.warning("Instagram API network error (attempt %s/%s): %s", attempt, MAX_RETRIES, exc)
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
            continue

        logger.info("Instagram API %s %s -> %s: %s", method, url.split("?")[0], response.status_code, response.text[:500])

        if response.status_code < 400:
            return response.json() if response.content else {}

        if _is_rate_limited(response) and attempt < MAX_RETRIES:
            wait = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning("Rate limited by Instagram API, retrying in %ss (attempt %s/%s)", wait, attempt, MAX_RETRIES)
            time.sleep(wait)
            continue

        # Non-retryable (or retries exhausted) error.
        try:
            error_body = response.json()
        except ValueError:
            error_body = {"raw": response.text}
        raise InstagramAPIError(f"Instagram API error ({response.status_code}): {error_body}")

    raise InstagramAPIError(f"Instagram API request failed after {MAX_RETRIES} attempts: {last_exception}")


def reply_to_comment(comment_id: str, message: str, access_token: str) -> dict:
    """Post a public reply to an Instagram comment.

    Graph API: POST /{comment-id}/replies
    """

    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    return _request("POST", url, data={"message": message, "access_token": access_token})


def send_dm(instagram_user_id: str, message: str, ig_business_account_id: str, access_token: str) -> dict:
    """Send a private direct message to a commenter.

    Graph API: POST /{ig-business-account-id}/messages

    NOTE: Instagram only allows a business to message a user who has
    previously messaged them (the 24-hour / private-reply window), unless
    the app has the instagram_manage_messages permission with an approved
    use case for outbound messaging. See README.md for details.
    """

    url = f"{GRAPH_API_BASE}/{ig_business_account_id}/messages"
    payload = {
        "recipient": {"id": instagram_user_id},
        "message": {"text": message},
        "access_token": access_token,
    }
    return _request("POST", url, json=payload)


def send_private_reply_to_comment(comment_id: str, message: str, access_token: str) -> dict:
    """Send a private reply to a comment (Instagram's recommended way to DM a
    commenter without requiring them to have messaged first).

    Graph API: POST /{comment-id}/private_replies
    """

    url = f"{GRAPH_API_BASE}/{comment_id}/private_replies"
    return _request("POST", url, data={"message": message, "access_token": access_token})


def get_post_details(post_id: str, access_token: str) -> dict:
    """Fetch a post's thumbnail URL and caption for display in the dashboard.

    Graph API: GET /{ig-media-id}?fields=caption,media_type,media_url,thumbnail_url,permalink
    """

    url = f"{GRAPH_API_BASE}/{post_id}"
    params = {
        "fields": "caption,media_type,media_url,thumbnail_url,permalink,timestamp",
        "access_token": access_token,
    }
    with httpx.Client(timeout=15) as client:
        response = client.get(url, params=params)

    logger.info("Instagram API GET %s -> %s: %s", url, response.status_code, response.text[:500])

    if response.status_code >= 400:
        try:
            error_body = response.json()
        except ValueError:
            error_body = {"raw": response.text}
        raise InstagramAPIError(f"Instagram API error ({response.status_code}): {error_body}")

    data = response.json()
    # Videos expose thumbnail_url; images use media_url as the preview.
    data["preview_url"] = data.get("thumbnail_url") or data.get("media_url")
    return data
