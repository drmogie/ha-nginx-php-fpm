"""The Contact API integration.

Receives a contact-form submission (JSON POST) via a Home Assistant
webhook and relays it to a Discord channel, using Discord's own
incoming-webhook mechanism. Written to be a drop-in replacement for the
standalone Flask `contact_api` container from the original
nginx + php-fpm + Flask docker-compose backend - see README.md for the
matching nginx configuration change.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import aiohttp
from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DISCORD_WEBHOOK_URL,
    DOMAIN,
    EMAIL_REGEX,
    MAX_MESSAGE_LENGTH,
    MAX_NAME_LENGTH,
    MAX_OTHER_LENGTH,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Contact API from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.data[CONF_WEBHOOK_ID]] = entry.data[
        CONF_DISCORD_WEBHOOK_URL
    ]

    webhook.async_register(
        hass,
        DOMAIN,
        entry.title,
        entry.data[CONF_WEBHOOK_ID],
        _handle_webhook,
        local_only=False,
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    webhook_url = webhook.async_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
    _LOGGER.info("Contact API webhook ready at: %s", webhook_url)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Contact API webhook ready",
            "message": (
                f"Point your nginx `/api/contact` location at:\n\n`{webhook_url}`\n\n"
                "See the ha-contact-api README for the exact nginx snippet."
            ),
            "notification_id": f"{DOMAIN}_{entry.entry_id}_webhook_url",
        },
        blocking=False,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    hass.data[DOMAIN].pop(entry.data[CONF_WEBHOOK_ID], None)
    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": f"{DOMAIN}_{entry.entry_id}_webhook_url"},
        blocking=False,
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options/data update - refresh the cached Discord URL."""
    hass.data[DOMAIN][entry.data[CONF_WEBHOOK_ID]] = entry.data[
        CONF_DISCORD_WEBHOOK_URL
    ]


def _clean(value: Any, max_length: int) -> str:
    """Coerce to a trimmed string, capped at max_length."""
    text = "" if value is None else str(value)
    return text.strip()[:max_length]


async def _handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle an incoming contact-form POST and relay it to Discord."""
    try:
        payload = await request.json()
    except ValueError:
        return web.json_response({"error": "invalid_json"}, status=400)

    if not isinstance(payload, dict):
        return web.json_response({"error": "invalid_json"}, status=400)

    name = _clean(payload.get("name"), MAX_NAME_LENGTH)
    email = _clean(payload.get("email"), MAX_NAME_LENGTH)
    other = _clean(payload.get("other"), MAX_OTHER_LENGTH)
    message = _clean(payload.get("message"), MAX_MESSAGE_LENGTH)

    errors: list[str] = []
    if not name:
        errors.append("name is required")
    if not message:
        errors.append("message is required")
    if email and not re.match(EMAIL_REGEX, email):
        errors.append("email is not a valid email address")

    if errors:
        return web.json_response(
            {"error": "validation_failed", "details": errors}, status=400
        )

    discord_url = hass.data.get(DOMAIN, {}).get(webhook_id)
    if not discord_url:
        _LOGGER.error(
            "No Discord webhook URL configured for webhook_id %s", webhook_id
        )
        return web.json_response({"error": "not_configured"}, status=500)

    embed = {
        "embeds": [
            {
                "title": "New Contact Form Submission",
                "color": 3447003,
                "fields": [
                    {"name": "Name", "value": name, "inline": True},
                    {"name": "Email", "value": email or "—", "inline": True},
                    {
                        "name": "Discord / Other",
                        "value": other or "—",
                        "inline": True,
                    },
                    {"name": "Message", "value": message, "inline": False},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    session = async_get_clientsession(hass)
    try:
        resp = await session.post(discord_url, json=embed, timeout=aiohttp.ClientTimeout(total=10))
        if resp.status >= 300:
            body = await resp.text()
            _LOGGER.error(
                "Discord webhook rejected the message (status %s): %s",
                resp.status,
                body,
            )
            return web.json_response({"error": "discord_rejected"}, status=502)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Failed to reach Discord webhook: %s", err)
        return web.json_response({"error": "discord_unreachable"}, status=502)

    return web.json_response({"status": "ok"})
