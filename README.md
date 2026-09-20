# Contact API

A Home Assistant custom integration that receives a website contact-form
submission and relays it to a Discord channel via a Discord incoming
webhook.

It's a drop-in replacement for a standalone Flask `contact_api` Docker
container sitting behind nginx - the same job, just running inside Home
Assistant instead of as a separate container, so there's one less thing to
patch, rebuild, and keep an eye on.

## What it replaces

The original setup was three containers behind nginx:

| Container | Role |
|---|---|
| `nginx` | Static site + PHP routing + reverse-proxies `/api/` to `contact_api` |
| `php_fpm` | PHP-FPM backend for the site |
| `contact_api` | Flask app: receives the contact form POST, forwards it to Discord |

This integration replaces **only** `contact_api`. `nginx` and `php_fpm` keep
doing exactly what they did before - you just repoint one `location` block
in nginx's config at Home Assistant instead of at the old Flask container,
and can retire `contact_api` from your `docker-compose.yml` entirely.

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo URL,
   category "Integration".
2. Install "Contact API", then restart Home Assistant.

### Manual

Copy `custom_components/contact_api` into your Home Assistant
`config/custom_components/` folder and restart.

## Setup

1. In Home Assistant: **Settings → Devices & Services → Add Integration →
   Contact API**.
2. Paste your Discord channel's incoming webhook URL
   (`https://discord.com/api/webhooks/...` - create one under a Discord
   channel's *Integrations → Webhooks* if you don't have one yet). Home
   Assistant checks it's reachable before accepting it.
3. On success, a notification appears in Home Assistant with the full
   webhook URL to point nginx at (also logged at `INFO` level from the
   `custom_components.contact_api` logger if you miss the notification).
   It looks like:

   ```
   http://<your-ha-host>:8123/api/webhook/<long-random-id>
   ```

To update the Discord webhook URL later (e.g. you moved channels), use the
integration's **Configure** button - no need to remove and re-add it.

## nginx migration

Your original `default.conf` proxied the API path straight to the Flask
container:

```nginx
location /api/ {
    proxy_pass http://contact_api:5055/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Replace that block with one pointing at the Home Assistant webhook URL
from setup (use your HA host/port, whatever they are on your network -
`homeassistant.local:8123`, a container name if HA is dockerized on the
same network, an internal IP, etc.):

```nginx
location = /api/contact {
    proxy_pass http://<your-ha-host>:8123/api/webhook/<your-webhook-id>;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Notes:

- This uses an **exact-match** `location = /api/contact` block, matching
  your front-end's only real endpoint - no need for a wildcard `/api/`
  prefix block anymore since there's nothing else under `/api/` to route.
- Your front-end doesn't change at all - it still POSTs JSON to the
  same-origin `/api/contact`.
- The webhook path (`/api/webhook/<id>`) is only ever called
  server-to-server, from nginx to Home Assistant - it's never exposed to
  the browser, same trust boundary as the old setup. Treat the full URL
  (specifically the id) as a secret the same way you treated the Discord
  webhook URL itself: it's not attacker-guessable, but don't publish it.
- Once you've confirmed the new endpoint works (see Testing below), remove
  the `contact_api` service from `docker-compose.yml` and delete
  `/opt/docker/nginx-php_fpm/contact_api/` - it's no longer used.

Reload nginx after editing:

```bash
docker exec -it nginx nginx -t
docker exec -it nginx nginx -s reload
```

## What changed vs. the original Flask app

- **Validation added** (the original app had none): `name` and `message`
  are required and non-empty; `email` is checked for a plausible format
  *only if you fill it in* (it's optional, same as before); all fields are
  length-capped. A bad request gets a `400` with a JSON `details` list
  instead of silently passing garbage through to Discord.
- **Discord message is a formatted embed** (name/email/other as fields,
  message as the body) instead of a plain-text POST - easier to read in
  Discord, same information.
- No rate limiting was added (the original didn't have any either) - if
  spam becomes a problem, that's a good nginx-level `limit_req` addition,
  or ask for it to be added here later.

## Testing

Mirrors the original recreation guide's checklist, adjusted for the new
endpoint:

```bash
# nginx config sanity check
docker exec -it nginx nginx -t

# Should still serve the site as before - unaffected by this change
curl -I http://localhost:8082/
curl -I http://localhost:8082/index.html

# HEAD isn't a valid method for a webhook - expect 405, same as before
curl -I http://localhost:8082/api/contact

# The real test: an actual submission
curl -i http://localhost:8082/api/contact \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"","other":"","message":"Hello from curl test"}'
```

A successful POST returns `{"status": "ok"}` with a `200`, and the message
shows up in your configured Discord channel. Check Home Assistant's log
(`custom_components.contact_api`) if it doesn't - a `502` means Home
Assistant reached the webhook handler fine but Discord rejected or refused
the forwarded message (webhook deleted, channel removed, etc.); a `400`
means the JSON payload itself failed validation.

## Security reminders

- The Discord webhook URL lives only in Home Assistant's config entry
  storage - it's never sent to the browser or logged in full.
- Home Assistant validates the webhook URL against Discord at setup and
  whenever you update it via Configure, so a typo'd or dead webhook is
  caught immediately instead of failing silently on the next real
  submission.
