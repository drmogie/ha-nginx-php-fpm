# Changelog

## 2026.09.19.02

Renamed the whole project (repo, integration domain, display name) from
`ha-contact-api`/`contact_api` to `ha-nginx-php-fpm`/`nginx_php_fpm`, to
match the original docker-compose project's own folder name
(`/opt/docker/nginx-php_fpm/`) rather than the one service being replaced.
No functional change - same config flow, same webhook behavior, same
validation. If you already installed the `.01` release under the old name,
remove that config entry and re-add it after updating (the domain change
means Home Assistant sees it as a different integration).

## 2026.09.19.01

Initial release.

- Config flow: paste a Discord webhook URL, validated live against Discord
  before the entry is created.
- Registers a Home Assistant webhook (`/api/webhook/<id>`) that accepts a
  contact-form POST (`name`, `email`, `other`, `message`), validates it,
  and relays it to Discord as a formatted embed.
- Basic validation: `name`/`message` required, `email` format-checked when
  present, all fields length-capped.
- Options flow to update the Discord webhook URL later without recreating
  the integration.
- Persistent notification + log line showing the webhook URL to point
  nginx at, right after setup.
- Recreated from `contact_backend_recreation_guide.docx` (original
  Flask/nginx/php-fpm/Discord-webhook backend) - see README.md for the
  matching nginx `location` block and full migration notes.
