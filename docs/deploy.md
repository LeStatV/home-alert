# Deploying home-alert

One home server, two containers: `agent` (Telethon -> rules -> ntfy) and self-hosted
`ntfy`. Everything the agent keeps -- the Telegram session and the SQLite trail -- lives
in `./data`.

## Prerequisites

- Docker with compose, and a Telegram account that **has joined all six channels**:
  Telegram only pushes updates for dialogs the account is in. A channel it cannot see
  is logged at startup (`channel X: not joined`) and the other five keep working.
- API credentials from https://my.telegram.org -> API development tools.
- `.env` next to `docker-compose.yml` (gitignored, never committed):

      TG_API_ID=1234567
      TG_API_HASH=...
      NTFY_TOKEN=tk_...        # filled in after the ntfy provisioning below

- In `config.yaml`, point `ntfy.url` at the ntfy service: `http://ntfy` from inside
  compose. The file is mounted read-only, so this needs no rebuild.

## First run

    mkdir -p data && chmod 700 data
    docker compose up -d ntfy
    # provision users and the agent token -- the commands are in ntfy/server.yml
    docker compose run --rm -it agent     # asks for phone number + login code, once
    docker compose up -d

The login writes `data/home-alert.session`. Every later start reuses it and asks
nothing. That file is full access to the Telegram account: it stays on the `data`
volume, mode 700, and is never logged or copied into the image.

## Volumes

| path | what |
| --- | --- |
| `./data/home-alert.session` | Telethon session (secret) |
| `./data/home-alert.db` | messages, events, notifications |
| `ntfy-lib` | ntfy user database |
| `ntfy-cache` | ntfy message cache |

## Subscribing phones

Topics: `urgent` (wakes the house), `all` (urgent + watch + info), `system` (agent
health, issue #8). The family subscribes `urgent`; the owner adds `all`. Sign in to
the ntfy app with the `family` user -- `auth-default-access: deny-all` means an
anonymous subscriber sees nothing.

- **iOS**: needs `upstream-base-url: https://ntfy.sh` (already in `ntfy/server.yml`)
  for APNS to deliver at all.
- **Android**: turn on instant delivery in the app, or pushes arrive in batches.

## Checking it

    docker compose logs -f agent      # "following 6/6 channels: ..." then the pushes

`home-alert replay <from> <to> --db data/home-alert.db` re-runs the rules over what
was stored.
