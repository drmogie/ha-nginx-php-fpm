"""Config flow for the Nginx PHP-FPM integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DISCORD_WEBHOOK_URL,
    DEFAULT_WEBHOOK_NAME,
    DISCORD_WEBHOOK_URL_PREFIXES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_discord_webhook(hass: HomeAssistant, url: str) -> str | None:
    """Return an error string, or None if the webhook URL looks good.

    Discord webhook URLs answer a plain GET with a JSON description of the
    webhook (channel/guild) when they're valid, so this both checks the
    shape of the URL and confirms Discord actually accepts it.
    """
    url = url.strip()
    if not url.startswith(DISCORD_WEBHOOK_URL_PREFIXES):
        return "invalid_url"

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            resp = await session.get(url)
            if resp.status == 200:
                return None
            if resp.status == 404:
                return "webhook_not_found"
            return "cannot_connect"
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"


class NginxPhpFpmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nginx PHP-FPM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: collect the Discord webhook URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_DISCORD_WEBHOOK_URL].strip()
            error = await _validate_discord_webhook(self.hass, url)
            if error is None:
                webhook_id = webhook.async_generate_id()
                return self.async_create_entry(
                    title=DEFAULT_WEBHOOK_NAME,
                    data={
                        CONF_WEBHOOK_ID: webhook_id,
                        CONF_DISCORD_WEBHOOK_URL: url,
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_DISCORD_WEBHOOK_URL): str}
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NginxPhpFpmOptionsFlow:
        """Get the options flow for this handler."""
        return NginxPhpFpmOptionsFlow(config_entry)


class NginxPhpFpmOptionsFlow(config_entries.OptionsFlow):
    """Let the Discord webhook URL be updated after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_DISCORD_WEBHOOK_URL].strip()
            error = await _validate_discord_webhook(self.hass, url)
            if error is None:
                new_data = dict(self._entry.data)
                new_data[CONF_DISCORD_WEBHOOK_URL] = url
                self.hass.config_entries.async_update_entry(
                    self._entry, data=new_data
                )
                return self.async_create_entry(title="", data={})
            errors["base"] = error

        current = self._entry.data.get(CONF_DISCORD_WEBHOOK_URL, "")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISCORD_WEBHOOK_URL, default=current
                    ): str
                }
            ),
            errors=errors,
        )
