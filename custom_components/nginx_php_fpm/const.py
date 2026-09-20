"""Constants for the Nginx PHP-FPM integration."""

DOMAIN = "nginx_php_fpm"

CONF_DISCORD_WEBHOOK_URL = "discord_webhook_url"

DEFAULT_WEBHOOK_NAME = "Nginx PHP-FPM"

# Discord embed description hard-limit is 4096 characters; leave headroom
# for the surrounding field formatting.
MAX_MESSAGE_LENGTH = 4000
MAX_NAME_LENGTH = 200
MAX_OTHER_LENGTH = 200

# Loose but effective "looks like an email" check. Only enforced when the
# submitter actually filled the field in - the original front-end allows it
# to be blank.
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# Accept both discord.com and the legacy discordapp.com host.
DISCORD_WEBHOOK_URL_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)
