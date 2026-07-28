"""
Low-level Google Calendar REST API wrapper.

Uses requests-oauthlib.OAuth2Session so that access tokens are refreshed
automatically. Credentials (client_id, client_secret, token URIs) are read
from the user's GoogleCalendarConfig — no environment variables required.
"""

# Standard library imports
import ipaddress
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlparse

# Third-party imports (Django)
from django.conf import settings

# Third-party imports
from requests_oauthlib import OAuth2Session

# Local imports
from .client_settings import (
    GOOGLE_CALENDAR_API_BASE,
    GOOGLE_USERINFO_URL,
    PRIMARY_CALENDAR_ID,
)

GOOGLE_TASKS_API_BASE = "https://tasks.googleapis.com/tasks/v1"

# (connect timeout, read timeout) in seconds for every outbound call to Google.
# requests_oauthlib defaults to no timeout at all, so a blocked/firewalled
# network path hangs the request (and the worker thread serving it) forever.
GOOGLE_API_TIMEOUT = (5, 15)

logger = logging.getLogger(__name__)


def _save_token(config, new_token):
    """Callback used by OAuth2Session to persist a refreshed token."""
    config.token = new_token
    config.save(update_fields=["token"])


def _get_oauth_session(config):
    """
    Return an OAuth2Session for the given GoogleCalendarConfig.

    The session auto-refreshes expired tokens and persists the new token via
    _save_token so subsequent requests don't need a re-auth.
    """
    return OAuth2Session(
        client_id=config.get_client_id(),
        token=config.token,
        auto_refresh_url=config.get_token_uri(),
        auto_refresh_kwargs={
            "client_id": config.get_client_id(),
            "client_secret": config.get_client_secret(),
        },
        token_updater=lambda new_token: _save_token(config, new_token),
    )


