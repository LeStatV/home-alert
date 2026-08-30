# Deploying home-alert

One home server, two containers: `agent` (Telethon -> rules -> ntfy) and self-hosted
`ntfy`. Everything the agent keeps -- the Telegram session and the SQLite trail -- lives
in `./data`.

## Prerequisites

- Docker with compose, and a Telegram account that **has joined all seven channels** --
  the six in `profiles/` plus `@air_alert_ua`, which carries no profile and is read only
  for the state of the Kyiv siren. Telegram only pushes updates for dialogs the account
  is in. A channel it cannot see is logged at startup (`channel X: not joined`) and the
  rest keep working; without `@air_alert_ua` every push reads `⚪ сирена невідома` and
  the all-clear waits for a channel to say it is over.
- API credentials from https://my.telegram.org -> API development tools.
- `.env` next to `docker-compose.yml` (gitignored, never committed):

      TG_API_ID=1234567
      TG_API_HASH=...
      NTFY_TOKEN=placeholder   # replace with the real token after provisioning ntfy

  All three must be present from the start: compose interpolates the whole file, so
  even `docker compose up -d ntfy` refuses to start while one of them is missing.

- In `config.yaml`, point `ntfy.url` at the ntfy service: `http://ntfy` from inside
  compose. The file is mounted read-only, so this needs no rebuild.

## First run

    mkdir -p data && chmod 700 data
    docker compose up -d ntfy
    # provision users, per-topic access and the agent token: the exact commands are
    # listed in ntfy/server.yml (one `ntfy access` command per topic -- it takes a
    # single topic, never a comma list)
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
- **Replace-in-place**: one event owns one entry in the notification shade, which the
  agent gets by publishing every update with the same ntfy `sequence_id`
  ([docs.ntfy.sh/publish](https://docs.ntfy.sh/publish/#updating-notifications)). This
  needs the ntfy **server >= 2.16** (pinned in `docker-compose.yml`) and the **Android
  app >= 1.22.2** (the app is versioned 1.x, the server 2.x). iOS is not on ntfy's supported list for notification updates, so an
  iPhone stacks the updates -- there is nothing the agent can send to change that.
  Worth an eyeball on the phone after the first raid: the trajectory should rewrite one
  notification, not add one per report.

## Checking it

    docker compose logs -f agent      # "following 7/7 channels: ..." then the pushes

The `system` topic should show `Агент запущено` within seconds of the start, then
`Агент працює` every `system.heartbeat_min` minutes (one entry, replaced in place).

`home-alert replay <from> <to> --db data/home-alert.db --from-db` re-runs the current
rules over what the agent stored that night and prints what it would send now. Without
`--from-db` the same command replays the research corpus and records into that file.

## The nightly review

`home-alert review` reads the night back out of the SQLite trail, lists what the rules
could not type, and -- if `llm.provider` is set -- writes proposed profile changes to
`profiles/reviews/<date>.diff`. It never edits a profile: the owner reads the file and
applies the hunks they agree with. One line lands on the `system` topic per run
(`4 unparsed across 1 channel, 1 proposal written`), so a night with nothing to say
still says it.

`profiles/` is baked into the image, not mounted, so the nightly run needs it bind-mounted
or the review file goes away with the container. In the host's crontab:

    17 5 * * *  cd /srv/home-alert && docker compose run --rm --no-deps \
                  -v "$PWD/profiles:/app/profiles" agent \
                  uv run --no-sync home-alert review --since 24h

Then `git -C /srv/home-alert diff profiles/` after applying anything, and restart the
agent: profiles are read once, at startup.