def get_google_user_email(config):
    """Fetch the email address of the connected Google account."""
    session = _get_oauth_session(config)
    resp = session.get(GOOGLE_USERINFO_URL, timeout=GOOGLE_API_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("email", "")


def push_event_to_google(config, event_data, return_full=False):
    """
    Create or update a Google Calendar event.

    If event_data contains a 'google_event_id' key it attempts a PUT (update).
    Falls back to POST (create) on 404. Returns the Google event ID string,
    or the full event resource dict when return_full=True (needed by callers
    that must read back e.g. hangoutLink after a conferenceData createRequest).

    conferenceDataVersion=1 is required on both PUT and POST for Google to honor
    a `conferenceData` field in the request body — without it, Google silently
    drops conferenceData and creates a plain event with no Meet link.
    """
    session = _get_oauth_session(config)
    google_event_id = event_data.pop("google_event_id", None)
    params = {"conferenceDataVersion": 1}

    if google_event_id:
        url = (
            f"{GOOGLE_CALENDAR_API_BASE}/calendars"
            f"/{PRIMARY_CALENDAR_ID}/events/{google_event_id}"
        )
        resp = session.put(
            url, json=event_data, params=params, timeout=GOOGLE_API_TIMEOUT
        )
        if resp.status_code == 404:
            # Event was deleted on the Google side — re-create it
            url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events"
            resp = session.post(
                url, json=event_data, params=params, timeout=GOOGLE_API_TIMEOUT
            )
    else:
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events"
        resp = session.post(
            url, json=event_data, params=params, timeout=GOOGLE_API_TIMEOUT
        )

    resp.raise_for_status()
    data = resp.json()
    return data if return_full else data["id"]


def delete_event_from_google(config, google_event_id):
    """
    Delete a Google Calendar event. Silently ignores 404 (already deleted).
    """
    if not google_event_id:
        return
    session = _get_oauth_session(config)
    url = (
        f"{GOOGLE_CALENDAR_API_BASE}/calendars"
        f"/{PRIMARY_CALENDAR_ID}/events/{google_event_id}"
    )
    resp = session.delete(url, timeout=GOOGLE_API_TIMEOUT)
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()


def list_google_events(config, sync_token=None, time_min=None):
    """
    Fetch Google Calendar events using incremental sync where possible.

    If sync_token is provided it uses incremental sync (only changes since the
    last call). On HTTP 410 (sync token expired) it falls back to a full sync.

    Returns (events_list, next_sync_token).
    """
    session = _get_oauth_session(config)
    url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events"

    if time_min is None:
        time_min = (datetime.now(tz=dt_timezone.utc) - timedelta(days=30)).isoformat()

    params = {"maxResults": 250}
    if sync_token:
        params["syncToken"] = sync_token
    else:
        # Do NOT add singleEvents or orderBy here.
        # singleEvents=true expands recurring events (e.g. birthday contacts) into
        # hundreds of instances and — critically — prevents Google from issuing a
        # nextSyncToken, so incremental sync never gets established.
        params["timeMin"] = time_min

    all_events = []
    next_sync_token = None

    while True:
        resp = session.get(url, params=params, timeout=GOOGLE_API_TIMEOUT)

        if resp.status_code == 410:
            # Sync token expired — fall back to a full sync
            logger.info(
                "Google sync token expired for user %s; doing full sync.", config.user
            )
            params = {
                "maxResults": 250,
                "timeMin": time_min,
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            config.google_sync_token = None
            config.save(update_fields=["google_sync_token"])
            continue

        resp.raise_for_status()
        data = resp.json()
        all_events.extend(data.get("items", []))
        next_page_token = data.get("nextPageToken")
        next_sync_token = data.get("nextSyncToken")

        if next_page_token:
            params = {"pageToken": next_page_token}
        else:
            break

    return all_events, next_sync_token


def list_google_tasks(config):
    """
    Fetch tasks from the user's default Google Tasks list only.

    Using @default avoids the extra API call to list all task lists and the
    sequential per-list fetches that made sync slow. Platform-pushed tasks always
    land in @default, so this covers the completion sync use case fully.

    completedMin is set to 30 days ago so we don't re-fetch all historical
    completed/hidden tasks on every scheduler tick.

    Returns a list of task dicts with keys: id, title, due, notes, status.
    """
    session = _get_oauth_session(config)

    completed_min = (datetime.now(tz=dt_timezone.utc) - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )

    tasks_url = f"{GOOGLE_TASKS_API_BASE}/lists/@default/tasks"
    base_params = {
        "maxResults": 100,
        "showCompleted": "true",
        "showHidden": "true",
        "updatedMin": completed_min,
    }
    params = dict(base_params)
    all_tasks = []

    while True:
        r = session.get(tasks_url, params=params, timeout=GOOGLE_API_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for t in data.get("items", []):
            t["_list_id"] = "@default"
            all_tasks.append(t)
        page_token = data.get("nextPageToken")
        if page_token:
            params = {**base_params, "pageToken": page_token}
        else:
            break

    return all_tasks


def _find_list_id_for_task(config, task_id):
    """
    Return the task list id that contains this task, or None if the task does not exist.

    Tries @default first, then every list returned by the API (tasks can live outside @default).
    """
    session = _get_oauth_session(config)
    r = session.get(
        f"{GOOGLE_TASKS_API_BASE}/lists/@default/tasks/{task_id}",
        timeout=GOOGLE_API_TIMEOUT,
    )
    if r.status_code == 200:
        return "@default"
    lists_resp = session.get(
        f"{GOOGLE_TASKS_API_BASE}/users/@me/lists",
        params={"maxResults": 100},
        timeout=GOOGLE_API_TIMEOUT,
    )
    if not lists_resp.ok:
        return None
    for task_list in lists_resp.json().get("items", []):
        lid = task_list["id"]
        if lid == "@default":
            continue
        r = session.get(
            f"{GOOGLE_TASKS_API_BASE}/lists/{lid}/tasks/{task_id}",
            timeout=GOOGLE_API_TIMEOUT,
        )
        if r.status_code == 200:
            return lid
    return None


def push_task_to_google_tasks(config, activity):
    """
    Create or update a Horilla platform task in Google Tasks (plain title; Horilla platform ownership is tracked on Activity).

    Uses PATCH for updates so we do not replace the whole resource (PUT without etag / full
    body can return 400). When that happened, the old code fell through to POST and created
    a duplicate task in Google Calendar.

    Returns the Google Task ID string.
    """
    session = _get_oauth_session(config)

    title = (activity.subject or activity.title or "Task")[:1024]
    notes = activity.description or ""
    due_dt = activity.due_datetime or activity.end_datetime or activity.start_datetime
    is_completed = getattr(activity, "status", None) == "completed"

    def _base_fields():
        p = {
            "title": title,
            "notes": notes,
            "status": "completed" if is_completed else "needsAction",
        }
        if due_dt:
            p["due"] = due_dt.strftime("%Y-%m-%dT00:00:00.000Z")
        return p

    # Insert: do not send completed=null (Google rejects); PATCH: set time or null to reopen.
    payload_insert = _base_fields()
    if is_completed:
        payload_insert["completed"] = datetime.now(tz=dt_timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    payload_patch = _base_fields()
    if is_completed:
        payload_patch["completed"] = payload_insert.get("completed")
    else:
        payload_patch["completed"] = None

    google_task_id = activity.google_event_id

    if google_task_id:
        list_id = _find_list_id_for_task(config, google_task_id)
        if list_id:
            url = f"{GOOGLE_TASKS_API_BASE}/lists/{list_id}/tasks/{google_task_id}"
            resp = session.patch(url, json=payload_patch, timeout=GOOGLE_API_TIMEOUT)
            if resp.ok:
                return resp.json()["id"]
            if resp.status_code in (404, 403):
                logger.info(
                    "Google task %s inaccessible (HTTP %s) — stale or cross-account ID; "
                    "creating a new task in @default",
                    google_task_id,
                    resp.status_code,
                )
                # Clear the stale ID so the caller stores the fresh one
                activity.google_event_id = None
            else:
                logger.error(
                    "Google Tasks PATCH failed for task %s list %s: %s %s",
                    google_task_id,
                    list_id,
                    resp.status_code,
                    resp.text[:500],
                )
                resp.raise_for_status()

    # No stored id, task was deleted in Google, or stale/cross-account ID — create in @default
    list_id = "@default"
    url = f"{GOOGLE_TASKS_API_BASE}/lists/{list_id}/tasks"
    resp = _post_with_retry(session, url, payload_insert)
    resp.raise_for_status()
    return resp.json()["id"]


def _post_with_retry(session, url, payload, max_retries=2):
    """POST with simple retry for transient 5xx errors."""
    for attempt in range(max_retries + 1):
        resp = session.post(url, json=payload, timeout=GOOGLE_API_TIMEOUT)
        if resp.status_code < 500 or attempt == max_retries:
            return resp
        wait = 2**attempt  # 1s, 2s
        logger.warning(
            "Google Tasks POST returned %s; retrying in %ss (attempt %s/%s)",
            resp.status_code,
            wait,
            attempt + 1,
            max_retries,
        )
        time.sleep(wait)
    return resp


def delete_task_from_google_tasks(config, google_task_id):
    """
    Delete a Google Task from whichever task list it belongs to.

    Tries @default first (covers Horilla platform-created tasks). If that returns 400/404,
    searches all task lists for the task ID and deletes from the correct list.
    Silently ignores tasks that no longer exist.
    """
    if not google_task_id:
        return
    session = _get_oauth_session(config)

    # Try the default list first (tasks created by Horilla platform live here)
    url = f"{GOOGLE_TASKS_API_BASE}/lists/@default/tasks/{google_task_id}"
    resp = session.delete(url, timeout=GOOGLE_API_TIMEOUT)
    if resp.status_code in (200, 204, 404):
        return

    # 400 or other error — task is in a non-default list; find and delete it
    lists_resp = session.get(
        f"{GOOGLE_TASKS_API_BASE}/users/@me/lists",
        params={"maxResults": 20},
        timeout=GOOGLE_API_TIMEOUT,
    )
    if not lists_resp.ok:
        return
    for task_list in lists_resp.json().get("items", []):
        list_id = task_list["id"]
        del_url = f"{GOOGLE_TASKS_API_BASE}/lists/{list_id}/tasks/{google_task_id}"
        r = session.delete(del_url, timeout=GOOGLE_API_TIMEOUT)
        if r.status_code in (200, 204):
            return  # deleted successfully
        if r.status_code == 404:
            continue  # not in this list, try next


# ---------------------------------------------------------------------------
# Google Calendar Push Notifications (watch channels)
# ---------------------------------------------------------------------------


def _format_google_api_error(resp):
    """Best-effort parse of Google JSON error body for logs and user messages."""
    try:
        data = resp.json()
        err = data.get("error") or {}
        bits = []
        main = err.get("message")
        if main:
            bits.append(main)
        for e in err.get("errors") or []:
            r, m = e.get("reason", ""), e.get("message", "")
            if r and m:
                bits.append(f"{r}: {m}")
            elif m:
                bits.append(m)
            elif r:
                bits.append(r)
        return (
            " | ".join(bits)
            if bits
            else (resp.text[:800] if resp.text else str(resp.status_code))
        )
    except Exception:
        return resp.text[:800] if resp.text else str(resp.status_code)


def _webhook_url_public_for_google(webhook_url):
    """
    Google Calendar push only accepts HTTPS URLs that resolve to a public endpoint
    with a trusted certificate. Localhost / loopback / RFC1918 hosts are rejected
    with 400 (e.g. push.webhookUrlNotHttps or similar).

    Returns (True, None) if the URL might be acceptable, or (False, error_message).
    """
    if not webhook_url or not webhook_url.startswith("https://"):
        return False, "Webhook URL must use HTTPS."

    parsed = urlparse(webhook_url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Webhook URL is missing a hostname."

    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost"):
        return (
            False,
            "Google cannot deliver webhooks to localhost. Open the app via a public HTTPS URL "
            "(e.g. ngrok, Cloudflare Tunnel, or your production domain) and register the webhook again.",
        )

    try:
        addr = ipaddress.ip_address(host)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
        ):
            return (
                False,
                "Google cannot deliver webhooks to private, loopback, or non-public IP addresses. "
                "Use a public DNS name with a valid SSL certificate.",
            )
    except ValueError:
        pass

    return True, None


def create_watch_channel(config, webhook_url=None):
    """
    Register a Google Calendar push-notification watch channel.

    webhook_url — the full HTTPS URL Google will POST to when the calendar
                  changes (e.g. https://abc.devtunnels.ms/calendar/webhook/google/).
                  If omitted, falls back to SITE_URL setting.

    Returns a (channel_id, resource_id, expiration_dt) tuple on success,
    or None if no HTTPS URL is available.

    Raises on HTTP error so the caller can decide whether to swallow.
    Persists all four watch_* fields to the config row on success.
    """
    if not webhook_url:
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        if site_url and site_url.startswith("https://"):
            webhook_url = f"{site_url}/calendar/webhook/google/"

    if not webhook_url or not webhook_url.startswith("https://"):
        logger.warning(
            "create_watch_channel: no HTTPS webhook URL available (%r). "
            "Skipping watch channel creation — polling will be used instead.",
            webhook_url,
        )
        return None

    ok, public_err = _webhook_url_public_for_google(webhook_url)
    if not ok:
        logger.warning(
            "create_watch_channel: URL not usable for Google push: %s", public_err
        )
        raise ValueError(public_err)

    channel_id = str(uuid.uuid4())
    webhook_token = secrets.token_urlsafe(32)

    # Omit params.ttl — API default is 604800s (7d). Keeps payload minimal.
    payload = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url.rstrip(),
        "token": webhook_token,
    }

    session = _get_oauth_session(config)
    url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events/watch"
    resp = session.post(url, json=payload, timeout=GOOGLE_API_TIMEOUT)
    if not resp.ok:
        detail = _format_google_api_error(resp)
        logger.error(
            "create_watch_channel failed: status=%s detail=%s payload=%s",
            resp.status_code,
            detail,
            {k: payload[k] for k in ("id", "type", "address")},  # omit token in logs
        )
        raise RuntimeError(detail) from None

    data = resp.json()
    resource_id = data["resourceId"]
    # Google returns expiration as milliseconds since epoch
    expiration_ms = int(data["expiration"])
    expiration_dt = datetime.fromtimestamp(expiration_ms / 1000, tz=dt_timezone.utc)

    config.watch_channel_id = channel_id
    config.watch_resource_id = resource_id
    config.watch_expiration = expiration_dt
    config.watch_token = webhook_token
    config.save(
        update_fields=[
            "watch_channel_id",
            "watch_resource_id",
            "watch_expiration",
            "watch_token",
        ]
    )

    logger.info(
        "Watch channel created for user %s: channel_id=%s expires=%s",
        config.user,
        channel_id,
        expiration_dt.isoformat(),
    )
    return channel_id, resource_id, expiration_dt


def stop_watch_channel(config):
    """
    Stop an active Google Calendar push-notification watch channel.

    Returns True on success (including 404 — channel already expired on Google's side).
    Returns False if the config has no active channel.

    Clears all four watch_* fields on the config row.
    """
    if not config.watch_channel_id or not config.watch_resource_id:
        return False

    session = _get_oauth_session(config)
    url = f"{GOOGLE_CALENDAR_API_BASE}/channels/stop"
    payload = {
        "id": config.watch_channel_id,
        "resourceId": config.watch_resource_id,
    }
    resp = session.post(url, json=payload, timeout=GOOGLE_API_TIMEOUT)

    # 200, 204, or 404 are all acceptable — channel may already be expired
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()

    logger.info(
        "Watch channel stopped for user %s (channel_id=%s, status=%s)",
        config.user,
        config.watch_channel_id,
        resp.status_code,
    )

    config.watch_channel_id = None
    config.watch_resource_id = None
    config.watch_expiration = None
    config.watch_token = None
    config.save(
        update_fields=[
            "watch_channel_id",
            "watch_resource_id",
            "watch_expiration",
            "watch_token",
        ]
    )

    return True
